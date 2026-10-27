"""Веб-кабинет: список уведомлений и отметка о прочтении."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from services import auth
from services import notifications as notifications_service

bp = Blueprint("notifications", __name__)


@bp.route("/notifications")
@auth.login_required
def page():
    user = auth.current_user()
    notifications_service.sync_missed()
    items = notifications_service.list_for_user(int(user["id"]), 100)
    return render_template(
        "notifications.html",
        user=user,
        notifications=items,
        unread=notifications_service.unread_count(int(user["id"])),
    )


@bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@auth.login_required
def read(notification_id: int):
    user = auth.current_user()
    notifications_service.mark_read(int(user["id"]), notification_id)
    return redirect(request.form.get("next") or url_for("notifications.page"))


@bp.route("/notifications/read-all", methods=["POST"])
@auth.login_required
def read_all():
    user = auth.current_user()
    notifications_service.mark_all_read(int(user["id"]))
    flash("Все уведомления отмечены как прочитанные", "info")
    return redirect(url_for("notifications.page"))
