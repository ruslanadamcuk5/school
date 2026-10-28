"""Обслуживание каталога загрузок.

Удаляет фотографии ответов, которые больше не привязаны к результатам работ,
и файлы, оставшиеся от прерванных загрузок. По умолчанию работает в режиме
отчёта; удаление — с флагом ``--apply``.

    python tools/cleanup_uploads.py                 # показать, что можно удалить
    python tools/cleanup_uploads.py --apply         # удалить
    python tools/cleanup_uploads.py --apply --days 30
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from database import query_all, upload_dir  # noqa: E402


def referenced_photos() -> set[str]:
    paths: set[str] = set()
    try:
        rows = query_all("SELECT photos FROM assignment_results WHERE photos IS NOT NULL")
    except Exception:  # noqa: BLE001 - старая схема без колонки
        return paths
    for row in rows:
        try:
            items = json.loads(row["photos"] or "[]")
        except (TypeError, ValueError):
            continue
        for item in items:
            if isinstance(item, str):
                paths.add(item.replace("\\", "/"))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Очистка каталога uploads")
    parser.add_argument("--apply", action="store_true", help="удалить найденные файлы")
    parser.add_argument("--days", type=int, default=90,
                        help="не трогать файлы новее N дней (по умолчанию 90)")
    args = parser.parse_args()

    root = os.path.join(upload_dir(), "assignment_answers")
    if not os.path.isdir(root):
        print("Каталог фотографий ответов пуст — чистить нечего.")
        return 0

    referenced = referenced_photos()
    cutoff = time.time() - max(0, args.days) * 86400
    total = 0
    removed = 0
    freed = 0

    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            absolute = os.path.join(dirpath, name)
            relative = os.path.relpath(absolute, os.path.join(upload_dir())).replace("\\", "/")
            try:
                stat = os.stat(absolute)
            except OSError:
                continue
            total += 1
            if relative in referenced or stat.st_mtime > cutoff:
                continue
            size = stat.st_size
            print(("удаляю  " if args.apply else "осиротел ") + relative)
            if args.apply:
                try:
                    os.remove(absolute)
                except OSError as exc:
                    print(f"  не удалось: {exc}")
                    continue
                removed += 1
                freed += size

    mode = "Удалено" if args.apply else "Найдено к удалению"
    print(f"\nВсего файлов: {total}. {mode}: {removed if args.apply else 'см. выше'}"
          + (f", освобождено {freed / 1024 / 1024:.2f} МБ" if args.apply else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
