"""Публикация Android-приложения и метаданных обновления.

Файлы лежат в ``data/releases`` (каталог не попадает в Git):

    data/releases/uchus-debug.apk
    data/releases/version.json

``version.json``::

    {
      "version_code": 2,
      "version_name": "1.1",
      "file_name": "uchus-debug.apk",
      "sha256": "…",
      "notes": "Что нового",
      "published_at": "2026-10-26T12:00:00+00:00"
    }

Чтобы выпустить обновление, достаточно заменить APK и увеличить
``version_code`` в ``version.json`` — приложение само предложит обновление.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_RELEASE_DIR = BASE_DIR / "data" / "releases"
DEFAULT_APK_NAME = "uchus-debug.apk"


def release_dir() -> Path:
    configured = (os.environ.get("RELEASE_DIR") or "").strip()
    return Path(configured).expanduser() if configured else DEFAULT_RELEASE_DIR


def metadata_path() -> Path:
    return release_dir() / "version.json"


def _read_metadata() -> dict[str, Any] | None:
    try:
        with metadata_path().open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_name(version_name: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z._-]+", "-", version_name).strip("-._")
    return f"uchus-{safe or 'release'}.apk"


def info() -> dict[str, Any] | None:
    """Метаданные опубликованного APK или ``None``, если релиза нет."""
    meta = _read_metadata()
    if not meta:
        return None

    try:
        version_code = int(meta.get("version_code") or 0)
    except (TypeError, ValueError):
        return None
    if version_code <= 0:
        return None

    file_name = str(meta.get("file_name") or DEFAULT_APK_NAME)
    # Не позволяем выйти за пределы каталога релизов через имя файла.
    if Path(file_name).name != file_name:
        return None

    path = release_dir() / file_name
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if not path.is_file() or size <= 0:
        return None

    version_name = str(meta.get("version_name") or version_code)
    sha256 = str(meta.get("sha256") or "").strip()
    if not sha256:
        try:
            sha256 = _sha256(path)
        except OSError:
            sha256 = ""

    return {
        "version_code": version_code,
        "version_name": version_name,
        "file_name": file_name,
        "download_name": _download_name(version_name),
        "size": size,
        "sha256": sha256,
        "notes": str(meta.get("notes") or ""),
        "published_at": str(meta.get("published_at") or ""),
    }


def file_path(item: dict[str, Any] | None = None) -> Path | None:
    item = item or info()
    if not item:
        return None
    path = release_dir() / str(item["file_name"])
    return path if path.is_file() else None
