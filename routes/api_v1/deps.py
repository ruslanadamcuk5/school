"""Общие зависимости JSON API: ошибки, Bearer-токен, роли, сериализация."""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Iterable

from flask import g, request

from database import query_one

SENSITIVE_FIELDS = {"password_hash", "pin_hash", "child_code"}


class ApiError(Exception):
    """Ошибка API с HTTP-статусом и машинным кодом."""

    def __init__(self, status: int, code: str, message: str = ""):
        super().__init__(message or code)
        self.status = status
        self.code = code
        self.message = message or code


def fail(status: int, code: str, message: str = "") -> None:
    raise ApiError(status, code, message)


def json_body() -> dict[str, Any]:
    """Тело запроса: JSON, а для multipart/форм — поля формы."""
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        return data
    if request.form:
        return request.form.to_dict()
    return {}


def int_arg(name: str, default: int | None = None, *, minimum: int | None = None,
            maximum: int | None = None) -> int | None:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        fail(400, "bad_parameter", f"Параметр «{name}» должен быть числом")
    if minimum is not None and value < minimum:
        fail(400, "bad_parameter", f"Параметр «{name}» должен быть ≥ {minimum}")
    if maximum is not None and value > maximum:
        fail(400, "bad_parameter", f"Параметр «{name}» должен быть ≤ {maximum}")
    return value


def bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header[:7].lower() == "bearer ":
        return header[7:].strip() or None
    return None


def load_actor() -> None:
    """Разобрать Bearer-токен и заполнить g.api_token / user / learner."""
    from services import api_tokens

    g.api_token = None
    g.api_user = None
    g.api_learner = None
    raw = bearer_token()
    if not raw:
        return
    token = api_tokens.resolve(raw)
    if not token:
        return
    g.api_token = token
    if token.get("user_id"):
        g.api_user = query_one(
            "SELECT * FROM users WHERE id = ? AND is_active = 1", (token["user_id"],)
        )
    if token.get("learner_id"):
        g.api_learner = query_one(
            "SELECT * FROM learners WHERE id = ?", (token["learner_id"],)
        )


def current_user():
    return getattr(g, "api_user", None)


def current_learner():
    return getattr(g, "api_learner", None)


def require_user(*roles: str) -> Callable:
    """Декоратор: нужен вход; необязательно — одна из ролей."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                fail(401, "unauthorized", "Требуется вход в аккаунт")
            if roles and user["role"] not in roles:
                fail(403, "forbidden", "Недостаточно прав")
            return view(*args, **kwargs)

        return wrapper

    return decorator


def require_actor(view):
    """Декоратор: нужен любой вошедший — аккаунт или семейный профиль."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None and current_learner() is None:
            fail(401, "unauthorized", "Требуется вход")
        return view(*args, **kwargs)

    return wrapper


def learner_for_request():
    """Профиль ребёнка: из токена, либо связанный с аккаунтом ученика."""
    learner = current_learner()
    if learner is not None:
        return learner
    user = current_user()
    if user is not None and user["role"] == "student":
        from services import learners as learners_service

        try:
            learner_id = learners_service.ensure_learner_for_user(user)
            return learners_service.get_learner(learner_id)
        except Exception:  # pragma: no cover - профиль недоступен
            return None
    return None


def require_learner(view):
    """Декоратор: нужен профиль ребёнка (ученик или семейный профиль)."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user() is None and current_learner() is None:
            fail(401, "unauthorized", "Требуется вход")
        learner = learner_for_request()
        if learner is None:
            fail(403, "no_learner", "Нужен профиль ученика")
        g.api_learner_resolved = learner
        return view(*args, **kwargs)

    return wrapper


def learner() -> Any:
    """Разрешённый профиль ребёнка внутри обработчика."""
    return getattr(g, "api_learner_resolved", None) or learner_for_request()


def row_dict(row, *, exclude: Iterable[str] = ()) -> dict[str, Any] | None:
    """sqlite3.Row → dict без чувствительных полей."""
    if row is None:
        return None
    blocked = set(SENSITIVE_FIELDS) | set(exclude)
    return {key: row[key] for key in row.keys() if key not in blocked}


def user_payload(user) -> dict[str, Any] | None:
    """Публичные поля пользователя."""
    return row_dict(user, exclude={"child_code"})


def learner_payload(learner) -> dict[str, Any] | None:
    """Публичные поля профиля ребёнка."""
    if learner is None:
        return None
    data = row_dict(learner)
    if data is not None and "pin_hash" in learner.keys():
        data["has_pin"] = bool(learner["pin_hash"])
    return data


def theme_for(user, learner) -> str:
    """Тема оформления: playful (1–4), strict (5–7), adult (8–11 и взрослые)."""
    if user is not None and user["role"] in ("admin", "teacher", "parent"):
        return "adult"
    grade = None
    if learner is not None:
        try:
            grade = int(learner["grade"])
        except (KeyError, TypeError, ValueError):
            grade = None
    if grade is None:
        return "playful"
    if grade <= 4:
        return "playful"
    if grade <= 7:
        return "strict"
    return "adult"
