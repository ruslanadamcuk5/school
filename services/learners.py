"""Профили учеников: создание, вход, PIN-код (родительская зона)."""
from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
from typing import Any

from database import execute, query_all, query_one

AVATARS = [
    "🦊", "🐻", "🐼", "🐨", "🦁", "🐯", "🐸", "🐧",
    "🦄", "🐙", "🦖", "🐳", "🦉", "🐝", "🦋", "🐢",
]


# --------------------------------------------------------------- PIN-коды
def hash_pin(pin: str) -> str:
    """Хеширование PIN (PBKDF2-HMAC-SHA256)."""
    salt = os.urandom(16)
    iterations = 120_000
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, iterations)
    return f"pbkdf2${iterations}${salt.hex()}${digest.hex()}"


def verify_pin(pin: str, stored: str | None) -> bool:
    if not stored or not pin:
        return False
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", pin.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------- профили
def create_learner(
    name: str,
    avatar: str = "🦊",
    grade: int = 3,
    pin: str | None = None,
    device_id: str | None = None,
    family_key: str | None = None,
) -> int:
    learner_id = execute(
        "INSERT INTO learners (name, avatar, grade, pin_hash, device_id, family_key) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            name.strip()[:24],
            avatar,
            grade,
            hash_pin(pin) if pin else None,
            (device_id or "")[:64] or None,
            (family_key or "")[:64] or None,
        ),
    )
    return learner_id


def list_learners(family_key: str | None = None) -> list[sqlite3.Row]:
    """Профили учеников.

    Без ``family_key`` возвращает все профили — это нужно только админке.
    Публичные страницы обязаны передавать ключ семьи, иначе утекут имена
    детей из других семей.
    """
    if family_key is None:
        return query_all("SELECT * FROM learners ORDER BY created_at, id")
    return query_all(
        "SELECT * FROM learners WHERE family_key = ? ORDER BY created_at, id",
        (family_key,),
    )


def unclaimed_learners() -> list[sqlite3.Row]:
    """Профили, созданные до появления семей (family_key пустой)."""
    return query_all(
        "SELECT * FROM learners WHERE family_key IS NULL OR family_key = '' "
        "ORDER BY created_at, id"
    )


def claim_learner(learner_id: int, family_key: str) -> bool:
    """Привязать «старый» профиль к семье. Занятые профили не трогаем."""
    if not family_key:
        return False
    execute(
        "UPDATE learners SET family_key = ? "
        " WHERE id = ? AND (family_key IS NULL OR family_key = '')",
        (family_key[:64], learner_id),
    )
    row = get_learner(learner_id)
    return bool(row and row["family_key"] == family_key)


# ------------------------------------------------------- ключ семьи (cookie)
FAMILY_SESSION_KEY = "family_key"


def family_key(create: bool = False) -> str | None:
    """Ключ семьи текущего посетителя (хранится в подписанной сессии)."""
    from flask import session

    key = session.get(FAMILY_SESSION_KEY)
    if not key and create:
        import secrets

        key = secrets.token_urlsafe(18)
        session[FAMILY_SESSION_KEY] = key
        session.permanent = True
    return key


def family_learners(create_key: bool = False) -> list[sqlite3.Row]:
    """Профили только своей семьи (для публичных страниц)."""
    key = family_key(create=create_key)
    if not key:
        return []
    return list_learners(family_key=key)


def owns(learner, key: str | None) -> bool:
    """Принадлежит ли профиль семье с указанным ключом."""
    return bool(key and learner is not None and learner["family_key"] == key)


def get_learner(learner_id: int) -> sqlite3.Row | None:
    return query_one("SELECT * FROM learners WHERE id = ?", (learner_id,))


def delete_learner(learner_id: int) -> None:
    for table in ("attempts", "topic_progress", "method_progress", "badges", "daily_answers", "play_sessions"):
        execute(f"DELETE FROM {table} WHERE learner_id = ?", (learner_id,))
    execute("DELETE FROM learners WHERE id = ?", (learner_id,))


def update_learner(learner_id: int, **fields: Any) -> None:
    allowed = {"name", "avatar", "grade", "pin_hash", "coins", "xp", "streak_days", "last_day",
               "sound_on", "voice_on", "daily_limit"}
    data = {k: v for k, v in fields.items() if k in allowed}
    if not data:
        return
    sets = ", ".join(f"{k} = ?" for k in data)
    execute(f"UPDATE learners SET {sets} WHERE id = ?", (*data.values(), learner_id))


def set_pin(learner_id: int, pin: str) -> None:
    update_learner(learner_id, pin_hash=hash_pin(pin))


def clear_pin(learner_id: int) -> None:
    update_learner(learner_id, pin_hash=None)


def has_pin(learner_id: int) -> bool:
    row = get_learner(learner_id)
    return bool(row and row["pin_hash"])


def reset_progress(learner_id: int) -> None:
    for table in ("attempts", "topic_progress", "method_progress", "daily_answers", "play_sessions"):
        execute(f"DELETE FROM {table} WHERE learner_id = ?", (learner_id,))
    execute("DELETE FROM badges WHERE learner_id = ?", (learner_id,))
    execute("UPDATE learners SET coins = 0, xp = 0, streak_days = 0, last_day = NULL WHERE id = ?",
            (learner_id,))


# ------------------------------------------------------------ сессия входа
def current_learner() -> sqlite3.Row | None:
    """Профиль прогресса текущего пользователя.

    Работает в двух режимах: семейный (выбор профиля ребёнка) и
    школьный (вход ученика по аккаунту).
    """
    from flask import session

    learner_id = session.get("learner_id")
    if learner_id:
        return get_learner(int(learner_id))

    user_id = session.get("user_id")
    if user_id:
        row = query_one(
            """SELECT l.* FROM learner_accounts la
                 JOIN learners l ON l.id = la.learner_id
                WHERE la.user_id = ?""",
            (int(user_id),),
        )
        if row:
            session["learner_id"] = row["id"]
            return row
    return None


def ensure_learner_for_user(user) -> int:
    """Создать (при необходимости) профиль прогресса для аккаунта ученика."""
    row = query_one(
        """SELECT l.* FROM learner_accounts la
             JOIN learners l ON l.id = la.learner_id
            WHERE la.user_id = ?""",
        (user["id"],),
    )
    grade = 3
    classes = query_all(
        """SELECT sc.grade FROM class_students cs
             JOIN school_classes sc ON sc.id = cs.class_id
            WHERE cs.student_id = ? ORDER BY sc.grade LIMIT 1""",
        (user["id"],),
    )
    if classes:
        grade = classes[0]["grade"]
    if row:
        if classes and int(row["grade"]) != int(grade):
            execute("UPDATE learners SET grade = ? WHERE id = ?", (grade, row["id"]))
        return row["id"]
    learner_id = create_learner(
        user["first_name"] or user["login"], user["avatar"], grade
    )
    execute("UPDATE learners SET user_id = ? WHERE id = ?", (user["id"], learner_id))
    execute(
        "INSERT OR REPLACE INTO learner_accounts (learner_id, user_id) VALUES (?, ?)",
        (learner_id, user["id"]),
    )
    return learner_id


def login(learner_id: int) -> None:
    from flask import session

    session["learner_id"] = learner_id
    session.permanent = True


def logout() -> None:
    from flask import session

    session.pop("learner_id", None)
