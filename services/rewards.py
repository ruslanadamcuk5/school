"""Награды: значки и ежедневное задание."""
from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from content.achievements import evaluate_badges
from database import execute, query_all
from services.progress import daily_answer_state, learner_stats, save_daily_answer

# Генераторы для ежедневного челленджа (разные темы — так задание разнообразно)
DAILY_POOL = [
    "numbers_1000.place_value",
    "add_sub_1000.add_column",
    "add_sub_1000.sub_column",
    "mult_div_table.mult",
    "mult_div_table.div",
    "mult_div_100.mult",
    "remainder.divide",
    "expressions.order",
    "equations.unknown_addend",
    "equations.unknown_factor",
    "fractions.from_parts",
    "fractions.of_number",
    "units.length",
    "units.time",
    "perimeter_area.area",
    "perimeter_area.perimeter",
    "word_problems.unit_rate",
    "data.chart",
    "mult_div_column.mult",
    "divisibility.by_3_9",
    "fractions_ops.add_same",
    "motion.speed",
    "area_units.square",
    "time_calc.clock",
]


def owned_badges(learner_id: int) -> set[str]:
    rows = query_all("SELECT badge_key FROM badges WHERE learner_id = ?", (learner_id,))
    return {r["badge_key"] for r in rows}


def badge_list(learner_id: int) -> list:
    return query_all(
        "SELECT * FROM badges WHERE learner_id = ? ORDER BY earned_at DESC", (learner_id,)
    )


def grant_badges(learner_id: int) -> list[dict[str, Any]]:
    """Выдать новые значки. Возвращает список новых достижений."""
    stats = learner_stats(learner_id)
    owned = owned_badges(learner_id)
    new_badges = evaluate_badges(stats, owned)
    granted: list[dict[str, Any]] = []
    for badge in new_badges:
        execute(
            "INSERT OR IGNORE INTO badges (learner_id, badge_key) VALUES (?, ?)",
            (learner_id, badge["key"]),
        )
        granted.append({
            "key": badge["key"],
            "name": badge["name"],
            "icon": badge["icon"],
            "description": badge["description"],
        })
    return granted


def daily_tasks(day: str | None = None) -> list[str]:
    """Детерминированный набор заданий на день."""
    day = day or date.today().isoformat()
    digest = hashlib.sha256(day.encode("utf-8")).digest()
    chosen: list[str] = []
    used_topics: set[str] = set()
    index = 0
    while len(chosen) < 3 and index < len(DAILY_POOL) * 4:
        candidate = DAILY_POOL[(digest[0] + index * 7) % len(DAILY_POOL)]
        topic = candidate.split(".")[0]
        if topic not in used_topics:
            chosen.append(candidate)
            used_topics.add(topic)
        index += 1
    return chosen


def daily_status(learner_id: int, day: str | None = None) -> list[dict[str, Any]]:
    """Состояние ежедневного задания для ученика."""
    from content.curriculum import topic_by_slug

    day = day or date.today().isoformat()
    out = []
    for generator in daily_tasks(day):
        state = daily_answer_state(learner_id, day, generator)
        topic_slug, _, key = generator.partition(".")
        topic = topic_by_slug(topic_slug)
        out.append({
            "generator": generator,
            "topic": topic["title"] if topic else topic_slug,
            "icon": topic["icon"] if topic else "⭐",
            "label": key.replace("_", " "),
            "done": state is not None,
            "correct": state,
        })
    return out


def daily_completed(learner_id: int, day: str | None = None) -> bool:
    return all(item["done"] for item in daily_status(learner_id, day))


def save_daily_result(learner_id: int, generator: str, correct: bool, day: str | None = None) -> None:
    day = day or date.today().isoformat()
    save_daily_answer(learner_id, day, generator, correct)
