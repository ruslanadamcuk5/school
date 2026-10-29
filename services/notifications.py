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
import time
from datetime import date, datetime, timedelta

from database import execute, query_all, query_one

KIND_NEW = "assignment_new"
KIND_DONE = "assignment_done"
KIND_MISSED = "assignment_missed"
KIND_DEADLINE = "assignment_deadline"
KIND_MESSAGE = "message"
KIND_REMINDER = "reminder"
KIND_LIBRARY_NEW = "library_new"
KIND_LIBRARY_READ = "library_unread"

ROLE_LABEL = {
    "teacher": "учителя",
    "parent": "родителя",
    "admin": "администратора",
}


# ------------------------------------------------------------------ создание
def dedup(kind: str, user_id: int, assignment_id: int = 0, student_id: int = 0) -> str:
    """Ключ дедупликации для событий «одно на человека»."""
    return f"{kind}:{int(user_id)}:{int(assignment_id or 0)}:{int(student_id or 0)}"


def push(
    user_id: int,
    kind: str,
    title: str,
    body: str,
    assignment_id: int = 0,
    student_id: int = 0,
    *,
    class_id: int = 0,
    sender_id: int = 0,
    link: str = "",
    dedup_key: str = "",
    learner_id: int = 0,
) -> None:
    """Создать уведомление.

    ``user_id`` — аккаунт, ``learner_id`` — семейный профиль без аккаунта
    (тогда ``user_id=0``). ``dedup_key`` защищает от повторов одного события;
    произвольные сообщения ключа не передают — каждое из них уникально.
    """
    if not user_id and not learner_id:
        return
    key = (dedup_key or "")[:200]
    if not key:
        key = f"{kind}:{int(user_id)}:{int(learner_id)}:{time.time_ns()}"
    execute(
        """INSERT OR IGNORE INTO app_notifications
           (user_id, kind, title, body, assignment_id, student_id,
            learner_id, class_id, sender_id, link, dedup_key)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            int(user_id) if user_id else None,
            kind,
            title.strip()[:200],
            body.strip(),
            int(assignment_id or 0),
            int(student_id or 0),
            int(learner_id or 0),
            int(class_id or 0),
            int(sender_id or 0),
            (link or "")[:500],
            key,
        ),
    )


def title_for_sender(sender: sqlite3.Row | None) -> str:
    """«Сообщение от родителя Ивана» — подпись для произвольных сообщений."""
    role = (sender["role"] if sender else "") or "teacher"
    role_label = ROLE_LABEL.get(role, "школы")
    return f"Сообщение от {role_label}"


def send_message(
    sender: sqlite3.Row | None,
    recipient_ids: list[int] | set[int],
    text: str,
    *,
    kind: str = KIND_MESSAGE,
    title: str = "",
    index_link: str = "",
    student_id: int = 0,
    class_id: int = 0,
    learner_ids: list[int] | set[int] = (),
) -> int:
    """Отправить произвольное сообщение (или напоминание) списку получателей.

    ``recipient_ids`` — аккаунты, ``learner_ids`` — семейные профили без
    аккаунта (им уведомление кладётся по learner_id).
    """
    text = (text or "").strip()
    if not text or (not recipient_ids and not learner_ids):
        return 0
    sender_id = int(sender["id"]) if sender is not None else 0
    name = _full_name(sender) if sender is not None else ""
    head = title.strip() or title_for_sender(sender)
    if name:
        head = f"{head} ({name})"
    sent = 0
    for user_id in {int(uid) for uid in recipient_ids if uid}:
        if user_id == sender_id:
            continue
        push(
            user_id,
            kind,
            head,
            text[:2000],
            student_id=student_id,
            class_id=class_id,
            sender_id=sender_id,
            link=index_link,
        )
        sent += 1
    for learner_id in {int(lid) for lid in learner_ids if lid}:
        push(
            0,
            kind,
            head,
            text[:2000],
            student_id=student_id,
            class_id=class_id,
            sender_id=sender_id,
            link=index_link,
            learner_id=learner_id,
        )
        sent += 1
    return sent


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
        push(
            int(student["id"]),
            KIND_NEW,
            title,
            body,
            assignment_id,
            int(student["id"]),
            class_id=int(assignment["class_id"] or 0),
            sender_id=int(author["id"]) if author is not None else 0,
            link=f"/student/works/{assignment_id}",
            dedup_key=dedup(KIND_NEW, int(student["id"]), assignment_id, int(student["id"])),
        )
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
                class_id=int(assignment["class_id"] or 0),
                sender_id=int(author["id"]) if author is not None else 0,
                link=f"/student/works/{assignment_id}",
                dedup_key=dedup(KIND_NEW, int(parent["id"]), assignment_id, int(student["id"])),
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
        push(
            user_id,
            KIND_DONE,
            title,
            body,
            assignment_id,
            int(student_id),
            class_id=int(assignment["class_id"] or 0),
            sender_id=int(student_id),
            link=f"/teacher/works/{assignment_id}",
            dedup_key=dedup(KIND_DONE, user_id, assignment_id, int(student_id)),
        )


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
    push(
        int(student_id),
        KIND_MISSED,
        title,
        body,
        assignment_id,
        int(student_id),
        class_id=int(assignment["class_id"] or 0),
        sender_id=int(assignment["teacher_id"] or 0),
        link=f"/student/works/{assignment_id}",
        dedup_key=dedup(KIND_MISSED, int(student_id), assignment_id, int(student_id)),
    )
    for parent in _parents_of(int(student_id)):
        push(
            int(parent["id"]),
            KIND_MISSED,
            f"{student_name}: задание просрочено",
            body,
            assignment_id,
            int(student_id),
            class_id=int(assignment["class_id"] or 0),
            sender_id=int(assignment["teacher_id"] or 0),
            link="/parent/assignments",
            dedup_key=dedup(KIND_MISSED, int(parent["id"]), assignment_id, int(student_id)),
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
            class_id=int(assignment["class_id"] or 0),
            sender_id=int(student_id),
            link=f"/teacher/works/{assignment_id}",
            dedup_key=dedup(KIND_MISSED, int(author["id"]), assignment_id, int(student_id)),
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
def _exists(key: str) -> bool:
    row = query_one("SELECT 1 FROM app_notifications WHERE dedup_key = ?", (key,))
    return row is not None


def _due_dt(value: str) -> datetime | None:
    """Разобрать срок сдачи: дата (конец дня) или дата со временем."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        if len(value) <= 10:
            day = date.fromisoformat(value[:10])
            return datetime(day.year, day.month, day.day, 23, 59)
        return datetime.fromisoformat(value.replace("Z", "")[:19])
    except ValueError:
        return None


def sync_deadlines(hours: int = 24) -> int:
    """Напомнить о приближающемся сроке сдачи (по умолчанию — за сутки)."""
    now = datetime.now()
    limit = timedelta(hours=hours)
    created = 0
    assignments = query_all(
        "SELECT * FROM assignments WHERE status = 'опубликована' AND id > 0"
    )
    for assignment in assignments:
        due = _due_dt(assignment["due_date"])
        if due is None:
            continue
        left = due - now
        if not (timedelta(0) < left <= limit):
            continue
        hours_left = max(1, round(left.total_seconds() / 3600))
        for student in _assignment_students(assignment):
            student_id = int(student["id"])
            result = query_one(
                "SELECT 1 FROM assignment_results WHERE assignment_id = ? AND student_id = ?",
                (assignment["id"], student_id),
            )
            if result is not None:
                continue
            key = dedup(KIND_DEADLINE, student_id, int(assignment["id"]), student_id)
            if _exists(key):
                continue
            body = (
                f"«{assignment['title']}» нужно сдать до {assignment['due_date']}. "
                f"Осталось около {hours_left} ч."
            )
            created += 1
            push(
                student_id,
                KIND_DEADLINE,
                "Скоро срок сдачи",
                body,
                int(assignment["id"]),
                student_id,
                class_id=int(assignment["class_id"] or 0),
                sender_id=int(assignment["teacher_id"] or 0),
                link=f"/student/works/{assignment['id']}",
                dedup_key=key,
            )
            for parent in _parents_of(student_id):
                push(
                    int(parent["id"]),
                    KIND_DEADLINE,
                    f"{_full_name(student)}: срок сдачи близко",
                    body,
                    int(assignment["id"]),
                    student_id,
                    class_id=int(assignment["class_id"] or 0),
                    sender_id=int(assignment["teacher_id"] or 0),
                    link="/parent/assignments",
                    dedup_key=dedup(KIND_DEADLINE, int(parent["id"]), int(assignment["id"]), student_id),
                )
    return created


_last_sync = 0.0
SYNC_INTERVAL = 300  # секунд между фоновыми проверками сроков


def sync_due(force: bool = False) -> int:
    """Проверить сроки (просрочено + скоро) не чаще раза в 5 минут.

    Вызывается из запросов, поэтому отдельный планировщик на сервере не нужен.
    """
    global _last_sync
    now = time.time()
    if not force and now - _last_sync < SYNC_INTERVAL:
        return 0
    _last_sync = now
    total = 0
    try:
        total += sync_missed() + sync_deadlines()
    except Exception:  # pragma: no cover - уведомления не должны ломать запросы
        pass
    try:
        from services import library as library_service

        total += library_service.sync_library_unread()
    except Exception:  # pragma: no cover
        pass
    return total


def list_for_user(user_id: int, limit: int = 50) -> list[sqlite3.Row]:
    return query_all(
        """SELECT * FROM app_notifications
            WHERE user_id = ?
            ORDER BY is_read ASC, created_at DESC, id DESC
            LIMIT ?""",
        (int(user_id), max(1, min(200, limit))),
    )


def list_for_learner(learner_id: int, limit: int = 50) -> list[sqlite3.Row]:
    return query_all(
        """SELECT * FROM app_notifications
            WHERE learner_id = ?
            ORDER BY is_read ASC, created_at DESC, id DESC
            LIMIT ?""",
        (int(learner_id), max(1, min(200, limit))),
    )


def unread_count_for_learner(learner_id: int) -> int:
    row = query_one(
        "SELECT COUNT(*) AS n FROM app_notifications "
        "WHERE learner_id = ? AND is_read = 0",
        (int(learner_id),),
    )
    return int(row["n"]) if row else 0


def mark_read_for_learner(learner_id: int, notification_id: int) -> None:
    execute(
        """UPDATE app_notifications
              SET is_read = 1, read_at = coalesce(read_at, datetime('now'))
            WHERE id = ? AND learner_id = ?""",
        (int(notification_id), int(learner_id)),
    )


def mark_all_read_for_learner(learner_id: int) -> None:
    execute(
        """UPDATE app_notifications
              SET is_read = 1, read_at = coalesce(read_at, datetime('now'))
            WHERE learner_id = ?""",
        (int(learner_id),),
    )


def unread_count(user_id: int) -> int:
    row = query_one(
        "SELECT COUNT(*) AS n FROM app_notifications WHERE user_id = ? AND is_read = 0",
        (int(user_id),),
    )
    return int(row["n"]) if row else 0


def mark_read(user_id: int, notification_id: int) -> None:
    execute(
        """UPDATE app_notifications
              SET is_read = 1, read_at = coalesce(read_at, datetime('now'))
            WHERE id = ? AND user_id = ?""",
        (int(notification_id), int(user_id)),
    )


def mark_all_read(user_id: int) -> None:
    execute(
        """UPDATE app_notifications
              SET is_read = 1, read_at = coalesce(read_at, datetime('now'))
            WHERE user_id = ?""",
        (int(user_id),),
    )
