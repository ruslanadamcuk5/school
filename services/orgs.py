"""Организационная структура: города, школы, классы, предметы, курсы."""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from database import execute, query_all, query_one


# ------------------------------------------------------------------ города
def list_cities(search: str = "") -> list[sqlite3.Row]:
    if search:
        return query_all(
            "SELECT * FROM cities WHERE name LIKE ? ORDER BY name", (f"%{search}%",)
        )
    return query_all("SELECT * FROM cities ORDER BY name")


def get_city(city_id: int) -> sqlite3.Row | None:
    return query_one("SELECT * FROM cities WHERE id = ?", (city_id,))


def create_city(name: str, region: str = "") -> int:
    return execute(
        "INSERT INTO cities (name, region) VALUES (?, ?)", (name.strip(), region.strip() or None)
    )


def delete_city(city_id: int) -> None:
    execute("DELETE FROM cities WHERE id = ?", (city_id,))


def city_stats() -> dict[str, int]:
    row = query_one(
        """SELECT (SELECT COUNT(*) FROM cities) AS cities,
                  (SELECT COUNT(*) FROM schools) AS schools,
                  (SELECT COUNT(*) FROM school_classes) AS classes"""
    )
    return dict(row) if row else {}


# ----------------------------------------------------------------- школы
def list_schools(city_id: int | None = None, search: str = "") -> list[sqlite3.Row]:
    sql = """SELECT s.*, c.name AS city_name,
                    (SELECT COUNT(*) FROM school_classes sc WHERE sc.school_id = s.id) AS classes_count,
                    (SELECT COUNT(*) FROM users u WHERE u.school_id = s.id AND u.role = 'student') AS students_count
               FROM schools s
               JOIN cities c ON c.id = s.city_id"""
    params: list[Any] = []
    where = []
    if city_id:
        where.append("s.city_id = ?")
        params.append(city_id)
    if search:
        where.append("(s.name LIKE ? OR c.name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY c.name, s.name"
    return query_all(sql, params)


def get_school(school_id: int) -> sqlite3.Row | None:
    return query_one(
        """SELECT s.*, c.name AS city_name FROM schools s
             JOIN cities c ON c.id = s.city_id WHERE s.id = ?""",
        (school_id,),
    )


def create_school(city_id: int, name: str, address: str = "", director: str = "") -> int:
    return execute(
        "INSERT INTO schools (city_id, name, address, director) VALUES (?, ?, ?, ?)",
        (city_id, name.strip(), address.strip() or None, director.strip() or None),
    )


def update_school(school_id: int, **fields: Any) -> None:
    allowed = {"city_id", "name", "short_name", "address", "director"}
    data = {k: v for k, v in fields.items() if k in allowed}
    if not data:
        return
    sets = ", ".join(f"{k} = ?" for k in data)
    execute(f"UPDATE schools SET {sets} WHERE id = ?", (*data.values(), school_id))


def delete_school(school_id: int) -> None:
    execute("DELETE FROM schools WHERE id = ?", (school_id,))


# ----------------------------------------------------------------- классы
def list_classes(
    school_id: int | None = None,
    teacher_id: int | None = None,
    grade: int | None = None,
) -> list[sqlite3.Row]:
    sql = """SELECT sc.*, s.name AS school_name, c.name AS city_name,
                    u.first_name AS teacher_first, u.last_name AS teacher_last,
                    (SELECT COUNT(*) FROM class_students cs WHERE cs.class_id = sc.id) AS students_count
               FROM school_classes sc
               JOIN schools s ON s.id = sc.school_id
               JOIN cities c ON c.id = s.city_id
          LEFT JOIN users u ON u.id = sc.teacher_id"""
    params: list[Any] = []
    where = []
    if school_id:
        where.append("sc.school_id = ?")
        params.append(school_id)
    if teacher_id:
        where.append("sc.teacher_id = ?")
        params.append(teacher_id)
    if grade:
        where.append("sc.grade = ?")
        params.append(grade)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY sc.grade, sc.letter, s.name"
    return query_all(sql, params)


def get_class(class_id: int) -> sqlite3.Row | None:
    return query_one(
        """SELECT sc.*, s.name AS school_name, s.city_id, c.name AS city_name,
                  u.first_name AS teacher_first, u.last_name AS teacher_last
             FROM school_classes sc
             JOIN schools s ON s.id = sc.school_id
             JOIN cities c ON c.id = s.city_id
        LEFT JOIN users u ON u.id = sc.teacher_id
            WHERE sc.id = ?""",
        (class_id,),
    )


def class_title(row: sqlite3.Row) -> str:
    letter = (row["letter"] or "").strip()
    return f"{row['grade']} «{letter}»" if letter else str(row["grade"])


def create_class(
    school_id: int,
    grade: int,
    letter: str = "",
    teacher_id: int | None = None,
    year: str = "2025/2026",
    title: str = "",
) -> int:
    return execute(
        """INSERT INTO school_classes (school_id, grade, letter, title, teacher_id, year)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (school_id, grade, letter.strip().upper(), title.strip() or None, teacher_id, year),
    )


def update_class(class_id: int, **fields: Any) -> None:
    allowed = {"school_id", "grade", "letter", "title", "teacher_id", "year"}
    data = {k: v for k, v in fields.items() if k in allowed}
    if not data:
        return
    sets = ", ".join(f"{k} = ?" for k in data)
    execute(f"UPDATE school_classes SET {sets} WHERE id = ?", (*data.values(), class_id))


def delete_class(class_id: int) -> None:
    execute("DELETE FROM school_classes WHERE id = ?", (class_id,))


def set_class_teacher(class_id: int, teacher_id: int | None) -> None:
    execute("UPDATE school_classes SET teacher_id = ? WHERE id = ?", (teacher_id, class_id))


def classes_of_teacher(teacher_id: int) -> list[sqlite3.Row]:
    return list_classes(teacher_id=teacher_id)


def classes_of_student(student_id: int) -> list[sqlite3.Row]:
    return query_all(
        """SELECT sc.*, s.name AS school_name, c.name AS city_name,
                  u.first_name AS teacher_first, u.last_name AS teacher_last
             FROM class_students cs
             JOIN school_classes sc ON sc.id = cs.class_id
             JOIN schools s ON s.id = sc.school_id
             JOIN cities c ON c.id = s.city_id
        LEFT JOIN users u ON u.id = sc.teacher_id
            WHERE cs.student_id = ?
            ORDER BY sc.grade""",
        (student_id,),
    )


def students_of_class(class_id: int) -> list[sqlite3.Row]:
    return query_all(
        """SELECT u.*, cs.joined_at FROM class_students cs
             JOIN users u ON u.id = cs.student_id
            WHERE cs.class_id = ?
            ORDER BY u.last_name, u.first_name""",
        (class_id,),
    )


def add_student_to_class(class_id: int, student_id: int) -> None:
    execute(
        "INSERT OR IGNORE INTO class_students (class_id, student_id) VALUES (?, ?)",
        (class_id, student_id),
    )


def remove_student_from_class(class_id: int, student_id: int) -> None:
    execute(
        "DELETE FROM class_students WHERE class_id = ? AND student_id = ?",
        (class_id, student_id),
    )


def teacher_of_class(class_id: int) -> sqlite3.Row | None:
    row = query_one(
        """SELECT u.* FROM school_classes sc JOIN users u ON u.id = sc.teacher_id
            WHERE sc.id = ?""",
        (class_id,),
    )
    return row


# --------------------------------------------------------------- предметы
def list_subjects(active_only: bool = False) -> list[sqlite3.Row]:
    sql = """SELECT s.*,
                    (SELECT COUNT(*) FROM courses c WHERE c.subject_id = s.id) AS courses_count,
                    (SELECT COUNT(*) FROM textbooks t WHERE t.subject_id = s.id) AS textbooks_count,
                    (SELECT COUNT(*) FROM topics t WHERE t.subject_id = s.id) AS topics_count
               FROM subjects s"""
    if active_only:
        sql += " WHERE s.is_active = 1"
    sql += " ORDER BY s.order_index, s.name"
    return query_all(sql)


def get_subject(subject_id: int) -> sqlite3.Row | None:
    return query_one("SELECT * FROM subjects WHERE id = ?", (subject_id,))


def get_subject_by_slug(slug: str) -> sqlite3.Row | None:
    return query_one("SELECT * FROM subjects WHERE slug = ?", (slug,))


def create_subject(slug: str, name: str, icon: str = "📘", color: str = "sky",
                   description: str = "") -> int:
    return execute(
        "INSERT INTO subjects (slug, name, icon, color, description) VALUES (?, ?, ?, ?, ?)",
        (slug.strip().lower(), name.strip(), icon, color, description.strip() or None),
    )


def update_subject(subject_id: int, **fields: Any) -> None:
    allowed = {"name", "icon", "color", "description", "is_active", "order_index"}
    data = {k: v for k, v in fields.items() if k in allowed}
    if not data:
        return
    sets = ", ".join(f"{k} = ?" for k in data)
    execute(f"UPDATE subjects SET {sets} WHERE id = ?", (*data.values(), subject_id))


def delete_subject(subject_id: int) -> None:
    execute(
        """DELETE FROM methods WHERE topic_slug IN
           (SELECT slug FROM topics WHERE subject_id = ?)""",
        (subject_id,),
    )
    execute(
        """DELETE FROM textbook_topics WHERE topic_slug IN
           (SELECT slug FROM topics WHERE subject_id = ?)""",
        (subject_id,),
    )
    execute(
        """DELETE FROM course_topics WHERE topic_slug IN
           (SELECT slug FROM topics WHERE subject_id = ?)""",
        (subject_id,),
    )
    execute("DELETE FROM topics WHERE subject_id = ?", (subject_id,))
    execute("DELETE FROM subjects WHERE id = ?", (subject_id,))


# ----------------------------------------------------------------- курсы
def list_courses(
    teacher_id: int | None = None,
    subject_id: int | None = None,
    class_id: int | None = None,
) -> list[sqlite3.Row]:
    sql = """SELECT c.*, s.name AS subject_name, s.icon AS subject_icon, s.color AS subject_color,
                    s.slug AS subject_slug,
                    u.first_name AS teacher_first, u.last_name AS teacher_last,
                    sch.name AS school_name,
                    (SELECT COUNT(*) FROM course_topics ct WHERE ct.course_id = c.id AND ct.enabled = 1) AS topics_count,
                    (SELECT COUNT(*) FROM course_classes cc WHERE cc.course_id = c.id) AS classes_count
               FROM courses c
               JOIN subjects s ON s.id = c.subject_id
          LEFT JOIN users u ON u.id = c.teacher_id
          LEFT JOIN schools sch ON sch.id = c.school_id"""
    params: list[Any] = []
    where = []
    if teacher_id:
        where.append("c.teacher_id = ?")
        params.append(teacher_id)
    if subject_id:
        where.append("c.subject_id = ?")
        params.append(subject_id)
    if class_id:
        where.append(
            "c.id IN (SELECT course_id FROM course_classes WHERE class_id = ?)"
        )
        params.append(class_id)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY s.name, c.title"
    return query_all(sql, params)


def get_course(course_id: int) -> sqlite3.Row | None:
    return query_one(
        """SELECT c.*, s.name AS subject_name, s.icon AS subject_icon, s.slug AS subject_slug
             FROM courses c JOIN subjects s ON s.id = c.subject_id WHERE c.id = ?""",
        (course_id,),
    )


def create_course(
    subject_id: int,
    title: str,
    grade: int = 3,
    description: str = "",
    teacher_id: int | None = None,
    school_id: int | None = None,
) -> int:
    return execute(
        """INSERT INTO courses (subject_id, title, grade, description, teacher_id, school_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (subject_id, title.strip(), grade, description.strip() or None, teacher_id, school_id),
    )


def update_course(course_id: int, **fields: Any) -> None:
    allowed = {"subject_id", "title", "grade", "description", "teacher_id", "school_id", "is_active"}
    data = {k: v for k, v in fields.items() if k in allowed}
    if not data:
        return
    sets = ", ".join(f"{k} = ?" for k in data)
    execute(f"UPDATE courses SET {sets} WHERE id = ?", (*data.values(), course_id))


def delete_course(course_id: int) -> None:
    execute("DELETE FROM courses WHERE id = ?", (course_id,))


# ---------------------------------------------------------- темы курса
def course_topic_slugs_for_student(student_id: int, subject_id: int, grade: int) -> list[str]:
    """Темы, включённые учителем в курсах ученика (для карты тем)."""
    rows = query_all(
        """SELECT ct.topic_slug
             FROM class_students cs
             JOIN course_classes cc ON cc.class_id = cs.class_id
             JOIN courses c ON c.id = cc.course_id
             JOIN course_topics ct ON ct.course_id = c.id
            WHERE cs.student_id = ? AND c.subject_id = ? AND c.grade = ?
              AND ct.enabled = 1
            ORDER BY ct.order_index, ct.topic_slug""",
        (student_id, subject_id, grade),
    )
    return list(dict.fromkeys(row["topic_slug"] for row in rows))


def course_topics(course_id: int, enabled_only: bool = False) -> list[sqlite3.Row]:
    sql = """SELECT ct.*, t.title, t.icon, t.grade, t.description
               FROM course_topics ct
          LEFT JOIN topics t ON t.slug = ct.topic_slug
              WHERE ct.course_id = ?"""
    if enabled_only:
        sql += " AND ct.enabled = 1"
    sql += " ORDER BY ct.order_index, t.title"
    return query_all(sql, (course_id,))


def set_course_topics(course_id: int, topic_slugs: list[str], enabled: dict[str, bool] | None = None) -> None:
    """Полностью переопределить набор тем курса."""
    execute("DELETE FROM course_topics WHERE course_id = ?", (course_id,))
    enabled = enabled or {}
    for index, slug in enumerate(topic_slugs):
        execute(
            """INSERT OR REPLACE INTO course_topics (course_id, topic_slug, order_index, enabled)
               VALUES (?, ?, ?, ?)""",
            (course_id, slug, index, 1 if enabled.get(slug, True) else 0),
        )


def toggle_course_topic(course_id: int, topic_slug: str, enabled: bool) -> None:
    execute(
        "UPDATE course_topics SET enabled = ? WHERE course_id = ? AND topic_slug = ?",
        (1 if enabled else 0, course_id, topic_slug),
    )


def course_classes(course_id: int) -> list[sqlite3.Row]:
    return query_all(
        """SELECT sc.*, s.name AS school_name, c.name AS city_name
             FROM course_classes cc
             JOIN school_classes sc ON sc.id = cc.class_id
             JOIN schools s ON s.id = sc.school_id
             JOIN cities c ON c.id = s.city_id
            WHERE cc.course_id = ? ORDER BY sc.grade, sc.letter""",
        (course_id,),
    )


def set_course_classes(course_id: int, class_ids: list[int]) -> None:
    execute("DELETE FROM course_classes WHERE course_id = ?", (course_id,))
    for class_id in class_ids:
        execute(
            "INSERT OR IGNORE INTO course_classes (course_id, class_id) VALUES (?, ?)",
            (course_id, class_id),
        )


def courses_for_student(student_id: int) -> list[sqlite3.Row]:
    return query_all(
        """SELECT DISTINCT c.*, s.name AS subject_name, s.icon AS subject_icon, s.color AS subject_color,
                  u.first_name AS teacher_first, u.last_name AS teacher_last
             FROM course_classes cc
             JOIN class_students cs ON cs.class_id = cc.class_id
             JOIN courses c ON c.id = cc.course_id
             JOIN subjects s ON s.id = c.subject_id
        LEFT JOIN users u ON u.id = c.teacher_id
            WHERE cs.student_id = ? AND c.is_active = 1
            ORDER BY s.name""",
        (student_id,),
    )


# ---------------------------------------------------------- расписание
def list_schedule(class_id: int) -> list[sqlite3.Row]:
    return query_all(
        """SELECT sc.*, s.name AS subject_name, s.icon AS subject_icon,
                  t.title AS topic_title
             FROM schedules sc
        LEFT JOIN subjects s ON s.id = sc.subject_id
        LEFT JOIN topics t ON t.slug = sc.topic_slug
            WHERE sc.class_id = ?
            ORDER BY sc.weekday, sc.lesson_no""",
        (class_id,),
    )


def save_schedule_item(
    class_id: int,
    weekday: int,
    lesson_no: int,
    subject_id: int | None = None,
    teacher_id: int | None = None,
    time_start: str = "",
    time_end: str = "",
    topic_slug: str = "",
    note: str = "",
) -> int:
    return execute(
        """INSERT INTO schedules
           (class_id, subject_id, teacher_id, weekday, lesson_no, time_start, time_end, topic_slug, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (class_id, subject_id, teacher_id, weekday, lesson_no, time_start or None,
         time_end or None, topic_slug or None, note or None),
    )


def delete_schedule_item(item_id: int) -> None:
    execute("DELETE FROM schedules WHERE id = ?", (item_id,))


def schedule_for_student(student_id: int) -> list[sqlite3.Row]:
    return query_all(
        """SELECT sc.*, s.name AS subject_name, s.icon AS subject_icon, t.title AS topic_title,
                  cl.letter, cl.grade
             FROM class_students cs
             JOIN schedules sc ON sc.class_id = cs.class_id
        LEFT JOIN subjects s ON s.id = sc.subject_id
        LEFT JOIN topics t ON t.slug = sc.topic_slug
             JOIN school_classes cl ON cl.id = cs.class_id
            WHERE cs.student_id = ?
            ORDER BY sc.weekday, sc.lesson_no""",
        (student_id,),
    )


WEEKDAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
WEEKDAYS_LIST = list(enumerate(WEEKDAYS, 1))


def topics_json(topics: list[sqlite3.Row]) -> str:
    return json.dumps([t["topic_slug"] for t in topics], ensure_ascii=False)
