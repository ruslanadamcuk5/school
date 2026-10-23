"""Игровой цикл: раунды, ответы, подсказки, итоги."""
from __future__ import annotations

import time
from typing import Any

from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for

from config import get_config
from content.answer import check_answer, expected_display
from content.curriculum import topic_by_slug
from services import learners as learners_service
from services import progress as progress_service
from services import rewards as rewards_service
from services import rounds as rounds_service

bp = Blueprint("play", __name__)


def _current_round():
    """Загрузить состояние текущего раунда из сессии."""
    round_id = session.get("round_id")
    if not round_id:
        return None, None
    state = rounds_service.load_round(int(round_id))
    if not state:
        return None, None
    return int(round_id), state


def _require_learner():
    learner = learners_service.current_learner()
    if not learner:
        return None
    return learner


@bp.route("/play/<slug>")
def start_play(slug: str):
    learner = _require_learner()
    if not learner:
        return redirect(url_for("main.welcome"))
    topic = topic_by_slug(slug)
    if not topic:
        abort(404)
    cfg = get_config()
    method = request.args.get("method") or None
    round_id, _ = rounds_service.create_round(
        learner["id"], slug, mode="practice", task_count=cfg.TASKS_PER_ROUND, method_slug=method
    )
    session["round_id"] = round_id
    session["round_topic"] = slug
    return redirect(url_for("play.task_page", slug=slug))


@bp.route("/boss/<slug>")
def start_boss(slug: str):
    learner = _require_learner()
    if not learner:
        return redirect(url_for("main.welcome"))
    topic = topic_by_slug(slug)
    if not topic:
        abort(404)
    cfg = get_config()
    round_id, _ = rounds_service.create_round(
        learner["id"], slug, mode="boss", task_count=cfg.BOSS_TASKS, method_slug=None
    )
    session["round_id"] = round_id
    session["round_topic"] = slug
    return redirect(url_for("play.task_page", slug=slug))


@bp.route("/play/<slug>/task")
def task_page(slug: str):
    learner = _require_learner()
    if not learner:
        return redirect(url_for("main.welcome"))
    topic = topic_by_slug(slug)
    if not topic:
        abort(404)
    round_id, state = _current_round()
    if not state or state.get("topic") != slug:
        return redirect(url_for("play.start_play", slug=slug))

    item = rounds_service.ensure_item(state)
    if item is None:
        return redirect(url_for("play.result_page", slug=slug))
    # сохраняем сгенерированное задание, чтобы ответ проверялся для той же задачи
    rounds_service.save_round(round_id, state)

    method = next((m for m in topic["methods"] if m["slug"] == state.get("method")), None)
    cfg = get_config()
    mode = state.get("mode", "practice")
    total = state.get("total") or (cfg.TASKS_PER_ROUND if mode == "practice" else cfg.BOSS_TASKS)
    return render_template(
        "play.html",
        learner=learner,
        topic=topic,
        method=method,
        task=item["task"],
        index=state.get("index", 0),
        total=total,
        correct=state.get("correct", 0),
        combo=state.get("combo", 0),
        mode=mode,
        hints_left=max(0, cfg.MAX_HINTS - item.get("hints", 0)),
        learner_stats=progress_service.learner_stats(learner["id"]),
    )


@bp.route("/api/answer", methods=["POST"])
def api_answer():
    learner = _require_learner()
    if not learner:
        return jsonify({"ok": False, "error": "no_learner"}), 401
    round_id, state = _current_round()
    if not state:
        return jsonify({"ok": False, "error": "no_round"}), 404

    payload = request.get_json(silent=True) or request.form
    given = (payload.get("answer") or "").strip()
    item = rounds_service.ensure_item(state)
    if item is None or item.get("answered"):
        return jsonify({"ok": False, "error": "already_answered"}), 409

    task = item["task"]
    correct, expected = check_answer(given, task)
    now = time.time()
    item["time_ms"] = int((now - item.get("shown_at", now)) * 1000)
    item["attempts"] = item.get("attempts", 0) + 1
    item["given"] = given

    cfg = get_config()
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
        xp_gained = cfg.XP_PER_CORRECT
        coins_gained = cfg.COINS_PER_CORRECT
        if state.get("mode") == "boss":
            xp_gained = cfg.XP_PER_BOSS
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
        learner["id"],
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

    badges: list[dict[str, Any]] = []
    if state.get("daily"):
        rewards_service.save_daily_result(learner["id"], item.get("generator", ""), correct)
    if done:
        badges = rewards_service.grant_badges(learner["id"])
        if state.get("mode") == "boss":
            progress_service.mark_boss_cleared(learner["id"], state["topic"])
        progress_service.finish_session(
            round_id, state.get("tasks_done", state.get("answered", 0)),
            state.get("correct", 0), state.get("xp", 0)
        )

    hint = None
    if not correct:
        hints = task.get("hints", [])
        index = item.get("hints", 0)
        if index < min(len(hints), cfg.MAX_HINTS):
            hint = hints[index]
            item["hints"] = index + 1
            state["hints_used"] = state.get("hints_used", 0) + 1
            rounds_service.save_round(round_id, state)

    return jsonify({
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
    })


@bp.route("/api/hint", methods=["POST"])
def api_hint():
    learner = _require_learner()
    if not learner:
        return jsonify({"ok": False, "error": "no_learner"}), 401
    round_id, state = _current_round()
    if not state:
        return jsonify({"ok": False, "error": "no_round"}), 404
    cfg = get_config()
    item = rounds_service.ensure_item(state)
    if item is None:
        return jsonify({"ok": False, "error": "no_task"}), 404
    hints = item["task"].get("hints", [])
    index = item.get("hints", 0)
    if index >= min(len(hints), cfg.MAX_HINTS):
        return jsonify({"ok": False, "error": "no_hints"}), 409
    hint = hints[index]
    item["hints"] = index + 1
    state["hints_used"] = state.get("hints_used", 0) + 1
    rounds_service.save_round(round_id, state)
    return jsonify({"ok": True, "hint": hint, "left": max(0, cfg.MAX_HINTS - item["hints"])})


@bp.route("/api/switch-method", methods=["POST"])
def api_switch_method():
    """Ребёнок попросил объяснить тему по-другому."""
    learner = _require_learner()
    if not learner:
        return jsonify({"ok": False, "error": "no_learner"}), 401
    round_id, state = _current_round()
    if not state:
        return jsonify({"ok": False, "error": "no_round"}), 404
    new_method = rounds_service.switch_method(state)
    rounds_service.save_round(round_id, state)
    topic = topic_by_slug(state["topic"])
    method = next((m for m in topic["methods"] if m["slug"] == new_method), None)
    return jsonify({
        "ok": True,
        "method": new_method,
        "name": method["name"] if method else "",
        "explanation": method.get("explanation", "") if method else "",
    })


@bp.route("/play/<slug>/result")
def result_page(slug: str):
    learner = _require_learner()
    if not learner:
        return redirect(url_for("main.welcome"))
    topic = topic_by_slug(slug)
    if not topic:
        abort(404)
    round_id, state = _current_round()
    if not state or state.get("topic") != slug:
        return redirect(url_for("main.map_page"))

    total = state.get("total") or len(state.get("items", [])) or get_config().TASKS_PER_ROUND
    correct = state.get("correct", 0)
    stars = 0
    if state.get("mode") != "daily":
        stars = progress_service.apply_round_result(learner["id"], slug, correct, total)
    badges = rewards_service.grant_badges(learner["id"])
    progress_service.finish_session(
        round_id, state.get("answered", 0), correct, state.get("xp", 0)
    )
    items = [
        {
            "question": i["task"]["question"],
            "correct": i.get("correct"),
            "given": i.get("given", ""),
            "answer": expected_display(i["task"]),
            "solution": i["task"].get("solution", ""),
        }
        for i in state.get("items", [])
    ]
    session.pop("round_id", None)
    session.pop("round_topic", None)
    return render_template(
        "result.html",
        learner=learner,
        topic=topic,
        stars=stars,
        correct=correct,
        total=total,
        xp=state.get("xp", 0),
        coins=state.get("coins", 0),
        combo=state.get("max_combo", 0),
        mode=state.get("mode", "practice"),
        items=items,
        badges=badges,
    )


@bp.route("/daily/start", methods=["POST"])
def daily_start():
    """Запуск ежедневного задания (по одной задаче за раз)."""
    learner = _require_learner()
    if not learner:
        return redirect(url_for("main.welcome"))
    generator = request.form.get("generator")
    tasks = rewards_service.daily_status(learner["id"])
    pending = [t for t in tasks if not t["done"]]
    if pending:
        generator = generator or pending[0]["generator"]
    else:
        generator = tasks[0]["generator"]
    topic_slug = generator.split(".")[0]
    round_id, state = rounds_service.create_round(
        learner["id"], topic_slug, mode="daily", task_count=1, method_slug=None
    )
    state["generator"] = generator
    state["daily"] = True
    rounds_service.save_round(round_id, state)
    session["round_id"] = round_id
    session["round_topic"] = topic_slug
    return redirect(url_for("play.task_page", slug=topic_slug))
