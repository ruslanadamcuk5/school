"""Импорт учебных пособий с национального портала e-padruchnik.adu.by.

Портал не имеет открытого API: поиск — это POST-форма, карточка книги
открывается POST-запросом с ``bookid``, а прямая ссылка на PDF выдаётся
``getbookurl.php``. Здесь эти запросы инкапсулированы, чтобы учитель или
администратор могли найти пособие на своём сайте (и в приложении), нажать
«Добавить в пособия» — платформа скачает PDF и разберёт оглавление тем же
пайплайном, что и обычную загрузку.

Сеть может быть недоступна, поэтому все функции возвращают понятную ошибку,
а результаты поиска кэшируются в памяти на несколько минут.
"""
from __future__ import annotations

import html as html_module
import os
import re
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
CACHE_TTL = 600

_languages = {"1": "Русский", "2": "Белорусский", "3": "Русский и белорусский"}

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_opener: urllib.request.OpenerDirector | None = None


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


def search(
    query: str = "",
    grade: int | None = None,
    language: str = "",
    year: str = "",
    page: int = 0,
) -> dict[str, Any]:
    """Найти пособия на портале.

    ``grade`` — класс, ``language`` — «1»/«2»/«3» или текст, ``page`` — 0-based.
    Пустые фильтры не отправляются: портал считает их отдельным условием и
    возвращает пустой список.
    """
    query = (query or "").strip()[:120]
    page = max(0, int(page or 0))
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
    try:
        page_html = _post(data)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
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
    """Карточка книги: метаданные из поиска + прямая ссылка на PDF."""
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
    try:
        card = _post({"bookid": str(book_id)})
    except (urllib.error.URLError, TimeoutError, OSError) as error:
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
    _cache_put(f"book:{book_id}", meta)
    return meta


def download_pdf(url: str, dest_dir: str, max_bytes: int = 80 * 1024 * 1024) -> tuple[str, int]:
    """Скачать PDF на диск. Возвращает (имя файла, размер)."""
    if not url.startswith("https://e-padruchnik.adu.by/"):
        raise ValueError("Ссылка на PDF с неожиданного домена")
    os.makedirs(dest_dir, exist_ok=True)
    name = f"{uuid.uuid4().hex}.pdf"
    path = os.path.join(dest_dir, name)
    request = urllib.request.Request(url)
    request.add_header("User-Agent", USER_AGENT)
    request.add_header("Referer", BASE_URL)
    try:
        with _client().open(request, timeout=TIMEOUT) as response:
            size = 0
            with open(path, "wb") as handle:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("PDF больше 80 МБ — добавьте вручную")
                    handle.write(chunk)
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise
    from services import filecheck

    if not filecheck.looks_like(".pdf", filecheck.head_of(path)):
        try:
            os.remove(path)
        except OSError:
            pass
        raise ValueError("Портал вернул файл, который не похож на PDF")
    return name, size


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
) -> dict[str, Any]:
    """Скачать пособие, создать запись и разобрать темы.

    ``class_ids`` — сразу открыть книгу классам в библиотеке (как если бы
    учитель нажал «В библиотеку»).
    """
    from services import library as library_service
    from services import textbooks as textbooks_service

    meta = book(book_id) or {}
    if not meta.get("pdf_url"):
        return {
            "ok": False,
            "error": meta.get("error") or "Не удалось получить ссылку на PDF",
        }
    try:
        filename, size = download_pdf(meta["pdf_url"], textbooks_service.upload_dir())
        path = os.path.join(textbooks_service.upload_dir(), filename)
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
