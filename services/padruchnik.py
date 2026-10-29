"""Импорт учебных пособий с национального портала e-padruchnik.adu.by.

Портал не имеет открытого API: поиск — это POST-форма, карточка книги
открывается POST-запросом с ``bookid``, а прямая ссылка на PDF выдаётся
``getbookurl.php``. Здесь эти запросы инкапсулированы, чтобы учитель или
администратор могли найти пособие на своём сайте (и в приложении), нажать
«Добавить в пособия» — платформа скачает PDF и разберёт оглавление тем же
пайплайном, что и обычную загрузку.

Сеть может быть недоступна, поэтому все функции возвращают понятную ошибку,
а результаты поиска кэшируются в памяти на несколько минут.

Отдельно поддерживается локальный каталог ``padruchnik_catalog.json``.
Он собирается скриптом ``tools/fetch_padruchnik_catalog.py`` на машине, у
которой есть прямой доступ к порталу, и позволяет искать пособия даже там,
где портал блокирует IP сервера (например, на Alwaysdata). Каталог содержит
метаданные и прямые ссылки на PDF.
"""
from __future__ import annotations

import html as html_module
import json
import logging
import os
import re
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.cookiejar import CookieJar
from typing import Any

BASE_URL = "https://e-padruchnik.adu.by/"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT = 25
PDF_TIMEOUT = 15
CACHE_TTL = 600
CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "padruchnik_catalog.json"
)

_languages = {"1": "Русский", "2": "Белорусский", "3": "Русский и белорусский"}

_log = logging.getLogger(__name__)

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_opener: urllib.request.OpenerDirector | None = None

_catalog_lock = threading.Lock()
_catalog_books: list[dict[str, Any]] | None = None
_catalog_index: dict[int, dict[str, Any]] = {}
_catalog_stamp: tuple[float, float] = (-1.0, -1.0)  # mtime, size
_catalog_generated = ""

_direct_blocked_until = 0.0


def _client() -> urllib.request.OpenerDirector:
    global _opener
    if _opener is None:
        jar = CookieJar()
        _opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar)
        )
        _opener.addheaders = [
            ("User-Agent", USER_AGENT),
            ("Referer", BASE_URL),
            ("Accept-Language", "ru,be;q=0.9,en;q=0.7"),
        ]
    return _opener


def _post(data: dict[str, str], url: str = BASE_URL) -> str:
    body = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    with _client().open(request, timeout=TIMEOUT) as response:
        raw = response.read()
    return raw.decode("utf-8", errors="replace")


def _proxy_get(target: str, timeout: int = 30) -> str:
    """Получить GET-страницу портала через переводчик Google.

    Нужен как резервный путь для карточек книг: прямой доступ к порталу с
    некоторых хостингов закрыт, а Google-переводчик страницу отдаёт. Поиск
    через него не работает — портал принимает условия поиска только POST-ом,
    поэтому для поиска используется локальный каталог.
    """
    url = (
        "https://translate.google.com/translate?sl=auto&tl=ru&u="
        + urllib.parse.quote(target, safe="")
    )
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "ru,be;q=0.9,en;q=0.7",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    return raw.decode("utf-8", errors="replace")


def _text(fragment: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_module.unescape(text)
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def _parse_rows(page: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for book_id, body in re.findall(r'<tr book-id="(\d+)">(.*?)</tr>', page, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", body, re.S)
        if not cells:
            continue
        level = _text(cells[0])
        grade = re.sub(r"\D", "", _text(cells[1])) if len(cells) > 1 else ""
        year = re.sub(r"\D", "", _text(cells[2])) if len(cells) > 2 else ""
        language = _text(cells[3]) if len(cells) > 3 else ""
        title_block = cells[-1]
        bold = re.search(r"<b>(.*?)</b>", title_block, re.S)
        title = _text(bold.group(1)) if bold else _text(title_block)
        rest = title_block[bold.end():] if bold else ""
        author = _text(rest).strip(" .")
        title = re.sub(r"\s+", " ", title).strip()
        items.append(
            {
                "id": int(book_id),
                "title": title,
                "author": author,
                "grade": int(grade) if grade else 0,
                "year": year,
                "level": level,
                "language": language,
            }
        )
    return items


def _cache_get(key: str) -> dict[str, Any] | None:
    with _lock:
        entry = _cache.get(key)
        if not entry:
            return None
        stamp, value = entry
        if time.time() - stamp > CACHE_TTL:
            _cache.pop(key, None)
            return None
        return value


def _cache_put(key: str, value: dict[str, Any]) -> None:
    with _lock:
        if len(_cache) > 120:
            for old in list(_cache)[:40]:
                _cache.pop(old, None)
        _cache[key] = (time.time(), value)


# ------------------------------------------------------------------ каталог
def _catalog_mode() -> str:
    """``auto`` — каталог, если он есть; ``catalog`` — только каталог;
    ``live`` — всегда ходить на портал (полезно для тестов)."""
    return (os.environ.get("PADRUCHNIK_MODE") or "auto").strip().lower()


def _load_catalog() -> list[dict[str, Any]]:
    """Прочитать каталог с диска (с перечитыванием при изменении файла)."""
    global _catalog_books, _catalog_index, _catalog_stamp, _catalog_generated
    if _catalog_mode() == "live":
        return []
    try:
        stat = os.stat(CATALOG_PATH)
    except OSError:
        with _catalog_lock:
            _catalog_books = []
            _catalog_index = {}
            _catalog_stamp = (-1.0, -1.0)
            _catalog_generated = ""
        return []
    stamp = (stat.st_mtime, float(stat.st_size))
    with _catalog_lock:
        if _catalog_books is not None and stamp == _catalog_stamp:
            return _catalog_books
        try:
            with open(CATALOG_PATH, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as error:  # pragma: no cover - битый файл
            _log.warning("Не удалось прочитать каталог e-padruchnik: %s", error)
            _catalog_books = []
            _catalog_index = {}
        else:
            books: list[dict[str, Any]] = []
            index: dict[int, dict[str, Any]] = {}
            for raw in data.get("books") or []:
                try:
                    book_id = int(raw.get("id") or 0)
                except (TypeError, ValueError):
                    continue
                if not book_id:
                    continue
                entry = {
                    "id": book_id,
                    "title": str(raw.get("title") or "").strip(),
                    "author": str(raw.get("author") or "").strip(),
                    "grade": int(raw.get("grade") or 0),
                    "year": str(raw.get("year") or "").strip(),
                    "level": str(raw.get("level") or "").strip(),
                    "language": str(raw.get("language") or "").strip(),
                    "pdf_url": str(raw.get("pdf_url") or "").strip(),
                }
                books.append(entry)
                index[book_id] = entry
            _catalog_books = books
            _catalog_index = index
            _catalog_generated = str(data.get("generated_at") or "")
        _catalog_stamp = stamp
        return _catalog_books or []


def catalog_info() -> dict[str, Any]:
    """Короткая информация о каталоге — для диагностики и страницы настроек."""
    books = _load_catalog()
    return {
        "loaded": bool(books),
        "total": len(books),
        "with_pdf": sum(1 for book in books if book.get("pdf_url")),
        "generated_at": _catalog_generated,
        "path": CATALOG_PATH,
        "mode": _catalog_mode(),
    }


def _fold(text: str) -> str:
    """Привести текст к виду, удобному для поиска по русским и белорусским
    названиям (і→и, э→е, ў→у, ё→е, ы→и, о→а).

    Белорусская орфография передаёт русские «о» и «ы» через «а» и «і»,
    поэтому «Інфарматыка» и «Информатика» после свёртки совпадают.
    """
    value = (text or "").lower().replace("ё", "е").replace("’", "'")
    value = value.translate(
        str.maketrans({"і": "и", "э": "е", "ў": "у", "ы": "и", "о": "а"})
    )
    value = re.sub(r"[^\w\-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _fold_variants(text: str) -> list[str]:
    """Варианты написания: белорусская «ў» может соответствовать «у» и «в»."""
    raw = (text or "").lower().replace("ё", "е").replace("’", "'")
    variants = {raw, raw.replace("ў", "у"), raw.replace("ў", "в")}
    result = set()
    for value in variants:
        value = value.translate(
            str.maketrans({"і": "и", "э": "е", "ы": "и", "о": "а"})
        )
        value = re.sub(r"[^\w\-]+", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        result.add(value)
    return [value for value in result if value]


def _book_year(book: dict[str, Any]) -> str:
    year = str(book.get("year") or "").strip()
    if year:
        return year
    match = re.search(r"\((\d{4})\)", book.get("title") or "")
    return match.group(1) if match else ""


def _catalog_search(
    query: str,
    grade: int | None,
    language: str,
    year: str,
    page: int,
) -> dict[str, Any] | None:
    books = _load_catalog()
    if not books:
        return None
    phrase = _fold(query)
    tokens = [token for token in phrase.split() if token]
    language_key = str(language or "").strip()
    language_name = _languages.get(language_key, language_key)
    year_key = str(year or "").strip()

    matches: list[tuple[int, dict[str, Any]]] = []
    for book in books:
        if grade and int(book.get("grade") or 0) != int(grade):
            continue
        if year_key and _book_year(book) != year_key:
            continue
        if language_key:
            if language_key in _languages:
                if book.get("language") != language_name:
                    continue
            elif _fold(language_name) not in " ".join(
                _fold_variants(book.get("language") or "")
            ):
                continue

        title_variants = _fold_variants(book.get("title") or "")
        author_variants = _fold_variants(book.get("author") or "")
        title = " ".join(title_variants)
        author = " ".join(author_variants)
        haystack = " ".join(
            [
                title,
                author,
                " ".join(_fold_variants(book.get("level") or "")),
                " ".join(_fold_variants(book.get("language") or "")),
                str(book.get("grade") or ""),
                _book_year(book),
                "класс",
            ]
        )
        if tokens and not all(token in haystack for token in tokens):
            continue

        score = 0
        if phrase:
            if title.startswith(phrase):
                score += 6
            elif phrase in title:
                score += 5
            elif phrase in author:
                score += 3
            for token in tokens:
                if token in title:
                    score += 2
                elif token in author:
                    score += 1
        book_year = _book_year(book)
        numeric_year = int(book_year) if book_year.isdigit() else 0
        matches.append((score, -numeric_year, book))

    matches.sort(key=lambda item: (-item[0], item[1], _fold(item[2]["title"])))
    rows = [book for _, _, book in matches]
    start = page * 10
    chunk = rows[start:start + 10]
    items = [
        {
            "id": book["id"],
            "title": book["title"],
            "author": book["author"],
            "grade": book["grade"],
            "year": _book_year(book),
            "level": book["level"],
            "language": book["language"],
            "pdf_url": book["pdf_url"],
        }
        for book in chunk
    ]
    return {
        "ok": True,
        "items": items,
        "page": page,
        "has_next": len(rows) > start + 10,
        "error": "",
        "source": "catalog",
        "total": len(rows),
        "generated_at": _catalog_generated,
    }


# ------------------------------------------------------------------ поиск
def _portal_blocked() -> bool:
    return time.time() < _direct_blocked_until


def _block_portal(seconds: int = 600) -> None:
    global _direct_blocked_until
    _direct_blocked_until = time.time() + seconds


def search(
    query: str = "",
    grade: int | None = None,
    language: str = "",
    year: str = "",
    page: int = 0,
) -> dict[str, Any]:
    """Найти пособия.

    ``grade`` — класс, ``language`` — «1»/«2»/«3» или текст, ``page`` — 0-based.
    Сначала используется локальный каталог: он работает даже там, где портал
    не пускает IP сервера, и отвечает мгновенно. Если каталога нет — прямой
    POST-запрос к порталу (как раньше).
    """
    query = (query or "").strip()[:120]
    page = max(0, int(page or 0))
    language = (language or "").strip()
    year = (year or "").strip()

    if _catalog_mode() != "live":
        catalog_result = _catalog_search(query, grade, language, year, page)
        if catalog_result is not None:
            return catalog_result
    if _catalog_mode() == "catalog":
        return {
            "ok": False,
            "items": [],
            "page": page,
            "has_next": False,
            "error": "Каталог пособий не загружен. Обратитесь к администратору.",
            "source": "catalog",
        }

    data = {"query": query, "char": "", "page-nav": str(page), "mode": "search"}
    if grade:
        data["class"] = str(int(grade))
    if language:
        data["lang"] = str(language)
    if year:
        data["year"] = str(year)
    key = "|".join(f"{k}={v}" for k, v in sorted(data.items()))
    cached = _cache_get(key)
    if cached is not None:
        return {**cached, "cached": True}
    if _portal_blocked():
        return {
            "ok": False,
            "items": [],
            "page": page,
            "has_next": False,
            "error": "Портал недоступен: сервер не может подключиться к e-padruchnik.adu.by",
        }
    try:
        page_html = _post(data)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        _block_portal()
        return {
            "ok": False,
            "items": [],
            "page": page,
            "has_next": False,
            "error": f"Портал недоступен: {error}",
        }
    items = _parse_rows(page_html)
    # На последней странице ссылки «вперёд» нет; проще проверить наличие
    # следующей страницы по счётчику «N...M из K».
    has_next = bool(items) and len(items) >= 10
    result = {
        "ok": True,
        "items": items,
        "page": page,
        "has_next": has_next,
        "error": "",
        "source": "e-padruchnik.adu.by",
    }
    _cache_put(key, result)
    return result


def book(book_id: int) -> dict[str, Any] | None:
    """Карточка книги: метаданные из каталога + прямая ссылка на PDF."""
    book_id = int(book_id)
    cached = _cache_get(f"book:{book_id}")
    if cached is not None:
        return cached
    meta: dict[str, Any] = {
        "id": book_id,
        "title": "",
        "author": "",
        "grade": 0,
        "year": "",
        "language": "",
        "level": "",
        "pdf_url": "",
        "error": "",
    }

    if _catalog_mode() != "live":
        catalog = _load_catalog()
        for entry in catalog:
            if entry["id"] == book_id:
                meta.update(
                    {key: entry.get(key) for key in meta if key in entry}
                )
                meta["source"] = "catalog"
                if not meta.get("pdf_url"):
                    meta["error"] = (
                        "У этого пособия нет электронной версии для скачивания"
                    )
                _cache_put(f"book:{book_id}", meta)
                return meta
        if _catalog_mode() == "catalog":
            meta["error"] = "Пособие не найдено в каталоге"
            return meta

    if _portal_blocked():
        meta["error"] = (
            "Портал недоступен: сервер не может подключиться к e-padruchnik.adu.by"
        )
        return meta
    try:
        card = _post({"bookid": str(book_id)})
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        _block_portal()
        meta["error"] = f"Портал недоступен: {error}"
        return meta
    plain = _text(card)
    match = re.search(
        r"Авторы книги\s*(.*?)\s*Год издания\s*(\d{4}).*?"
        r"Язык обучения\s*(.*?)\s*Класс\s*(\d+)\s*Уровень\s*(.*?)\s*Все права",
        plain,
        re.S,
    )
    if match:
        meta["author"] = re.sub(r"\s+", " ", match.group(1)).strip()
        meta["year"] = match.group(2)
        meta["language"] = re.sub(r"\s+", " ", match.group(3)).strip()
        meta["grade"] = int(match.group(4))
        meta["level"] = re.sub(r"\s+", " ", match.group(5)).strip()
    heading = re.search(r'<th colspan="2">(.*?)</th>', card, re.S)
    if heading:
        meta["title"] = _text(heading.group(1))
    try:
        url = _post({"id": str(book_id)}, url=BASE_URL + "getbookurl.php").strip()
        url = re.sub(r"^book-viewer[\\/]web[\\/]viewer\.html\?file=", "", url)
        if url.startswith("http"):
            meta["pdf_url"] = url
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        meta["error"] = meta["error"] or f"Не удалось получить ссылку: {error}"
    if not meta["pdf_url"] and not meta["error"]:
        meta["error"] = "У этого пособия нет электронной версии для скачивания"
    meta["source"] = "e-padruchnik.adu.by"
    _cache_put(f"book:{book_id}", meta)
    return meta


# ------------------------------------------------------------------ скачивание
def _pdf_opener() -> urllib.request.OpenerDirector:
    """Открывалка для PDF. Если задан ``PADRUCHNIK_PROXY`` (HTTP-прокси),
    скачивание идёт через него — это спасает на хостингах, чей IP портал
    не пускает."""
    proxy = (os.environ.get("PADRUCHNIK_PROXY") or "").strip()
    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
        opener.addheaders = [
            ("User-Agent", USER_AGENT),
            ("Referer", BASE_URL),
        ]
        return opener
    return _client()


def _relay_url(url: str) -> str:
    """Собрать ссылку на внешний релей для PDF.

    ``PADRUCHNIK_PDF_RELAY`` — шаблон с ``{url}`` (URL кодируется) или базовый
    адрес, к которому добавляется закодированная ссылка. Пусто — релея нет.
    """
    template = (os.environ.get("PADRUCHNIK_PDF_RELAY") or "").strip()
    if not template:
        return ""
    encoded = urllib.parse.quote(url, safe="")
    if "{url}" in template:
        return template.replace("{url}", encoded)
    return template.rstrip("/") + "/" + encoded


def _download_to_file(url: str, path: str, max_bytes: int) -> int:
    request = urllib.request.Request(url)
    request.add_header("User-Agent", USER_AGENT)
    request.add_header("Referer", BASE_URL)
    size = 0
    with _pdf_opener().open(request, timeout=PDF_TIMEOUT) as response:
        with open(path, "wb") as handle:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError("PDF больше 80 МБ — добавьте вручную")
                handle.write(chunk)
    return size


def download_pdf(url: str, dest_dir: str, max_bytes: int = 80 * 1024 * 1024) -> tuple[str, int]:
    """Скачать PDF на диск. Возвращает (имя файла, размер).

    Прямое скачивание может не работать, если портал блокирует IP сервера.
    Тогда используется релей из ``PADRUCHNIK_PDF_RELAY`` (если настроен).
    """
    if not url.startswith("https://e-padruchnik.adu.by/"):
        raise ValueError("Ссылка на PDF с неожиданного домена")
    os.makedirs(dest_dir, exist_ok=True)
    name = f"{uuid.uuid4().hex}.pdf"
    path = os.path.join(dest_dir, name)
    errors: list[str] = []
    sources = [url]
    relay = _relay_url(url)
    if relay:
        sources.append(relay)
    for source in sources:
        try:
            size = _download_to_file(source, path, max_bytes)
        except Exception as error:  # noqa: BLE001 - пробуем следующий источник
            errors.append(str(error))
            try:
                os.remove(path)
            except OSError:
                pass
            continue
        from services import filecheck

        if not filecheck.looks_like(".pdf", filecheck.head_of(path)):
            errors.append("ответ не похож на PDF")
            try:
                os.remove(path)
            except OSError:
                pass
            continue
        return name, size
    if errors and all("timed out" in error.lower() for error in errors):
        raise ValueError(
            "Сервер не может скачать PDF с портала (портал не отвечает). "
            "Скачайте файл по ссылке и загрузите его вручную."
        )
    raise ValueError("Не удалось скачать PDF: " + (errors[-1] if errors else "неизвестная ошибка"))


def save_pdf_bytes(data: bytes, dest_dir: str) -> tuple[str, int]:
    """Сохранить PDF, присланный клиентом (браузером или приложением)."""
    from services import filecheck

    if not data:
        raise ValueError("Пустой файл")
    if not filecheck.looks_like(".pdf", data[:2048]):
        raise ValueError("Файл не похож на PDF")
    os.makedirs(dest_dir, exist_ok=True)
    name = f"{uuid.uuid4().hex}.pdf"
    path = os.path.join(dest_dir, name)
    with open(path, "wb") as handle:
        handle.write(data)
    return name, len(data)


def import_saved_pdf(
    filename: str,
    size: int,
    book_id: int,
    subject_id: int,
    grade: int,
    uploaded_by: int | None = None,
    *,
    title: str = "",
    author: str = "",
    year: str = "",
    class_ids: list[int] | None = None,
    auto_link: bool = True,
) -> dict[str, Any]:
    """Создать пособие из PDF, который уже лежит в каталоге загрузок."""
    from services import library as library_service
    from services import textbooks as textbooks_service

    meta = book(book_id) or {}
    path = os.path.join(textbooks_service.upload_dir(), filename)
    try:
        pages = textbooks_service.count_pdf_pages(path)
        textbook_id = textbooks_service.create_textbook(
            subject_id,
            int(grade or meta.get("grade") or 0),
            title or meta.get("title") or "Пособие с e-padruchnik",
            filename,
            original_name=f"{title or meta.get('title') or book_id}.pdf",
            size_bytes=size,
            pages=pages,
            author=author or meta.get("author") or "",
            publisher="e-padruchnik.adu.by",
            year=year or meta.get("year") or "",
            description=f"Импортировано с e-padruchnik.adu.by (book-id {book_id})",
            uploaded_by=uploaded_by,
        )
    except (ValueError, OSError) as error:
        return {"ok": False, "error": str(error)}

    imported = {"linked": 0, "created": 0, "method": "none"}
    if auto_link:
        imported = textbooks_service.import_topics_from_pdf(textbook_id)

    book_row = None
    if class_ids and uploaded_by:
        book_row = library_service.ensure_book_for_textbook(
            int(uploaded_by), textbook_id, [int(c) for c in class_ids if c]
        )
    return {
        "ok": True,
        "textbook_id": textbook_id,
        "pages": pages,
        "size": size,
        "linked": imported.get("linked", 0),
        "created": imported.get("created", 0),
        "book_id": int(book_row["id"]) if book_row else None,
        "title": title or meta.get("title") or "",
    }


def import_book(
    book_id: int,
    subject_id: int,
    grade: int,
    uploaded_by: int | None = None,
    *,
    title: str = "",
    author: str = "",
    year: str = "",
    class_ids: list[int] | None = None,
    auto_link: bool = True,
    pdf_path: str | None = None,
) -> dict[str, Any]:
    """Скачать пособие, создать запись и разобрать темы.

    ``class_ids`` — сразу открыть книгу классам в библиотеке (как если бы
    учитель нажал «В библиотеку»). ``pdf_path`` — уже скачанный клиентом PDF
    (тогда сервер не ходит на портал).
    """
    from services import library as library_service
    from services import textbooks as textbooks_service

    meta = book(book_id) or {}
    filename = ""
    size = 0
    if pdf_path:
        try:
            target = os.path.join(
                textbooks_service.upload_dir(),
                f"{uuid.uuid4().hex}.pdf",
            )
            os.makedirs(textbooks_service.upload_dir(), exist_ok=True)
            shutil.copyfile(pdf_path, target)
            filename = os.path.basename(target)
            size = os.path.getsize(target)
        except OSError as error:
            return {"ok": False, "error": str(error)}
    else:
        if not meta.get("pdf_url"):
            return {
                "ok": False,
                "error": meta.get("error") or "Не удалось получить ссылку на PDF",
                "pdf_url": meta.get("pdf_url") or "",
            }
        try:
            filename, size = download_pdf(
                meta["pdf_url"], textbooks_service.upload_dir()
            )
        except (ValueError, OSError) as error:
            return {
                "ok": False,
                "error": str(error),
                "pdf_url": meta.get("pdf_url") or "",
                "can_upload": True,
            }

    return import_saved_pdf(
        filename,
        size,
        book_id,
        subject_id,
        grade,
        uploaded_by,
        title=title,
        author=author,
        year=year,
        class_ids=class_ids,
        auto_link=auto_link,
    )
