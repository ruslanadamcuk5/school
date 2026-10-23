"""Темы предметов: справочник, учебные пособия, импорт из содержания PDF."""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from typing import Any, Iterable

from database import execute, query_all, query_one

# Транслитерация для стабильных читаемых адресов тем (латиница).
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "і": "i", "ў": "u", "є": "e", "ґ": "g",
}


def slugify(text: str, max_len: int = 60) -> str:
    text = (text or "").lower()
    out: list[str] = []
    for char in text:
        if char in _TRANSLIT:
            out.append(_TRANSLIT[char])
        elif char.isascii() and char.isalnum():
            out.append(char)
        else:
            out.append("-")
    slug = re.sub(r"-{2,}", "-", "".join(out)).strip("-")
    return (slug or "topic")[:max_len].strip("-") or "topic"


def normalize_title(title: str) -> str:
    """Нормализованное название для поиска дублей при импорте."""
    text = unicodedata.normalize("NFKC", title or "").lower().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-яіў]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _unique_slug(subject_slug: str, grade: int, title: str) -> str:
    base = f"{slugify(subject_slug, 20)}-{grade}-{slugify(title, 50)}"[:90].strip("-")
    slug = base
    counter = 2
    while query_one("SELECT 1 AS x FROM topics WHERE slug = ?", (slug,)):
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def list_topics(
    subject_id: int | None = None,
    grade: int | None = None,
    search: str = "",
) -> list[sqlite3.Row]:
    sql = """SELECT t.*, s.name AS subject_name, s.icon AS subject_icon,
                    s.slug AS subject_slug, s.color AS subject_color,
                    (SELECT COUNT(*) FROM textbook_topics tt
                      WHERE tt.topic_slug = t.slug) AS books_count,
                    (SELECT COUNT(*) FROM course_topics ct
                      WHERE ct.topic_slug = t.slug AND ct.enabled = 1) AS courses_count
               FROM topics t
          LEFT JOIN subjects s ON s.id = t.subject_id"""
    params: list[Any] = []
    where: list[str] = []
    if subject_id:
        where.append("t.subject_id = ?")
        params.append(subject_id)
    if grade:
        where.append("t.grade = ?")
        params.append(grade)
    if search:
        where.append("t.title LIKE ?")
        params.append(f"%{search}%")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY t.grade, t.order_index, t.id"
    return query_all(sql, params)


def get_topic(slug: str) -> sqlite3.Row | None:
    return query_one(
        """SELECT t.*, s.name AS subject_name, s.icon AS subject_icon,
                  s.slug AS subject_slug, s.color AS subject_color
             FROM topics t LEFT JOIN subjects s ON s.id = t.subject_id
            WHERE t.slug = ?""",
        (slug,),
    )


def find_topic(subject_id: int, grade: int, title: str) -> sqlite3.Row | None:
    wanted = normalize_title(title)
    if not wanted:
        return None
    for row in query_all(
        "SELECT * FROM topics WHERE subject_id = ? AND grade = ?", (subject_id, grade)
    ):
        if normalize_title(row["title"]) == wanted:
            return row
    return None


def _subject_defaults(subject_id: int) -> sqlite3.Row | None:
    return query_one("SELECT * FROM subjects WHERE id = ?", (subject_id,))


def _next_order(subject_id: int, grade: int) -> int:
    row = query_one(
        "SELECT COALESCE(MAX(order_index), 0) AS n FROM topics WHERE subject_id = ? AND grade = ?",
        (subject_id, grade),
    )
    return (row["n"] if row else 0) + 1


def create_topic(
    subject_id: int,
    grade: int,
    title: str,
    description: str = "",
    icon: str | None = None,
    color: str | None = None,
    source: str = "manual",
    textbook_id: int | None = None,
    order_index: int | None = None,
) -> str:
    subject = _subject_defaults(subject_id)
    if not subject:
        raise ValueError("Предмет не найден")
    grade = int(grade or 3)
    slug = _unique_slug(subject["slug"], grade, title)
    execute(
        """INSERT INTO topics
           (slug, title, grade, subject_id, textbook_id, source, kind, icon, color,
            description, order_index, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'reading', ?, ?, ?, ?, datetime('now'))""",
        (
            slug, title.strip()[:150], grade, subject_id, textbook_id, source,
            icon or subject["icon"] or "⭐", color or subject["color"] or "sky",
            (description or "").strip(), order_index if order_index is not None
            else _next_order(subject_id, grade),
        ),
    )
    return slug


def update_topic(slug: str, **fields: Any) -> None:
    allowed = {
        "title", "grade", "description", "icon", "color", "order_index",
        "page_start", "page_end",
    }
    data = {k: v for k, v in fields.items() if k in allowed}
    if not data:
        return
    old = get_topic(slug)
    sets = ", ".join(f"{k} = ?" for k in data)
    execute(f"UPDATE topics SET {sets} WHERE slug = ?", (*data.values(), slug))
    if old and "grade" in data and int(data["grade"]) != int(old["grade"]):
        grade = int(data["grade"])
        # убираем тему из курсов и пособий другого класса
        execute(
            """DELETE FROM course_topics
                WHERE topic_slug = ?
                  AND course_id IN (SELECT id FROM courses WHERE grade != ?)""",
            (slug, grade),
        )
        execute(
            """DELETE FROM textbook_topics
                WHERE topic_slug = ?
                  AND textbook_id IN (SELECT id FROM textbooks WHERE grade != ?)""",
            (slug, grade),
        )


def delete_topic(slug: str) -> None:
    execute("DELETE FROM textbook_topics WHERE topic_slug = ?", (slug,))
    execute("DELETE FROM course_topics WHERE topic_slug = ?", (slug,))
    execute("DELETE FROM methods WHERE topic_slug = ?", (slug,))
    execute("DELETE FROM topics WHERE slug = ?", (slug,))


def reorder_topic(slug: str, direction: int) -> None:
    """Поменять тему местами с соседней (direction = -1 вверх, 1 вниз)."""
    topic = get_topic(slug)
    if not topic:
        return
    neighbours = query_all(
        """SELECT slug, order_index FROM topics
            WHERE subject_id = ? AND grade = ?
            ORDER BY order_index, id""",
        (topic["subject_id"], topic["grade"]),
    )
    index = next((i for i, row in enumerate(neighbours) if row["slug"] == slug), None)
    if index is None:
        return
    other_index = index + direction
    if other_index < 0 or other_index >= len(neighbours):
        return
    other = neighbours[other_index]
    execute(
        "UPDATE topics SET order_index = ? WHERE slug = ?",
        (other_index, topic["slug"]),
    )
    execute(
        "UPDATE topics SET order_index = ? WHERE slug = ?",
        (index, other["slug"]),
    )


def attach_to_courses(topic_slug: str) -> int:
    """Добавить тему во все активные курсы её предмета и класса."""
    topic = get_topic(topic_slug)
    if not topic:
        return 0
    courses = query_all(
        "SELECT id FROM courses WHERE subject_id = ? AND grade = ? AND is_active = 1",
        (topic["subject_id"], topic["grade"]),
    )
    for course in courses:
        row = query_one(
            "SELECT COALESCE(MAX(order_index), 0) AS n FROM course_topics WHERE course_id = ?",
            (course["id"],),
        )
        execute(
            """INSERT OR IGNORE INTO course_topics (course_id, topic_slug, order_index, enabled)
               VALUES (?, ?, ?, 1)""",
            (course["id"], topic_slug, (row["n"] if row else 0) + 1),
        )
    return len(courses)


def sync_course_topics(course_id: int | None = None) -> int:
    """Заполнить пустые курсы темами их предмета и класса."""
    sql = "SELECT * FROM courses"
    params: tuple[Any, ...] = ()
    if course_id:
        sql += " WHERE id = ?"
        params = (course_id,)
    count = 0
    for course in query_all(sql, params):
        existing = query_one(
            "SELECT COUNT(*) AS n FROM course_topics WHERE course_id = ?", (course["id"],)
        )
        if existing and existing["n"]:
            continue
        rows = list_topics(subject_id=course["subject_id"], grade=course["grade"])
        for index, row in enumerate(rows, 1):
            execute(
                """INSERT OR IGNORE INTO course_topics
                   (course_id, topic_slug, order_index, enabled) VALUES (?, ?, ?, 1)""",
                (course["id"], row["slug"], index),
            )
            count += 1
    return count


def topic_titles() -> dict[str, str]:
    return {row["slug"]: row["title"] for row in query_all("SELECT slug, title FROM topics")}


def titles_for(slugs: Iterable[str]) -> dict[str, str]:
    wanted = list(dict.fromkeys(slug for slug in slugs if slug))
    if not wanted:
        return {}
    marks = ", ".join("?" for _ in wanted)
    rows = query_all(
        f"SELECT slug, title FROM topics WHERE slug IN ({marks})", tuple(wanted)
    )
    return {row["slug"]: row["title"] for row in rows}
