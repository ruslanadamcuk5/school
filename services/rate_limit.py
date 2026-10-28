"""Серверное ограничение попыток входа (защита от подбора).

Счётчики живут в таблице ``throttle``, а не в cookie-сессии: очистка cookie
больше не сбрасывает блокировку. Ключ составляется из адреса клиента и
логина/профиля, поэтому один атакующий не блокирует всех пользователей.
"""
from __future__ import annotations

import time

from database import execute, query_one

DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_WINDOW_SECONDS = 15 * 60
DEFAULT_LOCK_SECONDS = 5 * 60


def client_ip(request) -> str:
    """Адрес клиента с учётом reverse-proxy (ProxyFix уже применил X-Forwarded-For)."""
    return (request.remote_addr or "unknown")[:64]


def make_key(scope: str, *parts: str) -> str:
    return ":".join([scope, *(str(part)[:64] for part in parts if part)])[:200]


def blocked_for(key: str) -> int:
    """Сколько секунд осталось до разблокировки (0 — можно пробовать)."""
    row = query_one("SELECT locked_until FROM throttle WHERE key = ?", (key,))
    if not row:
        return 0
    remaining = float(row["locked_until"] or 0) - time.time()
    return max(0, int(remaining))


def register_failure(
    key: str,
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    lock_seconds: int = DEFAULT_LOCK_SECONDS,
) -> int:
    """Учесть неудачную попытку. Возвращает секунды блокировки (0 — ещё нет)."""
    now = time.time()
    row = query_one(
        "SELECT attempts, first_at FROM throttle WHERE key = ?", (key,)
    )
    if row and now - float(row["first_at"] or 0) < window_seconds:
        attempts = int(row["attempts"] or 0) + 1
        first_at = float(row["first_at"] or now)
    else:
        attempts = 1
        first_at = now

    locked_until = now + lock_seconds if attempts >= max_attempts else 0
    execute(
        """INSERT INTO throttle(key, attempts, first_at, locked_until)
                VALUES(?, ?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET
                attempts = excluded.attempts,
                first_at = excluded.first_at,
                locked_until = excluded.locked_until""",
        (key, attempts if not locked_until else 0, first_at, locked_until),
    )
    return lock_seconds if locked_until else 0


def clear(key: str) -> None:
    execute("DELETE FROM throttle WHERE key = ?", (key,))


def cleanup(older_than_seconds: int = 24 * 60 * 60) -> None:
    """Удалить устаревшие записи (вызывается из обслуживания)."""
    execute(
        "DELETE FROM throttle WHERE locked_until < ? AND first_at < ?",
        (time.time() - older_than_seconds, time.time() - older_than_seconds),
    )
