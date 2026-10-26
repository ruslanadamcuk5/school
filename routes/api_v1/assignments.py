"""API: работы (задания) — ученик, учитель, родитель."""
from __future__ import annotations

import json

from flask import jsonify, request

from database import execute, query_one
from services import assignments as assignments_service
from services import auth as auth_service
from services import orgs
from services import topics as topics_service

from . import bp
from .deps import (
    current_user,
    fail,
    json_body,
    require_user,
    row_dict,
    user_payload,
)

MAX_QUESTIONS = 40
STUDENT_ROLE = "student"


# ------------------------------------------------------------------ helpers
def _result_summary(result) -> dict | None:
    if result is None:
        return None
    max_score = result["max_score"] or 0
    percent = round(result["score"] / max_score * 100) if max_score else 0
    return {
        "score": result["score"],
        "max_score": max_score,
        "percent": percent,
        "grade": assignments_service.grade_for_percent(percent),
        "completed_at": result["completed_at"],
        "duration_sec": result["duration_sec"],
    }


def _can_open(user, assignment) -> bool:
    if assignment["status"] != "опубликована":
        return False
    if assignment["student_id"]:
        return int(assignment["student_id"]) == int(user["id"])
    if assignment["class_id"]:
        classes = orgs.classes_of_student(user["id"])
        return int(assignment["class_id"]) in [int(klass["id"]) for klass in classes]
    return False


def _public_questions(tasks: list[dict]) -> list[dict]:
    out = []
    for index, task in enumerate(tasks):
        choices = task.get("choices") or []
        out.append(
            {
                "index": index,
                "question": task.get("question", ""),
                "answer_type": task.get("answer_type")
                or ("choice" if choices else "text"),
                "choices": choices,
                "points": task.get("points", 1),
            }
        )
    return out


def _teacher_owns(user, assignment) -> bool:
    if user["role"] == auth_service.ROLE_ADMIN:
        return True
    return int(assignment["teacher_id"] or 0) == int(user["id"])


# ------------------------------------------------------------------ ученик
@bp.get("/assignments")
@require_user(STUDENT_ROLE)
def student_assignments():
    user = current_user()
    rows = assignments_service.list_assignments(
        student_id=user["id"], status="опубликована"
    )
    result = []
    for row in rows:
        item = row_dict(row)
        item["result"] = _result_summary(
            assignments_service.get_result(row["id"], user["id"])
        )
        result.append(item)
    return jsonify({"ok": True, "assignments": result})


@bp.get("/assignments/<int:assignment_id>")
@require_user(STUDENT_ROLE)
def student_assignment(assignment_id: int):
    user = current_user()
    assignment = assignments_service.get_assignment(assignment_id)
    if assignment is None:
        fail(404, "not_found", "Работа не найдена")
    if not _can_open(user, assignment):
        fail(403, "forbidden", "Работа недоступна")

    result = assignments_service.get_result(assignment_id, user["id"])
    if result is not None:
        return jsonify(
            {
                "ok": True,
                "assignment": row_dict(assignment),
                "submitted": True,
                "result": _result_summary(result),
                "details": json.loads(result["answers"] or "[]"),
                "questions": [],
            }
        )

    tasks = assignments_service.assignment_tasks(assignment)
    return jsonify(
        {
            "ok": True,
            "assignment": row_dict(assignment),
            "submitted": False,
            "result": None,
            "questions": _public_questions(tasks),
        }
    )


@bp.post("/assignments/<int:assignment_id>/submit")
@require_user(STUDENT_ROLE)
def student_submit(assignment_id: int):
    user = current_user()
    assignment = assignments_service.get_assignment(assignment_id)
    if assignment is None:
        fail(404, "not_found", "Работа не найдена")
    if not _can_open(user, assignment):
        fail(403, "forbidden", "Работа недоступна")

    tasks = assignments_service.assignment_tasks(assignment)
    data = json_body()
    raw = data.get("answers")
    answers: list[str] = []
    if isinstance(raw, list):
        answers = [str(value or "") for value in raw]
    elif isinstance(raw, dict):
        answers = [str(raw.get(str(i), "")) for i in range(len(tasks))]
    else:
        fail(400, "bad_answers", "Передайте ответы списком")

    score, details = assignments_service.check_assignment_answers(tasks, answers)
    duration = int(data.get("duration_sec") or data.get("duration") or 0)
    assignments_service.save_result(
        assignment_id, user["id"], score, len(tasks), details, duration
    )
    result = assignments_service.get_result(assignment_id, user["id"])
    return jsonify(
        {
            "ok": True,
            "score": score,
            "max_score": len(tasks),
            "result": _result_summary(result),
            "details": details,
        }
    )


@bp.post("/assignments/<int:assignment_id>/retry")
@require_user(STUDENT_ROLE)
def student_retry(assignment_id: int):
    user = current_user()
    assignment = assignments_service.get_assignment(assignment_id)
    if assignment is None:
        fail(404, "not_found", "Работа не найдена")
    if not _can_open(user, assignment):
        fail(403, "forbidden", "Работа недоступна")
    execute(
        "DELETE FROM assignment_results WHERE assignment_id = ? AND student_id = ?",
        (assignment_id, user["id"]),
    )
    return jsonify({"ok": True})


@bp.get("/assignments/<int:assignment_id>/result")
@require_user(STUDENT_ROLE)
def student_result(assignment_id: int):
    user = current_user()
    assignment = assignments_service.get_assignment(assignment_id)
    if assignment is None:
        fail(404, "not_found", "Работа не найдена")
    if not _can_open(user, assignment):
        fail(403, "forbidden", "Работа недоступна")
    result = assignments_service.get_result(assignment_id, user["id"])
    if result is None:
        fail(404, "not_submitted", "Работа ещё не отправлена")
    return jsonify(
        {
            "ok": True,
            "assignment": row_dict(assignment),
            "result": _result_summary(result),
            "details": json.loads(result["answers"] or "[]"),
        }
    )


# ------------------------------------------------------------------ учитель
@bp.get("/teacher/assignments")
@require_user("teacher", "admin")
def teacher_assignments():
    user = current_user()
    teacher_id = None if user["role"] == auth_service.ROLE_ADMIN else user["id"]
    rows = assignments_service.list_assignments(teacher_id=teacher_id)
    return jsonify(
        {"ok": True, "assignments": [row_dict(row) for row in rows]}
    )


@bp.post("/teacher/assignments")
@require_user("teacher", "admin")
def teacher_create():
    user = current_user()
    data = json_body()
    title = str(data.get("title") or "").strip()
    if not title:
        fail(400, "bad_title", "Введите название работы")

    class_id = _optional_int(data.get("class_id"))
    student_id = _optional_int(data.get("student_id"))
    subject_id = _optional_int(data.get("subject_id"))
    topic_slugs = _string_list(data.get("topic_slugs") or data.get("topics"))
    if not topic_slugs:
        fail(400, "no_topics", "Выберите хотя бы одну тему")
    count = _clamp(_optional_int(data.get("questions_count")) or 10, 1, MAX_QUESTIONS)

    allowed_classes = {
        int(klass["id"]) for klass in orgs.classes_of_teacher(user["id"])
    }
    if class_id and user["role"] != auth_service.ROLE_ADMIN:
        if class_id not in allowed_classes:
            fail(403, "forbidden", "Класс не ваш")
    if student_id and not class_id:
        if user["role"] != auth_service.ROLE_ADMIN:
            students = {int(row["id"]) for row in orgs.teacher_students(user["id"])}
            if student_id not in students:
                fail(403, "forbidden", "Ученик не из ваших классов")

    tasks = assignments_service.build_tasks(topic_slugs, count)
    if not tasks:
        fail(400, "no_tasks", "Не удалось подобрать задания по выбранным темам")

    assignment_id = assignments_service.create_assignment(
        title=title,
        kind=str(data.get("kind") or "проверочная"),
        description=str(data.get("description") or ""),
        subject_id=subject_id,
        class_id=class_id,
        teacher_id=user["id"],
        student_id=student_id,
        topic_slugs=topic_slugs,
        questions_count=count,
        time_limit=_optional_int(data.get("time_limit")) or 0,
        due_date=str(data.get("due_date") or ""),
        status=str(data.get("status") or "опубликована"),
        tasks=tasks,
    )
    assignment = assignments_service.get_assignment(assignment_id)
    return jsonify({"ok": True, "assignment": row_dict(assignment)}), 201


@bp.patch("/teacher/assignments/<int:assignment_id>")
@require_user("teacher", "admin")
def teacher_update(assignment_id: int):
    user = current_user()
    assignment = assignments_service.get_assignment(assignment_id)
    if assignment is None:
        fail(404, "not_found", "Работа не найдена")
    if not _teacher_owns(user, assignment):
        fail(403, "forbidden", "Это не ваша работа")

    data = json_body()
    fields = {}
    for key in (
        "title",
        "kind",
        "description",
        "subject_id",
        "class_id",
        "student_id",
        "time_limit",
        "due_date",
        "status",
    ):
        if key in data:
            fields[key] = data[key]
    if "topic_slugs" in data or "topics" in data:
        slugs = _string_list(data.get("topic_slugs") or data.get("topics"))
        if not slugs:
            fail(400, "no_topics", "Выберите хотя бы одну тему")
        fields["topic_slugs"] = slugs
    assignments_service.update_assignment(assignment_id, **fields)
    if "topic_slugs" in fields:
        assignments_service.regenerate_tasks(assignment_id)

    return jsonify(
        {"ok": True, "assignment": row_dict(assignments_service.get_assignment(assignment_id))}
    )


@bp.post("/teacher/assignments/<int:assignment_id>/publish")
@require_user("teacher", "admin")
def teacher_publish(assignment_id: int):
    user = current_user()
    assignment = assignments_service.get_assignment(assignment_id)
    if assignment is None:
        fail(404, "not_found", "Работа не найдена")
    if not _teacher_owns(user, assignment):
        fail(403, "forbidden", "Это не ваша работа")
    assignments_service.publish_assignment(assignment_id)
    return jsonify({"ok": True})


@bp.post("/teacher/assignments/<int:assignment_id>/close")
@require_user("teacher", "admin")
def teacher_close(assignment_id: int):
    user = current_user()
    assignment = assignments_service.get_assignment(assignment_id)
    if assignment is None:
        fail(404, "not_found", "Работа не найдена")
    if not _teacher_owns(user, assignment):
        fail(403, "forbidden", "Это не ваша работа")
    assignments_service.close_assignment(assignment_id)
    return jsonify({"ok": True})


@bp.delete("/teacher/assignments/<int:assignment_id>")
@require_user("teacher", "admin")
def teacher_delete(assignment_id: int):
    user = current_user()
    assignment = assignments_service.get_assignment(assignment_id)
    if assignment is None:
        fail(404, "not_found", "Работа не найдена")
    if not _teacher_owns(user, assignment):
        fail(403, "forbidden", "Это не ваша работа")
    assignments_service.delete_assignment(assignment_id)
    return jsonify({"ok": True})


@bp.get("/teacher/assignments/<int:assignment_id>/results")
@require_user("teacher", "admin")
def teacher_results(assignment_id: int):
    user = current_user()
    assignment = assignments_service.get_assignment(assignment_id)
    if assignment is None:
        fail(404, "not_found", "Работа не найдена")
    if not _teacher_owns(user, assignment):
        fail(403, "forbidden", "Это не ваша работа")
    rows = assignments_service.results_with_students(assignment_id)
    return jsonify(
        {
            "ok": True,
            "assignment": row_dict(assignment),
            "results": [
                {
                    "student": user_payload(item.get("student")),
                    "result": row_dict(item.get("result")),
                    "percent": item.get("percent"),
                    "grade": item.get("grade"),
                }
                for item in rows
            ],
        }
    )


# ------------------------------------------------------------------ родитель
@bp.get("/parent/assignments")
@require_user("parent")
def parent_assignments():
    user = current_user()
    rows = assignments_service.list_assignments(teacher_id=user["id"])
    out = []
    for row in rows:
        item = row_dict(row)
        results = assignments_service.results_of(row["id"])
        item["results"] = [
            {
                "student_id": result["student_id"],
                "score": result["score"],
                "max_score": result["max_score"],
                "completed_at": result["completed_at"],
            }
            for result in results
        ]
        out.append(item)
    return jsonify({"ok": True, "assignments": out})


@bp.post("/parent/assignments")
@require_user("parent")
def parent_create():
    user = current_user()
    data = json_body()
    children = [
        child for child in auth_service.children_of(user["id"])
        if child["role"] == STUDENT_ROLE
    ]
    if not children:
        fail(409, "no_children", "Сначала привяжите аккаунт ребёнка на сайте")
    child_ids = {int(value) for value in _int_list(data.get("child_ids"))}
    chosen = [child for child in children if int(child["id"]) in child_ids] or children
    if not chosen:
        fail(400, "no_children", "Выберите ребёнка")

    topic_slugs = _string_list(data.get("topic_slugs") or data.get("topics"))
    if not topic_slugs:
        fail(400, "no_topics", "Выберите хотя бы одну тему")
    subject_id = _optional_int(data.get("subject_id"))
    count = _clamp(_optional_int(data.get("questions_count")) or 10, 1, MAX_QUESTIONS)
    title = str(data.get("title") or "").strip() or "Домашнее задание от родителя"
    all_topics = topics_service.list_topics()

    created = 0
    for child in chosen:
        classes = orgs.classes_of_student(child["id"])
        grade = classes[0]["grade"] if classes else 3
        child_topics = [
            topic["slug"]
            for topic in all_topics
            if topic["slug"] in topic_slugs
            and topic["grade"] == grade
            and (not subject_id or topic["subject_id"] == subject_id)
        ]
        if not child_topics:
            continue
        tasks = assignments_service.build_tasks(child_topics, count)
        if not tasks:
            continue
        child_subject = subject_id
        if not child_subject:
            first = next(
                (topic for topic in all_topics if topic["slug"] == child_topics[0]), None
            )
            child_subject = first["subject_id"] if first else None
        assignments_service.create_assignment(
            title=title,
            kind=str(data.get("kind") or "домашняя"),
            description=str(data.get("description") or ""),
            subject_id=child_subject,
            student_id=child["id"],
            teacher_id=user["id"],
            topic_slugs=child_topics,
            questions_count=count,
            time_limit=_optional_int(data.get("time_limit")) or 0,
            due_date=str(data.get("due_date") or ""),
            status="опубликована",
            tasks=tasks,
        )
        created += 1

    if not created:
        fail(
            400,
            "no_tasks",
            "Не удалось подобрать темы для класса ребёнка. Выберите темы нужного класса.",
        )
    return jsonify({"ok": True, "created": created}), 201


# ------------------------------------------------------------------ утилиты
def _optional_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(400, "bad_parameter", "Ожидалось число")


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _string_list(value) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _int_list(value) -> list[int]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out
