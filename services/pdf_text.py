"""Офлайн-извлечение текста из PDF-пособий.

Часть PDF (например, учебники издательства «Аверсэв») хранит кириллицу
в CP1251, но шрифт сообщает pypdf/PyMuPDF коды CP437. В результате текст
выглядит как «╨ατΣσδ» вместо «Раздел». Здесь такие страницы аккуратно
восстанавливаются, а также поддерживается запасной извлекатель PyMuPDF.
"""
from __future__ import annotations

import re
import threading
from functools import lru_cache

# CP437-глиф → кириллица CP1251 (только реально различающиеся символы).
_CP437_TO_CP1251: dict[str, str] = {}
for _code in range(0x80, 0x100):
    try:
        _glyph = bytes([_code]).decode("cp437")
        _cyrillic = bytes([_code]).decode("cp1251")
    except (UnicodeDecodeError, LookupError):
        continue
    if _glyph != _cyrillic:
        _CP437_TO_CP1251[_glyph] = _cyrillic

_TRANSLATION = str.maketrans(_CP437_TO_CP1251)
_CONTROL_RUN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]{3,}")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_CYRILLIC = re.compile(r"[А-Яа-яЁёІіЎў]")


def repair_text(text: str) -> str:
    """Восстановить кириллицу, если страница пришла в CP437-глифах.

    Преобразование применяется только когда «подозрительных» глифов
    достаточно много и после него заметно прибавляется кириллицы. Поэтому
    обычные английские/русские страницы не портятся.
    """
    if not text:
        return ""
    box_drawing = sum(1 for char in text if "\u2500" <= char <= "\u257f")
    greek = sum(1 for char in text if "\u0391" <= char <= "\u03c9")
    before = len(_CYRILLIC.findall(text))
    # Обычный текст с математическими значками (±, ≤, ∞) не трогаем:
    # для «перевёрнутой» кодировки нужны рамки или много греческих глифов.
    if box_drawing < 3 and not (greek >= 5 and before < 10):
        return text
    suspicious = sum(1 for char in text if char in _CP437_TO_CP1251)
    if suspicious < 5:
        return text
    repaired = text.translate(_TRANSLATION)
    after = len(_CYRILLIC.findall(repaired))
    if after > before + max(3, suspicious // 2):
        return repaired
    return text


def normalize_text(text: str) -> str:
    """Убрать управляющие символы, оставив разделители для оглавления."""
    if not text:
        return ""
    text = _CONTROL_RUN.sub("\t", text)
    return _CONTROL.sub(" ", text)


_DOCS = threading.local()


def _fitz_document(path: str):
    """Открытый документ PyMuPDF для текущего потока.

    PyMuPDF-документ нельзя безопасно использовать из нескольких потоков
    одновременно, поэтому кэш привязан к потоку, а не к процессу.
    """
    cache = getattr(_DOCS, "docs", None)
    if cache is None:
        cache = {}
        _DOCS.docs = cache
    document = cache.get(path)
    if document is not None:
        return document
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf  # type: ignore[no-redef]
        except ImportError:
            return None
    try:
        document = pymupdf.open(path)
    except Exception:  # noqa: BLE001
        return None
    cache[path] = document
    return document


def _looks_broken(text: str) -> bool:
    """pypdf иногда отдаёт вместо текста коды вида /GD0/GE0/... ."""
    if not text:
        return True
    if text.count("/G") >= 3 or text.count("/") > len(text) * 0.08:
        return True
    letters = sum(1 for char in text if char.isalpha())
    return letters < len(text) * 0.2


@lru_cache(maxsize=2048)
def page_text(path: str, page: int) -> str:
    """Текст страницы (нумерация с единицы) с восстановлением кодировки."""
    index = max(0, int(page) - 1)
    try:
        from pypdf import PdfReader
    except ImportError:
        PdfReader = None  # type: ignore[assignment]
    text = ""
    if PdfReader is not None:
        try:
            reader = PdfReader(path)
            if index < len(reader.pages):
                text = reader.pages[index].extract_text() or ""
        except Exception:  # noqa: BLE001
            text = ""
    if not _looks_broken(text):
        return normalize_text(repair_text(text))

    doc = _fitz_document(path)
    if doc is None or index >= doc.page_count:
        return normalize_text(repair_text(text))
    try:
        fallback = doc[index].get_text("text") or ""
    except Exception:  # noqa: BLE001
        fallback = ""
    if fallback:
        text = fallback
    return normalize_text(repair_text(text))


def page_count(path: str) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(path).pages)
    except Exception:  # noqa: BLE001
        doc = _fitz_document(path)
        return doc.page_count if doc is not None else 0
