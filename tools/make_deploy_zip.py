"""Собрать архив проекта для загрузки на хостинг.

    python tools/make_deploy_zip.py                # без данных (чистая установка)
    python tools/make_deploy_zip.py --with-data    # вместе с БД и загруженными PDF

Архив: dist/edu-math-deploy.zip или dist/edu-math-deploy-with-data.zip
"""
from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "dist"

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    "dist",
    "android",  # отдельный проект, в Python-деплой не входит
    "build",
    ".gradle",
    ".kotlin",
    "node_modules",
}

EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".apk", ".aab", ".iml"}

# Всегда исключаем: секреты и мусор.
EXCLUDE_NAMES = {".secret_key", ".env"}

DATA_EXCLUDES = (
    "math_tutor.db",
    "uploads/",
    ".secret_key",
    "covers/",
    "page_cache/",
)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _skip(path: Path, with_data: bool) -> bool:
    rel = _relative(path)
    parts = path.relative_to(ROOT).parts

    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    if path.suffix in EXCLUDE_SUFFIXES and not (
        with_data and rel.startswith("data/releases/")
    ):
        return True
    if path.name in EXCLUDE_NAMES:
        return True
    if rel.endswith(".db-wal") or rel.endswith(".db-shm"):
        return True
    if rel.startswith("data/page_cache/"):
        return True
    if with_data and rel.startswith("data/") and rel.endswith(".db"):
        if rel != "data/math_tutor.db":
            return True
    if not with_data:
        if rel.startswith("data/"):
            tail = rel[len("data/"):]
            if not tail:  # сам каталог
                return False
            if any(tail.startswith(prefix) for prefix in DATA_EXCLUDES):
                return True
            if tail.endswith(".db"):
                return True
    return False


def _checkpoint_database() -> None:
    """Перенести данные из WAL в основной файл БД перед упаковкой."""
    db = ROOT / "data" / "math_tutor.db"
    if not db.exists():
        return
    import sqlite3

    connection = sqlite3.connect(db)
    try:
        connection.execute("PRAGMA wal_checkpoint(FULL)")
        connection.commit()
    finally:
        connection.close()


def build(with_data: bool) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if with_data:
        _checkpoint_database()
    target = OUT_DIR / (
        "edu-math-deploy-with-data.zip" if with_data else "edu-math-deploy.zip"
    )
    count = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file() or _skip(path, with_data):
                continue
            archive.write(path, _relative(path))
            count += 1
        if not with_data:
            # пустой каталог data, чтобы приложение точно смогло его создать
            archive.writestr("data/.gitkeep", "")
    size_mb = target.stat().st_size / (1024 * 1024)
    print(f"Готово: {target}")
    print(f"Файлов: {count}, размер: {size_mb:.1f} МБ")
    if not with_data:
        print("Данные (БД и PDF) НЕ включены. Для переноса добавьте --with-data.")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Архив для деплоя")
    parser.add_argument(
        "--with-data",
        action="store_true",
        help="включить data/math_tutor.db и data/uploads",
    )
    args = parser.parse_args()
    build(args.with_data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
