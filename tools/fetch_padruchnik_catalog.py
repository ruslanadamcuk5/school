"""Собрать каталог e-padruchnik: книги, метаданные и ссылки на PDF.

Запускать с машины, у которой есть прямой доступ к порталу:

    python3 tools/fetch_padruchnik_catalog.py

Результат — ``services/padruchnik_catalog.json``. Он нужен сайту, чтобы
поиск работал даже там, где портал недоступен напрямую (например, на
хостинге, чей IP портал не пускает).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from services import padruchnik  # noqa: E402

OUT = os.path.join(BASE_DIR, "services", "padruchnik_catalog.json")


def fetch() -> dict:
    books: dict[int, dict] = {}
    for page in range(0, 80):
        data = {"query": "", "char": "", "page-nav": str(page), "mode": "page"}
        for attempt in range(3):
            try:
                html = padruchnik._post(data)
                break
            except Exception as error:  # noqa: BLE001
                if attempt == 2:
                    raise
                print(f"page {page} attempt {attempt + 1}: {error}", file=sys.stderr)
                time.sleep(2 * (attempt + 1))
        rows = padruchnik._parse_rows(html)
        fresh = [row for row in rows if row["id"] not in books]
        for row in rows:
            books.setdefault(row["id"], row)
        print(f"page {page}: {len(rows)} rows, new {len(fresh)}, total {len(books)}")
        if not rows or len(books) >= 499 and not fresh:
            break
        time.sleep(0.1)

    total = len(books)
    for index, (book_id, row) in enumerate(sorted(books.items()), 1):
        url = ""
        for attempt in range(3):
            try:
                raw = padruchnik._post(
                    {"id": str(book_id)},
                    url=padruchnik.BASE_URL + "getbookurl.php",
                ).strip()
                raw = re.sub(
                    r"^book-viewer[\\/]web[\\/]viewer\.html\?file=", "", raw
                )
                if raw.startswith("http"):
                    url = raw
                break
            except Exception as error:  # noqa: BLE001
                if attempt == 2:
                    print(f"book {book_id}: {error}", file=sys.stderr)
                time.sleep(1.5 * (attempt + 1))
        row["pdf_url"] = url
        if index % 25 == 0 or index == total:
            print(f"pdf {index}/{total}: {book_id} {'ok' if url else 'no url'}")
        time.sleep(0.05)

    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": padruchnik.BASE_URL,
        "total": total,
        "books": [books[key] for key in sorted(books)],
    }


def main() -> None:
    data = fetch()
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
    print(f"written {OUT}: {data['total']} books")


if __name__ == "__main__":
    main()
