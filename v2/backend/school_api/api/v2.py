"""Native FastAPI endpoints (``/api/v2``).

Only new behaviour lives here.  Everything that already exists for the Android
client keeps its contract under ``/api/v1``; the SPA uses both prefixes through
one small client.  Native endpoints are synchronous ``def`` functions, so
FastAPI runs them in its threadpool and never blocks the event loop on psycopg.
"""
from __future__ import annotations

import os
import re
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["v2"])


# ---------------------------------------------------------------- helpers
def _database():
    """The PostgreSQL-backed legacy module (installed by the bootstrap)."""
    import database as db  # noqa: WPS433  (intentional late import)

    return db


def _user_payload(user) -> dict:
    if not user:
        return {}
    data = dict(user)
    data.pop("password_hash", None)
    data.pop("pin_hash", None)
    return data


def _learner_payload(learner) -> dict | None:
    return dict(learner) if learner else None


def _theme(user) -> str:
    if user and user.get("role") == "student":
        return "playful"
    if user and user.get("role") in {"admin", "teacher", "parent"}:
        return "adult"
    return "adult"


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _session_for_token(raw: str | None):
    from services import api_tokens, auth, learners

    token_row = api_tokens.resolve(raw)
    if token_row is None:
        raise HTTPException(status_code=401, detail="Требуется вход")
    user_id = token_row.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Требуется вход")
    user = auth.get_user(int(user_id))
    if user is None or not user["is_active"]:
        raise HTTPException(status_code=403, detail="Аккаунт отключён")
    learner = None
    if user["role"] == auth.ROLE_STUDENT:
        learner_id = learners.ensure_learner_for_user(user)
        learner = learners.get_learner(learner_id)
    return token_row, user, learner


# ------------------------------------------------------------------ models
class RegisterIn(BaseModel):
    login: str = Field(min_length=3, max_length=24)
    password: str = Field(min_length=6, max_length=128)
    role: Literal["student", "teacher", "parent"]
    first_name: str = Field(default="", max_length=40)
    last_name: str = Field(default="", max_length=40)
    email: str | None = Field(default=None, max_length=120)
    grade: int = Field(default=3, ge=1, le=11)
    class_id: int | None = None
    school_id: int | None = None
    city_id: int | None = None
    child_code: str | None = Field(default=None, max_length=16)


class LoginIn(BaseModel):
    login: str
    password: str


# ------------------------------------------------------------------ public
@router.get("/health")
def health():
    from datetime import datetime, timezone

    db_ok = True
    try:
        _database().query_one("SELECT 1 AS ok")
    except Exception:
        db_ok = False
    return {
        "ok": db_ok,
        "api": 2,
        "database": "postgresql" if db_ok else "unavailable",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/public/landing")
def landing():
    """Everything the public landing page needs, in one round-trip."""
    db = _database()
    subjects = db.query_all(
        """SELECT s.id, s.slug, s.name, s.icon, s.color, s.description,
                  COUNT(t.id) AS topics_count
             FROM subjects s
        LEFT JOIN topics t ON t.subject_id = s.id
            WHERE s.is_active = 1
         GROUP BY s.id
         ORDER BY s.order_index, s.id"""
    )
    stats = db.query_one(
        """SELECT (SELECT COUNT(*) FROM topics)   AS topics,
                  (SELECT COUNT(*) FROM users)    AS users,
                  (SELECT COUNT(*) FROM subjects) AS subjects,
                  (SELECT COUNT(*) FROM attempts) AS attempts"""
    ) or {}
    featured = db.query_all(
        """SELECT slug, title, grade, icon, color, description
             FROM topics
         ORDER BY grade, order_index, id
            LIMIT 9"""
    )
    return {
        "ok": True,
        "app": {
            "name": "Школьник",
            "tagline": "Учёба, которая вдохновляет",
            "version": os.environ.get("APP_VERSION", "2.0.0"),
        },
        "stats": {key: int(value or 0) for key, value in stats.items()},
        "subjects": [dict(row) for row in subjects],
        "featured": [dict(row) for row in featured],
    }


# -------------------------------------------------------------------- auth
@router.post("/auth/register", status_code=201)
def register(payload: RegisterIn):
    from services import auth, learners, orgs

    login = auth.normalize_login(payload.login)
    if not login or not re.fullmatch(r"[a-z0-9._-]{3,24}", login):
        raise HTTPException(
            status_code=400,
            detail="Логин: 3–24 символа, латиница, цифры, точка, дефис или подчёркивание",
        )
    if auth.login_taken(login):
        raise HTTPException(status_code=409, detail="Такой логин уже занят")
    if payload.role == "student" and payload.class_id:
        if orgs.get_class(payload.class_id) is None:
            raise HTTPException(status_code=400, detail="Класс не найден")

    try:
        user_id = auth.create_user(
            login,
            payload.password,
            payload.role,
            payload.first_name.strip(),
            payload.last_name.strip(),
            email=(payload.email or None),
            city_id=payload.city_id,
            school_id=payload.school_id,
        )
    except Exception as exc:  # unique violation and similar
        raise HTTPException(status_code=409, detail="Не удалось создать аккаунт") from exc

    if payload.role == "student":
        if payload.class_id:
            orgs.add_student_to_class(payload.class_id, user_id)
        learner_id = learners.ensure_learner_for_user(auth.get_user(user_id))
        learners.update_learner(learner_id, grade=payload.grade)
    elif payload.role == "parent" and payload.child_code:
        child = auth.find_child_by_code(payload.child_code)
        if child:
            auth.link_parent_child(user_id, child["id"], "родитель")

    return _issue_session(user_id)


@router.post("/auth/login")
def login(payload: LoginIn):
    from services import api_tokens, auth

    login_name = auth.normalize_login(payload.login)
    user = auth.get_user_by_login(login_name)
    from services import rate_limit

    throttle_key = rate_limit.make_key("api-v2-login", "web", login_name)
    wait = rate_limit.blocked_for(throttle_key)
    if wait:
        raise HTTPException(
            status_code=429, detail=f"Слишком много попыток. Повторите через {wait} с."
        )
    if not user or not auth.verify_password(payload.password, user["password_hash"]):
        rate_limit.register_failure(throttle_key)
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Аккаунт отключён")
    rate_limit.clear(throttle_key)
    auth.touch_login(user["id"])
    return _session_payload(user)


def _issue_session(user_id: int):
    from services import api_tokens, auth, learners

    user = auth.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=500, detail="Аккаунт не найден")
    learner = None
    if user["role"] == auth.ROLE_STUDENT:
        learner_id = learners.ensure_learner_for_user(user)
        learner = learners.get_learner(learner_id)
    token = api_tokens.create(user_id=user["id"], label="web")
    return {
        "ok": True,
        "token": token,
        "user": _user_payload(user),
        "learner": _learner_payload(learner),
        "theme": _theme(user),
    }


def _session_payload(user):
    from services import api_tokens, auth, learners

    learner = None
    if user["role"] == auth.ROLE_STUDENT:
        learner_id = learners.ensure_learner_for_user(user)
        learner = learners.get_learner(learner_id)
    token = api_tokens.create(user_id=user["id"], label="web")
    return {
        "ok": True,
        "token": token,
        "user": _user_payload(user),
        "learner": _learner_payload(learner),
        "theme": _theme(user),
    }


@router.get("/auth/me")
def me(authorization: str | None = Header(default=None)):
    _, user, learner = _session_for_token(_bearer(authorization))
    return {
        "ok": True,
        "user": _user_payload(user),
        "learner": _learner_payload(learner),
        "theme": _theme(user),
    }


@router.post("/auth/logout")
def logout(authorization: str | None = Header(default=None)):
    from services import api_tokens

    api_tokens.revoke(_bearer(authorization))
    return {"ok": True}


# ------------------------------------------------------------- teacher view
@router.get("/teacher/overview")
def teacher_overview(authorization: str | None = Header(default=None)):
    """Small native example: a compact teacher summary for the SPA."""
    _, user, _ = _session_for_token(_bearer(authorization))
    if user["role"] not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    db = _database()
    data = db.query_one(
        """SELECT (SELECT COUNT(*) FROM school_classes WHERE teacher_id = ?) AS classes,
                  (SELECT COUNT(*) FROM class_students cs
                     JOIN school_classes sc ON sc.id = cs.class_id
                    WHERE sc.teacher_id = ?) AS students,
                  (SELECT COUNT(*) FROM assignments WHERE teacher_id = ?) AS assignments,
                  (SELECT COUNT(*) FROM library_recommendations
                    WHERE teacher_id = ?) AS recommendations""",
        (user["id"], user["id"], user["id"], user["id"]),
    ) or {}
    return {"ok": True, "stats": {key: int(value or 0) for key, value in data.items()}}
