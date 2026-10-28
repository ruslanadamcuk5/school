"""Учебные пособия (PDF): загрузка, привязка к темам и страницам."""
from __future__ import annotations

import os
import re
import sqlite3
import uuid
from typing import Any

from config import Config
from database import execute, query_all, query_one, upload_dir

ALLOWED_EXTENSIONS = {".pdf"}
MAX_UPLOAD_MB = Config.MAX_UPLOAD_MB


def _invalidate_topic_content(textbook_id: int) -> None:
    """Сбросить кэш текста тем, привязанных к пособию."""
    execute(
        """UPDATE topics SET content_json = NULL
            WHERE slug IN (SELECT topic_slug FROM textbook_topics WHERE textbook_id = ?)""",
        (textbook_id,),
    )


def list_textbooks(
    subject_id: int | None = None,
    grade: int | None = None,
    search: str = "",
) -> list[sqlite3.Row]:
    sql = """SELECT t.*, s.name AS subject_name, s.icon AS subject_icon, s.slug AS subject_slug,
                    u.first_name AS uploader_first, u.last_name AS uploader_last,
                    (SELECT COUNT(*) FROM textbook_topics tt WHERE tt.textbook_id = t.id) AS topics_count
               FROM textbooks t
               JOIN subjects s ON s.id = t.subject_id
          LEFT JOIN users u ON u.id = t.uploaded_by"""
    params: list[Any] = []
    where = []
    if subject_id:
        where.append("t.subject_id = ?")
        params.append(subject_id)
    if grade:
        where.append("t.grade = ?")
        params.append(grade)
    if search:
        where.append("(t.title LIKE ? OR t.author LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY t.subject_id, t.grade, t.title"
    return query_all(sql, params)


def get_textbook(textbook_id: int) -> sqlite3.Row | None:
    return query_one(
        """SELECT t.*, s.name AS subject_name, s.icon AS subject_icon, s.slug AS subject_slug
             FROM textbooks t JOIN subjects s ON s.id = t.subject_id WHERE t.id = ?""",
        (textbook_id,),
    )


def save_upload(file_storage, subject_id: int, grade: int, title: str) -> tuple[str, int]:
    """Сохранить загруженный PDF, вернуть (имя файла, размер)."""
    extension = os.path.splitext(file_storage.filename or "")[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Допустимы только файлы PDF")
    limit = MAX_UPLOAD_MB * 1024 * 1024
    stream = file_storage.stream
    if stream is not None and stream.seekable():
        position = stream.tell()
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(position)
        if size > limit:
            raise ValueError(
                f"Файл больше {MAX_UPLOAD_MB} МБ — уменьшите его или загрузите по частям"
            )
    name = f"{uuid.uuid4().hex}{extension}"
    path = os.path.join(upload_dir(), name)
    file_storage.save(path)
    # Расширение легко подделать: проверяем сигнатуру файла.
    from services import filecheck

    if not filecheck.looks_like(extension, filecheck.head_of(path)):
        try:
            os.remove(path)
        except OSError:
            pass
        raise ValueError("Файл не похож на PDF — загрузите настоящий документ")
    return name, os.path.getsize(path)


def count_pdf_pages(path: str) -> int:
    """Количество страниц PDF: pypdf/PyMuPDF, затем грубый разбор файла."""
    try:
        from services import pdf_text

        pages = pdf_text.page_count(path)
        if pages:
            return pages
    except Exception:  # noqa: BLE001
        pass
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError:
        return 0
    counts = [int(m) for m in re.findall(rb"/Count\s+(\d+)", data)]
    if counts:
        return max(counts)
    return len(re.findall(rb"/Type\s*/Page[^s]", data))


def create_textbook(
    subject_id: int,
    grade: int,
    title: str,
    filename: str,
    original_name: str = "",
    size_bytes: int = 0,
    pages: int = 0,
    author: str = "",
    publisher: str = "",
    year: str = "",
    description: str = "",
    uploaded_by: int | None = None,
) -> int:
    return execute(
        """INSERT INTO textbooks
           (subject_id, grade, title, author, publisher, year, filename, original_name,
            size_bytes, pages, description, uploaded_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            subject_id, grade, title.strip(), author.strip() or None, publisher.strip() or None,
            year.strip() or None, filename, original_name or None, size_bytes, pages,
            description.strip() or None, uploaded_by,
        ),
    )


def update_textbook(textbook_id: int, **fields: Any) -> None:
    allowed = {"subject_id", "grade", "title", "author", "publisher", "year", "description"}
    data = {k: v for k, v in fields.items() if k in allowed}
    if not data:
        return
    sets = ", ".join(f"{k} = ?" for k in data)
    execute(f"UPDATE textbooks SET {sets} WHERE id = ?", (*data.values(), textbook_id))
    if "subject_id" in data or "grade" in data:
        book = get_textbook(textbook_id)
        if book:
            # не оставляем привязки к темам другого предмета/класса
            _invalidate_topic_content(textbook_id)
            execute(
                """DELETE FROM textbook_topics
                    WHERE textbook_id = ?
                      AND topic_slug NOT IN (
                          SELECT slug FROM topics WHERE subject_id = ? AND grade = ?
                      )""",
                (textbook_id, book["subject_id"], book["grade"]),
            )


def delete_textbook(textbook_id: int) -> None:
    _invalidate_topic_content(textbook_id)
    row = get_textbook(textbook_id)
    if row:
        path = os.path.join(upload_dir(), row["filename"])
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    execute("DELETE FROM textbooks WHERE id = ?", (textbook_id,))


def file_path(textbook: sqlite3.Row) -> str:
    return os.path.join(upload_dir(), textbook["filename"])


# ------------------------------------------------- привязка к темам
def textbook_topics(textbook_id: int) -> list[sqlite3.Row]:
    return query_all(
        """SELECT tt.*, t.title, t.icon, t.grade
             FROM textbook_topics tt
        LEFT JOIN topics t ON t.slug = tt.topic_slug
            WHERE tt.textbook_id = ?
            ORDER BY tt.page, t.title""",
        (textbook_id,),
    )


def set_textbook_topics(
    textbook_id: int,
    mapping: dict[str, int],
    page_ends: dict[str, int] | None = None,
) -> None:
    """mapping: topic_slug -> страница начала; page_ends — необязательные концы."""
    _invalidate_topic_content(textbook_id)
    execute("DELETE FROM textbook_topics WHERE textbook_id = ?", (textbook_id,))
    page_ends = page_ends or {}
    for slug, page in mapping.items():
        start = int(page or 1)
        end = max(start, int(page_ends.get(slug) or start))
        execute(
            "INSERT OR REPLACE INTO textbook_topics (textbook_id, topic_slug, page, page_end) "
            "VALUES (?, ?, ?, ?)",
            (textbook_id, slug, start, end),
        )


def link_topic(textbook_id: int, topic_slug: str, page: int = 1, page_end: int | None = None) -> None:
    start = max(1, int(page or 1))
    end = max(start, int(page_end or start))
    execute("UPDATE topics SET content_json = NULL WHERE slug = ?", (topic_slug,))
    execute(
        "INSERT OR REPLACE INTO textbook_topics (textbook_id, topic_slug, page, page_end) "
        "VALUES (?, ?, ?, ?)",
        (textbook_id, topic_slug, start, end),
    )


def textbooks_for_topic(
    topic_slug: str,
    subject_id: int | None = None,
    grade: int | None = None,
) -> list[sqlite3.Row]:
    """Все пособия, в которых есть эта тема (с указанием страницы)."""
    sql = """SELECT t.*, s.name AS subject_name, s.icon AS subject_icon, s.slug AS subject_slug,
                    tt.page, tt.page_end
               FROM textbook_topics tt
               JOIN textbooks t ON t.id = tt.textbook_id
               JOIN subjects s ON s.id = t.subject_id
              WHERE tt.topic_slug = ?"""
    params: list[Any] = [topic_slug]
    if subject_id:
        sql += " AND t.subject_id = ?"
        params.append(subject_id)
    if grade:
        sql += " AND t.grade = ?"
        params.append(grade)
    sql += " ORDER BY s.name, t.grade, t.title"
    return query_all(sql, params)


def textbooks_for_grade(grade: int, subject_id: int | None = None) -> list[sqlite3.Row]:
    """Все пособия для класса (используются при обучении)."""
    sql = """SELECT t.*, s.name AS subject_name, s.icon AS subject_icon, s.slug AS subject_slug
               FROM textbooks t JOIN subjects s ON s.id = t.subject_id
              WHERE t.grade = ?"""
    params: list[Any] = [grade]
    if subject_id:
        sql += " AND t.subject_id = ?"
        params.append(subject_id)
    sql += " ORDER BY s.name, t.title"
    return query_all(sql, params)


def auto_link_topics(textbook_id: int, grade: int) -> int:
    """Совместимость: сформировать темы по содержанию пособия."""
    return import_topics_from_pdf(textbook_id)["linked"]


def import_topics_from_pdf(textbook_id: int) -> dict[str, Any]:
    """Создать темы из закладок/содержания PDF и привязать их к страницам."""
    from services import pdf_topics, topics as topics_service

    book = get_textbook(textbook_id)
    if not book:
        return {"found": 0, "created": 0, "linked": 0, "method": "none", "error": "Пособие не найдено"}
    path = file_path(book)
    if not os.path.exists(path):
        return {"found": 0, "created": 0, "linked": 0, "method": "none", "error": "Файл пособия не найден"}

    parsed = pdf_topics.extract_topics(path)
    created = linked = 0
    new_slugs: set[str] = set()
    skip_titles = {
        "пустая страница", "титульный лист", "обложка", "форзац",
        "содержание", "оглавление",
        "спіс выкарыстанай літаратуры", "список использованной литературы",
        "спіс выкарыстаных крыніц", "список использованных источников",
    }
    skip_prefixes = ("пустая страница", "правообладатель", "скачано с сайта")
    for entry in parsed["entries"]:
        title_key = re.sub(r"\s+", " ", entry["title"].strip().lower())
        if title_key in skip_titles or title_key.startswith(skip_prefixes):
            continue
        existing = topics_service.find_topic(book["subject_id"], book["grade"], entry["title"])
        if existing:
            slug = existing["slug"]
        else:
            slug = topics_service.create_topic(
                book["subject_id"], book["grade"], entry["title"],
                source="pdf", textbook_id=book["id"],
            )
            created += 1
        link_topic(book["id"], slug, entry["page"], entry["page_end"])
        if not existing or existing["source"] != "curriculum":
            topics_service.update_topic(
                slug,
                page_start=entry["page"], page_end=entry["page_end"],
            )
        topics_service.attach_to_courses(slug)
        new_slugs.add(slug)
        linked += 1

    # Убираем старые PDF-артефакты (обложка, имя файла, пустая страница),
    # которые остались от прежнего разбора закладок. Пользовательские темы,
    # темы курсов и темы с прогрессом не трогаем.
    if new_slugs:
        stale = query_all(
            """SELECT tp.slug
                 FROM textbook_topics tt JOIN topics tp ON tp.slug = tt.topic_slug
                WHERE tt.textbook_id = ? AND tp.source = 'pdf'""",
            (textbook_id,),
        )
        for row in stale:
            slug = row["slug"]
            if slug in new_slugs:
                continue
            execute(
                "DELETE FROM textbook_topics WHERE textbook_id = ? AND topic_slug = ?",
                (textbook_id, slug),
            )
            refs = query_one(
                """SELECT
                     (SELECT COUNT(*) FROM textbook_topics WHERE topic_slug = ?) +
                     (SELECT COUNT(*) FROM course_topics WHERE topic_slug = ?) +
                     (SELECT COUNT(*) FROM methods WHERE topic_slug = ?) +
                     (SELECT COUNT(*) FROM method_progress WHERE topic_slug = ?) +
                     (SELECT COUNT(*) FROM topic_progress WHERE topic_slug = ?) +
                     (SELECT COUNT(*) FROM attempts WHERE topic_slug = ?) +
                     (SELECT COUNT(*) FROM assignments WHERE topic_slugs LIKE ?) AS total""",
                (slug, slug, slug, slug, slug, slug, f"%{slug}%"),
            )
            if refs and int(refs["total"]) == 0:
                topics_service.delete_topic(slug)
    return {
        "found": len(parsed["entries"]),
        "created": created,
        "linked": linked,
        "method": parsed["method"],
        "offset": parsed["offset"],
        "toc_page": parsed["toc_page"],
        "error": parsed["error"],
    }


def add_topics_manually(textbook_id: int, entries: list[tuple[str, int]]) -> dict[str, int]:
    """Добавить темы вручную (название, страница) и привязать к пособию."""
    from services import topics as topics_service

    book = get_textbook(textbook_id)
    if not book:
        return {"created": 0, "linked": 0}
    cleaned = sorted(
        (
            (
                title,
                max(1, min(int(page or 1), book["pages"] or int(page or 1))),
            )
            for title, page in entries
        ),
        key=lambda item: item[1],
    )
    created = linked = 0
    for index, (title, page) in enumerate(cleaned):
        next_page = cleaned[index + 1][1] if index + 1 < len(cleaned) else 0
        page_end = (next_page - 1) if next_page > page else (book["pages"] or page)
        page_end = max(page, page_end)
        existing = topics_service.find_topic(book["subject_id"], book["grade"], title)
        if existing:
            slug = existing["slug"]
        else:
            slug = topics_service.create_topic(
                book["subject_id"], book["grade"], title,
                source="manual", textbook_id=book["id"],
            )
            created += 1
        link_topic(book["id"], slug, page, page_end)
        if not existing or existing["source"] != "curriculum":
            topics_service.update_topic(slug, page_start=page, page_end=page_end)
        topics_service.attach_to_courses(slug)
        linked += 1
    return {"created": created, "linked": linked}


def purge_textbook_topics(textbook_id: int) -> int:
    """Удалить темы, созданные из этого пособия, если они больше не нужны.

    Темы курсов, темы с прогрессом и пользовательские темы сохраняются.
    """
    from services import topics as topics_service

    rows = query_all(
        """SELECT tp.slug FROM textbook_topics tt
             JOIN topics tp ON tp.slug = tt.topic_slug
            WHERE tt.textbook_id = ? AND tp.source IN ('pdf', 'manual')""",
        (textbook_id,),
    )
    removed = 0
    for row in rows:
        slug = row["slug"]
        other = query_one(
            "SELECT COUNT(*) AS n FROM textbook_topics WHERE topic_slug = ? AND textbook_id <> ?",
            (slug, textbook_id),
        )
        if other and int(other["n"]):
            continue
        used = query_one(
            """SELECT
                 (SELECT COUNT(*) FROM method_progress WHERE topic_slug = ?) +
                 (SELECT COUNT(*) FROM topic_progress WHERE topic_slug = ?) +
                 (SELECT COUNT(*) FROM attempts WHERE topic_slug = ?) +
                 (SELECT COUNT(*) FROM assignments WHERE topic_slugs LIKE ?) AS total""",
            (slug, slug, slug, f"%{slug}%"),
        )
        if used and int(used["total"]) == 0:
            topics_service.delete_topic(slug)
            removed += 1
    return removed


def topics_for_textbook(textbook_id: int) -> list[sqlite3.Row]:
    return query_all(
        """SELECT tp.*, tt.topic_slug, tt.page, tt.page_end
             FROM textbook_topics tt JOIN topics tp ON tp.slug = tt.topic_slug
            WHERE tt.textbook_id = ?
            ORDER BY tt.page, tp.title""",
        (textbook_id,),
    )


def books_for_topics(topic_slugs: list[str]) -> dict[str, list[sqlite3.Row]]:
    """Пособия по каждой теме: {topic_slug: [book, ...]}."""
    slugs = [slug for slug in dict.fromkeys(topic_slugs) if slug]
    if not slugs:
        return {}
    marks = ", ".join("?" for _ in slugs)
    rows = query_all(
        f"""SELECT tt.topic_slug, tt.page, tt.page_end, t.*,
                   s.name AS subject_name, s.icon AS subject_icon, s.slug AS subject_slug
              FROM textbook_topics tt
              JOIN textbooks t ON t.id = tt.textbook_id
              JOIN subjects s ON s.id = t.subject_id
             WHERE tt.topic_slug IN ({marks})
             ORDER BY t.grade, t.title, tt.page""",
        tuple(slugs),
    )
    out: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        out.setdefault(row["topic_slug"], []).append(row)
    return out
