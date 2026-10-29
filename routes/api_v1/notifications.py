"""API: уведомления о заданиях, сообщениях и литературе.

Работает и для аккаунтов, и для семейных профилей без аккаунта: у последних
уведомления хранятся по ``learner_id`` и приходят в приложение тем же опросом.
"""
from __future__ import annotations

from flask import jsonify, request

from services import notifications as notifications_service

from . import bp
from .deps import current_learner, current_user, fail, require_actor, row_dict


def _actor():
    """Кто читает уведомления: ('user', id) или ('learner', id)."""
    user = current_user()
    if user is not None:
        return "user", int(user["id"])
    learner = current_learner()
    if learner is not None:
        return "learner", int(learner["id"])
    fail(401, "unauthorized", "Требуется вход")


def _list(kind: str, actor_id: int, limit: int) -> list:
    if kind == "user":
        return notifications_service.list_for_user(actor_id, limit)
    return notifications_service.list_for_learner(actor_id, limit)


def _unread(kind: str, actor_id: int) -> int:
    if kind == "user":
        return notifications_service.unread_count(actor_id)
    return notifications_service.unread_count_for_learner(actor_id)


@bp.get("/notifications")
@require_actor
def notifications_list():
    kind, actor_id = _actor()
    # Сроки проверяем лениво — при первом же опросе приложения.
    try:
        notifications_service.sync_due()
    except Exception:  # pragma: no cover - уведомления не должны ломать API
        pass
    limit = request.args.get("limit", type=int) or 50
    unread_only = str(request.args.get("unread_only") or "") in ("1", "true", "yes")
    rows = _list(kind, actor_id, limit)
    if unread_only:
        rows = [row for row in rows if not row["is_read"]]
    return jsonify(
        {
            "ok": True,
            "unread": _unread(kind, actor_id),
            "notifications": [
                {
                    **row_dict(row),
                    "is_read": bool(row["is_read"]),
                }
                for row in rows
            ],
        }
    )


@bp.post("/notifications/<int:notification_id>/read")
@require_actor
def notification_read(notification_id: int):
    kind, actor_id = _actor()
    if kind == "user":
        notifications_service.mark_read(actor_id, notification_id)
    else:
        notifications_service.mark_read_for_learner(actor_id, notification_id)
    return jsonify({"ok": True, "unread": _unread(kind, actor_id)})


@bp.post("/notifications/read-all")
@require_actor
def notifications_read_all():
    kind, actor_id = _actor()
    if kind == "user":
        notifications_service.mark_all_read(actor_id)
    else:
        notifications_service.mark_all_read_for_learner(actor_id)
    return jsonify({"ok": True, "unread": 0})
