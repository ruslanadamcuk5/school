"""Удалённая помощь: родитель смотрит экран ребёнка и помогает нажатиями.

Как это устроено
----------------
* Родитель создаёт сессию — на телефоне ребёнка появляется запрос.
* Ребёнок явно разрешает показ экрана (системное окно Android MediaProjection)
  и, при желании, управление (служба доступности).
* Телефон ребёнка отправляет сжатые кадры JPEG, родитель видит их в
  приложении. Нажатия родителя превращаются в команды, которые выполняет
  служба доступности на телефоне ребёнка.

Никакого скрытого наблюдения: сессия живёт ограниченное время, ребёнок видит
постоянное уведомление и может остановить помощь в любой момент.
"""
from __future__ import annotations

import os
from typing import Any

from database import execute, query_all, query_one, upload_dir
from services import auth as auth_service
from services import learners as learners_service
from services import notifications

MAX_SESSION_MINUTES = 30
PENDING_MINUTES = 2
MAX_FRAME_BYTES = 2_500_000
CONTROL_KINDS = {
    "tap",
    "swipe",
    "back",
    "home",
    "recents",
    "notifications",
}


class RemoteError(Exception):
    """Ошибка удалённой помощи с HTTP-статусом и машинным кодом."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _name(row, prefix: str) -> str:
    first = (row[f"{prefix}_first"] or "").strip()
    last = (row[f"{prefix}_last"] or "").strip()
    full = " ".join(part for part in (first, last) if part)
    return full or (row[f"{prefix}_login"] or "Пользователь")


def _frame_path(session_id: int) -> str:
    folder = os.path.join(upload_dir(), "remote")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"session_{int(session_id)}.jpg")


def _delete_frame(session_id: int) -> None:
    try:
        os.remove(_frame_path(session_id))
    except OSError:
        pass


def _expire_stale() -> None:
    """Закрыть старые сессии и удалить их кадры."""
    rows = query_all(
        """SELECT id FROM remote_sessions
            WHERE (status = 'pending' AND created_at < datetime('now', ?))
               OR (status = 'active' AND COALESCE(last_seen_at, accepted_at, created_at)
                   < datetime('now', ?))""",
        (f"-{PENDING_MINUTES} minutes", f"-{MAX_SESSION_MINUTES} minutes"),
    )
    for row in rows:
        _delete_frame(int(row["id"]))
    execute(
        """UPDATE remote_sessions
              SET status = 'expired',
                  ended_at = datetime('now'),
                  ended_by = 'timeout'
            WHERE status = 'pending' AND created_at < datetime('now', ?)""",
        (f"-{PENDING_MINUTES} minutes",),
    )
    execute(
        """UPDATE remote_sessions
              SET status = 'expired',
                  ended_at = datetime('now'),
                  ended_by = 'timeout'
            WHERE status = 'active'
              AND COALESCE(last_seen_at, accepted_at, created_at)
                  < datetime('now', ?)""",
        (f"-{MAX_SESSION_MINUTES} minutes",),
    )


def _row(session_id: int):
    return query_one(
        """SELECT s.*,
                  c.first_name AS child_first, c.last_name AS child_last,
                  c.login AS child_login,
                  p.first_name AS parent_first, p.last_name AS parent_last,
                  p.login AS parent_login
             FROM remote_sessions s
             JOIN users c ON c.id = s.child_user_id
             JOIN users p ON p.id = s.parent_user_id
            WHERE s.id = ?""",
        (int(session_id),),
    )


def payload(row) -> dict[str, Any]:
    if row is None:
        return {}
    frame = _frame_path(int(row["id"]))
    return {
        "id": int(row["id"]),
        "status": row["status"],
        "child_name": _name(row, "child"),
        "parent_name": _name(row, "parent"),
        "created_at": row["created_at"],
        "accepted_at": row["accepted_at"],
        "ended_at": row["ended_at"],
        "ended_by": row["ended_by"],
        "last_frame_at": row["last_frame_at"],
        "frame_width": int(row["frame_width"] or 0),
        "frame_height": int(row["frame_height"] or 0),
        "can_control": bool(row["can_control"]),
        "has_frame": os.path.exists(frame),
    }


def _linked_child(parent_id: int, learner_id: int):
    """Профиль ребёнка, привязанного к родителю, по learner_id."""
    learner = learners_service.get_learner(int(learner_id))
    if learner is None:
        raise RemoteError(404, "not_found", "Профиль не найден")
    rows = query_all(
        """SELECT u.id FROM parent_children pc
             JOIN users u ON u.id = pc.child_id
            WHERE pc.parent_id = ?""",
        (int(parent_id),),
    )
    child_ids = {int(item["id"]) for item in rows}
    owner_id = learner["user_id"]
    if owner_id is None:
        link = query_one(
            "SELECT user_id FROM learner_accounts WHERE learner_id = ?",
            (int(learner_id),),
        )
        owner_id = link["user_id"] if link else None
    if owner_id is None or int(owner_id) not in child_ids:
        raise RemoteError(404, "not_found", "Профиль не найден")
    return int(owner_id)


def _parent_session(parent_id: int, session_id: int):
    row = _row(session_id)
    if row is None or int(row["parent_user_id"]) != int(parent_id):
        raise RemoteError(404, "not_found", "Сессия не найдена")
    return row


def _child_session(child_id: int, session_id: int):
    row = _row(session_id)
    if row is None or int(row["child_user_id"]) != int(child_id):
        raise RemoteError(404, "not_found", "Сессия не найдена")
    return row


def start(parent_id: int, learner_id: int) -> dict[str, Any]:
    """Создать запрос на помощь и показать его ребёнку."""
    child_id = _linked_child(parent_id, learner_id)
    _expire_stale()

    existing = query_one(
        """SELECT * FROM remote_sessions
            WHERE child_user_id = ? AND status IN ('pending', 'active')
            ORDER BY id DESC LIMIT 1""",
        (child_id,),
    )
    if existing is not None:
        if int(existing["parent_user_id"]) == int(parent_id):
            return payload(_row(int(existing["id"])))
        raise RemoteError(
            409,
            "busy",
            "К экрану ребёнка уже подключён другой родитель",
        )

    session_id = execute(
        """INSERT INTO remote_sessions (child_user_id, parent_user_id, status)
           VALUES (?, ?, 'pending')""",
        (child_id, int(parent_id)),
    )
    row = _row(session_id)
    notifications.push(
        child_id,
        "remote_help",
        "Родитель предлагает помощь",
        f"{_name(row, 'parent')} просит показать экран, чтобы помочь. "
        "Откройте приложение и разрешите показ.",
        sender_id=int(parent_id),
        dedup_key=f"remote_help:{session_id}",
    )
    return payload(row)


def current(parent_id: int, learner_id: int) -> dict[str, Any] | None:
    """Последняя сессия родителя с этим ребёнком.

    Без ``learner_id`` возвращается последняя сессия родителя с любым из его
    детей: так клиент может восстановить начатую помощь после перезапуска,
    ещё не зная, какого ребёнка выбрали.
    """
    _expire_stale()
    if learner_id:
        child_id = _linked_child(parent_id, learner_id)
        row = query_one(
            """SELECT id FROM remote_sessions
                WHERE child_user_id = ? AND parent_user_id = ?
                ORDER BY id DESC LIMIT 1""",
            (child_id, int(parent_id)),
        )
    else:
        row = query_one(
            """SELECT id FROM remote_sessions
                WHERE parent_user_id = ?
                ORDER BY id DESC LIMIT 1""",
            (int(parent_id),),
        )
    if row is None:
        return None
    return payload(_row(int(row["id"])))


def accept(child_id: int, session_id: int, can_control: bool) -> dict[str, Any]:
    _expire_stale()
    row = _child_session(child_id, session_id)
    if row["status"] == "ended":
        raise RemoteError(409, "ended", "Сессия уже завершена")
    if row["status"] == "expired":
        raise RemoteError(409, "expired", "Запрос устарел. Попросите родителя начать заново.")
    if row["status"] == "pending":
        execute(
            """UPDATE remote_sessions
                  SET status = 'active',
                      accepted_at = datetime('now'),
                      last_seen_at = datetime('now'),
                      can_control = ?
                WHERE id = ?""",
            (1 if can_control else 0, int(session_id)),
        )
    else:
        execute(
            """UPDATE remote_sessions
                  SET last_seen_at = datetime('now'), can_control = ?
                WHERE id = ?""",
            (1 if can_control else 0, int(session_id)),
        )
    return payload(_row(int(session_id)))


def decline(child_id: int, session_id: int) -> dict[str, Any]:
    row = _child_session(child_id, session_id)
    if row["status"] == "pending":
        execute(
            """UPDATE remote_sessions
                  SET status = 'declined', ended_at = datetime('now'),
                      ended_by = 'child'
                WHERE id = ?""",
            (int(session_id),),
        )
    return payload(_row(int(session_id)))


def stop(actor_id: int, role: str, session_id: int) -> dict[str, Any]:
    row = _row(session_id)
    if row is None:
        raise RemoteError(404, "not_found", "Сессия не найдена")
    if role == "parent" and int(row["parent_user_id"]) != int(actor_id):
        raise RemoteError(404, "not_found", "Сессия не найдена")
    if role == "student" and int(row["child_user_id"]) != int(actor_id):
        raise RemoteError(404, "not_found", "Сессия не найдена")
    if row["status"] in ("pending", "active"):
        execute(
            """UPDATE remote_sessions
                  SET status = 'ended', ended_at = datetime('now'), ended_by = ?
                WHERE id = ?""",
            (role, int(session_id)),
        )
    _delete_frame(int(session_id))
    return payload(_row(int(session_id)))


def store_frame(
    child_id: int,
    session_id: int,
    data: bytes,
    width: int,
    height: int,
) -> dict[str, Any]:
    row = _child_session(child_id, session_id)
    if row["status"] != "active":
        raise RemoteError(409, "not_active", "Сессия не активна")
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise RemoteError(400, "bad_frame", "Ожидался JPEG-кадр")
    if len(data) > MAX_FRAME_BYTES:
        raise RemoteError(413, "frame_too_big", "Кадр слишком большой")
    path = _frame_path(session_id)
    part = path + ".part"
    with open(part, "wb") as handle:
        handle.write(data)
    os.replace(part, path)
    execute(
        """UPDATE remote_sessions
              SET last_frame_at = datetime('now'), last_seen_at = datetime('now'),
                  frame_width = ?, frame_height = ?
            WHERE id = ?""",
        (max(0, min(5000, int(width))), max(0, min(5000, int(height))), int(session_id)),
    )
    return payload(_row(int(session_id)))


def frame_path_for_parent(parent_id: int, session_id: int) -> str:
    row = _parent_session(parent_id, session_id)
    if row["status"] != "active":
        raise RemoteError(409, "not_active", "Сессия не активна")
    _linked_child(parent_id, _learner_for_child(int(row["child_user_id"])))
    path = _frame_path(session_id)
    if not os.path.exists(path):
        raise RemoteError(404, "no_frame", "Кадр ещё не пришёл")
    return path


def _learner_for_child(child_user_id: int) -> int:
    row = query_one(
        "SELECT learner_id FROM learner_accounts WHERE user_id = ?", (child_user_id,)
    )
    if row is not None:
        return int(row["learner_id"])
    row = query_one(
        "SELECT id FROM learners WHERE user_id = ? ORDER BY id LIMIT 1", (child_user_id,)
    )
    if row is None:
        raise RemoteError(404, "not_found", "Профиль не найден")
    return int(row["id"])


def queue_command(
    parent_id: int,
    session_id: int,
    kind: str,
    x: float,
    y: float,
    x2: float,
    y2: float,
    duration_ms: int,
) -> int:
    row = _parent_session(parent_id, session_id)
    if row["status"] != "active":
        raise RemoteError(409, "not_active", "Сессия не активна")
    _linked_child(parent_id, _learner_for_child(int(row["child_user_id"])))
    if not bool(row["can_control"]):
        raise RemoteError(
            409,
            "no_control",
            "На телефоне ребёнка не включено управление",
        )
    kind = (kind or "").strip().lower()
    if kind not in CONTROL_KINDS:
        raise RemoteError(400, "bad_command", "Неизвестная команда")
    if duration_ms < 0 or duration_ms > 2000:
        duration_ms = 0
    fields = [
        max(0.0, min(1.0, float(x))),
        max(0.0, min(1.0, float(y))),
        max(0.0, min(1.0, float(x2))),
        max(0.0, min(1.0, float(y2))),
    ]
    return execute(
        """INSERT INTO remote_commands
               (session_id, kind, x, y, x2, y2, duration_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (int(session_id), kind, *fields, int(duration_ms)),
    )


def take_commands(child_id: int, session_id: int, after_id: int) -> list[dict[str, Any]]:
    row = _child_session(child_id, session_id)
    if row["status"] != "active":
        raise RemoteError(409, "not_active", "Сессия не активна")
    rows = query_all(
        """SELECT * FROM remote_commands
            WHERE session_id = ? AND delivered_at IS NULL AND id > ?
            ORDER BY id""",
        (int(session_id), int(after_id)),
    )
    if rows:
        execute(
            """UPDATE remote_commands
                  SET delivered_at = datetime('now')
                WHERE session_id = ? AND delivered_at IS NULL AND id > ?""",
            (int(session_id), int(after_id)),
        )
    return [
        {
            "id": int(item["id"]),
            "kind": item["kind"],
            "x": float(item["x"] or 0),
            "y": float(item["y"] or 0),
            "x2": float(item["x2"] or 0),
            "y2": float(item["y2"] or 0),
            "duration_ms": int(item["duration_ms"] or 0),
        }
        for item in rows
    ]


def heartbeat(child_id: int, session_id: int, can_control: bool) -> dict[str, Any]:
    row = _child_session(child_id, session_id)
    if row["status"] == "active":
        execute(
            """UPDATE remote_sessions
                  SET last_seen_at = datetime('now'), can_control = ?
                WHERE id = ?""",
            (1 if can_control else 0, int(session_id)),
        )
    return payload(_row(int(session_id)))


def incoming(child_id: int) -> dict[str, Any] | None:
    """Активный или ожидающий запрос для телефона ребёнка."""
    _expire_stale()
    row = query_one(
        """SELECT id FROM remote_sessions
            WHERE child_user_id = ? AND status IN ('pending', 'active')
            ORDER BY id DESC LIMIT 1""",
        (int(child_id),),
    )
    if row is None:
        return None
    return payload(_row(int(row["id"])))
