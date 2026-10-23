"""Проверочные и контрольные работы: назначение, выполнение, результаты."""
from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime
from typing import Any

from content.answer import check_answer
from content.curriculum import TOPICS
from content.generators import REGISTRY
from database import execute, query_all, query_one

KINDS = {
    "проверочная": "Проверочная работа",
    "контрольная": "Контрольная работа",
    "срез": "Срез знаний",
    "тренировочная": "Тренировочная работа",
    "домашняя": "Домашнее задание",
}

TOPIC_BY_SLUG = {t["slug"]: t for t in TOPICS}


def list_assignments(
    teacher_id: int | None = None,
    class_id: int | None = None,
    student_id: int | None = None,
    status: str | None = None,
) -> list[sqlite3.Row]:
    sql = """SELECT a.*, c.title AS course_title, s.name AS subject_name, s.icon AS subject_icon,
                    cl.grade, cl.letter,
                    u.first_name AS teacher_first, u.last_name AS teacher_last,
                    st.first_name AS student_first, st.last_name AS student_last,
                    (SELECT COUNT(*) FROM assignment_results r
                      WHERE r.assignment_id = a.id) AS done_count,
                    CASE WHEN a.student_id IS NOT NULL THEN 1
                         ELSE (SELECT COUNT(*) FROM class_students cs
                                WHERE cs.class_id = a.class_id) END AS students_count
               FROM assignments a
          LEFT JOIN courses c ON c.id = a.course_id
          LEFT JOIN subjects s ON s.id = a.subject_id
          LEFT JOIN school_classes cl ON cl.id = a.class_id
          LEFT JOIN users u ON u.id = a.teacher_id
          LEFT JOIN users st ON st.id = a.student_id"""
    params: list[Any] = []
    where = []
    if teacher_id:
        where.append("a.teacher_id = ?")
        params.append(teacher_id)
    if class_id:
        where.append("a.class_id = ?")
        params.append(class_id)
    if student_id:
        where.append(
            "(a.student_id = ? OR (a.student_id IS NULL AND "
            "a.class_id IN (SELECT class_id FROM class_students WHERE student_id = ?)))"
        )
        params.extend([student_id, student_id])
    if status:
        where.append("a.status = ?")
        params.append(status)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY a.created_at DESC"
    return query_all(sql, params)


def get_assignment(assignment_id: int) -> sqlite3.Row | None:
    return query_one(
        """SELECT a.*, c.title AS course_title, s.name AS subject_name, s.icon AS subject_icon,
                  cl.grade, cl.letter, sch.name AS school_name,
                  u.first_name AS teacher_first, u.last_name AS teacher_last,
                  st.first_name AS student_first, st.last_name AS student_last
             FROM assignments a
        LEFT JOIN courses c ON c.id = a.course_id
        LEFT JOIN subjects s ON s.id = a.subject_id
        LEFT JOIN school_classes cl ON cl.id = a.class_id
        LEFT JOIN schools sch ON sch.id = cl.school_id
        LEFT JOIN users u ON u.id = a.teacher_id
        LEFT JOIN users st ON st.id = a.student_id
            WHERE a.id = ?""",
        (assignment_id,),
    )


def create_assignment(
    title: str,
    kind: str = "проверочная",
    description: str = "",
    course_id: int | None = None,
    subject_id: int | None = None,
    class_id: int | None = None,
    teacher_id: int | None = None,
    student_id: int | None = None,
    topic_slugs: list[str] | None = None,
    questions_count: int = 10,
    time_limit: int = 0,
    due_date: str = "",
    status: str = "черновик",
    tasks: list[dict[str, Any]] | None = None,
) -> int:
    topic_slugs = topic_slugs or []
    if tasks is None:
        tasks = build_tasks(topic_slugs, questions_count)
    question_total = len(tasks) if tasks else questions_count
    return execute(
        """INSERT INTO assignments
           (title, kind, description, course_id, subject_id, class_id, teacher_id,
            student_id, topic_slugs, questions_json, questions_count, time_limit,
            due_date, status, published_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            title.strip(), kind, description.strip() or None, course_id, subject_id, class_id,
            teacher_id, student_id, json.dumps(topic_slugs, ensure_ascii=False),
            json.dumps(tasks, ensure_ascii=False), question_total,
            time_limit, due_date or None, status,
            datetime.now().isoformat(timespec="seconds") if status == "опубликована" else None,
        ),
    )


def assignment_tasks(assignment: sqlite3.Row) -> list[dict[str, Any]]:
    """Задания работы (фиксируются при создании, чтобы проверка шла по тем же вопросам)."""
    try:
        tasks = json.loads(assignment["questions_json"] or "[]")
    except (ValueError, TypeError, KeyError, IndexError):
        tasks = []
    if not tasks:
        topics = assignment_topics(assignment)
        tasks = build_tasks(topics, assignment["questions_count"] or 10)
        execute(
            "UPDATE assignments SET questions_json = ? WHERE id = ?",
            (json.dumps(tasks, ensure_ascii=False), assignment["id"]),
        )
    return tasks


def regenerate_tasks(assignment_id: int) -> None:
    """Пересоздать задания (например, после смены тем)."""
    assignment = get_assignment(assignment_id)
    if not assignment:
        return
    tasks = build_tasks(assignment_topics(assignment), assignment["questions_count"] or 10)
    execute(
        "UPDATE assignments SET questions_json = ? WHERE id = ?",
        (json.dumps(tasks, ensure_ascii=False), assignment_id),
    )


def update_assignment(assignment_id: int, **fields: Any) -> None:
    allowed = {
        "title", "kind", "description", "course_id", "subject_id", "class_id",
        "teacher_id", "student_id", "questions_count", "time_limit", "due_date",
        "status", "topic_slugs",
    }
    data = {k: v for k, v in fields.items() if k in allowed}
    if "topic_slugs" in data and isinstance(data["topic_slugs"], list):
        data["topic_slugs"] = json.dumps(data["topic_slugs"], ensure_ascii=False)
    if not data:
        return
    sets = ", ".join(f"{k} = ?" for k in data)
    execute(f"UPDATE assignments SET {sets} WHERE id = ?", (*data.values(), assignment_id))


def delete_assignment(assignment_id: int) -> None:
    execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))


def publish_assignment(assignment_id: int) -> None:
    execute(
        "UPDATE assignments SET status = 'опубликована', published_at = datetime('now') WHERE id = ?",
        (assignment_id,),
    )


def close_assignment(assignment_id: int) -> None:
    execute("UPDATE assignments SET status = 'закрыта' WHERE id = ?", (assignment_id,))


def assignment_topics(assignment: sqlite3.Row) -> list[str]:
    try:
        data = json.loads(assignment["topic_slugs"] or "[]")
    except (ValueError, TypeError):
        return []
    from services import topics as topics_service

    known = {row["slug"] for row in topics_service.list_topics()}
    return [slug for slug in data if slug in TOPIC_BY_SLUG or slug in known]


def _math_tasks(slugs: list[str], count: int, difficulty: int = 2) -> list[dict[str, Any]]:
    pool: list[str] = []
    for slug in slugs:
        topic = TOPIC_BY_SLUG.get(slug)
        if topic:
            pool.extend(topic["generators"])
    if not pool or count <= 0:
        return []
    tasks = []
    for index in range(count):
        generator_key = pool[index % len(pool)] if index < len(pool) else random.choice(pool)
        fn = REGISTRY.get(generator_key)
        if not fn:
            continue
        task = fn(difficulty)
        task["generator"] = generator_key
        task["topic_slug"] = generator_key.split(".")[0]
        task["points"] = 1
        tasks.append(task)
    return tasks


def build_tasks(topic_slugs: list[str], count: int, difficulty: int = 2) -> list[dict[str, Any]]:
    """Собрать вопросы работы по выбранным темам любого предмета.

    Математические темы дают вычислительные задания, темы-чтение — вопросы
    по тексту пособия (пропущенное слово, страница, предмет, описание).
    """
    from services import topics as topics_service

    if count <= 0 or not topic_slugs:
        return []
    per_topic = max(1, -(-count // len(topic_slugs)))
    tasks: list[dict[str, Any]] = []
    math_slugs: list[str] = []
    for slug in topic_slugs:
        if slug in TOPIC_BY_SLUG:
            math_slugs.append(slug)
            tasks.extend(_math_tasks([slug], per_topic, difficulty))
            continue
        topic = topics_service.get_topic(slug)
        if not topic:
            continue
        from services.reading_quiz import build_questions

        tasks.extend(build_questions(topic, per_topic))
    # Если темы-чтение дали меньше вопросов, добираем математикой.
    if len(tasks) < count and math_slugs:
        tasks.extend(_math_tasks(math_slugs, count - len(tasks), difficulty))
    return tasks[:count]


def get_result(assignment_id: int, student_id: int) -> sqlite3.Row | None:
    return query_one(
        "SELECT * FROM assignment_results WHERE assignment_id = ? AND student_id = ?",
        (assignment_id, student_id),
    )


def save_result(
    assignment_id: int,
    student_id: int,
    score: int,
    max_score: int,
    answers: list[dict[str, Any]],
    duration_sec: int = 0,
) -> None:
    execute(
        """INSERT INTO assignment_results
           (assignment_id, student_id, score, max_score, answers, duration_sec, started_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
           ON CONFLICT(assignment_id, student_id) DO UPDATE SET
               score = excluded.score, max_score = excluded.max_score,
               answers = excluded.answers, duration_sec = excluded.duration_sec,
               completed_at = datetime('now')""",
        (
            assignment_id, student_id, score, max_score,
            json.dumps(answers, ensure_ascii=False), duration_sec,
        ),
    )


def results_of(assignment_id: int) -> list[sqlite3.Row]:
    return query_all(
        """SELECT r.*, u.first_name, u.last_name, u.avatar
             FROM assignment_results r JOIN users u ON u.id = r.student_id
            WHERE r.assignment_id = ?
            ORDER BY r.score DESC, u.last_name""",
        (assignment_id,),
    )


def results_with_students(assignment_id: int) -> list[dict[str, Any]]:
    """Результаты вместе со списком всех учеников класса (чтобы видеть «не сдал»)."""
    assignment = get_assignment(assignment_id)
    if not assignment:
        return []
    from services import orgs

    if assignment["student_id"]:
        student = query_one("SELECT * FROM users WHERE id = ?", (assignment["student_id"],))
        students = [student] if student else []
    else:
        students = orgs.students_of_class(assignment["class_id"]) if assignment["class_id"] else []
    done = {row["student_id"]: row for row in results_of(assignment_id)}
    out = []
    for student in students:
        result = done.get(student["id"])
        percent = round(result["score"] / result["max_score"] * 100) if result and result["max_score"] else None
        out.append({
            "student": student,
            "result": result,
            "percent": percent,
            "grade": grade_for_percent(percent) if percent is not None else None,
        })
    return out


def grade_for_percent(percent: int) -> int:
    """Оценка по белорусской 10-балльной шкале."""
    if percent >= 90:
        return 10
    if percent >= 80:
        return 9
    if percent >= 70:
        return 8
    if percent >= 60:
        return 7
    if percent >= 50:
        return 6
    if percent >= 40:
        return 5
    if percent >= 30:
        return 4
    if percent >= 20:
        return 3
    if percent >= 10:
        return 2
    return 1


def check_assignment_answers(tasks: list[dict[str, Any]], given: list[str]) -> tuple[int, list[dict[str, Any]]]:
    """Проверить ответы, вернуть (балл, детали)."""
    score = 0
    details = []
    for index, task in enumerate(tasks):
        answer = given[index] if index < len(given) else ""
        correct, expected = check_answer(answer, task)
        if correct:
            score += task.get("points", 1)
        details.append({
            "question": task["question"],
            "given": answer,
            "answer": expected,
            "correct": correct,
            "solution": task.get("solution", ""),
        })
    return score, details
