"""Раунд игры: генерация заданий, переключение способов, сохранение состояния."""
from __future__ import annotations

import json
import time
from typing import Any

from content.curriculum import topic_by_slug
from content.generators import REGISTRY
from database import execute, query_one

DIFFICULTY_BY_MODE = {"practice": 1, "boss": 3}


def _method_list(topic_slug: str) -> list[str]:
    topic = topic_by_slug(topic_slug)
    if not topic:
        return []
    return [m["slug"] for m in topic["methods"]]


def next_method_slug(topic_slug: str, current: str | None) -> str:
    """Следующий способ объяснения по кругу."""
    methods = _method_list(topic_slug)
    if not methods:
        return ""
    if current not in methods:
        return methods[0]
    idx = methods.index(current)
    return methods[(idx + 1) % len(methods)]


def generator_for(topic_slug: str, method_slug: str | None) -> str:
    """Ключ генератора, соответствующий способу объяснения."""
    topic = topic_by_slug(topic_slug)
    if not topic:
        return ""
    generators = topic["generators"]
    for method in topic["methods"]:
        if method["slug"] == method_slug and method.get("example") in REGISTRY:
            return method["example"]
    return generators[0] if generators else ""


def build_task(generator_key: str, difficulty: int = 1) -> dict[str, Any]:
    fn = REGISTRY.get(generator_key)
    if not fn:
        raise KeyError(f"Генератор {generator_key} не найден")
    task = fn(difficulty)
    task["generator"] = generator_key
    return task


def create_round(
    learner_id: int,
    topic_slug: str,
    mode: str = "practice",
    task_count: int = 8,
    method_slug: str | None = None,
) -> tuple[int, dict[str, Any]]:
    """Создать раунд, вернуть (session_id, state)."""
    session_id = execute(
        "INSERT INTO play_sessions (learner_id, topic_slug, mode) VALUES (?, ?, ?)",
        (learner_id, topic_slug, mode),
    )
    methods = _method_list(topic_slug)
    start_method = method_slug if method_slug in methods else (methods[0] if methods else None)
    state: dict[str, Any] = {
        "topic": topic_slug,
        "mode": mode,
        "method": start_method,
        "methods": methods,
        "items": [],
        "total": task_count,
        "index": 0,
        "correct": 0,
        "answered": 0,
        "tasks_done": 0,
        "wrong_streak": 0,
        "combo": 0,
        "max_combo": 0,
        "xp": 0,
        "coins": 0,
        "hints_used": 0,
        "started": time.time(),
        "finished": False,
    }
    save_round(session_id, state)
    return session_id, state


def save_round(session_id: int, state: dict[str, Any]) -> None:
    execute("UPDATE play_sessions SET round_state = ? WHERE id = ?", (json.dumps(state, ensure_ascii=False), session_id))


def load_round(session_id: int) -> dict[str, Any] | None:
    row = query_one("SELECT round_state FROM play_sessions WHERE id = ?", (session_id,))
    if not row or not row["round_state"]:
        return None
    try:
        return json.loads(row["round_state"])
    except (ValueError, TypeError):
        return None


def current_item(state: dict[str, Any]) -> dict[str, Any] | None:
    items = state.get("items", [])
    index = state.get("index", 0)
    if index >= len(items):
        return None
    return items[index]


def ensure_item(state: dict[str, Any]) -> dict[str, Any] | None:
    """Получить текущее задание, при необходимости сгенерировав его."""
    items = state.setdefault("items", [])
    index = state.get("index", 0)
    total = state.get("total", len(items))
    if index >= total:
        return None
    difficulty = DIFFICULTY_BY_MODE.get(state.get("mode", "practice"), 1)
    while len(items) <= index:
        method = state.get("method")
        generator_key = state.get("generator") or generator_for(state["topic"], method)
        task = build_task(generator_key, difficulty)
        items.append({
            "generator": generator_key,
            "method": method,
            "task": task,
            "hints": 0,
            "attempts": 0,
            "answered": False,
            "correct": False,
            "time_ms": 0,
            "shown_at": time.time(),
        })
    return items[index]


def switch_method(state: dict[str, Any]) -> str:
    """Переключить способ объяснения (используется при ошибках и по кнопке)."""
    new_method = next_method_slug(state["topic"], state.get("method"))
    state["method"] = new_method
    state["wrong_streak"] = 0
    return new_method
