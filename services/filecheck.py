"""Проверка реального типа загружаемого файла по сигнатуре (magic bytes).

Расширение контролируется браузером и подделывается тривиально, поэтому
перед сохранением проверяем начало файла. Это не заменяет антивирус, но
не даёт загрузить HTML/скрипт под видом PDF или картинки.
"""
from __future__ import annotations

HEAD_BYTES = 4096

_PDF = (b"%PDF-",)
_JPEG = (b"\xff\xd8\xff",)
_PNG = (b"\x89PNG\r\n\x1a\n",)
_GIF = (b"GIF87a", b"GIF89a")


def _webp(head: bytes) -> bool:
    return head[:4] == b"RIFF" and head[8:12] == b"WEBP"


def _heif(head: bytes) -> bool:
    return head[4:8] == b"ftyp" and head[8:12] in {
        b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1",
    }


def looks_like(extension: str, head: bytes) -> bool:
    """Похоже ли содержимое на файл с указанным расширением."""
    extension = (extension or "").lower()
    if not head:
        return False
    if extension == ".pdf":
        return head.startswith(_PDF)
    if extension in (".jpg", ".jpeg"):
        return head.startswith(_JPEG)
    if extension == ".png":
        return head.startswith(_PNG)
    if extension == ".gif":
        return head.startswith(_GIF)
    if extension == ".webp":
        return _webp(head)
    if extension in (".heic", ".heif"):
        return _heif(head)
    return False


def head_of(path: str) -> bytes:
    try:
        with open(path, "rb") as handle:
            return handle.read(HEAD_BYTES)
    except OSError:
        return b""
