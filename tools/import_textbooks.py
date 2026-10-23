"""Загрузить учебные пособия учебника в библиотеку (для проверки и демо)."""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import upload_dir  # noqa: E402
from services import orgs, textbooks  # noqa: E402

subject = orgs.get_subject_by_slug("math")
if not subject:
    print("Предмет «Математика» не найден — сначала выполните python seed.py")
    sys.exit(1)

SOURCES = [
    ("static/textbook/part1.pdf", "Математика. 3 класс (часть 1)", 3, "Муравьёва Г.Л., Урбан М.А.", "НИО", "2023"),
    ("static/textbook/part2.pdf", "Повторение за класс (часть 2)", 3, "Муравьёва Г.Л., Урбан М.А.", "НИО", "2023"),
]

for source, title, grade, author, publisher, year in SOURCES:
    if not os.path.exists(source):
        print(f"нет файла {source} — пропускаю")
        continue
    if any(b["title"] == title for b in textbooks.list_textbooks()):
        print(f"«{title}» уже загружено")
        continue
    name = os.path.basename(source)
    target = os.path.join(upload_dir(), name)
    if not os.path.exists(target):
        shutil.copy2(source, target)
    size = os.path.getsize(target)
    pages = textbooks.count_pdf_pages(target)
    book_id = textbooks.create_textbook(
        subject["id"], grade, title, name,
        original_name=name, size_bytes=size, pages=pages,
        author=author, publisher=publisher, year=year,
        description="Учебное пособие для 3 класса (Республика Беларусь).",
    )
    linked = textbooks.auto_link_topics(book_id, grade)
    print(f"загружено «{title}»: {pages} стр., тем привязано: {linked}")
