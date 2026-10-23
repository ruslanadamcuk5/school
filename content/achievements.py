"""Значки (достижения) — награды за прогресс ребёнка."""
from __future__ import annotations

from typing import Any, Callable

Check = Callable[[dict[str, Any]], bool]


def _get(stats: dict[str, Any], key: str, default: Any = 0) -> Any:
    value = stats.get(key, default)
    return default if value is None else value


ACHIEVEMENTS: list[dict[str, Any]] = [
    {
        "key": "first_step",
        "name": "Первый шаг",
        "icon": "🐣",
        "description": "Первый верный ответ",
        "check": lambda s: _get(s, "total_correct") >= 1,
    },
    {
        "key": "warmup",
        "name": "Разминка",
        "icon": "🔥",
        "description": "10 верных ответов",
        "check": lambda s: _get(s, "total_correct") >= 10,
    },
    {
        "key": "hundred",
        "name": "Сотка!",
        "icon": "💯",
        "description": "100 верных ответов",
        "check": lambda s: _get(s, "total_correct") >= 100,
    },
    {
        "key": "thousand",
        "name": "Тысяча!",
        "icon": "🏆",
        "description": "1000 верных ответов",
        "check": lambda s: _get(s, "total_correct") >= 1000,
    },
    {
        "key": "explorer",
        "name": "Исследователь",
        "icon": "🧭",
        "description": "Начать 3 темы",
        "check": lambda s: _get(s, "topics_started") >= 3,
    },
    {
        "key": "cartographer",
        "name": "Картограф",
        "icon": "🗺️",
        "description": "Начать 8 тем",
        "check": lambda s: _get(s, "topics_started") >= 8,
    },
    {
        "key": "polymath",
        "name": "Знаток программы",
        "icon": "🎓",
        "description": "Начать все темы",
        "check": lambda s: _get(s, "topics_started") >= _get(s, "topics_total", 99),
    },
    {
        "key": "first_boss",
        "name": "Босс повержен",
        "icon": "🐉",
        "description": "Пройти испытание-босс",
        "check": lambda s: _get(s, "bosses_cleared") >= 1,
    },
    {
        "key": "boss_hunter",
        "name": "Охотник за боссами",
        "icon": "⚔️",
        "description": "Пройти 5 испытаний-боссов",
        "check": lambda s: _get(s, "bosses_cleared") >= 5,
    },
    {
        "key": "perfect_round",
        "name": "Идеально!",
        "icon": "💎",
        "description": "Раунд без единой ошибки",
        "check": lambda s: _get(s, "perfect_rounds") >= 1,
    },
    {
        "key": "perfect_five",
        "name": "Безупречность",
        "icon": "👑",
        "description": "5 раундов без ошибок",
        "check": lambda s: _get(s, "perfect_rounds") >= 5,
    },
    {
        "key": "combo5",
        "name": "Серия!",
        "icon": "⚡",
        "description": "5 верных ответов подряд",
        "check": lambda s: _get(s, "max_combo") >= 5,
    },
    {
        "key": "combo10",
        "name": "Огненная серия",
        "icon": "🌋",
        "description": "10 верных ответов подряд",
        "check": lambda s: _get(s, "max_combo") >= 10,
    },
    {
        "key": "no_hints",
        "name": "Без подсказок",
        "icon": "🧠",
        "description": "10 верных ответов подряд без подсказок",
        "check": lambda s: _get(s, "max_combo_no_hint") >= 10,
    },
    {
        "key": "speedster",
        "name": "Скоростная",
        "icon": "🚀",
        "description": "Ответить меньше чем за 8 секунд",
        "check": lambda s: 0 < _get(s, "fastest_ms", 10**9) < 8000,
    },
    {
        "key": "streak3",
        "name": "Три дня подряд",
        "icon": "📅",
        "description": "Заниматься 3 дня подряд",
        "check": lambda s: _get(s, "streak_days") >= 3,
    },
    {
        "key": "streak7",
        "name": "Неделя занятий",
        "icon": "🗓️",
        "description": "Заниматься 7 дней подряд",
        "check": lambda s: _get(s, "streak_days") >= 7,
    },
    {
        "key": "streak30",
        "name": "Месяц дисциплины",
        "icon": "🌟",
        "description": "Заниматься 30 дней подряд",
        "check": lambda s: _get(s, "streak_days") >= 30,
    },
    {
        "key": "level5",
        "name": "Уровень 5",
        "icon": "⭐",
        "description": "Достичь 5 уровня",
        "check": lambda s: _get(s, "level") >= 5,
    },
    {
        "key": "level10",
        "name": "Уровень 10",
        "icon": "🌟",
        "description": "Достичь 10 уровня",
        "check": lambda s: _get(s, "level") >= 10,
    },
    {
        "key": "level20",
        "name": "Уровень 20",
        "icon": "💫",
        "description": "Достичь 20 уровня",
        "check": lambda s: _get(s, "level") >= 20,
    },
    {
        "key": "teacher",
        "name": "Знаток всех способов",
        "icon": "🧙",
        "description": "Освоить все способы объяснения одной темы",
        "check": lambda s: _get(s, "max_methods_mastered") >= 3,
    },
    {
        "key": "fraction_master",
        "name": "Мастер дробей",
        "icon": "🍰",
        "description": "20 верных ответов по дробям",
        "check": lambda s: _get(s, "correct_fractions") >= 20,
    },
    {
        "key": "motion_master",
        "name": "Знаток движения",
        "icon": "🚄",
        "description": "15 верных ответов по движению",
        "check": lambda s: _get(s, "correct_motion") >= 15,
    },
    {
        "key": "star_collector",
        "name": "Собиратель звёзд",
        "icon": "🌠",
        "description": "3 звезды в 5 темах",
        "check": lambda s: _get(s, "topics_three_stars") >= 5,
    },
    {
        "key": "daily",
        "name": "Челленджер",
        "icon": "🎯",
        "description": "Выполнить ежедневное задание",
        "check": lambda s: _get(s, "daily_done") >= 1,
    },
    {
        "key": "comeback",
        "name": "Не сдавайся!",
        "icon": "💪",
        "description": "Ошибиться 2 раза подряд и затем ответить верно",
        "check": lambda s: _get(s, "comebacks") >= 1,
    },
    {
        "key": "curious",
        "name": "Любознательный",
        "icon": "🤓",
        "description": "Посмотреть 5 разных способов объяснения",
        "check": lambda s: _get(s, "methods_seen") >= 5,
    },
]

BY_KEY = {a["key"]: a for a in ACHIEVEMENTS}


def evaluate_badges(stats: dict[str, Any], owned: set[str]) -> list[dict[str, Any]]:
    """Вернуть список новых значков, которые нужно выдать."""
    new = []
    for badge in ACHIEVEMENTS:
        if badge["key"] in owned:
            continue
        try:
            if badge["check"](stats):
                new.append(badge)
        except Exception:  # pragma: no cover - защита от ошибок в условиях
            continue
    return new
