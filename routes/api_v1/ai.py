"""API: объяснение темы и помощник (только когда ИИ настроен)."""
from __future__ import annotations

import time

from flask import jsonify, request

from services import ai as ai_service

from . import bp
from .deps import current_user, fail, json_body, learner, require_actor

# Простое ограничение частоты на процесс: не больше AI_MAX_PER_HOUR на ключ.
_BUCKETS: dict[str, list[float]] = {}


def _bucket_key() -> str:
    from flask import g

    token = getattr(g, "api_token", None)
    if token:
        return f"token:{token['id']}"
    return f"ip:{request.remote_addr or '?'}"


def _allow() -> bool:
    from config import Config

    limit = max(1, int(Config.AI_MAX_PER_HOUR))
    now = time.time()
    bucket = [moment for moment in _BUCKETS.get(_bucket_key(), []) if now - moment < 3600]
    if len(bucket) >= limit:
        _BUCKETS[_bucket_key()] = bucket
        return False
    bucket.append(now)
    _BUCKETS[_bucket_key()] = bucket
    return True


def _ensure_enabled() -> None:
    if not ai_service.is_enabled():
        fail(404, "ai_disabled", "ИИ не настроен")


def _topic_info(slug: str) -> dict:
    from routes.ai import _topic_info as web_topic_info

    info = web_topic_info(slug)
    if not info:
        fail(404, "not_found", "Тема не найдена")
    return info


def _actor_id() -> int | None:
    user = current_user()
    return int(user["id"]) if user is not None else None


@bp.get("/ai/status")
@require_actor
def status():
    _ensure_enabled()
    return jsonify({"ok": True, "ai": ai_service.status()})


@bp.get("/ai/explain/<slug>")
@require_actor
def explain(slug: str):
    _ensure_enabled()
    info = _topic_info(slug)
    cached = ai_service.cached_explanation(slug)
    if cached and cached.get("content"):
        return jsonify(
            {
                "ok": True,
                "cached": True,
                "topic": info,
                "content": cached["content"],
                "html": ai_service.render_ai_text(cached["content"]),
                "model": cached.get("model"),
                "created_at": cached.get("created_at"),
            }
        )
    if not _allow():
        fail(429, "too_many", "Слишком много запросов к ИИ. Попробуйте позже.")
    text, error = ai_service.explain_topic(info, user_id=_actor_id())
    if error:
        fail(502, "ai_error", error)
    return jsonify(
        {
            "ok": True,
            "cached": False,
            "topic": info,
            "content": text,
            "html": ai_service.render_ai_text(text),
            "model": ai_service.get_settings().get("model"),
        }
    )


@bp.post("/ai/explain/<slug>/refresh")
@require_actor
def refresh(slug: str):
    _ensure_enabled()
    info = _topic_info(slug)
    if not _allow():
        fail(429, "too_many", "Слишком много запросов к ИИ. Попробуйте позже.")
    text, error = ai_service.explain_topic(info, force=True, user_id=_actor_id())
    if error:
        fail(502, "ai_error", error)
    return jsonify(
        {
            "ok": True,
            "topic": info,
            "content": text,
            "html": ai_service.render_ai_text(text),
        }
    )


@bp.post("/ai/assistant")
@require_actor
def assistant():
    _ensure_enabled()
    data = json_body()
    question = str(data.get("question") or "").strip()
    if not question:
        fail(400, "empty_question", "Введите вопрос")
    if not _allow():
        fail(429, "too_many", "Слишком много запросов к ИИ. Попробуйте позже.")
    user = current_user()
    profile = learner()
    role = user["role"] if user is not None else "student"
    name = ""
    if user is not None:
        name = f"{user['first_name'] or ''} {user['last_name'] or ''}".strip()
    elif profile is not None:
        name = profile["name"]
    answer, error = ai_service.assistant_reply(
        question,
        role=role,
        name=name,
        page=str(data.get("page") or ""),
        user_id=_actor_id(),
    )
    if error:
        fail(502, "ai_error", error)
    return jsonify(
        {
            "ok": True,
            "answer": answer,
            "html": ai_service.render_ai_text(answer),
        }
    )
