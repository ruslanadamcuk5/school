"""API удалённой помощи: экран ребёнка и управление для родителя."""
from __future__ import annotations

from functools import wraps

from flask import jsonify, request, send_file

from services import remote as remote_service

from . import bp
from .deps import current_user, fail, int_arg, json_body, require_user


def _guard(view):
    """Превратить ошибки сервиса в обычный JSON-ответ API."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except remote_service.RemoteError as exc:
            fail(exc.status, exc.code, exc.message)

    return wrapper


def _learner_id(data) -> int:
    try:
        value = int(data.get("learner_id"))
    except (TypeError, ValueError):
        fail(400, "bad_learner", "Нужен профиль ребёнка")
    return value


# ------------------------------------------------------------------ родитель
@bp.post("/remote/start")
@require_user("parent")
@_guard
def remote_start():
    user = current_user()
    data = json_body()
    session = remote_service.start(int(user["id"]), _learner_id(data))
    return jsonify({"ok": True, "session": session})


@bp.get("/remote/current")
@require_user("parent")
@_guard
def remote_current():
    user = current_user()
    learner_id = int_arg("learner_id", 0, minimum=1)
    session = remote_service.current(int(user["id"]), int(learner_id or 0))
    return jsonify({"ok": True, "session": session})


@bp.get("/remote/frame")
@require_user("parent")
@_guard
def remote_frame():
    user = current_user()
    session_id = int_arg("session_id", 0, minimum=1)
    path = remote_service.frame_path_for_parent(int(user["id"]), int(session_id or 0))
    response = send_file(
        path,
        mimetype="image/jpeg",
        as_attachment=False,
        conditional=False,
        max_age=0,
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


@bp.post("/remote/command")
@require_user("parent")
@_guard
def remote_command():
    user = current_user()
    data = json_body()
    try:
        session_id = int(data.get("session_id"))
    except (TypeError, ValueError):
        fail(400, "bad_session", "Нужна сессия помощи")
    try:
        command_id = remote_service.queue_command(
            int(user["id"]),
            session_id,
            str(data.get("kind") or ""),
            float(data.get("x") or 0),
            float(data.get("y") or 0),
            float(data.get("x2") or 0),
            float(data.get("y2") or 0),
            int(data.get("duration_ms") or 0),
        )
    except (TypeError, ValueError):
        fail(400, "bad_command", "Неверные координаты команды")
    return jsonify({"ok": True, "id": command_id})


@bp.post("/remote/stop")
@require_user("parent", "student")
@_guard
def remote_stop():
    user = current_user()
    data = json_body()
    try:
        session_id = int(data.get("session_id"))
    except (TypeError, ValueError):
        fail(400, "bad_session", "Нужна сессия помощи")
    session = remote_service.stop(int(user["id"]), user["role"], session_id)
    return jsonify({"ok": True, "session": session})


# ------------------------------------------------------------------ ребёнок
@bp.get("/remote/incoming")
@require_user("student")
@_guard
def remote_incoming():
    user = current_user()
    session = remote_service.incoming(int(user["id"]))
    return jsonify({"ok": True, "session": session})


@bp.post("/remote/accept")
@require_user("student")
@_guard
def remote_accept():
    user = current_user()
    data = json_body()
    try:
        session_id = int(data.get("session_id"))
    except (TypeError, ValueError):
        fail(400, "bad_session", "Нужна сессия помощи")
    session = remote_service.accept(
        int(user["id"]),
        session_id,
        bool(data.get("can_control")),
    )
    return jsonify({"ok": True, "session": session})


@bp.post("/remote/decline")
@require_user("student")
@_guard
def remote_decline():
    user = current_user()
    data = json_body()
    try:
        session_id = int(data.get("session_id"))
    except (TypeError, ValueError):
        fail(400, "bad_session", "Нужна сессия помощи")
    session = remote_service.decline(int(user["id"]), session_id)
    return jsonify({"ok": True, "session": session})


@bp.post("/remote/frame")
@require_user("student")
@_guard
def remote_frame_upload():
    user = current_user()
    session_id = int_arg("session_id", 0, minimum=1)
    width = int_arg("width", 0, minimum=0, maximum=5000)
    height = int_arg("height", 0, minimum=0, maximum=5000)
    data = request.get_data(cache=False)
    session = remote_service.store_frame(
        int(user["id"]),
        int(session_id or 0),
        data,
        int(width or 0),
        int(height or 0),
    )
    return jsonify({"ok": True, "session": session})


@bp.get("/remote/commands")
@require_user("student")
@_guard
def remote_commands():
    user = current_user()
    session_id = int_arg("session_id", 0, minimum=1)
    after_id = int_arg("after_id", 0, minimum=0)
    commands = remote_service.take_commands(
        int(user["id"]), int(session_id or 0), int(after_id or 0)
    )
    return jsonify({"ok": True, "commands": commands})


@bp.post("/remote/heartbeat")
@require_user("student")
@_guard
def remote_heartbeat():
    user = current_user()
    data = json_body()
    try:
        session_id = int(data.get("session_id"))
    except (TypeError, ValueError):
        fail(400, "bad_session", "Нужна сессия помощи")
    session = remote_service.heartbeat(
        int(user["id"]),
        session_id,
        bool(data.get("can_control")),
    )
    return jsonify({"ok": True, "session": session})
