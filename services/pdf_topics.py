"""Определение тем (оглавления) загруженного PDF-пособия.

Работает офлайн: pypdf читает закладки и текстовый слой страниц в начале
и в конце книги. Оглавление может находиться как в начале, так и в конце
(например, в белорусских учебниках). Если у PDF нет ни закладок, ни
текстового «Содержания» (например, скан), возвращаем пустой список —
темы можно добавить вручную в админ-панели.
"""
from __future__ import annotations

import re
from typing import Any

from services import pdf_text

TOC_WORDS = ("contents", "содержание", "змест")
_LEADER = re.compile(r"(?:\s*\.\s*){3,}|…+")
_ENTRY = re.compile(r"([^\t\n]{2,200}?)\t\s*(\d{1,4})")
_FIRST_NUMBER = re.compile(r"^\s*(\d{1,4})(?=[\s.)])")
_PREPOSITIONS = {
    "и", "в", "во", "на", "по", "с", "со", "к", "ко", "у", "за", "от", "до",
    "при", "про", "над", "под", "без", "через", "для", "из", "о", "об",
    "па", "да", "ад", "пра", "пры", "праз", "ў", "паводле",
}


def clean_title(raw: str) -> str:
    title = re.sub(r"\s+", " ", raw or "").strip(" .·…-\t")
    title = re.sub(r"^\d{1,4}\s+", "", title)
    for word in ("Contents", "Содержание", "Змест"):
        if title.lower().startswith(word.lower()):
            title = title[len(word):].strip(" .:—-")
    return title.strip()


def _merge_wrapped_titles(text: str) -> str:
    """Склеить названия тем, перенесённые на две строки.

    В оглавлении бывает «Название темы, которое не поместилось» на одной
    строке и «продолжение .... 12» на следующей. Без склейки в темы попадают
    обрывки вроде «значэнні» или «слова». Короткие заголовки разделов
    (ТЭКСТ, СКАЗ) не склеиваем.
    """
    lines = (text or "").splitlines()
    merged: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        next_line = lines[index + 1].strip() if index + 1 < len(lines) else ""
        line_has_page = bool(re.search(r"\d{1,4}\s*$", line))
        next_has_page = bool(re.search(r"\d{1,4}\s*$", next_line))
        line_has_leader = bool(_LEADER.search(line))
        next_has_leader = bool(_LEADER.search(next_line))
        previous_word = line.split()[-1].lower() if line.split() else ""
        continuation = (
            line and next_line
            and not line_has_page
            and not re.fullmatch(r"\d{1,4}", next_line)
            and len(line) >= 15
            and not line.isupper()
            and not next_line.isupper()
            and (
                next_has_page
                or (
                    not line_has_leader
                    and next_has_leader
                    and (
                        next_line[:1].islower()
                        or line.endswith("-")
                        or previous_word in _PREPOSITIONS
                        or line.count("(") > line.count(")")
                        or line.count("«") > line.count("»")
                    )
                )
            )
        )
        if continuation:
            if line.endswith("-") and next_line[:1].islower():
                merged.append(f"{line}{next_line}")
            else:
                merged.append(f"{line} {next_line}")
            index += 2
            continue
        merged.append(lines[index])
        index += 1
    return "\n".join(merged)


def _parse_column_contents(text: str) -> list[tuple[str, int]]:
    """Оглавление, где страницы набраны отдельным столбцом чисел.

    В некоторых вёрстках названия идут с точками, а номера страниц — общим
    списком ниже. Сопоставляем их по порядку, отбрасывая лишние числа
    (например, колонцифру самой страницы содержания).
    """
    titles: list[str] = []
    pages: list[int] = []
    numbers_started = False
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.fullmatch(r"\d{1,4}", line):
            numbers_started = True
            pages.append(int(line))
            continue
        if numbers_started:
            # подпись «Скачано с сайта…», колонтитул и т.п. после чисел
            continue
        title = clean_title(_LEADER.sub("", line)) if _LEADER.search(line) else clean_title(line)
        compact = re.sub(r"\s+", "", title).casefold()
        if compact in {"содержание", "змест", "contents"}:
            continue
        if re.match(r"^(правообладатель|скачано|издательский центр)", title, re.I):
            continue
        if len(title) >= 2 and not title.isdigit():
            titles.append(title)
    if len(titles) < 2 or len(pages) < 2:
        return []
    count = min(len(titles), len(pages))
    return list(zip(titles[:count], pages[:count]))


def parse_contents_text(text: str) -> list[tuple[str, int]]:
    """Разобрать текст оглавления: «Название .... 12» (в т.ч. в одну строку)."""
    merged = _merge_wrapped_titles(text or "")
    text = _LEADER.sub("\t", merged)
    # оглавления без точек: «Название        12»
    text = re.sub(
        r"(?<=\S)[ \t]{2,}(\d{1,4})(?=[ \t]*$)", r"\t\1", text, flags=re.MULTILINE
    )
    entries: list[tuple[str, int]] = []
    for match in _ENTRY.finditer(text):
        title = clean_title(match.group(1))
        page = int(match.group(2))
        if len(title) < 2 or title.isdigit():
            continue
        entries.append((title, page))
    if len(entries) < 2:
        column_entries = _parse_column_contents(merged)
        if len(column_entries) >= 2:
            return column_entries
    return entries


def _is_junk_outline_title(title: str) -> bool:
    """Закладки-артефакты вёрстки: обложка, форзац, имя файла и т.п."""
    key = re.sub(r"\s+", " ", (title or "").strip()).casefold()
    if not key:
        return True
    if key in {"пустая страница", "обложка", "титульный лист", "форзац"}:
        return True
    if re.match(r"^(обложка|титул|форзац|форз|страница\s*\d+|пустая страница)", key):
        return True
    if re.match(r"^\d+\s*:\s*ок$", key):
        return True
    if "maket" in key or "#" in key or ".pdf" in key:
        return True
    if "_" in key and any(char.isdigit() for char in key):
        return True
    return False


def _outline_entries(reader) -> list[dict[str, Any]]:
    outline = getattr(reader, "outline", None)
    if not outline:
        return []
    flat: list[Any] = []

    def walk(items) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item)
            else:
                flat.append(item)

    walk(outline)
    entries = []
    for item in flat[:60]:
        title = clean_title(getattr(item, "title", "") or "")
        if len(title) < 2 or _is_junk_outline_title(title):
            continue
        try:
            page = reader.get_destination_page_number(item) + 1
        except Exception:  # noqa: BLE001 - повреждённая закладка не должна ронять импорт
            continue
        if page > 0:
            entries.append({"title": title, "page": page})
    return entries


def _first_number(text: str) -> int | None:
    match = _FIRST_NUMBER.match((text or "")[:200])
    return int(match.group(1)) if match else None


def _page_number(text: str) -> int | None:
    """Колонцифра страницы: сверху, снизу или в начале текста."""
    number = _first_number(text)
    if number is not None:
        return number
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    for line in lines[:2] + lines[-4:]:
        match = re.fullmatch(r"(\d{1,4})", line)
        if match:
            return int(match.group(1))
    return None


def _detect_offset(
    path: str, entries: list[dict[str, Any]], toc_index: int, total: int
) -> int:
    """Найти сдвиг: печатная страница → страница PDF (обложка, титул и т.п.)."""
    printed = {entry["page"] for entry in entries}
    if toc_index > total // 2:
        # оглавление в конце: колонцифры и в начале, и перед оглавлением
        indexes = list(range(0, min(total, 40)))
        indexes += list(range(max(0, toc_index - 40), toc_index))
    else:
        indexes = list(range(toc_index + 1, min(total, toc_index + 90)))
    seen: list[tuple[int, int]] = []
    for index in dict.fromkeys(indexes):
        number = _page_number(pdf_text.page_text(path, index + 1))
        if number is not None:
            seen.append((index + 1, number))
    best_offset, best_score = 0, 0
    for offset in range(0, 31):
        score = sum(
            1 for pdf_page, number in seen
            if number in printed and pdf_page == number + offset
        )
        if score > best_score:
            best_offset, best_score = offset, score
    return best_offset if best_score >= 2 else 0


def extract_topics(path: str, max_scan: int = 30) -> dict[str, Any]:
    """Вернуть темы пособия по закладкам или текстовому содержанию."""
    result: dict[str, Any] = {
        "entries": [], "pages": 0, "toc_page": None,
        "offset": 0, "method": "none", "error": "",
    }
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - зависимость указана в requirements.txt
        result["error"] = "Модуль pypdf не установлен"
        return result

    try:
        reader = PdfReader(path)
        result["pages"] = len(reader.pages)
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"Не удалось прочитать PDF: {exc}"
        return result

    entries = _outline_entries(reader)
    outline_titles = {
        clean_title(entry["title"]).casefold() for entry in entries
    }
    if len(outline_titles) >= 2:
        result["method"] = "outline"
    else:
        entries, toc_index = [], None
        total = len(reader.pages)
        # оглавление бывает и в начале, и в конце пособия
        scan_indexes = list(dict.fromkeys([
            *range(min(max_scan, total)),
            *range(max(0, total - max_scan), total),
        ]))
        candidates: dict[int, list[tuple[str, int]]] = {}
        for index in scan_indexes:
            text = pdf_text.page_text(path, index + 1)
            if not text:
                continue
            parsed = parse_contents_text(text)
            has_word = any(word in text.lower() for word in TOC_WORDS)
            if len(parsed) >= 2 and (has_word or len(parsed) >= 4):
                candidates[index] = parsed

        # оглавление может занимать две-три соседние страницы
        groups: list[list[int]] = []
        for index in sorted(candidates):
            if groups and index - groups[-1][-1] <= 2:
                groups[-1].append(index)
            else:
                groups.append([index])

        best_group: list[int] = []
        best_count = 0
        for group in groups:
            chosen: list[int] = []
            last_page = -1
            for index in group:
                pages = [page for _, page in candidates[index]]
                if chosen and min(pages) < last_page:
                    # это уже не продолжение: например, список литературы
                    continue
                chosen.append(index)
                last_page = max(pages)
            count = sum(len(candidates[index]) for index in chosen)
            if count > best_count:
                best_group, best_count = chosen, count

        if best_group:
            toc_index = best_group[0]
            parsed: list[tuple[str, int]] = []
            for index in best_group:
                parsed.extend(candidates[index])
            offset = _detect_offset(
                path, [{"page": page} for _, page in parsed], toc_index, total
            )
            result.update(offset=offset, method="contents", toc_page=toc_index + 1)
            entries = [
                {"title": title, "page": page + offset, "printed_page": page}
                for title, page in parsed
            ]

    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        title = clean_title(entry["title"])
        page = int(entry["page"])
        if page < 1 or page > result["pages"] or not title:
            continue
        key = re.sub(r"\s+", " ", title.lower())
        if key in seen:
            continue
        seen.add(key)
        cleaned.append({"title": title, "page": page})

    cleaned.sort(key=lambda item: item["page"])
    for index, entry in enumerate(cleaned):
        next_page = cleaned[index + 1]["page"] if index + 1 < len(cleaned) else 0
        end = (next_page - 1) if next_page > entry["page"] else entry["page"]
        entry["page_end"] = min(max(end, entry["page"]), result["pages"] or entry["page"])
    result["entries"] = cleaned
    return result


def parse_manual_topics(text: str) -> list[tuple[str, int]]:
    """Разобрать ручной список тем: «Название — 12» (построчно)."""
    entries: list[tuple[str, int]] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^(.+?)\s*(?:[—–\-|:;]|\s{2,}|\t)\s*(\d{1,4})\s*$", line)
        if not match:
            match = re.match(r"^(.+?)\s+(\d{1,4})\s*$", line)
        if not match:
            continue
        title = clean_title(match.group(1))
        if len(title) >= 2:
            entries.append((title, int(match.group(2))))
    return entries
