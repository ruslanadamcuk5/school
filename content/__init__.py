"""Пакет учебного контента: программа, генераторы, значки."""
from __future__ import annotations

from .curriculum import TOPICS, topic_by_slug, topics_for_grade  # noqa: F401
from .achievements import ACHIEVEMENTS, evaluate_badges  # noqa: F401

__all__ = [
    "TOPICS",
    "topic_by_slug",
    "topics_for_grade",
    "ACHIEVEMENTS",
    "evaluate_badges",
]
