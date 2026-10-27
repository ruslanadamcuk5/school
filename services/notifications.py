"""Уведомления для учеников, родителей и учителей.

Уведомления хранятся на сервере и доставляются:

* в веб-кабинеты (страница «Уведомления» и счётчик в шапке);
* в Android-приложение — фоновый опрос ``GET /api/v1/notifications``
  (WorkManager) и системные уведомления Android.

Внешние push-сервисы (FCM и т.п.) не используются: платформа работает
без сторонних облачных зависимостей.
"""
from __future__ import annotations

import sqlite3
from datetime import date

from database import execute, query_all, query_one

KIND_NEW = "assignment_new"
KIND_DONE = "assignment_done"
KIND_MISSED = "assignment_missed"

ROLE_LABEL = {
    "teacher": "учителя",
    "parent": "родителя",
    "admin": "администратора",
}


# ------------------------------------------------------------------ создание
def push(
    user_id: int,
    kind: str,
    title: str,
    body: str,
    assignment_id: int = 0,
    student_id: int = 0,
) -> None:
    """Создать уведомление (повторы по тому же событию игнорируются)."""
    if not user_id:
        return
    execute(
        """INSERT OR IGNORE INTO app_notifications
           (user_id, kind, title, body, assignment_id, student_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (int(user_id), kind, title.strip(), body.strip(), int(assignment_id or 0),
         int(student_id or 0)),
    )


def _full_name(row: sqlite3.Row | None) -> str:
    if row is None:
        return "Ученик"
    name = " ".join(
        part for part in (row["first_name"] or "", row["last_name"] or "") if part
    ).strip()
    return name or "Ученик"


def _assignment_students(assignment: sqlite3.Row) -> list[sqlite3.Row]:
    if assignment["student_id"]:
        return query_all(
            "SELECT * FROM users WHERE id = ? AND role = 'student'",
            (assignment["student_id"],),
        )
    if assignment["class_id"]:
        return query_all(
            """SELECT u.* FROM class_students cs
                 JOIN users u ON u.id = cs.student_id
                WHERE cs.class_id = ? AND u.is_active = 1""",
            (assignment["class_id"],),
        )
    return []


def _parents_of(student_id: int) -> list[sqlite3.Row]:
    return query_all(
        """SELECT u.* FROM parent_children pc
             JOIN users u ON u.id = pc.parent_id
            WHERE pc.child_id = ? AND u.is_active = 1""",
        (student_id,),
    )


def _author(assignment: sqlite3.Row) -> sqlite3.Row | None:
    if not assignment["teacher_id"]:
        return None
    return query_one("SELECT * FROM users WHERE id = ?", (assignment["teacher_id"],))


def _due_text(assignment: sqlite3.Row) -> str:
    due = (assignment["due_date"] or "").strip()
    return f" Срок сдачи: {due}." if due else ""


def notify_published(assignment_id: int) -> None:
    """Разослать уведомления о новом задании ученикам и их родителям."""
    assignment = query_one("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
    if assignment is None or assignment["status"] != "опубликована":
        return
    author = _author(assignment)
    role = (assignment["author_role"] or (author["role"] if author else "teacher"))
    role_label = ROLE_LABEL.get(role, "учителя")
    author_name = _full_name(author) if author else "Школа"
    students = _assignment_students(assignment)
    for student in students:
        student_name = _full_name(student)
        title = "Новое задание"
        body = (
            f"«{assignment['title']}» — от {role_label} {author_name}. "
            f"Заданий: {assignment['questions_count']}.{_due_text(assignment)}"
        )
        push(int(student["id"]), KIND_NEW, title, body, assignment_id, int(student["id"]))
        for parent in _parents_of(int(student["id"])):
            if author is not None and int(parent["id"]) == int(author["id"]):
                continue
            push(
                int(parent["id"]),
                KIND_NEW,
                f"Задание для {student_name}",
                body,
                assignment_id,
                int(student["id"]),
            )


def notify_result(assignment_id: int, student_id: int, score: int, max_score: int) -> None:
    """Уведомить автора задания и родителей о выполненной работе."""
    assignment = query_one("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
    if assignment is None:
        return
    student = query_one("SELECT * FROM users WHERE id = ?", (student_id,))
    if student is None:
        return
    student_name = _full_name(student)
    percent = round(score / max_score * 100) if max_score else 0
    title = "Работа выполнена"
    body = (
        f"{student_name} выполнил(а) «{assignment['title']}»: "
        f"{score} из {max_score} ({percent}%)."
    )

    recipients: set[int] = set()
    author = _author(assignment)
    if author is not None:
        recipients.add(int(author["id"]))
    for parent in _parents_of(int(student_id)):
        recipients.add(int(parent["id"]))
    for user_id in recipients:
        if user_id == int(student_id):
            continue
        push(user_id, KIND_DONE, title, body, assignment_id, int(student_id))


def notify_missed(assignment_id: int, student_id: int) -> None:
    """Уведомить о пропущенном (просроченном) задании."""
    assignment = query_one("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
    student = query_one("SELECT * FROM users WHERE id = ?", (student_id,))
    if assignment is None or student is None:
        return
    student_name = _full_name(student)
    title = "Задание просрочено"
    body = (
        f"«{assignment['title']}» не выполнено. "
        f"Срок сдачи: {assignment['due_date'] or 'истёк'}."
    )
    push(int(student_id), KIND_MISSED, title, body, assignment_id, int(student_id))
    for parent in _parents_of(int(student_id)):
        push(
            int(parent["id"]),
            KIND_MISSED,
            f"{student_name}: задание просрочено",
            body,
            assignment_id,
            int(student_id),
        )
    author = _author(assignment)
    if author is not None and int(author["id"]) != int(student_id):
        push(
            int(author["id"]),
            KIND_MISSED,
            f"{student_name} не сдал(а) работу",
            body,
            assignment_id,
            int(student_id),
        )


def sync_missed(assignment_id: int | None = None) -> int:
    """Найти просроченные/закрытые работы без результата и создать уведомления.

    Вызывается при запросе списка уведомлений (веб и Android), поэтому
    отдельный планировщик на сервере не нужен.
    """
    today = date.today().isoformat()
    sql = """SELECT * FROM assignments
              WHERE status IN ('опубликована', 'закрыта')
                AND id > 0"""
    params: list = []
    if assignment_id is not None:
        sql += " AND id = ?"
        params.append(assignment_id)
    created = 0
    for assignment in query_all(sql, params):
        due = (assignment["due_date"] or "").strip()
        overdue = bool(due) and due[:10] < today
        closed = assignment["status"] == "закрыта"
        if not overdue and not closed:
            continue
        for student in _assignment_students(assignment):
            result = query_one(
                "SELECT 1 FROM assignment_results WHERE assignment_id = ? AND student_id = ?",
                (assignment["id"], student["id"]),
            )
            if result is not None:
                continue
            before = query_one(
                """SELECT 1 FROM app_notifications
                    WHERE user_id = ? AND kind = ? AND assignment_id = ? AND student_id = ?""",
                (student["id"], KIND_MISSED, assignment["id"], student["id"]),
            )
            if before is None:
                created += 1
            notify_missed(int(assignment["id"]), int(student["id"]))
    return created


# ------------------------------------------------------------------ чтение
def list_for_user(user_id: int, limit: int = 50) -> list[sqlite3.Row]:
    return query_all(
        """SELECT * FROM app_notifications
            WHERE user_id = ?
            ORDER BY is_read ASC, created_at DESC, id DESC
            LIMIT ?""",
        (int(user_id), max(1, min(200, limit))),
    )


def unread_count(user_id: int) -> int:
    row = query_one(
        "SELECT COUNT(*) AS n FROM app_notifications WHERE user_id = ? AND is_read = 0",
        (int(user_id),),
    )
    return int(row["n"]) if row else 0


def mark_read(user_id: int, notification_id: int) -> None:
    execute(
        "UPDATE app_notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
        (int(notification_id), int(user_id)),
    )


def mark_all_read(user_id: int) -> None:
    execute(
        "UPDATE app_notifications SET is_read = 1 WHERE user_id = ?",
        (int(user_id),),
    )
