"""Подсказки администратору: кто старается и кого стоит наградить.

Сервис не хранит отдельную статистику, а считает её из ``attempts`` и
``shop_gifts``. Это честнее: подсказки всегда соответствуют реальной
активности ребёнка, а не последнему нажатию кнопки.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from database import query_all, query_one
from services import shop as shop_service
from services.progress import level_for_xp

ACTIVE_DAYS = 7


def _days_since(value: str | None) -> int | None:
    if not value:
        return None
    try:
        day = datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return max(0, (date.today() - day).days)


def _accuracy(correct: int, attempts: int) -> float:
    return (correct / attempts) if attempts else 0.0


def _base_rows(days: int = ACTIVE_DAYS) -> list[dict[str, Any]]:
    """Все профили с активностью за две недели — одним запросом."""
    days = max(1, min(30, int(days or ACTIVE_DAYS)))
    rows = query_all(
        f"""SELECT l.id, l.name, l.avatar, l.grade, l.coins, l.xp, l.xp_spent,
                   l.streak_days, l.last_day,
                   COALESCE(SUM(CASE WHEN a.created_at >= datetime('now', '-{days} days')
                                     THEN 1 ELSE 0 END), 0) AS attempts_now,
                   COALESCE(SUM(CASE WHEN a.created_at >= datetime('now', '-{days} days')
                                      AND a.correct = 1 THEN 1 ELSE 0 END), 0) AS correct_now,
                   COUNT(DISTINCT CASE WHEN a.created_at >= datetime('now', '-{days} days')
                                       THEN date(a.created_at) END) AS days_now,
                   COALESCE(SUM(CASE WHEN a.created_at < datetime('now', '-{days} days')
                                     THEN 1 ELSE 0 END), 0) AS attempts_prev,
                   COALESCE(SUM(CASE WHEN a.created_at < datetime('now', '-{days} days')
                                      AND a.correct = 1 THEN 1 ELSE 0 END), 0) AS correct_prev,
                   MAX(a.created_at) AS last_attempt
              FROM learners l
              LEFT JOIN attempts a
                     ON a.learner_id = l.id
                    AND a.created_at >= datetime('now', '-{days * 2} days')
             GROUP BY l.id
             ORDER BY attempts_now DESC, l.id"""
    )
    return [dict(row) for row in rows]


def _maps() -> tuple[dict[int, str], dict[int, int]]:
    last_gifts: dict[int, str] = {}
    for row in query_all(
        """SELECT learner_id, MAX(created_at) AS last_gift
             FROM shop_gifts WHERE status = 'claimed'
            GROUP BY learner_id"""
    ):
        last_gifts[int(row["learner_id"])] = row["last_gift"]
    pending: dict[int, int] = {}
    for row in query_all(
        """SELECT learner_id, COUNT(*) AS n FROM shop_gifts
            WHERE status = 'pending' GROUP BY learner_id"""
    ):
        pending[int(row["learner_id"])] = int(row["n"])
    return last_gifts, pending


def _accounts() -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
    for row in query_all(
        """SELECT la.learner_id, u.login, u.first_name, u.last_name
             FROM learner_accounts la JOIN users u ON u.id = la.user_id"""
    ):
        out[int(row["learner_id"])] = {
            "login": row["login"] or "",
            "name": " ".join(
                part for part in (row["first_name"] or "", row["last_name"] or "") if part
            ).strip(),
        }
    return out


def _owned_keys(learner_id: int) -> set[str]:
    return {
        row["item_key"]
        for row in query_all(
            "SELECT item_key FROM learner_items WHERE learner_id = ?", (learner_id,)
        )
    }


def _suggestion(item: dict[str, Any]) -> dict[str, Any]:
    price = shop_service.price_for(item)
    return {
        "key": item["key"],
        "name": item["name"],
        "icon": item["icon"],
        "tagline": item["tagline"],
        "coins": price["coins"],
        "level": item["level"],
        "rarity": item["rarity"],
        "rarity_name": item["rarity_name"],
    }


def gift_ideas(learner_id: int, level: int, limit: int = 3) -> list[dict[str, Any]]:
    """Что подарить: сначала то, чего у ребёнка ещё нет."""
    owned = _owned_keys(learner_id)
    catalog = [item for item in shop_service.catalog_items() if item["key"] not in owned]
    preferred = {"style": 0, "minecraft": 1, "pets": 2, "perks": 3}
    catalog.sort(
        key=lambda item: (
            preferred.get(item["category"], 9),
            abs(int(item["level"]) - int(level)),
            int(item["coins"]),
        )
    )
    ideas = [_suggestion(item) for item in catalog[:limit]]
    if not ideas:
        for key in ("hint_pack", "boost_xp", "mc_potion"):
            item = shop_service.get_item(key)
            if item:
                ideas.append(_suggestion(item))
    return ideas


def _reason_list(row: dict[str, Any], days_since_gift: int | None,
                 days_since_attempt: int | None) -> list[dict[str, str]]:
    reasons: list[dict[str, str]] = []
    days_now = int(row["days_now"] or 0)
    attempts = int(row["attempts_now"] or 0)
    correct = int(row["correct_now"] or 0)
    accuracy = _accuracy(correct, attempts)
    prev = int(row["attempts_prev"] or 0)
    streak = int(row["streak_days"] or 0)
    growth = (attempts - prev) / prev if prev else 0

    if days_now >= ACTIVE_DAYS:
        reasons.append({"icon": "🔥", "text": "Занимался каждый день недели"})
    elif days_now >= 4:
        reasons.append({"icon": "📅", "text": f"Занимался {days_now} дней из 7"})
    if streak >= 3:
        reasons.append({"icon": "⚡", "text": f"Серия {streak} дней подряд"})
    if attempts >= 10 and accuracy >= 0.85:
        reasons.append({"icon": "🎯", "text": f"Точность {round(accuracy * 100)}%"})
    if attempts >= 40:
        reasons.append({"icon": "💪", "text": f"{attempts} заданий за неделю"})
    if prev and growth >= 0.25:
        reasons.append({"icon": "📈", "text": f"Активность выросла на {round(growth * 100)}%"})
    if days_since_attempt is not None and days_since_attempt <= 1 and days_now <= 2:
        reasons.append({"icon": "🌱", "text": "Снова вернулся к занятиям"})
    if days_since_gift is not None and days_since_gift >= 14:
        reasons.append({"icon": "🎁", "text": f"{days_since_gift} дней без подарка"})
    elif days_since_gift is None and attempts >= 15:
        reasons.append({"icon": "🎁", "text": "Подарков ещё не получал"})
    return reasons


def _score(row: dict[str, Any]) -> tuple[float, float]:
    days_now = int(row["days_now"] or 0)
    attempts = int(row["attempts_now"] or 0)
    correct = int(row["correct_now"] or 0)
    accuracy = _accuracy(correct, attempts)
    prev = int(row["attempts_prev"] or 0)
    growth = (attempts - prev) / prev if prev else 0
    streak = int(row["streak_days"] or 0)
    score = (
        min(days_now / ACTIVE_DAYS, 1.0) * 35
        + min(attempts / 60, 1.0) * 25
        + accuracy * 25
        + min(streak / 7, 1.0) * 15
        + min(max(growth, 0), 1.0) * 10
    )
    return round(score, 1), growth


def leaderboard(days: int = ACTIVE_DAYS, limit: int = 100) -> list[dict[str, Any]]:
    """Рейтинг старания с причинами и идеями подарков."""
    rows = _base_rows(days)
    last_gifts, pending = _maps()
    accounts = _accounts()
    board: list[dict[str, Any]] = []
    for row in rows:
        learner_id = int(row["id"])
        attempts = int(row["attempts_now"] or 0)
        correct = int(row["correct_now"] or 0)
        score, growth = _score(row)
        total_xp = int(row["xp"] or 0) + int(row["xp_spent"] or 0)
        level = level_for_xp(total_xp)
        last_gift = last_gifts.get(learner_id)
        days_since_gift = _days_since(last_gift)
        days_since_attempt = _days_since(row["last_attempt"])
        reasons = _reason_list(row, days_since_gift, days_since_attempt)
        account = accounts.get(learner_id, {})
        board.append({
            "id": learner_id,
            "name": row["name"],
            "avatar": row["avatar"],
            "grade": int(row["grade"] or 1),
            "coins": int(row["coins"] or 0),
            "xp": int(row["xp"] or 0),
            "total_xp": total_xp,
            "level": level,
            "streak_days": int(row["streak_days"] or 0),
            "attempts": attempts,
            "correct": correct,
            "accuracy": round(_accuracy(correct, attempts) * 100),
            "days_active": int(row["days_now"] or 0),
            "attempts_prev": int(row["attempts_prev"] or 0),
            "growth": round(growth * 100),
            "last_attempt": row["last_attempt"],
            "days_since_attempt": days_since_attempt,
            "last_gift": last_gift,
            "days_since_gift": days_since_gift,
            "pending_gifts": pending.get(learner_id, 0),
            "score": score,
            "reasons": reasons,
            "reason_text": " · ".join(reason["text"] for reason in reasons[:2]),
            "account_login": account.get("login", ""),
            "account_name": account.get("name", ""),
            "ideas": gift_ideas(learner_id, level),
            "deserving": False,
        })

    board.sort(key=lambda item: (item["score"], item["attempts"], item["streak_days"]),
               reverse=True)
    for index, item in enumerate(board, start=1):
        item["rank"] = index
    # Подсказка админу: старается, но давно без подарка (или ещё не получал).
    for item in board[:12]:
        if item["score"] >= 40 and (item["days_since_gift"] is None
                                    or item["days_since_gift"] >= 10):
            item["deserving"] = True
    for item in board[:3]:
        if item["attempts"] >= 10:
            item["deserving"] = True
    return board[: max(1, min(200, int(limit or 100)))]


def summary() -> dict[str, Any]:
    row = query_one(
        """SELECT
              (SELECT COUNT(*) FROM shop_gifts WHERE status = 'pending') AS pending,
              (SELECT COUNT(*) FROM shop_gifts WHERE status = 'claimed') AS claimed,
              (SELECT COUNT(*) FROM shop_gifts WHERE date(created_at) = date('now')) AS today,
              (SELECT COUNT(*) FROM shop_purchases WHERE date(created_at) = date('now')) AS purchases_today,
              (SELECT COALESCE(SUM(paid_coins), 0) FROM shop_purchases) AS coins_spent
        """
    )
    data = dict(row) if row else {}
    return {key: int(data[key] or 0) for key in data}
