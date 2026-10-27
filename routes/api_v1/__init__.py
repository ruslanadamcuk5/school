"""JSON REST API v1 для Android-приложения.

Аутентификация: ``Authorization: Bearer <token>`` (см. services/api_tokens.py).
CSRF для этих маршрутов не применяется: токен передаётся заголовком, а не
cookie. Все ответы — JSON вида ``{"ok": true, ...}`` либо
``{"ok": false, "error": "код", "message": "текст"}``.
"""
from __future__ import annotations

from flask import Blueprint, jsonify

from .deps import ApiError, fail, load_actor

bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")


@bp.before_request
def _load_actor():
    load_actor()


@bp.errorhandler(ApiError)
def _handle_api_error(exc: ApiError):
    return jsonify({"ok": False, "error": exc.code, "message": exc.message}), exc.status


@bp.after_request
def _api_headers(response):
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@bp.get("/health")
def health():
    from datetime import datetime, timezone

    from database import query_one

    try:
        query_one("SELECT 1 AS ok")
        db_ok = True
    except Exception:  # pragma: no cover
        db_ok = False
    return (
        jsonify(
            {
                "ok": db_ok,
                "status": "ok" if db_ok else "degraded",
                "db": db_ok,
                "api": 1,
                "time": datetime.now(timezone.utc).isoformat(),
            }
        ),
        200 if db_ok else 503,
    )


# Регистрация разделов (импорт в конце, чтобы bp уже существовал).
from . import auth as _auth  # noqa: E402,F401
from . import content as _content  # noqa: E402,F401
from . import play as _play  # noqa: E402,F401
from . import assignments as _assignments  # noqa: E402,F401
from . import library as _library  # noqa: E402,F401
from . import teacher as _teacher  # noqa: E402,F401
from . import parent as _parent  # noqa: E402,F401
from . import notifications as _notifications  # noqa: E402,F401
from . import admin as _admin  # noqa: E402,F401
from . import ai as _ai  # noqa: E402,F401
