"""Звуковой вызов ребёнка с телефона родителя.

Родитель нажимает «Включить звук», сервер ставит команду, а приложение ребёнка
в течение нескольких секунд включает громкий сигнал будильника. Сигнал слышен
даже в беззвучном режиме, поэтому ребёнок успевает ответить на звонок.

Полностью переключить системный режим «Без звука» обычное Android-приложение
не может: для этого нужен доступ к режиму «Не беспокоить», который выдаёт сам
ребёнок в настройках Android. Если доступ есть, приложение дополнительно
переводит телефон в обычный режим. Подтверждение каждой команды не требуется.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from database import execute, query_one

# Команда живёт две минуты: если телефон был офлайн, приложение успеет её
# получить, но старое «позвать» уже не зазвонит неожиданно.
TTL_SECONDS = 120
# Защита от случайного двойного нажатия. Повторная команда в это окно просто
# возвращает уже созданную.
COOLDOWN_SECONDS = 10

ACK_STATUSES = {"ringing", "done", "failed"}


class SoundError(Exception):
    """Ошибка команды звука с кодом для JSON-API."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _timestamp(value) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return datetime.now(timezone.utc)


def _iso(value) -> str | None:
    if not value:
        return None
    return str(value).replace(" ", "T") + "Z"


def _payload(row) -> dict | None:
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "learner_id": int(row["learner_id"]),
        "status": str(row["status"]),
        "created_at": _iso(row["created_at"]),
        "delivered_at": _iso(row["delivered_at"]),
        "finished_at": _iso(row["finished_at"]),
        "mode": str(row["mode"] or ""),
        "detail": str(row["detail"] or ""),
    }


def request(learner_id: int, sender_id: int = 0) -> dict:
    """Создать команду «включить звук» для телефона ребёнка."""
    learner_id = int(learner_id)
    now = datetime.now(timezone.utc)
    fresh_after = (now - timedelta(seconds=COOLDOWN_SECONDS)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    recent = query_one(
        """SELECT * FROM sound_commands
            WHERE learner_id = ? AND created_at > ?
              AND status IN ('pending', 'ringing')
            ORDER BY id DESC LIMIT 1""",
        (learner_id, fresh_after),
    )
    if recent is not None:
        return {
            "command": _payload(recent),
            "already": True,
            "message": (
                "Звук уже включается. Если телефон не зазвонил, "
                "подождите несколько секунд и попробуйте снова."
            ),
        }

    execute(
        """UPDATE sound_commands
              SET status = 'expired', finished_at = datetime('now')
            WHERE learner_id = ? AND status = 'pending'""",
        (learner_id,),
    )
    command_id = execute(
        """INSERT INTO sound_commands (learner_id, requested_by, status)
           VALUES (?, ?, 'pending')""",
        (learner_id, int(sender_id or 0)),
    )
    if sender_id:
        execute(
            "INSERT INTO audit_log (user_id, action, entity, entity_id, details) "
            "VALUES (?, 'sound_call', 'learner', ?, '')",
            (int(sender_id), str(learner_id)),
        )
    row = query_one("SELECT * FROM sound_commands WHERE id = ?", (command_id,))
    return {
        "command": _payload(row),
        "already": False,
        "message": (
            "Команда отправлена. Телефон ребёнка зазвонит громко в ближайшие "
            "секунды, даже если включён беззвучный режим."
        ),
    }


def pending(learner_id: int, after_id: int = 0) -> dict | None:
    """Вернуть новую необработанную команду для приложения ребёнка."""
    row = query_one(
        """SELECT * FROM sound_commands
            WHERE learner_id = ? AND id > ? AND status = 'pending'
            ORDER BY id DESC LIMIT 1""",
        (int(learner_id), int(after_id or 0)),
    )
    if row is None:
        return None
    age = (datetime.now(timezone.utc) - _timestamp(row["created_at"])).total_seconds()
    if age > TTL_SECONDS:
        execute(
            """UPDATE sound_commands
                  SET status = 'expired', finished_at = datetime('now')
                WHERE id = ? AND status = 'pending'""",
            (int(row["id"]),),
        )
        return None
    return _payload(row)


def ack(
    learner_id: int,
    command_id: int,
    status: str,
    mode: str = "",
    detail: str = "",
) -> dict:
    """Отметить состояние команды на телефоне ребёнка."""
    if status not in ACK_STATUSES:
        raise SoundError("bad_status", "Неизвестное состояние команды")

    row = query_one(
        "SELECT * FROM sound_commands WHERE id = ? AND learner_id = ?",
        (int(command_id), int(learner_id)),
    )
    if row is None:
        raise SoundError("not_found", "Команда не найдена", 404)

    current = str(row["status"])
    if current in ("done", "failed", "expired"):
        # Повторный ack после остановки или истечения ничего не меняет.
        return _payload(row)

    mode = str(mode or "")[:40]
    detail = str(detail or "")[:200]
    if status == "ringing":
        execute(
            """UPDATE sound_commands
                  SET status = 'ringing',
                      delivered_at = COALESCE(delivered_at, datetime('now')),
                      mode = ?, detail = ?
                WHERE id = ?""",
            (mode, detail, int(command_id)),
        )
    else:
        execute(
            """UPDATE sound_commands
                  SET status = ?, delivered_at = COALESCE(delivered_at, datetime('now')),
                      finished_at = datetime('now'), mode = ?, detail = ?
                WHERE id = ?""",
            (status, mode, detail, int(command_id)),
        )
    return _payload(
        query_one("SELECT * FROM sound_commands WHERE id = ?", (int(command_id),))
    )


def latest(learner_id: int) -> dict | None:
    """Последняя команда ребёнка — для статуса в кабинете родителя."""
    row = query_one(
        """SELECT * FROM sound_commands
            WHERE learner_id = ?
            ORDER BY id DESC LIMIT 1""",
        (int(learner_id),),
    )
    return _payload(row)
