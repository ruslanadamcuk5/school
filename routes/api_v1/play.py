"""API: тренировочные раунды и ежедневные задания.

Раунд хранится на сервере в ``play_sessions.round_state``; клиент передаёт
``round_id`` в каждом запросе. Ответы никогда не отдаются до проверки.
"""
from __future__ import annotations

import time
from typing import Any

from flask import jsonify, request

from config import get_config
from content.answer import check_answer, expected_display
from content.curriculum import topic_by_slug
from database import query_one
from services import progress as progress_service
from services import rewards as rewards_service
from services import rounds as rounds_service
from services import shop as shop_service
from services import topics as topics_service

from . import bp
from .deps import fail, json_body, learner, require_learner


def _topic_title(slug: str) -> str:
    topic = topic_by_slug(slug)
    if topic:
        return topic["title"]
    row = topics_service.get_topic(slug)
    return row["title"] if row else slug


def _methods(slug: str) -> list[dict]:
    topic = topic_by_slug(slug)
    if not topic:
        return []
    return [
        {"slug": method["slug"], "name": method["name"]}
        for method in topic.get("methods", [])
    ]


def _method_name(slug: str, method_slug: str | None) -> str:
    for method in _methods(slug):
        if method["slug"] == method_slug:
            return method["name"]
    return ""


def _load(round_id: int) -> tuple[Any, dict]:
    profile = learner()
    session_row = query_one(
        "SELECT * FROM play_sessions WHERE id = ? AND learner_id = ?",
        (round_id, profile["id"]),
    )
    state = rounds_service.load_round(round_id)
    if session_row is None or not state:
        fail(404, "round_not_found", "Тренировка не найдена. Начните заново.")
    return session_row, state


def _task_payload(item: dict, state: dict) -> dict:
    task = item["task"]
    profile = learner()
    hint_base, hint_credits = shop_service.hints_budget(profile["id"])
    total = state.get("total") or len(state.get("items", []))
    choices = task.get("choices") or []
    return {
        "question": task.get("question", ""),
        "answer_type": task.get("answer_type")
        or ("choice" if choices else "number"),
        "choices": choices,
        "widget": task.get("widget"),
        "difficulty": task.get("difficulty", 1),
        "generator": task.get("generator"),
        "index": state.get("index", 0),
        "total": total,
        "method": {
            "slug": state.get("method"),
            "name": _method_name(state.get("topic", ""), state.get("method")),
        },
        "methods": _methods(state.get("topic", "")),
        "hints_left": max(0, hint_base + hint_credits - item.get("hints", 0)),
        "can_switch_method": len(state.get("methods") or []) > 1,
    }


def _round_summary(state: dict) -> dict:
    return {
        "correct": state.get("correct", 0),
        "answered": state.get("answered", 0),
        "xp": state.get("xp", 0),
        "coins": state.get("coins", 0),
        "combo": state.get("combo", 0),
        "max_combo": state.get("max_combo", 0),
        "index": state.get("index", 0),
        "total": state.get("total") or len(state.get("items", [])),
        "mode": state.get("mode", "practice"),
    }


@bp.post("/play/start")
@require_learner
def start():
    profile = learner()
    data = json_body()
    slug = str(data.get("topic_slug") or data.get("slug") or "").strip()
    topic = topic_by_slug(slug)
    if topic is None:
        fail(404, "not_found", "Тренировочная тема не найдена")

    cfg = get_config()
    mode = "boss" if str(data.get("mode") or "") == "boss" else "practice"
    task_count = cfg.BOSS_TASKS if mode == "boss" else cfg.TASKS_PER_ROUND
    method = str(data.get("method") or "").strip() or None

    round_id, state = rounds_service.create_round(
        profile["id"], slug, mode=mode, task_count=task_count, method_slug=method
    )
    item = rounds_service.ensure_item(state)
    rounds_service.save_round(round_id, state)
    if item is None:
        fail(500, "no_tasks", "Не удалось создать задание. Попробуйте другую тему.")

    return jsonify(
        {
            "ok": True,
            "round_id": round_id,
            "topic": {"slug": slug, "title": topic["title"], "icon": topic.get("icon")},
            "task": _task_payload(item, state),
            "state": _round_summary(state),
            "done": False,
        }
    )


@bp.get("/play/<int:round_id>")
@require_learner
def current(round_id: int):
    _, state = _load(round_id)
    item = rounds_service.ensure_item(state)
    rounds_service.save_round(round_id, state)
    if item is None:
        return jsonify(
            {
                "ok": True,
                "round_id": round_id,
                "done": True,
                "state": _round_summary(state),
                "task": None,
            }
        )
    return jsonify(
        {
            "ok": True,
            "round_id": round_id,
            "done": False,
            "topic": {
                "slug": state.get("topic"),
                "title": _topic_title(state.get("topic", "")),
            },
            "task": _task_payload(item, state),
            "state": _round_summary(state),
        }
    )


@bp.post("/play/<int:round_id>/answer")
@require_learner
def answer(round_id: int):
    profile = learner()
    _, state = _load(round_id)
    payload = request.get_json(silent=True) or request.form
    given = str(payload.get("answer") or "").strip()

    item = rounds_service.ensure_item(state)
    if item is None or item.get("answered"):
        fail(409, "already_answered", "На этот вопрос уже ответили")

    cfg = get_config()
    task = item["task"]
    correct, expected = check_answer(given, task)
    now = time.time()
    item["time_ms"] = int((now - item.get("shown_at", now)) * 1000)
    item["attempts"] = item.get("attempts", 0) + 1
    item["given"] = given

    state["answered"] = state.get("answered", 0) + 1
    xp_gained = 0
    coins_gained = 0
    final = False

    if correct:
        item["answered"] = True
        item["correct"] = True
        state["correct"] = state.get("correct", 0) + 1
        state["combo"] = state.get("combo", 0) + 1
        state["max_combo"] = max(state.get("max_combo", 0), state["combo"])
        state["wrong_streak"] = 0
        xp_gained, coins_gained = progress_service.reward_amounts(
            profile["id"], state.get("mode", "practice")
        )
        state["xp"] = state.get("xp", 0) + xp_gained
        state["coins"] = state.get("coins", 0) + coins_gained
        final = True
    else:
        state["combo"] = 0
        state["wrong_streak"] = state.get("wrong_streak", 0) + 1
        if item["attempts"] >= 2:
            item["answered"] = True
            final = True

    switched = False
    if final and not correct and state.get("wrong_streak", 0) >= 2:
        rounds_service.switch_method(state)
        switched = True

    if final:
        state["index"] = state.get("index", 0) + 1
        state["tasks_done"] = state.get("tasks_done", 0) + 1

    progress_service.record_attempt(
        profile["id"],
        state["topic"],
        state.get("method"),
        item.get("generator"),
        correct,
        given,
        str(expected),
        item.get("time_ms", 0),
        item.get("hints", 0),
        state.get("mode", "practice"),
    )

    done = state.get("index", 0) >= state.get("total", len(state.get("items", [])))
    rounds_service.save_round(round_id, state)

    badges: list[dict] = []
    if state.get("daily"):
        rewards_service.save_daily_result(
            profile["id"], item.get("generator", ""), correct
        )
    if done:
        badges = rewards_service.grant_badges(profile["id"])
        if state.get("mode") == "boss":
            progress_service.mark_boss_cleared(profile["id"], state["topic"])
        progress_service.finish_session(
            round_id,
            state.get("tasks_done", state.get("answered", 0)),
            state.get("correct", 0),
            state.get("xp", 0),
        )

    hint = None
    if not correct:
        hints = task.get("hints", [])
        index = item.get("hints", 0)
        base, credits = shop_service.hints_budget(profile["id"])
        if index < min(len(hints), base + credits):
            hint = hints[index]
            item["hints"] = index + 1
            if index >= base:
                shop_service.consume_hint_credit(profile["id"])
            state["hints_used"] = state.get("hints_used", 0) + 1
            rounds_service.save_round(round_id, state)

    return jsonify(
        {
            "ok": True,
            "correct": correct,
            "retry": not final,
            "correct_answer": expected_display(task),
            "solution": task.get("solution", ""),
            "xp": xp_gained,
            "coins": coins_gained,
            "combo": state.get("combo", 0),
            "hints_used": item.get("hints", 0),
            "hint": hint,
            "method_switched": switched,
            "method": state.get("method"),
            "done": done,
            "badges": badges,
            "state": _round_summary(state),
        }
    )


@bp.post("/play/<int:round_id>/hint")
@require_learner
def hint(round_id: int):
    _, state = _load(round_id)
    cfg = get_config()
    item = rounds_service.ensure_item(state)
    if item is None:
        fail(404, "no_task", "Задание не найдено")
    hints = item["task"].get("hints", [])
    index = item.get("hints", 0)
    base, credits = shop_service.hints_budget(profile["id"])
    if index >= min(len(hints), base + credits):
        fail(409, "no_hints", "Подсказки закончились")
    text = hints[index]
    item["hints"] = index + 1
    if index >= base:
        shop_service.consume_hint_credit(profile["id"])
    state["hints_used"] = state.get("hints_used", 0) + 1
    rounds_service.save_round(round_id, state)
    return jsonify(
        {
            "ok": True,
            "hint": text,
            "left": max(0, base + credits - item["hints"]),
        }
    )


@bp.post("/play/<int:round_id>/switch-method")
@require_learner
def switch_method(round_id: int):
    _, state = _load(round_id)
    new_method = rounds_service.switch_method(state)
    rounds_service.save_round(round_id, state)
    topic = topic_by_slug(state["topic"])
    method = next(
        (m for m in (topic or {}).get("methods", []) if m["slug"] == new_method), None
    )
    return jsonify(
        {
            "ok": True,
            "method": new_method,
            "name": method["name"] if method else "",
            "explanation": method.get("explanation", "") if method else "",
        }
    )


@bp.get("/play/<int:round_id>/result")
@require_learner
def result(round_id: int):
    profile = learner()
    _, state = _load(round_id)

    if not state.get("result_applied"):
        stars = 0
        if state.get("mode") != "daily":
            stars = progress_service.apply_round_result(
                profile["id"],
                state["topic"],
                state.get("correct", 0),
                state.get("total") or len(state.get("items", [])),
            )
        state["result_applied"] = True
        state["stars"] = stars
        rounds_service.save_round(round_id, state)
    else:
        stars = state.get("stars", 0)

    badges = rewards_service.grant_badges(profile["id"])
    items = [
        {
            "question": item["task"]["question"],
            "correct": bool(item.get("correct")),
            "given": item.get("given", ""),
            "answer": expected_display(item["task"]),
            "solution": item["task"].get("solution", ""),
        }
        for item in state.get("items", [])
    ]
    return jsonify(
        {
            "ok": True,
            "stars": stars,
            "correct": state.get("correct", 0),
            "total": state.get("total") or len(items),
            "xp": state.get("xp", 0),
            "coins": state.get("coins", 0),
            "max_combo": state.get("max_combo", 0),
            "mode": state.get("mode", "practice"),
            "items": items,
            "badges": badges,
        }
    )


# ------------------------------------------------------------------ ежедневные задания
@bp.get("/daily")
@require_learner
def daily():
    profile = learner()
    tasks = rewards_service.daily_status(profile["id"])
    return jsonify(
        {
            "ok": True,
            "tasks": tasks,
            "done": all(item["done"] for item in tasks),
        }
    )


@bp.post("/daily/start")
@require_learner
def daily_start():
    profile = learner()
    data = json_body()
    generator = str(data.get("generator") or "").strip()
    tasks = rewards_service.daily_status(profile["id"])
    pending = [item for item in tasks if not item["done"]]
    if pending:
        generator = generator or pending[0]["generator"]
    elif tasks:
        generator = generator or tasks[0]["generator"]
    else:
        fail(409, "no_daily", "На сегодня заданий нет")

    slug = generator.split(".")[0]
    round_id, state = rounds_service.create_round(
        profile["id"], slug, mode="daily", task_count=1, method_slug=None
    )
    state["generator"] = generator
    state["daily"] = True
    item = rounds_service.ensure_item(state)
    rounds_service.save_round(round_id, state)
    if item is None:
        fail(500, "no_task", "Не удалось создать задание")

    return jsonify(
        {
            "ok": True,
            "round_id": round_id,
            "topic": {"slug": slug, "title": _topic_title(slug)},
            "task": _task_payload(item, state),
            "state": _round_summary(state),
        }
    )
