"""Прогресс ученика: XP, уровни, звёзды, серии, статистика."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any

from config import get_config
from database import execute, query_all, query_one

LEVEL_THRESHOLDS = [
    0, 60, 150, 280, 450, 650, 900, 1200, 1550, 1950, 2400, 2900,
    3500, 4200, 5000, 6000, 7000, 8200, 9500, 11000, 13000, 15000,
    17500, 20000, 23000, 26000, 30000, 35000, 40000, 46000, 53000,
]


# ------------------------------------------------------------------ уровни
def level_for_xp(xp: int) -> int:
    level = 1
    for index, threshold in enumerate(LEVEL_THRESHOLDS):
        if xp >= threshold:
            level = index + 1
    return level


def level_info(xp: int) -> dict[str, Any]:
    level = level_for_xp(xp)
    current = LEVEL_THRESHOLDS[level - 1]
    nxt = LEVEL_THRESHOLDS[level] if level < len(LEVEL_THRESHOLDS) else current + 5000
    need = max(0, nxt - xp)
    percent = 100 if need == 0 else int(100 * (xp - current) / (nxt - current))
    return {
        "level": level,
        "xp": xp,
        "current_threshold": current,
        "next_threshold": nxt,
        "need": need,
        "percent": max(0, min(100, percent)),
        "title": level_titles(level),
    }


def level_titles(level: int) -> str:
    titles = [
        "Новичок", "Ученик", "Знаток", "Умелец", "Исследователь",
        "Мастер", "Эксперт", "Легенда",
    ]
    return titles[min(level - 1, len(titles) - 1)]


def total_xp(learner) -> int:
    """Заработанный опыт: свободный остаток + потраченный в магазине.

    Уровень считается по этой сумме, поэтому покупки в магазине не понижают
    ребёнка в уровне — тратится только «свободный» опыт.
    """
    spent = 0
    try:
        spent = int(learner["xp_spent"] or 0)
    except (KeyError, IndexError, TypeError, ValueError):
        spent = 0
    return int(learner["xp"] or 0) + spent


def stars_for(correct: int, total: int) -> int:
    if total <= 0:
        return 0
    accuracy = correct / total
    if correct == total:
        return 3
    if accuracy >= 0.75:
        return 2
    if accuracy >= 0.5:
        return 1
    return 0


# --------------------------------------------------------------- серии дней
def touch_day(learner_id: int) -> int:
    """Обновить серию дней. Возвращает новую длину серии."""
    learner = query_one("SELECT streak_days, last_day FROM learners WHERE id = ?", (learner_id,))
    if not learner:
        return 0
    today = date.today()
    last = learner["last_day"]
    streak = learner["streak_days"] or 0
    if last:
        try:
            last_date = datetime.strptime(last, "%Y-%m-%d").date()
        except ValueError:
            last_date = None
        if last_date == today:
            return streak
        if last_date == today - timedelta(days=1):
            streak += 1
        else:
            # Щит серии из магазина спасает огонёк ровно за один пропущенный
            # день (позавчера занимался, вчера — нет). Если пропущено больше,
            # серия начинается заново, иначе щит «съедал» бы любую паузу.
            from services import shop as shop_service

            gap_ok = last_date == today - timedelta(days=2)
            if streak > 0 and gap_ok and shop_service.consume_shield(learner_id):
                streak += 1
            else:
                streak = 1
    else:
        streak = 1
    execute(
        "UPDATE learners SET streak_days = ?, last_day = ? WHERE id = ?",
        (streak, today.isoformat(), learner_id),
    )
    return streak


# ----------------------------------------------------------------- попытки
def record_attempt(
    learner_id: int,
    topic_slug: str,
    method_slug: str | None,
    generator: str | None,
    correct: bool,
    given_answer: str,
    expected: str,
    time_ms: int,
    hints_used: int,
    mode: str = "practice",
) -> None:
    execute(
        """INSERT INTO attempts
        (learner_id, topic_slug, method_slug, generator, correct, given_answer,
         expected, time_ms, hints_used, mode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            learner_id, topic_slug, method_slug, generator, 1 if correct else 0,
            given_answer[:120], expected[:120], int(time_ms or 0), int(hints_used or 0), mode,
        ),
    )
    _bump_topic_progress(learner_id, topic_slug, correct)
    _bump_method_progress(learner_id, topic_slug, method_slug, correct)
    _bump_learner(learner_id, correct, mode)
    touch_day(learner_id)


def _bump_topic_progress(learner_id: int, topic_slug: str, correct: bool) -> None:
    row = query_one(
        "SELECT attempts, correct FROM topic_progress WHERE learner_id = ? AND topic_slug = ?",
        (learner_id, topic_slug),
    )
    attempts = (row["attempts"] if row else 0 or 0) + 1
    correct_total = (row["correct"] if row else 0 or 0) + (1 if correct else 0)
    accuracy = correct_total / attempts if attempts else 0.0
    if row:
        execute(
            """UPDATE topic_progress
               SET attempts = ?, correct = ?, best_accuracy = MAX(best_accuracy, ?),
                   updated_at = datetime('now')
             WHERE learner_id = ? AND topic_slug = ?""",
            (attempts, correct_total, accuracy, learner_id, topic_slug),
        )
    else:
        execute(
            """INSERT INTO topic_progress
               (learner_id, topic_slug, attempts, correct, best_accuracy, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (learner_id, topic_slug, attempts, correct_total, accuracy),
        )


def _bump_method_progress(learner_id: int, topic_slug: str, method_slug: str | None, correct: bool) -> None:
    if not method_slug:
        return
    execute(
        """
        INSERT INTO method_progress (learner_id, topic_slug, method_slug, seen, attempts, correct, updated_at)
        VALUES (?, ?, ?, 1, 1, ?, datetime('now'))
        ON CONFLICT(learner_id, topic_slug, method_slug) DO UPDATE SET
            seen = 1,
            attempts = attempts + 1,
            correct = correct + excluded.correct,
            mastered = CASE WHEN method_progress.correct + excluded.correct >= 5 THEN 1 ELSE 0 END,
            updated_at = datetime('now')
        """,
        (learner_id, topic_slug, method_slug, 1 if correct else 0),
    )


def reward_amounts(learner_id: int, mode: str = "practice") -> tuple[int, int]:
    """Сколько опыта и монет даёт верный ответ с учётом усилителей."""
    from services import shop as shop_service

    cfg = get_config()
    base_xp = cfg.XP_PER_BOSS if mode == "boss" else cfg.XP_PER_CORRECT
    base_coins = cfg.COINS_PER_CORRECT
    return (
        shop_service.apply_multiplier(learner_id, base_xp, "xp"),
        shop_service.apply_multiplier(learner_id, base_coins, "coins"),
    )


def _bump_learner(learner_id: int, correct: bool, mode: str = "practice") -> None:
    if not correct:
        return
    xp, coins = reward_amounts(learner_id, mode)
    execute(
        "UPDATE learners SET xp = xp + ?, coins = coins + ? WHERE id = ?",
        (xp, coins, learner_id),
    )
    from services import shop as shop_service

    shop_service.bump_pet(learner_id)


def apply_round_result(learner_id: int, topic_slug: str, correct: int, total: int) -> int:
    """Записать итог раунда, обновить звёзды. Возвращает количество звёзд."""
    stars = stars_for(correct, total)
    row = query_one(
        "SELECT stars FROM topic_progress WHERE learner_id = ? AND topic_slug = ?",
        (learner_id, topic_slug),
    )
    best = row["stars"] if row else 0
    if stars > best:
        execute(
            """INSERT INTO topic_progress (learner_id, topic_slug, stars, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(learner_id, topic_slug) DO UPDATE SET
                stars = excluded.stars, updated_at = datetime('now')""",
            (learner_id, topic_slug, stars),
        )
    return max(stars, best)


def mark_topic_read(learner_id: int, topic_slug: str) -> dict[str, Any]:
    """Отметить изучение темы по пособию. Награда начисляется один раз."""
    already = query_one(
        """SELECT id FROM attempts
            WHERE learner_id = ? AND topic_slug = ? AND mode = 'reading' AND correct = 1
            LIMIT 1""",
        (learner_id, topic_slug),
    )
    if already:
        return {"already": True, "xp": 0, "coins": 0}
    record_attempt(
        learner_id, topic_slug, None, None, True,
        "изучено по пособию", "изучено", 0, 0, mode="reading",
    )
    execute(
        """INSERT INTO topic_progress (learner_id, topic_slug, stars, updated_at)
           VALUES (?, ?, 1, datetime('now'))
           ON CONFLICT(learner_id, topic_slug) DO UPDATE SET
               stars = MAX(topic_progress.stars, 1), updated_at = datetime('now')""",
        (learner_id, topic_slug),
    )
    xp, coins = reward_amounts(learner_id, "reading")
    return {"already": False, "xp": xp, "coins": coins}


def mark_boss_cleared(learner_id: int, topic_slug: str) -> None:
    execute(
        """INSERT INTO topic_progress (learner_id, topic_slug, boss_cleared, updated_at)
        VALUES (?, ?, 1, datetime('now'))
        ON CONFLICT(learner_id, topic_slug) DO UPDATE SET
            boss_cleared = 1, updated_at = datetime('now')""",
        (learner_id, topic_slug),
    )


def start_session(learner_id: int, topic_slug: str, mode: str = "practice") -> int:
    return execute(
        "INSERT INTO play_sessions (learner_id, topic_slug, mode) VALUES (?, ?, ?)",
        (learner_id, topic_slug, mode),
    )


def finish_session(session_id: int, task_count: int, correct_count: int, xp_gained: int) -> None:
    execute(
        """UPDATE play_sessions
        SET ended_at = datetime('now'), task_count = ?, correct_count = ?, xp_gained = ?
        WHERE id = ?""",
        (task_count, correct_count, xp_gained, session_id),
    )


# ------------------------------------------------------------------ выборки
def topic_progress_map(learner_id: int) -> dict[str, sqlite3.Row]:
    rows = query_all("SELECT * FROM topic_progress WHERE learner_id = ?", (learner_id,))
    return {r["topic_slug"]: r for r in rows}


def method_progress_map(learner_id: int) -> dict[tuple[str, str], sqlite3.Row]:
    rows = query_all("SELECT * FROM method_progress WHERE learner_id = ?", (learner_id,))
    return {(r["topic_slug"], r["method_slug"]): r for r in rows}


def learner_stats(learner_id: int) -> dict[str, Any]:
    """Полная статистика ученика (для значков и шаблонов)."""
    learner = query_one("SELECT * FROM learners WHERE id = ?", (learner_id,))
    if not learner:
        return {}

    totals = query_one(
        """SELECT COUNT(*) AS attempts,
                  COALESCE(SUM(correct), 0) AS correct
             FROM attempts WHERE learner_id = ?""",
        (learner_id,),
    )
    attempts = totals["attempts"] or 0
    correct = totals["correct"] or 0

    topics = query_all("SELECT * FROM topic_progress WHERE learner_id = ?", (learner_id,))
    topics_started = len([t for t in topics if (t["attempts"] or 0) > 0])
    topics_three_stars = len([t for t in topics if (t["stars"] or 0) >= 3])
    bosses_cleared = len([t for t in topics if (t["boss_cleared"] or 0) >= 1])

    method_rows = query_all("SELECT * FROM method_progress WHERE learner_id = ?", (learner_id,))
    methods_seen = len([m for m in method_rows if (m["seen"] or 0) > 0])
    by_topic: dict[str, int] = {}
    for m in method_rows:
        if (m["mastered"] or 0) >= 1:
            by_topic[m["topic_slug"]] = by_topic.get(m["topic_slug"], 0) + 1
    max_methods_mastered = max(by_topic.values()) if by_topic else 0

    attempt_rows = query_all(
        """SELECT correct, hints_used, topic_slug, time_ms
             FROM attempts WHERE learner_id = ? ORDER BY id DESC LIMIT 5000""",
        (learner_id,),
    )
    attempt_rows.reverse()

    max_combo = 0
    combo = 0
    max_combo_no_hint = 0
    combo_no_hint = 0
    fastest = 10 ** 9
    comebacks = 0
    wrong_streak = 0
    correct_fractions = 0
    correct_motion = 0

    for row in attempt_rows:
        if row["correct"]:
            combo += 1
            combo_no_hint += 1
            max_combo = max(max_combo, combo)
            max_combo_no_hint = max(max_combo_no_hint, combo_no_hint)
            if row["time_ms"] and row["time_ms"] > 0:
                fastest = min(fastest, row["time_ms"])
            if wrong_streak >= 2:
                comebacks += 1
            wrong_streak = 0
            if row["topic_slug"] in ("fractions", "fractions_ops"):
                correct_fractions += 1
            if row["topic_slug"] == "motion":
                correct_motion += 1
        else:
            combo = 0
            combo_no_hint = 0
            wrong_streak += 1

    sessions = query_all(
        "SELECT task_count, correct_count FROM play_sessions WHERE learner_id = ? AND task_count > 0",
        (learner_id,),
    )
    perfect_rounds = len([s for s in sessions if s["correct_count"] >= s["task_count"]])

    daily_rows = query_all(
        "SELECT DISTINCT day FROM daily_answers WHERE learner_id = ? AND correct = 1", (learner_id,)
    )
    daily_done = len(daily_rows)

    xp = total_xp(learner)
    info = level_info(xp)
    return {
        "learner_id": learner_id,
        "name": learner["name"],
        "avatar": learner["avatar"],
        "grade": learner["grade"],
        "coins": learner["coins"] or 0,
        "xp": xp,
        "xp_balance": learner["xp"] or 0,
        "level": info["level"],
        "level_info": info,
        "streak_days": learner["streak_days"] or 0,
        "total_attempts": attempts,
        "total_correct": correct,
        "accuracy": round(correct / attempts * 100) if attempts else 0,
        "topics_started": topics_started,
        "topics_total": 0,
        "topics_three_stars": topics_three_stars,
        "bosses_cleared": bosses_cleared,
        "perfect_rounds": perfect_rounds,
        "max_combo": max_combo,
        "max_combo_no_hint": max_combo_no_hint,
        "fastest_ms": fastest,
        "comebacks": comebacks,
        "correct_fractions": correct_fractions,
        "correct_motion": correct_motion,
        "max_methods_mastered": max_methods_mastered,
        "methods_seen": methods_seen,
        "daily_done": daily_done,
    }


def topic_accuracy(learner_id: int) -> dict[str, dict[str, Any]]:
    """Точность и счётчики по каждой теме (для родительской зоны)."""
    rows = query_all(
        """SELECT topic_slug,
                  COUNT(*) AS attempts,
                  COALESCE(SUM(correct), 0) AS correct,
                  AVG(time_ms) AS avg_time
             FROM attempts WHERE learner_id = ?
            GROUP BY topic_slug""",
        (learner_id,),
    )
    stars = topic_progress_map(learner_id)
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        attempts = row["attempts"] or 0
        correct = row["correct"] or 0
        out[row["topic_slug"]] = {
            "attempts": attempts,
            "correct": correct,
            "accuracy": round(correct / attempts * 100) if attempts else 0,
            "avg_time_ms": int(row["avg_time"] or 0),
            "stars": (stars.get(row["topic_slug"])["stars"] if row["topic_slug"] in stars else 0) or 0,
        }
    return out


def weekly_activity(learner_id: int, days: int = 14) -> list[dict[str, Any]]:
    """Активность по дням за последние N дней."""
    rows = query_all(
        """SELECT date(created_at) AS day, COUNT(*) AS attempts,
                  COALESCE(SUM(correct), 0) AS correct
             FROM attempts WHERE learner_id = ?
              AND created_at >= datetime('now', ?)
            GROUP BY day""",
        (learner_id, f"-{days} days"),
    )
    mapping = {r["day"]: r for r in rows}
    out = []
    today = date.today()
    for offset in range(days - 1, -1, -1):
        day = (today - timedelta(days=offset)).isoformat()
        row = mapping.get(day)
        out.append({
            "day": day,
            "attempts": row["attempts"] if row else 0,
            "correct": row["correct"] if row else 0,
        })
    return out


def daily_answer_state(learner_id: int, day: str, generator: str) -> bool | None:
    row = query_one(
        "SELECT correct FROM daily_answers WHERE learner_id = ? AND day = ? AND generator = ?",
        (learner_id, day, generator),
    )
    return None if row is None else bool(row["correct"])


def save_daily_answer(learner_id: int, day: str, generator: str, correct: bool) -> None:
    execute(
        """INSERT INTO daily_answers (learner_id, day, generator, correct)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(learner_id, day, generator) DO UPDATE SET correct = excluded.correct""",
        (learner_id, day, generator, 1 if correct else 0),
    )
