"""API: работы (задания) — ученик, учитель, родитель."""
from __future__ import annotations

import json
from datetime import date

from flask import jsonify, request

from database import execute, query_one
from services import assignment_photos
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
AUTHOR_LABEL = {"teacher": "учителя", "parent": "родителя", "admin": "администратора"}


def _assignment_payload(row, *, include_reference: bool = False) -> dict:
    """Безопасное представление работы для мобильного клиента."""
    item = row_dict(row)
    item.pop("questions_json", None)
    if not include_reference:
        item.pop("reference_text", None)
        item.pop("audio_text", None)
    # SQLite хранит флаги как 0/1. Android-клиент ждёт настоящие boolean:
    # Gson не умеет читать число в поле Boolean и падает на разборе ответа.
    for field in ("allow_photo", "allow_text"):
        if field in item:
            item[field] = bool(item[field])
    item["task_type"] = item.get("task_type") or "test"
    role = item.get("author_role") or item.get("teacher_role") or "teacher"
    item["author_role"] = role
    item["author_label"] = AUTHOR_LABEL.get(role, "учителя")
    name = " ".join(
        part for part in (item.get("teacher_first") or "", item.get("teacher_last") or "")
        if part
    ).strip()
    if role == "parent":
        item["author_name"] = name or "Родитель"
    elif role == "admin":
        item["author_name"] = name or "Администрация школы"
    else:
        item["author_name"] = name or "Учитель"
    due = (item.get("due_date") or "").strip()
    item["overdue"] = bool(due) and due[:10] < date.today().isoformat()
    return item


def _details_of(result) -> list[dict]:
    if result is None:
        return []
    try:
        return json.loads(result["answers"] or "[]")
    except (ValueError, TypeError, KeyError):
        return []


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
        "submission_type": result["submission_type"] if "submission_type" in result.keys() else "inline",
        "ai_status": result["ai_status"] if "ai_status" in result.keys() else "not_requested",
        "ai_feedback": result["ai_feedback"] if "ai_feedback" in result.keys() else None,
        "ai_model": result["ai_model"] if "ai_model" in result.keys() else None,
        "ai_score": result["ai_score"] if "ai_score" in result.keys() else None,
        "photos": assignments_service.result_photos(result),
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
                "task_type": task.get("task_type")
                or ("read" if task.get("answer_type") == "read" else "test"),
                "choices": choices,
                "points": task.get("points", 1),
                # Для диктанта это текст, который читает синтезатор речи.
                # Для чтения — текст темы. Поле нужно и веб-, и Android-клиенту.
                "audio_text": task.get("audio_text") or "",
                "content_text": task.get("content_text") or "",
                "topic_slug": task.get("topic_slug") or "",
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
        item = _assignment_payload(row)
        saved = assignments_service.get_result(row["id"], user["id"])
        item["result"] = _result_summary(saved)
        item["missed"] = bool(item.get("overdue")) and saved is None
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
                "assignment": _assignment_payload(assignment),
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
            "assignment": _assignment_payload(assignment),
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
    if any(value.strip() for value in answers) and not assignment["allow_text"]:
        fail(403, "text_forbidden", "В этой работе нельзя отвечать текстом")

    duration = int(data.get("duration_sec") or data.get("duration") or 0)
    result = assignments_service.evaluate_submission(
        assignment, tasks, answers, [], user_id=user["id"]
    )
    assignments_service.save_result(
        assignment_id,
        user["id"],
        result["score"],
        result["max_score"],
        result["details"],
        duration,
        submission_type=result["submission_type"],
        photos=result["photos"],
        ai_status=result["ai_status"],
        ai_feedback=result["ai_feedback"],
        ai_model=result["ai_model"],
        ai_score=result["ai_score"],
    )
    saved = assignments_service.get_result(assignment_id, user["id"])
    return jsonify(
        {
            "ok": True,
            "score": result["score"],
            "max_score": result["max_score"],
            "result": _result_summary(saved),
            "details": result["details"],
        }
    )


@bp.post("/assignments/<int:assignment_id>/submit-photo")
@require_user(STUDENT_ROLE)
def student_submit_photo(assignment_id: int):
    """Сдать письменные ответы фотографией. Поле answers — JSON-массив."""
    user = current_user()
    assignment = assignments_service.get_assignment(assignment_id)
    if assignment is None:
        fail(404, "not_found", "Работа не найдена")
    if not _can_open(user, assignment):
        fail(403, "forbidden", "Работа недоступна")
    if not assignment["allow_photo"]:
        fail(403, "photo_forbidden", "В этой работе нельзя отвечать фотографией")
    tasks = assignments_service.assignment_tasks(assignment)
    raw = request.form.get("answers")
    answers: list[str] = []
    if raw:
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = None
        if isinstance(parsed, list):
            answers = [str(value or "") for value in parsed]
        elif isinstance(parsed, dict):
            answers = [str(parsed.get(str(i), "")) for i in range(len(tasks))]
    if len(answers) < len(tasks):
        answers.extend([""] * (len(tasks) - len(answers)))
    try:
        photos = assignment_photos.save_photos(
            request.files.getlist("photos"), assignment_id, user["id"]
        )
    except ValueError as exc:
        fail(400, "bad_photo", str(exc))
    if not photos:
        fail(400, "no_photos", "Прикрепите хотя бы одну фотографию ответа")
    duration = int(request.form.get("duration_sec") or request.form.get("duration") or 0)
    result = assignments_service.evaluate_submission(
        assignment, tasks, answers, photos, user_id=user["id"]
    )
    assignments_service.save_result(
        assignment_id,
        user["id"],
        result["score"],
        result["max_score"],
        result["details"],
        duration,
        submission_type=result["submission_type"],
        photos=result["photos"],
        ai_status=result["ai_status"],
        ai_feedback=result["ai_feedback"],
        ai_model=result["ai_model"],
        ai_score=result["ai_score"],
    )
    saved = assignments_service.get_result(assignment_id, user["id"])
    return jsonify(
        {
            "ok": True,
            "score": result["score"],
            "max_score": result["max_score"],
            "result": _result_summary(saved),
            "details": result["details"],
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
    old = assignments_service.get_result(assignment_id, user["id"])
    if old is not None:
        assignment_photos.delete_photos(assignments_service.result_photos(old))
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
            "assignment": _assignment_payload(assignment),
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
        {"ok": True, "assignments": [_assignment_payload(row) for row in rows]}
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
    task_type = str(data.get("task_type") or "test").strip()
    if task_type not in assignments_service.TASK_TYPES:
        task_type = "test"
    topic_slugs = _string_list(data.get("topic_slugs") or data.get("topics"))
    description = str(data.get("description") or "").strip()
    reference_text = str(data.get("reference_text") or "").strip()
    audio_text = str(data.get("audio_text") or "").strip()
    allow_photo = _bool_flag(data, "allow_photo")
    allow_text = _bool_flag(data, "allow_text")
    if not allow_photo and not allow_text:
        fail(400, "no_answer_mode", "Разрешите ответ текстом или фото")
    if task_type in ("test", "read") and not topic_slugs:
        fail(400, "no_topics", "Выберите хотя бы одну тему")
    if task_type == "read":
        topic_slugs = topic_slugs[:1]
    if task_type == "dictation" and not reference_text and not topic_slugs:
        fail(400, "no_dictation_text", "Вставьте текст диктанта или выберите тему")
    if task_type == "other" and not description:
        fail(400, "no_description", "Опишите задание")
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

    tasks = assignments_service.build_typed_tasks(
        task_type,
        topic_slugs,
        count,
        description=description,
        reference_text=reference_text,
        audio_text=audio_text,
    )
    if not tasks:
        fail(400, "no_tasks", "Не удалось подобрать задания по выбранным темам")

    assignment_id = assignments_service.create_assignment(
        title=title,
        kind=str(data.get("kind") or "проверочная"),
        description=description,
        subject_id=subject_id,
        class_id=class_id,
        teacher_id=user["id"],
        student_id=student_id,
        topic_slugs=topic_slugs,
        questions_count=len(tasks),
        time_limit=_optional_int(data.get("time_limit")) or 0,
        due_date=str(data.get("due_date") or ""),
        status=str(data.get("status") or "опубликована"),
        tasks=tasks,
        task_type=task_type,
        reference_text=reference_text,
        audio_text=audio_text,
        allow_photo=allow_photo,
        allow_text=allow_text,
    )
    assignment = assignments_service.get_assignment(assignment_id)
    return jsonify({"ok": True, "assignment": _assignment_payload(assignment)}), 201


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
        "task_type",
        "reference_text",
        "audio_text",
        "allow_photo",
        "allow_text",
    ):
        if key in data:
            fields[key] = data[key]
    if "topic_slugs" in data or "topics" in data:
        slugs = _string_list(data.get("topic_slugs") or data.get("topics"))
        if not slugs:
            fail(400, "no_topics", "Выберите хотя бы одну тему")
        fields["topic_slugs"] = slugs
    assignments_service.update_assignment(assignment_id, **fields)
    if any(
        key in fields
        for key in ("topic_slugs", "task_type", "reference_text", "description", "audio_text")
    ):
        assignments_service.regenerate_tasks(assignment_id)

    return jsonify(
        {"ok": True, "assignment": _assignment_payload(assignments_service.get_assignment(assignment_id))}
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
            "assignment": _assignment_payload(assignment),
            "results": [
                {
                    "student": user_payload(item.get("student")),
                    "result": row_dict(item.get("result")),
                    "percent": item.get("percent"),
                    "grade": item.get("grade"),
                    "details": _details_of(item.get("result")),
                    "photos": item.get("photos") or [],
                    "ai_status": (
                        item["result"]["ai_status"]
                        if item.get("result") is not None and "ai_status" in item["result"].keys()
                        else "not_requested"
                    ),
                    "ai_feedback": (
                        item["result"]["ai_feedback"]
                        if item.get("result") is not None and "ai_feedback" in item["result"].keys()
                        else None
                    ),
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
        item = _assignment_payload(row)
        results = assignments_service.results_of(row["id"])
        item["results"] = [
            {
                "student_id": result["student_id"],
                "student_name": " ".join(
                    part for part in (result["first_name"] or "", result["last_name"] or "")
                    if part
                ).strip() or "Ученик",
                "score": result["score"],
                "max_score": result["max_score"],
                "percent": round(result["score"] / result["max_score"] * 100)
                if result["max_score"] else 0,
                "completed_at": result["completed_at"],
                "details": _details_of(result),
                "photos": assignments_service.result_photos(result),
                "ai_status": result["ai_status"] if "ai_status" in result.keys() else "not_requested",
                "ai_feedback": result["ai_feedback"] if "ai_feedback" in result.keys() else None,
                "ai_score": result["ai_score"] if "ai_score" in result.keys() else None,
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
    task_type = str(data.get("task_type") or "test").strip()
    if task_type not in assignments_service.TASK_TYPES:
        task_type = "test"
    description = str(data.get("description") or "").strip()
    reference_text = str(data.get("reference_text") or "").strip()
    audio_text = str(data.get("audio_text") or "").strip()
    allow_photo = _bool_flag(data, "allow_photo")
    allow_text = _bool_flag(data, "allow_text")
    if not allow_photo and not allow_text:
        fail(400, "no_answer_mode", "Разрешите ответ текстом или фото")
    if task_type in ("test", "read") and not topic_slugs:
        fail(400, "no_topics", "Выберите хотя бы одну тему")
    if task_type == "dictation" and not reference_text and not topic_slugs:
        fail(400, "no_dictation_text", "Вставьте текст диктанта или выберите тему")
    if task_type == "other" and not description:
        fail(400, "no_description", "Опишите задание")
    subject_id = _optional_int(data.get("subject_id"))
    count = _clamp(_optional_int(data.get("questions_count")) or 10, 1, MAX_QUESTIONS)
    default_title = {
        "test": "Домашнее задание от родителя",
        "read": "Прочитать тему",
        "dictation": "Диктант",
        "other": "Задание от родителя",
    }.get(task_type, "Домашнее задание от родителя")
    title = str(data.get("title") or "").strip() or default_title
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
        if task_type in ("test", "read") and not child_topics:
            continue
        if task_type == "read":
            child_topics = child_topics[:1]
        tasks = assignments_service.build_typed_tasks(
            task_type,
            child_topics,
            count,
            description=description,
            reference_text=reference_text,
            audio_text=audio_text,
        )
        if not tasks:
            continue
        child_subject = subject_id
        if not child_subject and child_topics:
            first = next(
                (topic for topic in all_topics if topic["slug"] == child_topics[0]), None
            )
            child_subject = first["subject_id"] if first else None
        assignments_service.create_assignment(
            title=title,
            kind=str(data.get("kind") or "домашняя"),
            description=description,
            subject_id=child_subject,
            student_id=child["id"],
            teacher_id=user["id"],
            topic_slugs=child_topics,
            questions_count=len(tasks),
            time_limit=_optional_int(data.get("time_limit")) or 0,
            due_date=str(data.get("due_date") or ""),
            status="опубликована",
            tasks=tasks,
            task_type=task_type,
            reference_text=reference_text,
            audio_text=audio_text,
            allow_photo=allow_photo,
            allow_text=allow_text,
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


def _bool_flag(data: dict, key: str, default: bool = True) -> bool:
    """Флаг из JSON: принимает bool, 0/1 и строки true/false."""
    if key not in data:
        return default
    value = data.get(key)
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "no", "off")
    return bool(value)


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
