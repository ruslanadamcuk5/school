"""API: геолокация ребёнка и карта для родителей.

Передача местоположения всегда включена: устройство присылает пачки точек в
``POST /location/points``. Родитель видит последние точки и трек за выбранный
день, а также может принудительно включить геолокацию на телефоне ребёнка.
"""
from __future__ import annotations

from datetime import date

from flask import jsonify, request

from database import query_one
from services import learners as learners_service
from services import locations as locations_service
from services import map_settings as map_settings_service

from . import bp
from .deps import (
    current_user,
    fail,
    json_body,
    learner,
    require_learner,
    require_user,
)

MAX_TZ = 840


def _tz() -> int:
    raw = request.args.get("tz")
    try:
        value = int(raw or 0)
    except (TypeError, ValueError):
        value = 0
    return max(-720, min(MAX_TZ, value))


def _day(default_tz: int) -> date:
    try:
        return locations_service.parse_day(request.args.get("date"), default_tz)
    except locations_service.LocationError as exc:
        fail(exc.status, exc.code, exc.message)


def _status_payload(learner_id: int, tz_minutes: int = 0) -> dict:
    info = locations_service.settings(learner_id)
    latest = locations_service.latest_point(learner_id, tz_minutes)
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


@bp.get("/location/status")
@require_learner
def location_status():
    profile = learner()
    return jsonify(_status_payload(int(profile["id"]), _tz()))


@bp.put("/location/status")
@require_learner
def location_set_status():
    """Совместимость со старыми сборками: передачу нельзя выключить."""
    profile = learner()
    json_body()
    locations_service.set_sharing(
        int(profile["id"]), True,
        by_user_id=int(current_user()["id"]) if current_user() else None,
    )
    payload = _status_payload(int(profile["id"]), _tz())
    payload["message"] = "Геолокация включена — родители видят, где ты находишься"
    return jsonify(payload)


@bp.post("/location/points")
@require_learner
def location_add_points():
    profile = learner()
    data = json_body()
    points = data.get("points")
    if points is None and ("lat" in data or "latitude" in data):
        points = [data]
    try:
        result = locations_service.record_points(
            int(profile["id"]), points, battery=data.get("battery")
        )
    except locations_service.LocationError as exc:
        fail(exc.status, exc.code, exc.message)
    return jsonify({"ok": True, **result})


@bp.post("/location/force/ack")
@require_learner
def location_ack_force():
    profile = learner()
    info = locations_service.ack_force(int(profile["id"]))
    return jsonify(
        {
            "ok": True,
            "settings": info,
            "force_pending": False,
            "message": "Команда включения геолокации выполнена",
        }
    )


# ------------------------------------------------------------------ родитель
def _parent_learner(learner_id: int):
    user = current_user()
    if not locations_service.can_parent_see(int(user["id"]), learner_id):
        fail(404, "not_found", "Профиль не найден")
    profile = learners_service.get_learner(learner_id)
    if profile is None:
        fail(404, "not_found", "Профиль не найден")
    return profile


@bp.get("/parent/locations")
@require_user("parent")
def parent_locations():
    user = current_user()
    tz_minutes = _tz()
    children = []
    for child in _parent_children(user):
        children.extend(locations_service.overview([child], tz_minutes))
    return jsonify(
        {
            "ok": True,
            "children": children,
            "date": locations_service.today_for_tz(tz_minutes).isoformat(),
            "retention_days": locations_service.RETENTION_DAYS,
            "map": map_settings_service.public_settings(),
        }
    )


def _parent_children(user) -> list:
    rows = []
    for child in _parent_child_users(int(user["id"])):
        profile = query_one(
            """SELECT l.* FROM learner_accounts la
                 JOIN learners l ON l.id = la.learner_id
                WHERE la.user_id = ?""",
            (int(child["id"]),),
        )
        if profile is None:
            profile = query_one("SELECT * FROM learners WHERE user_id = ?", (int(child["id"]),))
        if profile is not None:
            rows.append(profile)
    # Если один и тот же профиль привязан дважды — не дублируем.
    unique = {}
    for row in rows:
        unique[int(row["id"])] = row
    return list(unique.values())


def _parent_child_users(parent_id: int) -> list:
    from services import auth as auth_service

    return [
        child for child in auth_service.children_of(parent_id)
        if child["role"] == auth_service.ROLE_STUDENT
    ]


@bp.get("/parent/children/<int:learner_id>/location")
@require_user("parent")
def parent_child_location(learner_id: int):
    profile = _parent_learner(learner_id)
    tz_minutes = _tz()
    day = _day(tz_minutes)
    data = locations_service.trail(learner_id, day, tz_minutes)
    return jsonify(
        {
            "ok": True,
            "learner": {
                "id": int(profile["id"]),
                "name": profile["name"],
                "avatar": profile["avatar"],
                "grade": int(profile["grade"] or 1),
            },
            **data,
            "map": map_settings_service.public_settings(),
            "retention_days": locations_service.RETENTION_DAYS,
        }
    )


@bp.post("/parent/children/<int:learner_id>/location/force")
@require_user("parent")
def parent_force_location(learner_id: int):
    profile = _parent_learner(learner_id)
    user = current_user()
    info = locations_service.force_request(learner_id, int(user["id"]))
    return jsonify(
        {
            "ok": True,
            "message": (
                f"Включаем GPS на телефоне: {profile['name']}. "
                "Точка появится на карте автоматически."
            ),
            "settings": info,
            "force_pending": info["force_pending"],
        }
    )


@bp.post("/parent/children/<int:learner_id>/location/request")
@require_user("parent")
def parent_request_location(learner_id: int):
    """Совместимость со старыми сборками: просьба теперь принудительная."""
    return parent_force_location(learner_id)
