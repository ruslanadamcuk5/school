"""Собрать архив проекта для загрузки на хостинг.

    python tools/make_deploy_zip.py                # без данных (чистая установка)
    python tools/make_deploy_zip.py --with-apk     # код + новый APK для автообновления
    python tools/make_deploy_zip.py --with-data    # вместе с БД и загруженными PDF

Архив: dist/edu-math-deploy.zip, dist/edu-math-deploy-with-apk.zip или
dist/edu-math-deploy-with-data.zip
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
    # релиз Android публикуется отдельно и не должен затираться кодом
    "releases/",
)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _skip(path: Path, with_data: bool, with_apk: bool = False) -> bool:
    rel = _relative(path)
    parts = path.relative_to(ROOT).parts

    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    is_release = rel.startswith("data/releases/")
    if path.suffix in EXCLUDE_SUFFIXES and not (
        is_release and (with_data or with_apk)
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
    if with_apk and is_release:
        # обновление сайта вместе с новым APK, но без базы и загрузок
        return False
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


def build(with_data: bool, with_apk: bool = False) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if with_data:
        _checkpoint_database()
    if with_data:
        name = "edu-math-deploy-with-data.zip"
    elif with_apk:
        name = "edu-math-deploy-with-apk.zip"
    else:
        name = "edu-math-deploy.zip"
    target = OUT_DIR / name
    count = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file() or _skip(path, with_data, with_apk):
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
    if with_apk:
        print("Включён data/releases (APK и version.json) для автообновления.")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Архив для деплоя")
    parser.add_argument(
        "--with-data",
        action="store_true",
        help="включить data/math_tutor.db и data/uploads",
    )
    parser.add_argument(
        "--with-apk",
        action="store_true",
        help="включить data/releases (APK и version.json), не трогая базу",
    )
    args = parser.parse_args()
    build(args.with_data, args.with_apk)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
