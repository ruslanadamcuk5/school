"""API: уведомления о заданиях и результатах."""
from __future__ import annotations

from flask import jsonify, request

from services import notifications as notifications_service

from . import bp
from .deps import current_user, fail, require_user, row_dict


@bp.get("/notifications")
@require_user()
def notifications_list():
    user = current_user()
    # Просроченные работы фиксируем лениво — при первом же опросе приложения.
    try:
        notifications_service.sync_missed()
    except Exception:  # pragma: no cover - уведомления не должны ломать API
        pass
    limit = request.args.get("limit", type=int) or 50
    unread_only = str(request.args.get("unread_only") or "") in ("1", "true", "yes")
    rows = notifications_service.list_for_user(int(user["id"]), limit)
    if unread_only:
        rows = [row for row in rows if not row["is_read"]]
    return jsonify(
        {
            "ok": True,
            "unread": notifications_service.unread_count(int(user["id"])),
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
@require_user()
def notification_read(notification_id: int):
    user = current_user()
    notifications_service.mark_read(int(user["id"]), notification_id)
    return jsonify({"ok": True, "unread": notifications_service.unread_count(int(user["id"]))})


@bp.post("/notifications/read-all")
@require_user()
def notifications_read_all():
    user = current_user()
    notifications_service.mark_all_read(int(user["id"]))
    return jsonify({"ok": True, "unread": 0})
