"""API звукового вызова ребёнка: родитель включает громкий сигнал на телефоне."""
from __future__ import annotations

from functools import wraps

from flask import jsonify

from services import locations as locations_service
from services import sound as sound_service

from . import bp
from .deps import (
    current_user,
    fail,
    int_arg,
    json_body,
    learner,
    require_learner,
    require_user,
)


def _guard(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except sound_service.SoundError as exc:
            fail(exc.status, exc.code, exc.message)

    return wrapper


def _owned_learner(learner_id: int) -> int:
    """Проверить, что ребёнок принадлежит вошедшему родителю."""
    user = current_user()
    if not locations_service.can_parent_see(int(user["id"]), int(learner_id)):
        fail(404, "not_found", "Ребёнок не найден")
    return int(learner_id)


@bp.post("/parent/children/<int:learner_id>/sound")
@require_user("parent")
@_guard
def parent_sound_call(learner_id: int):
    """Попросить телефон ребёнка громко зазвонить."""
    learner_id = _owned_learner(learner_id)
    user = current_user()
    result = sound_service.request(learner_id, int(user["id"]))
    return jsonify({"ok": True, **result})


@bp.get("/parent/children/<int:learner_id>/sound")
@require_user("parent")
@_guard
def parent_sound_status(learner_id: int):
    """Последняя команда звука: пригодится для статуса в кабинете родителя."""
    learner_id = _owned_learner(learner_id)
    return jsonify({"ok": True, "command": sound_service.latest(learner_id)})


@bp.get("/sound/command")
@require_learner
@_guard
def child_sound_command():
    """Новая команда для телефона ребёнка (опрос из фоновой службы)."""
    profile = learner()
    after_id = int_arg("after_id", 0, minimum=0) or 0
    command = sound_service.pending(int(profile["id"]), after_id)
    return jsonify({"ok": True, "command": command})


@bp.post("/sound/command/<int:command_id>/ack")
@require_learner
@_guard
def child_sound_ack(command_id: int):
    """Телефон ребёнка сообщает, что звонок начался, закончился или не удался."""
    profile = learner()
    data = json_body()
    command = sound_service.ack(
        int(profile["id"]),
        int(command_id),
        str(data.get("status") or "done"),
        str(data.get("mode") or ""),
        str(data.get("detail") or ""),
    )
    return jsonify({"ok": True, "command": command})
