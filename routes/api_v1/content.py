"""API: предметы, карта тем, тема, тест по теме, чтение пособия."""
from __future__ import annotations

import io
from pathlib import Path

from flask import jsonify, request, send_file

from content.answer import check_answer
from content.curriculum import TOPICS, topic_by_slug
from database import execute, query_one
from services import ai as ai_service
from services import library as library_service
from services import orgs
from services import progress as progress_service
from services import quests as quests_service
from services import reading_quiz
from services import rewards as rewards_service
from services import rounds as rounds_service
from services import textbooks as textbooks_service
from services import topics as topics_service
from services import youtube as youtube_service

from . import bp
from .deps import (
    current_user,
    fail,
    int_arg,
    learner,
    learner_for_request,
    require_actor,
    require_learner,
    row_dict,
)

GRADES = list(range(1, 12))
SUBJECT_FALLBACK = "math"


def _subjects() -> list:
    rows = orgs.list_subjects(active_only=True) or orgs.list_subjects()
    return rows


def _ai_available() -> bool:
    """ИИ настроен и включён — можно показать кнопку объяснения темы."""
    try:
        return bool(ai_service.is_enabled())
    except Exception:  # noqa: BLE001 - отсутствие настроек не должно ломать тему
        return False


def _visible_slugs(profile, subject_id: int) -> set[str]:
    """Темы, включённые учителем в курсах класса (пусто = все)."""
    if not profile["user_id"]:
        return set()
    return set(
        orgs.course_topic_slugs_for_student(
            profile["user_id"], subject_id, profile["grade"]
        )
    )


def _method_names(topic: dict) -> list[dict]:
    return [
        {"slug": m["slug"], "name": m["name"], "icon": m.get("icon", "💡")}
        for m in topic.get("methods", [])
    ]


def _subject_counts(grade: int) -> dict[int, int]:
    counts: dict[int, int] = {}
    for row in topics_service.list_topics(grade=grade):
        counts[int(row["subject_id"])] = counts.get(int(row["subject_id"]), 0) + 1
    return counts


def _math_cards(profile, grade: int, visible: set[str]) -> list[dict]:
    tp = progress_service.topic_progress_map(profile["id"])
    mp = progress_service.method_progress_map(profile["id"])
    cards = []
    for topic in TOPICS:
        if topic["grade"] != grade:
            continue
        if visible and topic["slug"] not in visible:
            continue
        row = tp.get(topic["slug"])
        stars = (row["stars"] if row else 0) or 0
        attempts = (row["attempts"] if row else 0) or 0
        correct = (row["correct"] if row else 0) or 0
        mastered = sum(
            1
            for method in topic["methods"]
            if (mp.get((topic["slug"], method["slug"])) or {"mastered": 0})["mastered"]
        )
        cards.append(
            {
                "slug": topic["slug"],
                "title": topic["title"],
                "icon": topic.get("icon", "🔢"),
                "grade": topic["grade"],
                "part": topic.get("part", ""),
                "description": topic.get("description", ""),
                "min_level": topic.get("min_level", 1),
                "page_start": topic.get("page_start"),
                "page_end": topic.get("page_end"),
                "kind": "practice",
                "source": "curriculum",
                "stars": stars,
                "attempts": attempts,
                "correct": correct,
                "accuracy": round(correct / attempts * 100) if attempts else 0,
                "boss_cleared": bool(row["boss_cleared"] if row else 0),
                "methods_total": len(topic["methods"]),
                "methods_mastered": mastered,
            }
        )

    # Темы 1–2 и 5–11 классов: изучаются по описанию, ИИ-объяснению и тесту.
    math = orgs.get_subject_by_slug("math")
    if math is not None:
        for row in topics_service.list_topics(subject_id=int(math["id"]), grade=grade):
            if (row["source"] or "") == "curriculum":
                continue
            if visible and row["slug"] not in visible:
                continue
            progress_row = tp.get(row["slug"])
            cards.append(
                {
                    "slug": row["slug"],
                    "title": row["title"],
                    "icon": row["icon"] or "📖",
                    "grade": row["grade"],
                    "part": row["part"] or "",
                    "description": row["description"] or "",
                    "min_level": 1,
                    "page_start": row["page_start"],
                    "page_end": row["page_end"],
                    "kind": "reading",
                    "source": row["source"] or "starter",
                    "stars": (progress_row["stars"] if progress_row else 0) or 0,
                    "read": bool(progress_row and (progress_row["stars"] or 0) > 0),
                    "attempts": (progress_row["attempts"] if progress_row else 0) or 0,
                    "correct": (progress_row["correct"] if progress_row else 0) or 0,
                    "accuracy": 0,
                    "boss_cleared": False,
                    "methods_total": 0,
                    "methods_mastered": 0,
                    "books_count": 0,
                    "books": [],
                }
            )
    return cards


def _reading_cards(profile, subject_id: int, grade: int, visible: set[str]) -> list[dict]:
    rows = topics_service.list_topics(subject_id=subject_id, grade=grade)
    if visible:
        rows = [row for row in rows if row["slug"] in visible]
    books = textbooks_service.books_for_topics([row["slug"] for row in rows])
    tp = progress_service.topic_progress_map(profile["id"])
    cards = []
    for row in rows:
        progress_row = tp.get(row["slug"])
        topic_books = books.get(row["slug"], [])
        cards.append(
            {
                "slug": row["slug"],
                "title": row["title"],
                "icon": row["icon"] or "📖",
                "grade": row["grade"],
                "part": row["part"] or "",
                "description": row["description"] or "",
                "page_start": row["page_start"],
                "page_end": row["page_end"],
                "kind": "reading",
                "source": row["source"] or "pdf",
                "stars": (progress_row["stars"] if progress_row else 0) or 0,
                "read": bool(progress_row and (progress_row["stars"] or 0) > 0),
                "books_count": len(topic_books),
                "books": [
                    {
                        "id": book["id"] if "id" in book.keys() else book["textbook_id"],
                        "title": book["title"] if "title" in book.keys() else "",
                        "page": book["page"] if "page" in book.keys() else None,
                        "page_end": book["page_end"] if "page_end" in book.keys() else None,
                    }
                    for book in topic_books
                ],
            }
        )
    return cards


@bp.get("/meta")
def meta():
    subjects = _subjects()
    enabled = False
    provider_name = None
    model = None
    try:
        enabled = ai_service.is_enabled()
        if enabled:
            settings = ai_service.get_settings()
            provider_name = settings.get("provider_name")
            model = settings.get("model")
    except Exception:  # noqa: BLE001 - метаданные не должны падать из-за ИИ
        enabled = False
    return jsonify(
        {
            "ok": True,
            "app": {"name": "Учусь", "version": "1.0", "api": 1},
            "grades": GRADES,
            "subjects": [row_dict(row) for row in subjects],
            "ai": {
                "enabled": enabled,
                "provider_name": provider_name,
                "model": model,
            },
        }
    )


@bp.get("/topics")
@require_actor
def topics_catalog():
    """Каталог тем (метаданные) — для выбора тем в работах и админке."""
    grade = int_arg("grade", minimum=1, maximum=11)
    subject_id = int_arg("subject_id", minimum=1)
    search = (request.args.get("search") or "").strip()
    rows = topics_service.list_topics(
        subject_id=subject_id, grade=grade, search=search
    )
    return jsonify(
        {
            "ok": True,
            "topics": [row_dict(row, exclude={"content_json"}) for row in rows],
            "subjects": [row_dict(row) for row in _subjects()],
        }
    )


@bp.get("/map")
@require_learner
def map_view():
    profile = learner()
    grade = int_arg("grade", int(profile["grade"]), minimum=1, maximum=11)
    subjects = _subjects()
    if not subjects:
        fail(503, "no_subjects", "На сервере ещё не настроены предметы")

    # Предмет без единой темы для класса не показываем: иначе ученик видит
    # пустые разделы, в которые невозможно зайти.
    counts = _subject_counts(grade)
    available = [s for s in subjects if counts.get(int(s["id"]), 0) > 0]
    if available:
        subjects = available

    requested = (request.args.get("subject") or "").strip()
    subject = next((s for s in subjects if s["slug"] == requested), None)
    if subject is None:
        subject = next(
            (s for s in subjects if s["slug"] == SUBJECT_FALLBACK),
            subjects[0],
        )

    visible = _visible_slugs(profile, int(subject["id"]))
    if subject["slug"] == SUBJECT_FALLBACK:
        cards = _math_cards(profile, grade, visible)
    else:
        cards = _reading_cards(profile, int(subject["id"]), grade, visible)

    daily = rewards_service.daily_status(profile["id"])
    return jsonify(
        {
            "ok": True,
            "grade": grade,
            "subject": row_dict(subject),
            "subjects": [
                {**row_dict(item), "topics_count": counts.get(int(item["id"]), 0)}
                for item in subjects
            ],
            "topics": cards,
            "daily": daily,
            "daily_done": all(item["done"] for item in daily),
            "stats": _stats_payload(profile),
        }
    )


def _stats_payload(profile) -> dict:
    stats = progress_service.learner_stats(profile["id"]) or {}
    return {
        "level": stats.get("level", 1),
        "level_title": (stats.get("level_info") or {}).get("title", ""),
        "xp": stats.get("xp", 0),
        "coins": stats.get("coins", 0),
        "stars": stats.get("stars", 0),
        "total_attempts": stats.get("total_attempts", 0),
        "total_correct": stats.get("total_correct", 0),
        "accuracy": stats.get("accuracy", 0),
        "streak_days": stats.get("streak_days", 0),
    }


@bp.get("/topics/<slug>")
@require_learner
def topic_detail(slug: str):
    profile = learner()
    curriculum = topic_by_slug(slug)
    if curriculum:
        tp = progress_service.topic_progress_map(profile["id"])
        mp = progress_service.method_progress_map(profile["id"])
        row = tp.get(slug)
        methods = []
        for method in curriculum["methods"]:
            state = mp.get((slug, method["slug"]))
            methods.append(
                {
                    **{k: v for k, v in method.items() if k != "generators"},
                    "mastered": bool(state and state["mastered"]),
                    "attempts": (state["attempts"] if state else 0) or 0,
                    "correct": (state["correct"] if state else 0) or 0,
                }
            )
        books = textbooks_service.textbooks_for_topic(slug, grade=curriculum["grade"])
        video_payload = youtube_service.page_payload(slug)
        return jsonify(
            {
                "ok": True,
                "topic": {
                    **{
                        k: v
                        for k, v in curriculum.items()
                        if k not in ("generators", "methods")
                    },
                    "kind": "practice",
                    "source": "curriculum",
                    "stars": (row["stars"] if row else 0) or 0,
                    "attempts": (row["attempts"] if row else 0) or 0,
                    "correct": (row["correct"] if row else 0) or 0,
                    "boss_cleared": bool(row and row["boss_cleared"]),
                },
                "methods": methods,
                "books": [_book_link(book) for book in books],
                "youtube_enabled": video_payload["youtube_enabled"],
                "videos": video_payload["youtube_videos"],
                "videos_stale": video_payload["youtube_stale"],
                "can_play": True,
                "can_quest": True,
                "can_quiz": True,
                "ai_available": _ai_available(),
            }
        )

    row = topics_service.get_topic(slug)
    if row is None:
        fail(404, "not_found", "Тема не найдена")
    if int(row["grade"]) != int(profile["grade"]):
        fail(403, "grade_mismatch", "Тема другого класса")

    books = textbooks_service.textbooks_for_topic(
        slug, subject_id=row["subject_id"], grade=row["grade"]
    )
    progress_row = query_one(
        "SELECT * FROM topic_progress WHERE learner_id = ? AND topic_slug = ?",
        (profile["id"], slug),
    )
    read = query_one(
        """SELECT id FROM attempts
            WHERE learner_id = ? AND topic_slug = ? AND mode = 'reading' AND correct = 1
            LIMIT 1""",
        (profile["id"], slug),
    )
    siblings = topics_service.list_topics(
        subject_id=row["subject_id"], grade=row["grade"]
    )
    index = next((i for i, item in enumerate(siblings) if item["slug"] == slug), None)
    previous_topic = siblings[index - 1] if index not in (None, 0) else None
    next_topic = (
        siblings[index + 1]
        if index is not None and index + 1 < len(siblings)
        else None
    )
    video_payload = youtube_service.page_payload(slug)
    return jsonify(
        {
            "ok": True,
            "topic": {
                **row_dict(row, exclude={"content_json"}),
                "stars": (progress_row["stars"] if progress_row else 0) or 0,
                "read": bool(read),
            },
            "methods": [],
            "books": [_book_link(book) for book in books],
            "previous": row_dict(previous_topic),
            "next": row_dict(next_topic),
            "youtube_enabled": video_payload["youtube_enabled"],
            "videos": video_payload["youtube_videos"],
            "videos_stale": video_payload["youtube_stale"],
            "can_play": False,
            "can_quest": quests_service.topic_can_quest(dict(row)),
            "can_quiz": True,
            "can_read": True,
            "ai_available": _ai_available(),
        }
    )


@bp.get("/topics/<slug>/videos")
@require_learner
def topic_videos(slug: str):
    """Видео темы для Android: кэш сразу, недостающие — отдельным запросом."""
    profile = learner()
    curriculum = topic_by_slug(slug)
    row = None if curriculum else topics_service.get_topic(slug)
    if not curriculum and not row:
        fail(404, "not_found", "Тема не найдена")
    grade = curriculum["grade"] if curriculum else row["grade"]
    if int(grade) != int(profile["grade"]):
        fail(403, "grade_mismatch", "Тема другого класса")
    payload = youtube_service.videos_for_topic(
        slug,
        allow_fetch=True,
        user_id=int(profile["user_id"]) if profile["user_id"] else None,
    )
    return jsonify(payload)


def _book_link(book) -> dict:
    data = dict(book)
    return {
        "id": data.get("id") or data.get("textbook_id"),
        "title": data.get("title", ""),
        "author": data.get("author", ""),
        "pages": data.get("pages", 0),
        "page": data.get("page"),
        "page_end": data.get("page_end"),
    }

@bp.get("/topics/<slug>/text")
@require_learner
def topic_text(slug: str):
    """Текст страниц пособия для чтения (в том числе офлайн-кэша)."""
    profile = learner()
    row = topics_service.get_topic(slug)
    if row is None:
        fail(404, "not_found", "Тема не найдена")
    if int(row["grade"]) != int(profile["grade"]):
        fail(403, "grade_mismatch", "Тема другого класса")
    pages = reading_quiz.topic_pages(row)
    topic_books = textbooks_service.books_for_topics([slug]).get(slug, [])
    topic = row_dict(row, exclude={"content_json"}) or {}
    topic["books"] = [
        {
            "id": book["id"] if "id" in book.keys() else book["textbook_id"],
            "title": book["title"] if "title" in book.keys() else "",
            "page": book["page"] if "page" in book.keys() else None,
            "page_end": book["page_end"] if "page_end" in book.keys() else None,
        }
        for book in topic_books
    ]
    return jsonify(
        {
            "ok": True,
            "topic": topic,
            "pages": [{"page": page, "text": text} for page, text in pages],
        }
    )


def _curriculum_quiz_items(topic: dict, count: int = 8) -> list[dict]:
    """Вопросы теста для темы учебной программы (математика 3–4 класса).

    Задания берутся из тех же генераторов, что и тренировка: так тест всегда
    собирается без внешнего ИИ и проверяет именно эту тему.
    """
    from content.generators import REGISTRY

    generators: list[str] = []
    for method in topic.get("methods") or []:
        key = method.get("example")
        if key in REGISTRY and key not in generators:
            generators.append(key)
    for key in topic.get("generators") or []:
        if key in REGISTRY and key not in generators:
            generators.append(key)
    if not generators:
        return []

    items: list[dict] = []
    seen: set[str] = set()
    attempts = 0
    while len(items) < count and attempts < count * 8:
        generator = generators[len(items) % len(generators)]
        attempts += 1
        try:
            item = rounds_service.build_task(generator, 1)
        except Exception:  # noqa: BLE001 - один генератор не должен ломать тест
            continue
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        if not question or not answer:
            continue
        key = question.casefold()
        if key in seen:
            continue
        seen.add(key)
        choices = [str(choice) for choice in (item.get("choices") or [])]
        kind = item.get("answer_type") or ("choice" if choices else "number")
        if kind == "choice" and not choices:
            continue
        items.append(
            {
                "question": question,
                "answer": answer,
                "accept": [str(value) for value in (item.get("accept") or [])],
                "answer_type": kind,
                "choices": choices,
                "solution": str(item.get("solution") or ""),
            }
        )
    return items


@bp.get("/topics/<slug>/quiz")
@require_learner
def quiz_start(slug: str):
    profile = learner()
    curriculum = topic_by_slug(slug)
    if curriculum:
        if int(curriculum["grade"]) != int(profile["grade"]):
            fail(403, "grade_mismatch", "Тема другого класса")
        questions = _curriculum_quiz_items(curriculum, 8)
        title = curriculum["title"]
    else:
        topic = topics_service.get_topic(slug)
        if topic is None:
            fail(404, "not_found", "Тема не найдена")
        if topic["source"] == "curriculum" or topic["kind"] == "practice":
            fail(400, "not_reading", "Тест для этой темы пока недоступен")
        if int(topic["grade"]) != int(profile["grade"]):
            fail(403, "grade_mismatch", "Тема другого класса")
        questions = reading_quiz.build_questions(
            topic, 8, user_id=int(profile["user_id"]) if profile["user_id"] else None
        )
        title = topic["title"]

    if not questions:
        fail(
            409,
            "no_questions",
            "По этой теме не удалось составить вопросы: нет читаемого текста "
            "пособия. Включите ИИ в админке или загрузите пособие с текстом.",
        )

    items = [
        {
            "question": item["question"],
            "answer": str(item.get("answer", "")),
            "accept": [str(value) for value in (item.get("accept") or [])],
            "answer_type": item.get("answer_type") or "choice",
            "choices": item.get("choices") or [],
            "solution": item.get("solution", ""),
        }
        for item in questions
    ]
    quiz_id = execute(
        "INSERT INTO play_sessions (learner_id, topic_slug, mode, task_count) "
        "VALUES (?, ?, 'reading_quiz', ?)",
        (profile["id"], slug, len(items)),
    )
    rounds_service.save_round(quiz_id, {"slug": slug, "items": items, "done": False})
    return jsonify(
        {
            "ok": True,
            "quiz_id": quiz_id,
            "topic": {"slug": slug, "title": title},
            "can_photo": ai_service.is_enabled(),
            "questions": [
                {
                    "index": index,
                    "question": item["question"],
                    "choices": item["choices"],
                    "answer_type": item["answer_type"],
                }
                for index, item in enumerate(items)
            ],
        }
    )


@bp.post("/topics/<slug>/quiz")
@require_learner
def quiz_submit(slug: str):
    profile = learner()
    data = request.get_json(silent=True) or {}
    try:
        quiz_id = int(data.get("quiz_id"))
    except (TypeError, ValueError):
        fail(400, "bad_quiz", "Не передан quiz_id")

    state = rounds_service.load_round(quiz_id)
    session_row = query_one(
        "SELECT * FROM play_sessions WHERE id = ? AND learner_id = ?",
        (quiz_id, profile["id"]),
    )
    if not state or not session_row or state.get("slug") != slug:
        fail(404, "quiz_not_found", "Тест не найден. Начните заново.")

    raw_answers = data.get("answers")
    answers: list[str] = []
    if isinstance(raw_answers, list):
        answers = [str(value or "") for value in raw_answers]
    elif isinstance(raw_answers, dict):
        answers = [str(raw_answers.get(str(i), "")) for i in range(len(state["items"]))]
    else:
        fail(400, "bad_answers", "Передайте ответы списком")

    results = []
    correct_count = 0
    for index, item in enumerate(state["items"]):
        given = answers[index] if index < len(answers) else ""
        correct, expected = check_answer(
            given,
            {
                "answer": item["answer"],
                "answer_type": item.get("answer_type") or "choice",
                "accept": item.get("accept") or [],
            },
        )
        if correct:
            correct_count += 1
        progress_service.record_attempt(
            profile["id"],
            slug,
            None,
            "reading.quiz",
            correct,
            given,
            str(expected),
            0,
            0,
            mode="reading_quiz",
        )
        results.append(
            {
                "index": index,
                "question": item["question"],
                "given": given,
                "expected": str(expected),
                "correct": correct,
                "solution": item.get("solution", ""),
            }
        )

    stars = progress_service.apply_round_result(
        profile["id"], slug, correct_count, len(results)
    )
    badges = rewards_service.grant_badges(profile["id"])
    state["done"] = True
    rounds_service.save_round(quiz_id, state)
    return jsonify(
        {
            "ok": True,
            "correct": correct_count,
            "total": len(results),
            "stars": stars,
            "results": results,
            "badges": badges,
        }
    )


@bp.post("/topics/<slug>/quiz/photo")
@require_learner
def quiz_submit_photo(slug: str):
    """Проверить письменные ответы по фотографии через подключённый ИИ."""
    profile = learner()
    if not ai_service.is_enabled():
        fail(
            409,
            "ai_disabled",
            "Проверка по фото недоступна: ИИ не подключён. Ответьте вариантами "
            "или попросите администратора подключить ИИ.",
        )
    try:
        quiz_id = int(request.form.get("quiz_id") or 0)
    except (TypeError, ValueError):
        fail(400, "bad_quiz", "Не передан quiz_id")
    state = rounds_service.load_round(quiz_id) if quiz_id else None
    session_row = query_one(
        "SELECT * FROM play_sessions WHERE id = ? AND learner_id = ?",
        (quiz_id, profile["id"]),
    )
    if not state or not session_row or state.get("slug") != slug:
        fail(404, "quiz_not_found", "Тест не найден. Начните заново.")
    uploads = [
        item for item in request.files.getlist("photos")
        if item is not None and getattr(item, "filename", "")
    ]
    if not uploads:
        fail(400, "no_photos", "Прикрепите хотя бы одну фотографию решения")

    from services import quiz_review

    token = f"{quiz_id}-{profile['id']}"
    try:
        photos = quiz_review.save_photos(uploads, int(profile["id"]), token)
    except ValueError as exc:
        fail(400, "bad_photo", str(exc))

    items = state.get("items") or []
    title = state.get("title") or slug
    review = quiz_review.review_with_photos(
        items,
        photos,
        title,
        user_id=int(profile["user_id"]) if profile["user_id"] else None,
    )
    quiz_review.save_review(int(profile["id"]), slug, token, photos, review)
    if review.get("ai_status") != "checked":
        return jsonify(
            {
                "ok": False,
                "ai_status": review.get("ai_status") or "failed",
                "ai_feedback": review.get("ai_feedback")
                or "Не удалось проверить фото. Попробуйте ещё раз или ответьте вариантами.",
                "correct": 0,
                "total": len(items),
                "stars": 0,
                "results": [],
            }
        )

    details = review.get("details") or []
    results = []
    for index, entry in enumerate(details):
        item = items[index] if index < len(items) else {}
        correct = bool(entry.get("correct"))
        results.append(
            {
                "index": index,
                "question": entry.get("question") or item.get("question", ""),
                "given": entry.get("given") or "фото ответа",
                "expected": entry.get("answer") or item.get("answer", ""),
                "correct": correct,
                "solution": item.get("solution", ""),
                "ai_comment": entry.get("ai_comment") or "",
            }
        )
        progress_service.record_attempt(
            profile["id"],
            slug,
            None,
            "reading.quiz",
            correct,
            entry.get("given") or "",
            entry.get("answer") or "",
            0,
            0,
            mode="reading_quiz_photo",
        )
    correct_count = sum(1 for item in results if item["correct"])
    stars = progress_service.apply_round_result(
        profile["id"], slug, correct_count, len(results)
    )
    badges = rewards_service.grant_badges(profile["id"])
    state["done"] = True
    rounds_service.save_round(quiz_id, state)
    return jsonify(
        {
            "ok": True,
            "ai_status": "checked",
            "ai_feedback": review.get("ai_feedback") or "",
            "correct": correct_count,
            "total": len(results),
            "stars": stars,
            "badges": badges,
            "results": results,
        }
    )


@bp.post("/topics/<slug>/read")
@require_learner
def mark_read(slug: str):
    profile = learner()
    topic = topics_service.get_topic(slug)
    if topic is None:
        fail(404, "not_found", "Тема не найдена")
    if topic["source"] == "curriculum" or topic["kind"] == "practice":
        fail(400, "not_reading", "Это тренировочная тема")
    if int(topic["grade"]) != int(profile["grade"]):
        fail(403, "grade_mismatch", "Тема другого класса")

    result = progress_service.mark_topic_read(profile["id"], slug)
    badges = rewards_service.grant_badges(profile["id"])
    return jsonify(
        {
            "ok": True,
            "already": result["already"],
            "xp": result["xp"],
            "coins": result["coins"],
            "badges": badges,
        }
    )


# ------------------------------------------------------------------ пособия (PDF)
def _can_read_textbook(textbook_id: int) -> bool:
    """Доступ к файлу пособия.

    Та же логика, что и на сайте (``routes/admin.py:textbook_open``):

    * администратор, учитель и родитель — любое пособие;
    * ученик и семейный профиль — пособия своего класса;
    * дополнительно — книга из доступной библиотеки (даже другого класса).

    Раньше ученику разрешались только книги из библиотеки, поэтому ссылка
    «В учебнике» из темы открывала пустую страницу (API отвечал 403).
    """
    from database import query_all

    from .deps import current_user

    user = current_user()
    profile = learner_for_request()
    if user is None and profile is None:
        return False

    row = textbooks_service.get_textbook(textbook_id)
    if row is None:
        return False

    if user is not None:
        for book in query_all(
            "SELECT id FROM library_books WHERE textbook_id = ?", (textbook_id,)
        ):
            if library_service.can_access_book(user, int(book["id"])):
                return True
        if user["role"] in ("admin", "teacher", "parent"):
            return True

    return bool(profile and int(row["grade"]) == int(profile["grade"]))


@bp.get("/books/<int:textbook_id>")
@require_actor
def book_info(textbook_id: int):
    row = textbooks_service.get_textbook(textbook_id)
    if row is None:
        user = current_user()
        if user is not None and user["role"] in ("admin", "teacher", "parent"):
            fail(404, "not_found", "Пособие не найдено")
        fail(403, "forbidden", "Книга недоступна")
    if not _can_read_textbook(textbook_id):
        fail(403, "forbidden", "Книга недоступна")
    links = textbooks_service.textbook_topics(textbook_id)
    topics = []
    for link in links:
        slug = link["topic_slug"]
        curriculum = topic_by_slug(slug)
        # Оглавление хранит только слаги и страницы; название берём из базы,
        # а для тем учебной программы — из curriculum (в таблице topics их нет).
        topics.append(
            {
                "topic_slug": slug,
                "title": link["title"] or (curriculum or {}).get("title") or slug.replace("_", " "),
                "icon": link["icon"] or (curriculum or {}).get("icon") or "📖",
                "grade": link["grade"] or (curriculum or {}).get("grade"),
                "page": link["page"],
                "page_end": link["page_end"],
            }
        )
    return jsonify({"ok": True, "book": row_dict(row), "topics": topics})


def _page_cache_dir() -> Path:
    return Path(textbooks_service.upload_dir()).parent / "page_cache"


@bp.get("/books/<int:textbook_id>/page/<int:page_number>.png")
@require_actor
def book_page(textbook_id: int, page_number: int):
    """Страница PDF как PNG — удобно для мобильного просмотра."""
    if not _can_read_textbook(textbook_id):
        fail(403, "forbidden", "Книга недоступна")
    row = textbooks_service.get_textbook(textbook_id)
    if row is None:
        fail(404, "not_found", "Пособие не найдено")

    pages = int(row["pages"] or 0)
    if pages and not 1 <= page_number <= pages:
        fail(404, "page_not_found", f"В книге {pages} страниц")

    cache = _page_cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"{textbook_id}_{page_number}.png"
    if not target.is_file():
        path = textbooks_service.file_path(row)
        if not Path(path).is_file():
            fail(404, "file_missing", "Файл пособия не найден на сервере")
        try:
            import fitz  # PyMuPDF

            with fitz.open(path) as doc:
                if not 1 <= page_number <= doc.page_count:
                    fail(404, "page_not_found", "Страница не найдена")
                pixmap = doc[page_number - 1].get_pixmap(matrix=fitz.Matrix(1.6, 1.6))
                target.write_bytes(pixmap.tobytes("png"))
        except Exception as exc:  # noqa: BLE001
            fail(500, "render_failed", f"Не удалось отрисовать страницу: {exc}")

    return send_file(
        io.BytesIO(target.read_bytes()), mimetype="image/png", max_age=3600
    )
