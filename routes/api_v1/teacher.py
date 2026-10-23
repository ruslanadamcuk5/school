"""API: кабинет учителя — классы, ученики, расписание, сводка."""
from __future__ import annotations

from flask import jsonify, request

from database import execute, query_all, query_one
from services import assignments as assignments_service
from services import auth as auth_service
from services import library as library_service
from services import orgs
from services import progress as progress_service

from . import bp
from .deps import current_user, fail, json_body, require_user, row_dict

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _learner_of(user_id: int):
    return query_one(
        """SELECT l.* FROM learner_accounts la
             JOIN learners l ON l.id = la.learner_id
            WHERE la.user_id = ?""",
        (user_id,),
    )


def _student_card(student) -> dict:
    data = row_dict(student)
    learner = _learner_of(int(student["id"]))
    if learner is None:
        data["learner"] = None
        data["stats"] = None
        return data
    stats = progress_service.learner_stats(int(learner["id"])) or {}
    data["learner"] = {
        "id": learner["id"],
        "name": learner["name"],
        "avatar": learner["avatar"],
        "grade": learner["grade"],
    }
    data["stats"] = {
        "level": stats.get("level", 1),
        "xp": stats.get("xp", 0),
        "coins": stats.get("coins", 0),
        "stars": stats.get("topics_three_stars", 0),
        "accuracy": stats.get("accuracy", 0),
        "attempts": stats.get("total_attempts", 0),
        "streak_days": stats.get("streak_days", 0),
    }
    return data


def _teacher_students(user) -> list:
    if user["role"] == auth_service.ROLE_ADMIN:
        return query_all(
            """SELECT DISTINCT u.id, u.first_name, u.last_name, u.login,
                      sc.id AS class_id, sc.grade, sc.letter
                 FROM users u
                 JOIN class_students cs ON cs.student_id = u.id
                 JOIN school_classes sc ON sc.id = cs.class_id
                WHERE u.role = 'student' AND u.is_active = 1
                ORDER BY sc.grade, sc.letter, u.last_name, u.first_name"""
        )
    return library_service.teacher_students(int(user["id"]))


def _teacher_classes(user) -> list:
    if user["role"] == auth_service.ROLE_ADMIN:
        return orgs.list_classes()
    return orgs.classes_of_teacher(int(user["id"]))


def _class_owned(user, class_id: int):
    for klass in _teacher_classes(user):
        if int(klass["id"]) == class_id:
            return klass
    return None


@bp.get("/teacher/dashboard")
@require_user("teacher", "admin")
def teacher_dashboard():
    user = current_user()
    classes = _teacher_classes(user)
    students = _teacher_students(user)
    assignments = assignments_service.list_assignments(
        teacher_id=None if user["role"] == auth_service.ROLE_ADMIN else int(user["id"])
    )
    library_stats = (
        {"books": 0, "classes": 0, "recommendations": 0}
        if user["role"] == auth_service.ROLE_ADMIN
        else library_service.teacher_stats(int(user["id"]))
    )
    open_assignments = sum(
        1 for item in assignments if item["status"] == "опубликована"
    )
    return jsonify(
        {
            "ok": True,
            "stats": {
                "classes": len(classes),
                "students": len({int(student["id"]) for student in students}),
                "assignments": len(assignments),
                "open_assignments": open_assignments,
                "books": library_stats.get("books", 0),
                "recommendations": library_stats.get("recommendations", 0),
            },
            "classes": [row_dict(klass) for klass in classes],
            "recent_assignments": [row_dict(item) for item in assignments[:6]],
            "students": [_student_card(student) for student in students[:12]],
        }
    )


@bp.get("/teacher/classes")
@require_user("teacher", "admin")
def classes():
    user = current_user()
    students = _teacher_students(user)
    counts: dict[int, int] = {}
    for student in students:
        counts[int(student["class_id"])] = counts.get(int(student["class_id"]), 0) + 1
    items = []
    for klass in _teacher_classes(user):
        data = row_dict(klass)
        data["students_count"] = counts.get(int(klass["id"]), 0)
        data["title"] = orgs.class_title(klass)
        items.append(data)
    return jsonify({"ok": True, "classes": items})


@bp.get("/teacher/classes/<int:class_id>")
@require_user("teacher", "admin")
def class_detail(class_id: int):
    user = current_user()
    klass = _class_owned(user, class_id)
    if klass is None:
        fail(404, "not_found", "Класс не найден")
    students = [
        _student_card(student)
        for student in _teacher_students(user)
        if int(student["class_id"]) == class_id
    ]
    assignments = [
        row_dict(item)
        for item in assignments_service.list_assignments(
            teacher_id=None if user["role"] == auth_service.ROLE_ADMIN else int(user["id"]),
            class_id=class_id,
        )
    ]
    return jsonify(
        {
            "ok": True,
            "class": {**row_dict(klass), "title": orgs.class_title(klass)},
            "students": students,
            "assignments": assignments,
            "schedule": [row_dict(row) for row in orgs.list_schedule(class_id)],
        }
    )


@bp.get("/teacher/students")
@require_user("teacher", "admin")
def students():
    user = current_user()
    return jsonify(
        {
            "ok": True,
            "students": [
                _student_card(student) for student in _teacher_students(user)
            ],
        }
    )


@bp.get("/teacher/students/<int:student_id>")
@require_user("teacher", "admin")
def student_detail(student_id: int):
    user = current_user()
    allowed = {int(student["id"]) for student in _teacher_students(user)}
    if student_id not in allowed:
        fail(404, "not_found", "Ученик не найден в ваших классах")

    student = query_one("SELECT * FROM users WHERE id = ?", (student_id,))
    if student is None:
        fail(404, "not_found", "Ученик не найден")
    learner = _learner_of(student_id)
    stats = (
        progress_service.learner_stats(int(learner["id"])) if learner else {}
    )
    topic_rows = (
        query_all(
            "SELECT * FROM topic_progress WHERE learner_id = ? ORDER BY attempts DESC",
            (learner["id"],),
        )
        if learner
        else []
    )
    results = query_all(
        """SELECT r.*, a.title
             FROM assignment_results r
             JOIN assignments a ON a.id = r.assignment_id
            WHERE r.student_id = ? AND a.teacher_id = ?
            ORDER BY r.completed_at DESC""",
        (student_id, int(user["id"])),
    )
    return jsonify(
        {
            "ok": True,
            "student": row_dict(student, exclude={"password_hash"}),
            "learner": row_dict(learner) if learner else None,
            "classes": [row_dict(klass) for klass in orgs.classes_of_student(student_id)],
            "stats": stats,
            "topics": [
                {
                    "slug": row["topic_slug"],
                    "stars": row["stars"],
                    "attempts": row["attempts"],
                    "correct": row["correct"],
                    "boss_cleared": bool(row["boss_cleared"]),
                }
                for row in topic_rows
            ],
            "weekly": progress_service.weekly_activity(int(learner["id"]))
            if learner
            else [],
            "results": [
                {
                    "assignment_id": row["assignment_id"],
                    "title": row["title"],
                    "score": row["score"],
                    "max_score": row["max_score"],
                    "completed_at": row["completed_at"],
                }
                for row in results
            ],
        }
    )


# ------------------------------------------------------------------ расписание
@bp.get("/teacher/schedule")
@require_user("teacher", "admin")
def teacher_schedule():
    user = current_user()
    class_id = request.args.get("class_id", type=int)
    if class_id:
        klass = _class_owned(user, class_id)
        if klass is None:
            fail(404, "not_found", "Класс не найден")
    else:
        classes = _teacher_classes(user)
        if not classes:
            return jsonify({"ok": True, "class_id": None, "schedule": []})
        class_id = int(classes[0]["id"])
    return jsonify(
        {
            "ok": True,
            "class_id": class_id,
            "weekdays": WEEKDAYS,
            "schedule": [row_dict(row) for row in orgs.list_schedule(class_id)],
        }
    )


@bp.post("/teacher/schedule")
@require_user("teacher", "admin")
def save_schedule():
    user = current_user()
    data = json_body()
    try:
        class_id = int(data.get("class_id"))
        weekday = int(data.get("weekday"))
        lesson_no = int(data.get("lesson_no"))
    except (TypeError, ValueError):
        fail(400, "bad_parameter", "Нужны class_id, weekday и lesson_no")
    if _class_owned(user, class_id) is None:
        fail(403, "forbidden", "Класс не ваш")
    if not 0 <= weekday <= 6:
        fail(400, "bad_weekday", "День недели — от 0 (Пн) до 6 (Вс)")
    if not 1 <= lesson_no <= 12:
        fail(400, "bad_lesson", "Номер урока — от 1 до 12")

    execute(
        "DELETE FROM schedules WHERE class_id = ? AND weekday = ? AND lesson_no = ?",
        (class_id, weekday, lesson_no),
    )
    orgs.save_schedule_item(
        class_id=class_id,
        weekday=weekday,
        lesson_no=lesson_no,
        subject_id=_optional_int(data.get("subject_id")),
        teacher_id=int(user["id"]),
        time_start=str(data.get("time_start") or ""),
        time_end=str(data.get("time_end") or ""),
        topic_slug=str(data.get("topic_slug") or ""),
        note=str(data.get("note") or ""),
    )
    return jsonify(
        {
            "ok": True,
            "class_id": class_id,
            "weekdays": WEEKDAYS,
            "schedule": [row_dict(row) for row in orgs.list_schedule(class_id)],
        }
    )


@bp.delete("/teacher/schedule/<int:item_id>")
@require_user("teacher", "admin")
def delete_schedule(item_id: int):
    user = current_user()
    row = query_one(
        """SELECT sc.id, sc.class_id FROM schedules sc
             JOIN school_classes c ON c.id = sc.class_id
            WHERE sc.id = ?""",
        (item_id,),
    )
    if row is None:
        fail(404, "not_found", "Урок не найден")
    if _class_owned(user, int(row["class_id"])) is None:
        fail(403, "forbidden", "Класс не ваш")
    orgs.delete_schedule_item(item_id)
    return jsonify({"ok": True})


@bp.get("/schedule")
@require_user("student")
def student_schedule():
    user = current_user()
    return jsonify(
        {
            "ok": True,
            "weekdays": WEEKDAYS,
            "schedule": [
                row_dict(row) for row in orgs.schedule_for_student(int(user["id"]))
            ],
        }
    )


def _optional_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
