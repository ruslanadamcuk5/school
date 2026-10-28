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

# Тип задания определяет, что именно выполняет ученик.
# test      — тест из автоматически подобранных вопросов;
# read      — прочитать тему (с озвучкой и отметкой о прочтении);
# dictation — диктант: текст читает синтезатор речи, ответ письменный;
# other     — свободное задание с проверкой ИИ (пересказ, упражнение и т.п.).
TASK_TYPES = {
    "test": "Тест",
    "read": "Прочитать тему",
    "dictation": "Диктант",
    "other": "Иное задание",
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
                    u.role AS teacher_role,
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
                  u.role AS teacher_role,
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
    author_role: str | None = None,
    task_type: str = "test",
    reference_text: str = "",
    audio_text: str = "",
    allow_photo: bool = True,
    allow_text: bool = True,
) -> int:
    topic_slugs = topic_slugs or []
    task_type = task_type if task_type in TASK_TYPES else "test"
    if tasks is None:
        tasks = build_typed_tasks(
            task_type,
            topic_slugs,
            questions_count,
            description=description,
            reference_text=reference_text,
        )
    question_total = len(tasks) if tasks else questions_count
    if author_role is None and teacher_id:
        row = query_one("SELECT role FROM users WHERE id = ?", (teacher_id,))
        author_role = row["role"] if row else None
    assignment_id = execute(
        """INSERT INTO assignments
           (title, kind, description, course_id, subject_id, class_id, teacher_id,
            author_role, student_id, topic_slugs, questions_json, task_type,
            reference_text, audio_text, allow_photo, allow_text, questions_count,
            time_limit, due_date, status, published_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            title.strip(), kind, description.strip() or None, course_id, subject_id, class_id,
            teacher_id, author_role, student_id, json.dumps(topic_slugs, ensure_ascii=False),
            json.dumps(tasks, ensure_ascii=False), task_type,
            (reference_text or "").strip() or None,
            (audio_text or "").strip() or None,
            1 if allow_photo else 0, 1 if allow_text else 0,
            question_total, time_limit, due_date or None, status,
            datetime.now().isoformat(timespec="seconds") if status == "опубликована" else None,
        ),
    )
    if status == "опубликована":
        from services import notifications

        notifications.notify_published(assignment_id)
    return assignment_id


def assignment_tasks(assignment: sqlite3.Row) -> list[dict[str, Any]]:
    """Задания работы (фиксируются при создании, чтобы проверка шла по тем же вопросам)."""
    try:
        tasks = json.loads(assignment["questions_json"] or "[]")
    except (ValueError, TypeError, KeyError, IndexError):
        tasks = []
    if not tasks:
        task_type = assignment["task_type"] if "task_type" in assignment.keys() else "test"
        topics = assignment_topics(assignment)
        tasks = build_typed_tasks(
            task_type,
            topics,
            assignment["questions_count"] or 10,
            description=assignment["description"] if "description" in assignment.keys() else "",
            reference_text=(
                assignment["reference_text"] if "reference_text" in assignment.keys() else ""
            ),
            audio_text=assignment["audio_text"] if "audio_text" in assignment.keys() else "",
        )
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
    task_type = assignment["task_type"] if "task_type" in assignment.keys() else "test"
    tasks = build_typed_tasks(
        task_type,
        assignment_topics(assignment),
        assignment["questions_count"] or 10,
        description=assignment["description"] or "",
        reference_text=(
            assignment["reference_text"] if "reference_text" in assignment.keys() else ""
        ),
        audio_text=assignment["audio_text"] if "audio_text" in assignment.keys() else "",
    )
    execute(
        "UPDATE assignments SET questions_json = ? WHERE id = ?",
        (json.dumps(tasks, ensure_ascii=False), assignment_id),
    )


def update_assignment(assignment_id: int, **fields: Any) -> None:
    allowed = {
        "title", "kind", "description", "course_id", "subject_id", "class_id",
        "teacher_id", "student_id", "questions_count", "time_limit", "due_date",
        "status", "topic_slugs", "task_type", "reference_text", "audio_text",
        "allow_photo", "allow_text",
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
    from services import notifications

    notifications.notify_published(assignment_id)


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


def topic_reading_text(topic_slug: str, max_chars: int = 12000) -> str:
    """Текст темы для чтения и озвучивания."""
    from services import reading_quiz, topics as topics_service

    topic = topics_service.get_topic(topic_slug)
    if not topic:
        return ""
    parts: list[str] = []
    try:
        for page, text in reading_quiz.topic_pages(topic):
            clean = (text or "").strip()
            if not clean:
                continue
            parts.append(f"Страница {page}. {clean}" if page else clean)
            if sum(len(part) for part in parts) >= max_chars:
                break
    except Exception:  # noqa: BLE001 - повреждённый PDF не должен ломать работу
        parts = []
    if not parts:
        parts.append((topic["description"] or "").strip())
    return "\n\n".join(part for part in parts if part)[:max_chars]


def build_typed_tasks(
    task_type: str,
    topic_slugs: list[str] | None = None,
    count: int = 10,
    *,
    description: str = "",
    reference_text: str = "",
    audio_text: str = "",
) -> list[dict[str, Any]]:
    """Собрать задания выбранного типа.

    Для теста используется прежний генератор вопросов. Остальные типы дают
    одно задание: прочитать тему, написать диктант или выполнить свободное
    задание. Текст диктанта хранится в задании, но не показывается ученику
    до проверки — его читает синтезатор речи.
    """
    task_type = task_type if task_type in TASK_TYPES else "test"
    topic_slugs = topic_slugs or []
    if task_type == "test":
        return build_tasks(topic_slugs, count)

    if task_type == "read":
        slug = topic_slugs[0] if topic_slugs else ""
        if not slug:
            return []
        from services import topics as topics_service

        topic = topics_service.get_topic(slug)
        if not topic:
            return []
        content = topic_reading_text(slug)
        prompt = f"Прочитай тему «{topic['title']}»"
        if description.strip():
            prompt += f". {description.strip()}"
        return [
            {
                "question": prompt,
                "answer_type": "read",
                "points": 1,
                "task_type": "read",
                "topic_slug": slug,
                "content_text": content,
                "audio_text": audio_text.strip() or content or topic["title"],
            }
        ]

    if task_type == "dictation":
        text = (reference_text or "").strip()
        if not text and topic_slugs:
            text = topic_reading_text(topic_slugs[0], max_chars=3000)
        if not text:
            return []
        prompt = (description or "").strip() or "Напиши диктант под диктовку."
        return [
            {
                "question": prompt,
                "answer_type": "text",
                "points": 1,
                "task_type": "dictation",
                "topic_slug": topic_slugs[0] if topic_slugs else "",
                "reference_text": text,
                "audio_text": audio_text.strip() or text,
            }
        ]

    prompt = (description or "").strip() or "Выполни задание."
    return [
        {
            "question": prompt,
            "answer_type": "text",
            "points": 1,
            "task_type": "other",
            "topic_slug": topic_slugs[0] if topic_slugs else "",
            "audio_text": audio_text.strip() or prompt,
        }
    ]


def evaluate_submission(
    assignment: sqlite3.Row,
    tasks: list[dict[str, Any]],
    answers: list[str],
    photo_paths: list[str] | None = None,
    *,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Проверить ответы и, если подключён ИИ, получить разбор ошибок.

    Возвращает всё, что нужно для сохранения результата: score, max_score,
    details, ai_status, ai_feedback, ai_model, ai_score.
    """
    from services import ai as ai_service
    from services import assignment_photos

    photos = list(photo_paths or [])
    task_type = assignment["task_type"] if "task_type" in assignment.keys() else "test"
    task_type = task_type if task_type in TASK_TYPES else "test"
    reference = (
        assignment["reference_text"]
        if "reference_text" in assignment.keys() and assignment["reference_text"]
        else ""
    )
    instruction = assignment["description"] or "" if "description" in assignment.keys() else ""
    ai_enabled = ai_service.is_enabled()
    ai_status = "not_requested"
    ai_feedback = ""
    ai_model = ""
    ai_score: int | None = None

    if task_type == "read":
        score, max_score = 1, 1
        details = [
            {
                "index": 0,
                "question": tasks[0].get("question", "Прочитать тему") if tasks else "Прочитать тему",
                "given": (answers[0] if answers else "") or "прочитано",
                "answer": "тема прочитана",
                "correct": True,
                "solution": "",
                "task_type": "read",
            }
        ]
    elif task_type in ("dictation", "other"):
        max_score = 100
        if photos:
            score = 0
        elif task_type == "dictation" and reference:
            score = dictation_similarity(reference, answers[0] if answers else "")
        else:
            score = 0
        details = [
            {
                "index": 0,
                "question": tasks[0].get("question", "") if tasks else "",
                "given": (answers[0] if answers else "") or ("фото ответа" if photos else ""),
                "answer": reference[:2000] if reference else "",
                "correct": score >= 60,
                "solution": "",
                "task_type": task_type,
            }
        ]
    else:
        max_score = len(tasks)
        if photos:
            score, details = 0, [
                {
                    "index": index,
                    "question": task.get("question", ""),
                    "given": "фото ответа",
                    "answer": task.get("answer", ""),
                    "correct": False,
                    "solution": task.get("solution", ""),
                    "task_type": "test",
                }
                for index, task in enumerate(tasks)
            ]
        else:
            score, details = check_assignment_answers(tasks, answers)

    needs_ai = ai_enabled and (
        bool(photos)
        or task_type in ("dictation", "other")
        or (task_type == "test" and any(not item["correct"] for item in details))
        or (task_type == "read" and bool(answers and answers[0].strip()))
    )
    if needs_ai:
        review = ai_service.review_submission(
            task_type=task_type,
            tasks=tasks,
            answers=answers,
            photo_paths=[
                path for path in (assignment_photos.absolute_path(item) for item in photos) if path
            ],
            assignment_title=assignment["title"] if "title" in assignment.keys() else "",
            instruction=instruction,
            reference_text=reference,
            user_id=user_id,
        )
        ai_model = review.get("model") or ""
        if not review.get("ok"):
            ai_status = "failed"
            ai_feedback = f"ИИ не смог проверить работу: {review.get('error', 'неизвестная ошибка')}"
        else:
            ai_status = "checked"
            ai_feedback = review.get("summary") or ""
            ai_score = review.get("score_percent")
            corrected = (review.get("corrected_text") or "").strip()
            if corrected:
                ai_feedback = (
                    ai_feedback + "\n\nИсправленный текст:\n" + corrected
                ).strip()
            comments = {
                int(item.get("index", 0)): item
                for item in review.get("items", [])
                if isinstance(item, dict)
            }
            for index, detail in enumerate(details):
                item = comments.get(index)
                if not item:
                    continue
                detail["ai_comment"] = item.get("comment") or ""
                if photos and task_type in ("test", "dictation", "other"):
                    detail["correct"] = bool(item.get("correct"))
            if task_type == "test" and photos:
                max_score = len(tasks)
                if ai_score is not None:
                    score = max(0, min(max_score, round(ai_score / 100 * max_score)))
                else:
                    score = sum(
                        int(tasks[index].get("points", 1))
                        for index, detail in enumerate(details)
                        if detail.get("correct")
                    )
            elif task_type in ("dictation", "other") and ai_score is not None:
                score = ai_score
                details[0]["correct"] = ai_score >= 60
    elif not ai_enabled:
        ai_status = "disabled"

    submission_type = "mixed" if photos and any(str(a).strip() for a in answers) else (
        "photo" if photos else "inline"
    )
    return {
        "score": int(score),
        "max_score": int(max_score or 0),
        "details": details,
        "submission_type": submission_type,
        "photos": photos,
        "ai_status": ai_status,
        "ai_feedback": ai_feedback,
        "ai_model": ai_model,
        "ai_score": ai_score,
    }


def get_result(assignment_id: int, student_id: int) -> sqlite3.Row | None:
    return query_one(
        "SELECT * FROM assignment_results WHERE assignment_id = ? AND student_id = ?",
        (assignment_id, student_id),
    )


def result_photos(result: sqlite3.Row | None) -> list[str]:
    """Список относительных путей к фото ответа."""
    if result is None:
        return []
    try:
        data = json.loads(result["photos"] or "[]")
    except (ValueError, TypeError, KeyError):
        return []
    return [str(item) for item in data if isinstance(item, str) and item.strip()]


def save_result(
    assignment_id: int,
    student_id: int,
    score: int,
    max_score: int,
    answers: list[dict[str, Any]],
    duration_sec: int = 0,
    *,
    submission_type: str = "inline",
    photos: list[str] | None = None,
    ai_status: str = "not_requested",
    ai_feedback: str = "",
    ai_model: str = "",
    ai_score: int | None = None,
) -> None:
    execute(
        """INSERT INTO assignment_results
           (assignment_id, student_id, score, max_score, answers, duration_sec,
            submission_type, photos, ai_status, ai_feedback, ai_model, ai_score,
            started_at, completed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
           ON CONFLICT(assignment_id, student_id) DO UPDATE SET
               score = excluded.score, max_score = excluded.max_score,
               answers = excluded.answers, duration_sec = excluded.duration_sec,
               submission_type = excluded.submission_type, photos = excluded.photos,
               ai_status = excluded.ai_status, ai_feedback = excluded.ai_feedback,
               ai_model = excluded.ai_model, ai_score = excluded.ai_score,
               completed_at = datetime('now')""",
        (
            assignment_id, student_id, score, max_score,
            json.dumps(answers, ensure_ascii=False), duration_sec,
            submission_type, json.dumps(photos or [], ensure_ascii=False),
            ai_status, (ai_feedback or "").strip()[:8000] or None,
            (ai_model or "").strip()[:200] or None, ai_score,
        ),
    )
    from services import notifications

    notifications.notify_result(assignment_id, student_id, score, max_score)


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
        details: list[dict[str, Any]] = []
        if result is not None:
            try:
                details = json.loads(result["answers"] or "[]")
            except (ValueError, TypeError):
                details = []
        out.append({
            "student": student,
            "result": result,
            "percent": percent,
            "grade": grade_for_percent(percent) if percent is not None else None,
            "details": details,
            "photos": result_photos(result),
        })
    return out


def dictation_similarity(reference: str, given: str) -> int:
    """Офлайн-оценка диктанта, если облачный ИИ не подключён.

    Сравниваем нормализованный текст посимвольно: это не заменяет учителя,
    но позволяет сразу показать примерный процент и не оставить работу без
    результата.
    """
    import re
    from difflib import SequenceMatcher

    def clean(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().casefold().replace("ё", "е"))

    left, right = clean(reference), clean(given)
    if not left:
        return 0
    if not right:
        return 0
    return max(0, min(100, round(SequenceMatcher(None, left, right).ratio() * 100)))


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
        task_type = task.get("task_type", "test")
        if task_type == "read":
            correct, expected = True, "тема прочитана"
        else:
            correct, expected = check_answer(answer, task)
        if correct:
            score += task.get("points", 1)
        details.append({
            "index": index,
            "question": task["question"],
            "given": answer,
            "answer": expected,
            "correct": correct,
            "solution": task.get("solution", ""),
            "task_type": task_type,
        })
    return score, details
