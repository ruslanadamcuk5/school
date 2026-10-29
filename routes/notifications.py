"""Веб-кабинет: список уведомлений и отметка о прочтении.

Страница доступна и аккаунтам (ученик, родитель, учитель, админ), и семейным
профилям без аккаунта — им уведомления приходят по ``learner_id``.
"""
from __future__ import annotations

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from services import auth
from services import learners as learners_service
from services import notifications as notifications_service

bp = Blueprint("notifications", __name__)


def _actor():
    """(user, learner, kind) для текущего посетителя."""
    user = auth.current_user()
    if user is not None:
        return user, None, "user"
    learner = learners_service.current_learner()
    if learner is not None:
        return None, learner, "learner"
    return None, None, ""


@bp.route("/notifications")
def page():
    user, learner, kind = _actor()
    if not kind:
        return redirect(url_for("auth.login"))
    notifications_service.sync_due()
    if kind == "user":
        items = notifications_service.list_for_user(int(user["id"]), 100)
        unread = notifications_service.unread_count(int(user["id"]))
    else:
        items = notifications_service.list_for_learner(int(learner["id"]), 100)
        unread = notifications_service.unread_count_for_learner(int(learner["id"]))
    return render_template(
        "notifications.html",
        user=user,
        learner=learner,
        actor_kind=kind,
        notifications=items,
        unread=unread,
    )


@bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
def read(notification_id: int):
    user, learner, kind = _actor()
    if kind == "user":
        notifications_service.mark_read(int(user["id"]), notification_id)
    elif kind == "learner":
        notifications_service.mark_read_for_learner(int(learner["id"]), notification_id)
    return redirect(request.form.get("next") or url_for("notifications.page"))


@bp.route("/notifications/read-all", methods=["POST"])
def read_all():
    user, learner, kind = _actor()
    if kind == "user":
        notifications_service.mark_all_read(int(user["id"]))
    elif kind == "learner":
        notifications_service.mark_all_read_for_learner(int(learner["id"]))
    flash("Все уведомления отмечены как прочитанные", "info")
    return redirect(url_for("notifications.page"))


ICONS = {
    "assignment_new": "📝",
    "assignment_done": "✅",
    "assignment_missed": "⏰",
    "assignment_deadline": "⏳",
    "message": "💬",
    "reminder": "🔔",
    "library_new": "📚",
    "library_unread": "📖",
}


def _serialize(rows) -> list[dict]:
    return [
        {
            "id": int(item["id"]),
            "kind": item["kind"],
            "icon": ICONS.get(item["kind"], "🔔"),
            "title": item["title"],
            "body": item["body"],
            "link": item["link"] or "",
            "assignment_id": int(item["assignment_id"] or 0),
            "is_read": bool(item["is_read"]),
            "read_at": item["read_at"] or "",
            "created_at": item["created_at"],
        }
        for item in rows
    ]


@bp.route("/notifications/feed")
def feed():
    """JSON для React-компонентов (шапка и страница уведомлений)."""
    user, learner, kind = _actor()
    if not kind:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    notifications_service.sync_due()
    limit = min(100, max(1, request.args.get("limit", type=int) or 30))
    if kind == "user":
        rows = notifications_service.list_for_user(int(user["id"]), limit)
        unread = notifications_service.unread_count(int(user["id"]))
    else:
        rows = notifications_service.list_for_learner(int(learner["id"]), limit)
        unread = notifications_service.unread_count_for_learner(int(learner["id"]))
    return jsonify({"ok": True, "unread": unread, "items": _serialize(rows)})


@bp.route("/notifications/feed/read", methods=["POST"])
def feed_read():
    user, learner, kind = _actor()
    if not kind:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    payload = request.get_json(silent=True) or {}
    try:
        notification_id = int(payload.get("id") or 0)
    except (TypeError, ValueError):
        notification_id = 0
    if not notification_id:
        return jsonify({"ok": False, "error": "bad_request"}), 400
    if kind == "user":
        notifications_service.mark_read(int(user["id"]), notification_id)
        unread = notifications_service.unread_count(int(user["id"]))
    else:
        notifications_service.mark_read_for_learner(int(learner["id"]), notification_id)
        unread = notifications_service.unread_count_for_learner(int(learner["id"]))
    return jsonify({"ok": True, "unread": unread})


@bp.route("/notifications/feed/read-all", methods=["POST"])
def feed_read_all():
    user, learner, kind = _actor()
    if not kind:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if kind == "user":
        notifications_service.mark_all_read(int(user["id"]))
    else:
        notifications_service.mark_all_read_for_learner(int(learner["id"]))
    return jsonify({"ok": True, "unread": 0})
