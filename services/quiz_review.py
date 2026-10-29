"""Проверка самодельных тестов по фото.

Ребёнок открывает тему, отвечает на вопросы письменно и фотографирует лист.
Проверка идёт тем же ИИ, что и домашние работы, результат сохраняется в
``self_quiz_reviews``. Файлы лежат вне статики, доступ — по проверке владельца.
"""
from __future__ import annotations

import json
import os
import uuid

from database import execute, query_one, upload_dir
from services import ai as ai_service
from services import filecheck

ALLOWED_EXTENSIONS = assignment_extensions = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
MAX_BYTES = 8 * 1024 * 1024
MAX_FILES = 6


def photos_root() -> str:
    path = os.path.join(upload_dir(), "quiz_answers")
    os.makedirs(path, exist_ok=True)
    return path


def save_photos(files, learner_id: int, token: str) -> list[str]:
    """Сохранить фото ответов, вернуть относительные пути."""
    saved: list[str] = []
    target_dir = os.path.join(photos_root(), str(learner_id), token[:32])
    os.makedirs(target_dir, exist_ok=True)
    for storage in list(files or [])[:MAX_FILES]:
        filename = (getattr(storage, "filename", "") or "").strip()
        if not filename:
            continue
        extension = os.path.splitext(filename)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            continue
        data = storage.read(MAX_BYTES + 1)
        if not data or len(data) > MAX_BYTES:
            continue
        if not filecheck.looks_like(extension, data[: filecheck.HEAD_BYTES]):
            continue
        new_name = f"{uuid.uuid4().hex}{extension}"
        with open(os.path.join(target_dir, new_name), "wb") as handle:
            handle.write(data)
        saved.append(f"{learner_id}/{token[:32]}/{new_name}")
    if files and not saved:
        raise ValueError(
            "Не удалось сохранить фото. Загрузите JPG/PNG/WebP размером до 8 МБ."
        )
    return saved


def absolute_path(relative: str) -> str | None:
    if not relative:
        return None
    root = os.path.realpath(photos_root())
    target = os.path.realpath(os.path.join(root, relative))
    if not target.startswith(root + os.sep):
        return None
    return target if os.path.isfile(target) else None


def _tasks(items: list[dict]) -> list[dict]:
    return [
        {
            "question": item.get("question", ""),
            "answer": item.get("answer", ""),
            "points": 1,
            "task_type": "test",
        }
        for item in items
    ]


def review_with_photos(
    items: list[dict],
    photos: list[str],
    topic_title: str,
    user_id: int | None = None,
) -> dict:
    """Проверить фото ответов и вернуть разбор в формате работы."""
    tasks = _tasks(items)
    absolute = [path for path in (absolute_path(item) for item in photos) if path]
    if not absolute:
        return {"ok": False, "ai_status": "failed", "error": "Фото не сохранились"}
    if not ai_service.is_enabled():
        details = [
            {
                "question": task["question"],
                "given": "фото ответа",
                "answer": task["answer"],
                "correct": False,
                "ai_comment": "",
            }
            for task in tasks
        ]
        return {
            "ok": False,
            "ai_status": "disabled",
            "details": details,
            "score": 0,
            "max_score": len(tasks),
            "ai_feedback": "ИИ не подключён, поэтому фото не проверены.",
            "ai_model": "",
            "ai_score": None,
        }

    result = ai_service.review_submission(
        task_type="test",
        tasks=tasks,
        answers=[],
        photo_paths=absolute,
        assignment_title=topic_title,
        user_id=user_id,
    )
    ai_items = {}
    for index, item in enumerate(result.get("items") or []):
        try:
            ai_items[int(item.get("index", index))] = item
        except (TypeError, ValueError):
            ai_items[index] = item
    details = []
    for index, task in enumerate(tasks):
        item = ai_items.get(index, {})
        details.append(
            {
                "question": task["question"],
                "given": "фото ответа",
                "answer": task["answer"],
                "correct": bool(item.get("correct")),
                "ai_comment": str(item.get("comment") or "").strip(),
            }
        )
    score = sum(1 for item in details if item["correct"])
    return {
        "ok": bool(result.get("ok")),
        "ai_status": "checked" if result.get("ok") else "failed",
        "details": details,
        "score": score,
        "max_score": len(tasks),
        "ai_feedback": result.get("summary") or "",
        "ai_model": result.get("model") or "",
        "ai_score": result.get("score_percent"),
        "error": result.get("error") or "",
    }


def save_review(
    learner_id: int,
    topic_slug: str,
    token: str,
    photos: list[str],
    review: dict,
) -> int:
    return execute(
        """INSERT INTO self_quiz_reviews
               (learner_id, topic_slug, quiz_token, photos, details, score,
                max_score, ai_status, ai_feedback, ai_model, ai_score)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            int(learner_id),
            topic_slug,
            token,
            json.dumps(photos, ensure_ascii=False),
            json.dumps(review.get("details") or [], ensure_ascii=False),
            int(review.get("score") or 0),
            int(review.get("max_score") or 0),
            review.get("ai_status") or "not_requested",
            review.get("ai_feedback") or "",
            review.get("ai_model") or "",
            review.get("ai_score"),
        ),
    )


def get_review(review_id: int):
    return query_one("SELECT * FROM self_quiz_reviews WHERE id = ?", (int(review_id),))
