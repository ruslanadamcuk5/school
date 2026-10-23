"""Сформировать темы из содержания загруженных PDF-пособий.

Примеры:
    python tools/import_textbook_topics.py --id 4
    python tools/import_textbook_topics.py --all
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db  # noqa: E402
from services import textbooks  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", type=int, help="ID пособия")
    parser.add_argument("--all", action="store_true", help="все пособия без тем")
    args = parser.parse_args()
    if not args.id and not args.all:
        parser.error("укажите --id или --all")

    init_db()
    if args.id:
        books = [textbooks.get_textbook(args.id)]
    else:
        books = [
            book for book in textbooks.list_textbooks() if not book["topics_count"]
        ]
    books = [book for book in books if book]
    if not books:
        print("Нет пособий для обработки.")
        return 0

    for book in books:
        print(f"Обработка: {book['title']} (id={book['id']}, {book['pages']} стр.)")
        result = textbooks.import_topics_from_pdf(book["id"])
        print(
            f"  найдено: {result['found']}, новых тем: {result['created']}, "
            f"привязано: {result['linked']}, способ: {result['method']}"
        )
        if result.get("error"):
            print(f"  ошибка: {result['error']}")
        if not result["linked"]:
            print("  тем не найдено — добавьте вручную на странице пособия")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
