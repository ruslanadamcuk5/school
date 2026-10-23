"""Подготовить текст пособий для тестов по темам-чтению.

Извлекает страницы PDF один раз и сохраняет их в topics.content_json,
чтобы тесты и работы открывались без задержки.

Примеры:
    python tools/cache_topic_text.py
    python tools/cache_topic_text.py --slug angl-3-unit-1-about-me --force
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import execute, init_db  # noqa: E402
from services import reading_quiz, topics  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", help="только одна тема")
    parser.add_argument("--force", action="store_true", help="перечитать PDF")
    args = parser.parse_args()

    init_db()
    rows = (
        [topics.get_topic(args.slug)]
        if args.slug
        else topics.list_topics()
    )
    rows = [row for row in rows if row and row["kind"] != "practice"]
    if not rows:
        print("Нет тем-чтения для обработки.")
        return 0

    cached = extracted = empty = 0
    for row in rows:
        if args.force:
            execute("UPDATE topics SET content_json = NULL WHERE slug = ?", (row["slug"],))
            row = topics.get_topic(row["slug"])
        if row["content_json"]:
            cached += 1
            print(f"  кэш: {row['title']}")
            continue
        pages = reading_quiz.topic_pages(row)
        if any(page is not None for page, _ in pages):
            extracted += 1
            total = sum(len(text) for _, text in pages)
            print(f"  текст: {row['title']} — страниц {len(pages)}, символов {total}")
        else:
            empty += 1
            print(f"  нет текста: {row['title']}")
    print(f"Готово. Уже было: {cached}, извлечено: {extracted}, без текста: {empty}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
