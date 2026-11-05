"""API: 3D-квесты по темам учебных пособий.

Сценарий и правильные ответы живут на сервере: клиент получает вопросы,
варианты и подсказки, но не ответы. Каждая станция проверяется отдельно.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import jsonify

from services import quests as quests_service

from . import bp
from .deps import fail, int_arg, json_body, learner, require_learner


def _call(fn: Callable[..., Any], *args: Any):
    """Превратить доменную ошибку квеста в ответ API."""
    try:
        return fn(*args)
    except quests_service.QuestError as exc:
        fail(exc.status, exc.code, exc.message)


@bp.get("/quests")
@require_learner
def quests_catalog():
    profile = learner()
    payload = _call(quests_service.list_quests, profile, int_arg("subject_id"))
    return jsonify({"ok": True, **payload})


@bp.get("/quests/<slug>")
@require_learner
def quest_detail(slug: str):
    profile = learner()
    episode = _call(quests_service.quest_detail, profile, slug)
    return jsonify({"ok": True, "quest": episode})


@bp.post("/quests/<slug>/start")
@require_learner
def quest_start(slug: str):
    profile = learner()
    run = _call(quests_service.start_run, profile, slug)
    return jsonify({"ok": True, **run})


@bp.get("/quests/runs/<run_id>")
@require_learner
def quest_run(run_id: str):
    profile = learner()
    run = _call(quests_service.get_run, profile, run_id)
    return jsonify({"ok": True, **run})


@bp.post("/quests/runs/<run_id>/check")
@require_learner
def quest_check(run_id: str):
    profile = learner()
    data = json_body()
    station = data.get("station")
    if isinstance(station, str) and station.strip().isdigit():
        station = int(station)
    try:
        station = int(station)
    except (TypeError, ValueError):
        fail(400, "bad_station", "Не указана станция")
    result = _call(
        quests_service.check_station, profile, run_id, station, data.get("answer")
    )
    return jsonify({"ok": True, **result})


@bp.post("/quests/runs/<run_id>/finish")
@require_learner
def quest_finish(run_id: str):
    profile = learner()
    result = _call(quests_service.finish_run, profile, run_id)
    return jsonify({"ok": True, **result})
