"""Аутентификация и авторизация: аккаунты, роли, сессии."""
from __future__ import annotations

import functools
import hashlib
import hmac
import os
import secrets
import sqlite3
from typing import Any, Callable

from database import execute, query_all, query_one

ROLE_ADMIN = "admin"
ROLE_TEACHER = "teacher"
ROLE_STUDENT = "student"
ROLE_PARENT = "parent"

ROLES = {
    ROLE_ADMIN: "Администратор",
    ROLE_TEACHER: "Учитель",
    ROLE_STUDENT: "Ученик",
    ROLE_PARENT: "Родитель",
}

MIN_PASSWORD_LENGTH = 6


# --------------------------------------------------------------- пароли
def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 с уникальной солью."""
    salt = os.urandom(16)
    iterations = 150_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not password:
        return False
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
        if algo != "pbkdf2":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


# ----------------------------------------------------------- аккаунты
def normalize_login(login: str) -> str:
    return (login or "").strip().lower()


def login_taken(login: str, user_id: int | None = None) -> bool:
    row = query_one("SELECT id FROM users WHERE login = ?", (normalize_login(login),))
    return bool(row and (user_id is None or row["id"] != user_id))


def create_user(
    login: str,
    password: str,
    role: str,
    first_name: str = "",
    last_name: str = "",
    email: str | None = None,
    avatar: str = "🦊",
    city_id: int | None = None,
    school_id: int | None = None,
) -> int:
    user_id = execute(
        """INSERT INTO users
           (login, email, password_hash, role, first_name, last_name, avatar, city_id, school_id, child_code)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            normalize_login(login),
            (email or None),
            hash_password(password),
            role,
            first_name.strip()[:40],
            last_name.strip()[:40],
            avatar,
            city_id,
            school_id,
            secrets.token_hex(3).upper() if role == ROLE_STUDENT else None,
        ),
    )
    return user_id


def get_user(user_id: int) -> sqlite3.Row | None:
    return query_one("SELECT * FROM users WHERE id = ?", (user_id,))


def get_user_by_login(login: str) -> sqlite3.Row | None:
    return query_one("SELECT * FROM users WHERE login = ?", (normalize_login(login),))


def list_users(role: str | None = None, search: str = "") -> list[sqlite3.Row]:
    sql = """SELECT u.*, s.name AS school_name, c.name AS city_name
               FROM users u
          LEFT JOIN schools s ON s.id = u.school_id
          LEFT JOIN cities  c ON c.id = u.city_id"""
    params: list[Any] = []
    where = []
    if role:
        where.append("u.role = ?")
        params.append(role)
    if search:
        where.append("(u.login LIKE ? OR u.first_name LIKE ? OR u.last_name LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY u.role, u.last_name, u.first_name"
    return query_all(sql, params)


def update_user(user_id: int, **fields: Any) -> None:
    allowed = {
        "login", "email", "password_hash", "role", "first_name", "last_name",
        "avatar", "phone", "city_id", "school_id", "child_code", "is_active", "last_login",
    }
    data = {k: v for k, v in fields.items() if k in allowed}
    if not data:
        return
    sets = ", ".join(f"{k} = ?" for k in data)
    execute(f"UPDATE users SET {sets} WHERE id = ?", (*data.values(), user_id))


def set_password(user_id: int, password: str) -> None:
    update_user(user_id, password_hash=hash_password(password))


def touch_login(user_id: int) -> None:
    execute("UPDATE users SET last_login = datetime('now') WHERE id = ?", (user_id,))


def delete_user(user_id: int) -> None:
    execute("DELETE FROM users WHERE id = ?", (user_id,))


def children_of(parent_id: int) -> list[sqlite3.Row]:
    return query_all(
        """SELECT u.*, pc.relation
             FROM parent_children pc
             JOIN users u ON u.id = pc.child_id
            WHERE pc.parent_id = ?
            ORDER BY u.first_name, u.last_name""",
        (parent_id,),
    )


def parents_of(student_id: int) -> list[sqlite3.Row]:
    return query_all(
        """SELECT u.*, pc.relation
             FROM parent_children pc
             JOIN users u ON u.id = pc.parent_id
            WHERE pc.child_id = ?""",
        (student_id,),
    )


def link_parent_child(parent_id: int, child_id: int, relation: str = "родитель") -> bool:
    """Привязать ребёнка к родителю по коду ребёнка."""
    child = get_user(child_id)
    if not child or child["role"] != ROLE_STUDENT:
        return False
    execute(
        "INSERT OR IGNORE INTO parent_children (parent_id, child_id, relation) VALUES (?, ?, ?)",
        (parent_id, child_id, relation),
    )
    return True


def find_child_by_code(code: str) -> sqlite3.Row | None:
    code = (code or "").strip().upper()
    if not code:
        return None
    return query_one(
        "SELECT * FROM users WHERE role = ? AND UPPER(child_code) = ?",
        (ROLE_STUDENT, code),
    )


# --------------------------------------------------------------- сессия
def current_user() -> sqlite3.Row | None:
    from flask import session

    user_id = session.get("user_id")
    if not user_id:
        return None
    user = get_user(int(user_id))
    if not user or not user["is_active"]:
        session.pop("user_id", None)
        return None
    return user


def login_user(user_id: int) -> None:
    from flask import session

    # CSRF-токен сохраняем, чтобы формы не ломались после входа
    session.pop("learner_id", None)
    session["user_id"] = user_id
    session.permanent = True
    touch_login(user_id)


def logout_user() -> None:
    from flask import session

    session.pop("user_id", None)
    session.pop("learner_id", None)


def has_role(*roles: str) -> bool:
    user = current_user()
    return bool(user and user["role"] in roles)


# ------------------------------------------------------------- декораторы
def login_required(view: Callable) -> Callable:
    @functools.wraps(view)
    def wrapper(*args: Any, **kwargs: Any):
        from flask import redirect, url_for

        if not current_user():
            return redirect(url_for("auth.login", next=view.__name__))
        return view(*args, **kwargs)

    return wrapper


def role_required(*roles: str) -> Callable:
    def decorator(view: Callable) -> Callable:
        @functools.wraps(view)
        def wrapper(*args: Any, **kwargs: Any):
            from flask import abort, redirect, url_for

            user = current_user()
            if not user:
                return redirect(url_for("auth.login", next=view.__name__))
            if user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapper

    return decorator


def admin_required(view: Callable) -> Callable:
    return role_required(ROLE_ADMIN)(view)


def teacher_required(view: Callable) -> Callable:
    return role_required(ROLE_TEACHER, ROLE_ADMIN)(view)
