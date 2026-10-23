"""Bearer-токены для мобильного API.

Веб-приложение живёт на cookie-сессиях, а мобильному клиенту удобнее
долгоживущий токен в заголовке ``Authorization: Bearer <token>``.

В базе хранится только SHA-256 от токена, поэтому утечка файла БД не даёт
войти в аккаунт. Токен можно отозвать (выход из приложения, блокировка
пользователя).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from database import execute, query_all, query_one

DEFAULT_DAYS = 180
TOUCH_AFTER_MINUTES = 5


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def create(
    *,
    user_id: int | None = None,
    learner_id: int | None = None,
    kind: str | None = None,
    days: int = DEFAULT_DAYS,
    label: str | None = None,
) -> str:
    """Создать токен и вернуть его «сырое» значение (единственный раз)."""
    if kind is None:
        kind = "user" if user_id else "learner"
    raw = secrets.token_urlsafe(32)
    expires_at = _stamp(_now() + timedelta(days=days)) if days else None
    execute(
        """INSERT INTO api_tokens
               (token_hash, kind, user_id, learner_id, label, expires_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (_hash(raw), kind, user_id, learner_id, (label or "")[:120] or None, expires_at),
    )
    return raw


def resolve(raw: str | None) -> dict[str, Any] | None:
    """Найти действующий токен. Возвращает строку api_tokens или None."""
    if not raw:
        return None
    row = query_one(
        "SELECT * FROM api_tokens WHERE token_hash = ? AND revoked = 0",
        (_hash(raw),),
    )
    if row is None:
        return None
    expires_at = row["expires_at"]
    if expires_at:
        try:
            if _stamp(_now()) > expires_at:
                return None
        except Exception:  # pragma: no cover - кривая дата в БД
            return None
    # Не пишем в БД на каждый запрос — только раз в несколько минут.
    execute(
        """UPDATE api_tokens SET last_used_at = datetime('now')
            WHERE id = ?
              AND (last_used_at IS NULL
                   OR last_used_at < datetime('now', ?))""",
        (row["id"], f"-{TOUCH_AFTER_MINUTES} minutes"),
    )
    return dict(row)


def revoke(raw: str | None) -> bool:
    """Отозвать конкретный токен (выход из приложения)."""
    if not raw:
        return False
    row = query_one("SELECT id FROM api_tokens WHERE token_hash = ?", (_hash(raw),))
    if row is None:
        return False
    execute("UPDATE api_tokens SET revoked = 1 WHERE id = ?", (row["id"],))
    return True


def revoke_all(*, user_id: int | None = None, learner_id: int | None = None) -> int:
    """Отозвать все токены пользователя/профиля (смена пароля, блокировка)."""
    if user_id is not None:
        rows = query_all("SELECT id FROM api_tokens WHERE user_id = ? AND revoked = 0", (user_id,))
        execute("UPDATE api_tokens SET revoked = 1 WHERE user_id = ?", (user_id,))
        return len(rows)
    if learner_id is not None:
        rows = query_all(
            "SELECT id FROM api_tokens WHERE learner_id = ? AND revoked = 0", (learner_id,)
        )
        execute("UPDATE api_tokens SET revoked = 1 WHERE learner_id = ?", (learner_id,))
        return len(rows)
    return 0


def cleanup(expired_days: int = 30) -> int:
    """Удалить старые отозванные/просроченные токены."""
    rows = query_all(
        """SELECT id FROM api_tokens
            WHERE revoked = 1
              AND created_at < datetime('now', ?)""",
        (f"-{max(1, expired_days)} days",),
    )
    if rows:
        execute(
            """DELETE FROM api_tokens
                WHERE revoked = 1 AND created_at < datetime('now', ?)""",
            (f"-{max(1, expired_days)} days",),
        )
    return len(rows)


def active_count(user_id: int | None = None) -> int:
    if user_id is None:
        row = query_one("SELECT COUNT(*) AS c FROM api_tokens WHERE revoked = 0")
    else:
        row = query_one(
            "SELECT COUNT(*) AS c FROM api_tokens WHERE revoked = 0 AND user_id = ?",
            (user_id,),
        )
    return int(row["c"]) if row else 0
