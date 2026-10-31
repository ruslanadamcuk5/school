"""Веб-геолокация ребёнка: постоянная передача точек из браузера."""
from __future__ import annotations

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from services import learners as learners_service
from services import locations as locations_service

bp = Blueprint("location", __name__)


def _learner():
    return learners_service.current_learner()


def _tz() -> int:
    try:
        return locations_service.clamp_tz(int(request.args.get("tz") or 0))
    except (TypeError, ValueError):
        return 0


def _status_payload(learner_id: int) -> dict:
    info = locations_service.settings(learner_id)
    latest = locations_service.latest_point(learner_id, _tz())
    return {
        "ok": True,
        "enabled": True,
        "settings": info,
        "force_pending": info["force_pending"],
        "force_requested_at": info["force_requested_at"],
        "force_ack_at": info["force_ack_at"],
        "last_point": latest,
        "retention_days": locations_service.RETENTION_DAYS,
    }


@bp.route("/location")
def page():
    profile = _learner()
    if profile is None:
        return redirect(url_for("main.welcome"))
    return render_template(
        "location/index.html",
        learner=profile,
        settings=locations_service.settings(int(profile["id"])),
        retention_days=locations_service.RETENTION_DAYS,
    )


@bp.route("/location/status")
def status():
    profile = _learner()
    if profile is None:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    return jsonify(_status_payload(int(profile["id"])))


@bp.route("/location/status", methods=["POST"])
def set_status():
    """Совместимость со старыми сборками: передачу нельзя выключить."""
    profile = _learner()
    if profile is None:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    locations_service.set_sharing(int(profile["id"]), True)
    payload = _status_payload(int(profile["id"]))
    payload["message"] = "Геолокация включена — родители видят, где ты находишься"
    return jsonify(payload)


def _upload_learner():
    """Профиль, которому разрешено писать точки с этого запроса.

    Геолокацию передаёт только телефон ребёнка. Аккаунт родителя (даже если
    он открыл карту ребёнка) не должен сохранять свои маршруты в чужой трек.
    """
    profile = _learner()
    if profile is None:
        return None, "unauthorized"
    from services import auth

    user = auth.current_user()
    if user is not None:
        if user["role"] != auth.ROLE_STUDENT:
            return None, "forbidden"
        from database import query_one

        linked = query_one(
            "SELECT 1 AS ok FROM learner_accounts WHERE learner_id = ? AND user_id = ?",
            (int(profile["id"]), int(user["id"])),
        )
        if not linked:
            return None, "forbidden"
    return profile, None


@bp.route("/location/points", methods=["POST"])
def points():
    profile, error = _upload_learner()
    if error == "unauthorized":
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    if error == "forbidden":
        return jsonify({
            "ok": False,
            "error": "forbidden",
            "message": "Геолокацию передаёт только телефон ребёнка",
        }), 403
    data = request.get_json(silent=True) or {}
    raw = data.get("points")
    if raw is None and ("lat" in data or "latitude" in data):
        raw = [data]
    try:
        result = locations_service.record_points(
            int(profile["id"]), raw, battery=data.get("battery")
        )
    except locations_service.LocationError as exc:
        return jsonify({"ok": False, "error": exc.code, "message": exc.message}), exc.status
    return jsonify({"ok": True, **result})


@bp.route("/location/force/ack", methods=["POST"])
def ack_force():
    profile = _learner()
    if profile is None:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    info = locations_service.ack_force(int(profile["id"]))
    return jsonify(
        {
            "ok": True,
            "settings": info,
            "force_pending": False,
            "message": "Команда включения геолокации выполнена",
        }
    )
