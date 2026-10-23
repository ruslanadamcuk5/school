"""ИИ: объяснение тем моделью и помощник по приложению.

Все маршруты доступны только когда администратор подключил модель
(иначе — 404, и в интерфейсе ссылок на ИИ нет). Работает и для семейных
профилей без аккаунта, и для вошедших пользователей.
"""
from __future__ import annotations

import time

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from content.curriculum import topic_by_slug
from services import ai as ai_service
from services import auth, learners as learners_service, textbooks as textbooks_service
from services import topics as topics_service
from config import Config

bp = Blueprint("ai", __name__, url_prefix="/ai")

HISTORY_KEY = "ai_assistant_history"
HISTORY_LIMIT = 6


# ------------------------------------------------------------------ доступ
def _actor() -> dict:
    """Кто пользуется ИИ: вошедший пользователь или семейный профиль."""
    user = auth.current_user()
    if user:
        name = f"{user['first_name'] or ''} {user['last_name'] or ''}".strip()
        return {"user_id": int(user["id"]), "role": user["role"], "name": name}
    learner = learners_service.current_learner()
    if learner:
        return {"user_id": None, "role": "student", "name": learner["name"]}
    return {"user_id": None, "role": "", "name": ""}


def _available() -> bool:
    actor = _actor()
    return bool(actor["role"]) and ai_service.is_enabled()


def _guard() -> dict:
    if not _available():
        abort(404)
    return _actor()


def _throttled() -> bool:
    """Простое ограничение частоты запросов на сессию."""
    limit = int(Config.AI_MAX_PER_HOUR)
    now = time.time()
    reset = float(session.get("ai_reset") or 0)
    count = int(session.get("ai_count") or 0)
    if now > reset:
        count, reset = 0, now + 3600
    if count >= limit:
        session["ai_count"] = count
        session["ai_reset"] = reset
        return True
    session["ai_count"] = count + 1
    session["ai_reset"] = reset
    return False


# ------------------------------------------------------------------ тема
def _topic_info(slug: str) -> dict | None:
    """Собрать сведения о теме для подсказки модели."""
    topic = topic_by_slug(slug)
    if topic:
        return {
            "slug": slug,
            "title": topic.get("title") or slug,
            "subject": "Математика",
            "grade": topic.get("grade"),
            "description": topic.get("description") or "",
            "page_start": topic.get("page_start"),
            "page_end": topic.get("page_end"),
        }
    row = topics_service.get_topic(slug)
    if not row:
        return None
    books = textbooks_service.textbooks_for_topic(
        slug, subject_id=row["subject_id"], grade=row["grade"]
    )
    page_start = row["page_start"]
    page_end = row["page_end"]
    if books and not page_start:
        page_start = books[0]["page"]
        page_end = books[0]["page_end"]
    return {
        "slug": slug,
        "title": row["title"],
        "subject": row["subject_name"] or "школьный предмет",
        "grade": row["grade"],
        "description": row["description"] or "",
        "page_start": page_start,
        "page_end": page_end,
        "extra": "Тема изучается по учебному пособию (PDF).",
    }


@bp.route("/explain/<slug>")
def explain_topic(slug: str):
    actor = _guard()
    info = _topic_info(slug)
    if not info:
        abort(404)
    content = ""
    error = None
    cached = ai_service.cached_explanation(slug)
    if cached and cached.get("content"):
        content = cached["content"]
    elif _throttled():
        error = "Слишком много запросов к ИИ. Попробуйте позже."
    else:
        content, error = ai_service.explain_topic(info, user_id=actor["user_id"])
    return _render_explain(info, content, error, cached)


@bp.route("/explain/<slug>/refresh", methods=["POST"])
def refresh_explanation(slug: str):
    actor = _guard()
    info = _topic_info(slug)
    if not info:
        abort(404)
    if _throttled():
        flash("Слишком много запросов к ИИ. Попробуйте через минуту.", "error")
        return redirect(url_for("ai.explain_topic", slug=slug))
    content, error = ai_service.explain_topic(info, force=True, user_id=actor["user_id"])
    if error:
        flash(f"Не удалось получить объяснение: {error}", "error")
    else:
        flash("Объяснение обновлено ✅", "success")
    return redirect(url_for("ai.explain_topic", slug=slug))


def _render_explain(info, content, error, cached):
    return render_template(
        "ai/explain.html",
        info=info,
        topic_title=info["title"],
        content_html=ai_service.render_ai_text(content) if content else "",
        error=error,
        cached=cached,
        ai_status=ai_service.status(),
    )


# ------------------------------------------------------------------ помощник
def _history() -> list[dict[str, str]]:
    history = session.get(HISTORY_KEY)
    return history if isinstance(history, list) else []


def _push_history(question: str, answer: str) -> None:
    history = _history()
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})
    session[HISTORY_KEY] = history[-(HISTORY_LIMIT * 2):]


def _page_label() -> str:
    ref = request.referrer or ""
    if ref.startswith(request.host_url):
        return ref[len(request.host_url) - 1 :]
    return "—"


@bp.route("/assistant")
def assistant():
    _guard()
    return render_template(
        "ai/assistant.html",
        history=_history(),
        answer=None,
        error=None,
        question="",
        ai_status=ai_service.status(),
    )


@bp.route("/assistant", methods=["POST"])
def assistant_ask_form():
    actor = _guard()
    question = (request.form.get("question") or "").strip()
    answer = None
    error = None
    if not question:
        error = "Введите вопрос."
    elif _throttled():
        error = "Слишком много запросов к ИИ. Попробуйте позже."
    else:
        answer, error = ai_service.assistant_reply(
            question,
            role=actor["role"],
            name=actor["name"],
            page=_page_label(),
            history=_history(),
            user_id=actor["user_id"],
        )
        if answer:
            _push_history(question, answer)
    return render_template(
        "ai/assistant.html",
        history=_history(),
        answer=answer,
        error=error,
        question=question,
        ai_status=ai_service.status(),
    )


@bp.route("/assistant/ask", methods=["POST"])
def assistant_ask():
    """JSON-эндпоинт для всплывающего помощника."""
    actor = _guard()
    payload = request.get_json(silent=True) or request.form
    question = (payload.get("question") or "").strip()
    if not question:
        return jsonify({"ok": False, "error": "Введите вопрос."}), 400
    if _throttled():
        return jsonify({"ok": False, "error": "Слишком много запросов. Попробуйте позже."}), 429
    answer, error = ai_service.assistant_reply(
        question,
        role=actor["role"],
        name=actor["name"],
        page=payload.get("page") or _page_label(),
        history=_history(),
        user_id=actor["user_id"],
    )
    if error:
        return jsonify({"ok": False, "error": error}), 502
    _push_history(question, answer)
    return jsonify({"ok": True, "answer": answer, "html": ai_service.render_ai_text(answer)})
