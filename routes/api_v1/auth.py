"""API: вход, выход, текущий пользователь и семейные профили.

Семейные профили (дети без аккаунта) привязаны к устройству: приложение
присылает заголовок ``X-Device-Id``, и список профилей ограничен этим
устройством. Так публичный сервер не отдаёт имена всех детей сразу.
Профиль с PIN-кодом требует PIN при входе.
"""
from __future__ import annotations

from functools import wraps

from flask import g, jsonify, request

from database import execute, query_all
from services import api_tokens
from services import auth as auth_service
from services import google_auth
from services import learners as learners_service

from . import bp
from .deps import (
    current_user,
    fail,
    json_body,
    learner_for_request,
    learner_payload,
    require_actor,
    theme_for,
    user_payload,
)

MAX_GRADE = 11
MAX_PROFILES_PER_DEVICE = 8


def _session_payload(user, learner) -> dict:
    return {
        "ok": True,
        "user": user_payload(user),
        "learner": learner_payload(learner),
        "theme": theme_for(user, learner),
    }


def device_id() -> str:
    return (request.headers.get("X-Device-Id") or "").strip()[:64]


def require_family_token(view):
    """Разрешить только семейный профиль (не аккаунт)."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if getattr(g, "api_token", None) is None:
            fail(401, "unauthorized", "Требуется вход")
        if current_user() is not None:
            fail(400, "not_family", "Действие доступно только семейным профилям")
        return view(*args, **kwargs)

    return wrapper


@bp.post("/auth/login")
def login():
    data = json_body()
    login_name = auth_service.normalize_login(str(data.get("login") or ""))
    password = str(data.get("password") or "")
    from services import rate_limit

    throttle_key = rate_limit.make_key(
        "api-login", rate_limit.client_ip(request), login_name
    )
    wait = rate_limit.blocked_for(throttle_key)
    if wait:
        fail(429, "too_many_attempts", f"Слишком много попыток. Повторите через {wait} с.")
    user = auth_service.get_user_by_login(login_name)
    if not user or not auth_service.verify_password(password, user["password_hash"]):
        rate_limit.register_failure(throttle_key)
        fail(401, "bad_credentials", "Неверный логин или пароль")
    if not user["is_active"]:
        fail(403, "inactive", "Аккаунт отключён. Обратитесь к администратору.")
    rate_limit.clear(throttle_key)

    learner = None
    if user["role"] == auth_service.ROLE_STUDENT:
        learner_id = learners_service.ensure_learner_for_user(user)
        learner = learners_service.get_learner(learner_id)

    token = api_tokens.create(
        user_id=user["id"], label=request.headers.get("User-Agent")
    )
    payload = _session_payload(user, learner)
    payload["token"] = token
    return jsonify(payload)


def _issue_token(user, label: str | None = None) -> dict:
    """Bearer-токен и снимок сессии для аккаунта (общий код входа)."""
    learner = None
    if user["role"] == auth_service.ROLE_STUDENT:
        learner_id = learners_service.ensure_learner_for_user(user)
        learner = learners_service.get_learner(learner_id)
    token = api_tokens.create(
        user_id=user["id"], label=label or request.headers.get("User-Agent")
    )
    payload = _session_payload(user, learner)
    payload["token"] = token
    return payload


@bp.post("/auth/google")
def google_login():
    """Вход по ID-токену из Android (Credential Manager)."""
    data = json_body()
    id_token = str(data.get("id_token") or "").strip()
    nonce = str(data.get("nonce") or "").strip()
    if not google_auth.is_configured():
        fail(503, "google_disabled", "Вход через Google не настроен на сервере")
    if not id_token:
        fail(400, "bad_request", "Не передан id_token")
    if len(nonce) < 16:
        fail(400, "bad_nonce", "Не передан nonce")

    from services import rate_limit

    throttle_key = rate_limit.make_key(
        "api-google", rate_limit.client_ip(request)
    )
    wait = rate_limit.blocked_for(throttle_key)
    if wait:
        fail(429, "too_many_attempts", f"Слишком много попыток. Повторите через {wait} с.")
    try:
        profile = google_auth.verify_id_token(id_token, nonce)
    except google_auth.GoogleAuthError as exc:
        rate_limit.register_failure(throttle_key)
        fail(401, "google_token_invalid", str(exc))
    rate_limit.clear(throttle_key)

    user = auth_service.get_user_by_google_sub(profile["sub"])
    if user is None:
        accounts = auth_service.users_by_email(profile["email"])
        # Привязываем только при однозначном совпадении: почту Google подтвердил.
        if len(accounts) == 1 and not accounts[0]["google_sub"]:
            user = accounts[0]
            auth_service.attach_google(user["id"], profile["sub"], profile["email"])
            user = auth_service.get_user(user["id"])
    if user is not None:
        if not user["is_active"]:
            fail(403, "inactive", "Аккаунт отключён. Обратитесь к администратору.")
        return jsonify(_issue_token(user))

    suggested = auth_service.suggest_login(profile["email"])
    return jsonify(
        {
            "ok": True,
            "needs_signup": True,
            "signup_token": google_auth.make_signup_token(profile),
            "email": profile["email"],
            "first_name": profile.get("first_name", ""),
            "last_name": profile.get("last_name", ""),
            "picture": profile.get("picture", ""),
            "suggested_login": suggested,
        }
    )


@bp.post("/auth/google/finish")
def google_finish():
    """Завершить регистрацию из приложения: роль, имя и логин."""
    data = json_body()
    try:
        profile = google_auth.read_signup_token(str(data.get("signup_token") or ""))
    except google_auth.GoogleAuthError as exc:
        fail(400, "signup_expired", str(exc))

    role = str(data.get("role") or "").strip()
    if role not in (
        auth_service.ROLE_STUDENT,
        auth_service.ROLE_TEACHER,
        auth_service.ROLE_PARENT,
    ):
        fail(400, "bad_role", "Выберите роль: ученик, учитель или родитель")

    first_name = str(data.get("first_name") or profile.get("first_name") or "").strip()[:40]
    last_name = str(data.get("last_name") or profile.get("last_name") or "").strip()[:40]
    if not first_name:
        fail(400, "bad_name", "Укажите имя")

    login_name = auth_service.normalize_login(str(data.get("login") or ""))
    if len(login_name) < 3:
        fail(400, "bad_login", "Логин должен содержать минимум 3 символа")

    user = auth_service.get_user_by_google_sub(profile["sub"])
    if user is None:
        if auth_service.login_taken(login_name):
            fail(409, "login_taken", "Такой логин уже занят")
        avatar = str(data.get("avatar") or "🦊").strip()[:4] or "🦊"
        user_id = auth_service.create_user(
            login_name,
            "",
            role,
            first_name,
            last_name,
            email=profile["email"],
            avatar=avatar,
            google_sub=profile["sub"],
        )
        user = auth_service.get_user(user_id)
        if role == auth_service.ROLE_STUDENT:
            learners_service.ensure_learner_for_user(user)
        elif role == auth_service.ROLE_PARENT:
            code = str(data.get("child_code") or "").strip().upper()
            child = auth_service.find_child_by_code(code) if code else None
            if child:
                auth_service.link_parent_child(user_id, child["id"])

    if not user["is_active"]:
        fail(403, "inactive", "Аккаунт отключён. Обратитесь к администратору.")
    return jsonify(_issue_token(user))


@bp.post("/auth/logout")
@require_actor
def logout():
    from .deps import bearer_token

    api_tokens.revoke(bearer_token())
    return jsonify({"ok": True})


@bp.get("/auth/me")
@require_actor
def me():
    user = current_user()
    learner = learner_for_request() if user is not None else _current_family_learner()
    return jsonify(_session_payload(user, learner))


def _current_family_learner():
    token = getattr(g, "api_token", None)
    if not token or not token.get("learner_id"):
        return None
    return learners_service.get_learner(int(token["learner_id"]))


# ------------------------------------------------------------------ семейные профили
@bp.get("/learners")
def list_learners():
    """Профили детей, созданные на этом устройстве."""
    device = device_id()
    if not device:
        return jsonify({"ok": True, "learners": [], "device_required": True})
    rows = query_all(
        """SELECT id, name, avatar, grade, pin_hash
             FROM learners WHERE device_id = ?
            ORDER BY grade, name""",
        (device,),
    )
    return jsonify(
        {
            "ok": True,
            "learners": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "avatar": row["avatar"],
                    "grade": row["grade"],
                    "has_pin": bool(row["pin_hash"]),
                }
                for row in rows
            ],
        }
    )


@bp.post("/learners")
def create_learner():
    device = device_id()
    if not device:
        fail(400, "device_required", "Приложение не передало идентификатор устройства")

    count = query_all(
        "SELECT id FROM learners WHERE device_id = ?", (device,)
    )
    if len(count) >= MAX_PROFILES_PER_DEVICE:
        fail(409, "too_many_profiles", "На устройстве уже максимум профилей")

    data = json_body()
    name = str(data.get("name") or "").strip()
    if not name:
        fail(400, "bad_name", "Введите имя ребёнка")
    avatar = str(data.get("avatar") or "🦊")[:8]
    try:
        grade = int(data.get("grade") or 3)
    except (TypeError, ValueError):
        fail(400, "bad_grade", "Класс должен быть числом")
    if not 1 <= grade <= MAX_GRADE:
        fail(400, "bad_grade", f"Класс должен быть от 1 до {MAX_GRADE}")

    pin = str(data.get("pin") or "").strip()
    if pin and (not pin.isdigit() or len(pin) != 4):
        fail(400, "bad_pin", "PIN должен состоять из 4 цифр")

    learner_id = learners_service.create_learner(
        name[:60], avatar, grade, pin or None, device_id=device
    )
    learner = learners_service.get_learner(learner_id)
    token = api_tokens.create(
        learner_id=learner_id, label=request.headers.get("User-Agent")
    )
    payload = _session_payload(None, learner)
    payload["token"] = token
    return jsonify(payload), 201


@bp.post("/learners/<int:learner_id>/login")
def login_learner(learner_id: int):
    device = device_id()
    learner = learners_service.get_learner(learner_id)
    if learner is None:
        fail(404, "not_found", "Профиль не найден")
    owner = learner["device_id"] if "device_id" in learner.keys() else None
    if owner and owner != device:
        # не подтверждаем существование чужого профиля
        fail(404, "not_found", "Профиль не найден")

    stored_pin = learner["pin_hash"]
    if stored_pin:
        from services import rate_limit

        throttle_key = rate_limit.make_key(
            "api-learner-pin", rate_limit.client_ip(request), str(learner_id)
        )
        wait = rate_limit.blocked_for(throttle_key)
        if wait:
            fail(
                429,
                "too_many_attempts",
                f"Слишком много попыток. Повторите через {wait} с.",
            )
        pin = str(json_body().get("pin") or "").strip()
        if not pin:
            fail(401, "pin_required", "Введите PIN-код профиля")
        if not learners_service.verify_pin(pin, stored_pin):
            rate_limit.register_failure(throttle_key)
            fail(403, "bad_pin", "Неверный PIN-код")
        rate_limit.clear(throttle_key)

    token = api_tokens.create(
        learner_id=learner_id, label=request.headers.get("User-Agent")
    )
    payload = _session_payload(None, learner)
    payload["token"] = token
    return jsonify(payload)


@bp.post("/learners/switch")
@require_family_token
def switch_learner():
    """Переключить активный профиль, сохранив тот же токен."""
    data = json_body()
    try:
        learner_id = int(data.get("learner_id"))
    except (TypeError, ValueError):
        fail(400, "bad_learner", "Укажите learner_id")

    learner = learners_service.get_learner(learner_id)
    if learner is None:
        fail(404, "not_found", "Профиль не найден")
    owner = learner["device_id"] if "device_id" in learner.keys() else None
    if owner and owner != device_id():
        fail(404, "not_found", "Профиль не найден")

    token = g.api_token
    execute(
        "UPDATE api_tokens SET learner_id = ? WHERE id = ?", (learner_id, token["id"])
    )
    return jsonify(_session_payload(None, learner))
