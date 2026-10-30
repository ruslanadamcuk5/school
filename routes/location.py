"""Веб-геолокация ребёнка: согласие и передача точек из браузера."""
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
        "enabled": info["enabled"],
        "settings": info,
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
    profile = _learner()
    if profile is None:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or request.form
    if "enabled" not in data:
        return jsonify(
            {"ok": False, "error": "enabled_required", "message": "Укажите enabled"}
        ), 400
    enabled = str(data.get("enabled")).lower() in ("1", "true", "yes", "on")
    locations_service.set_sharing(int(profile["id"]), enabled)
    payload = _status_payload(int(profile["id"]))
    payload["message"] = (
        "Геолокация включена — родители видят, где ты находишься"
        if enabled
        else "Передача геолокации остановлена"
    )
    return jsonify(payload)


@bp.route("/location/points", methods=["POST"])
def points():
    profile = _learner()
    if profile is None:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
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


@bp.route("/location/history", methods=["DELETE"])
def clear_history():
    profile = _learner()
    if profile is None:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    removed = locations_service.clear_history(int(profile["id"]))
    return jsonify(
        {
            "ok": True,
            "removed": removed,
            "message": "История геолокации удалена",
            "settings": locations_service.settings(int(profile["id"])),
        }
    )
