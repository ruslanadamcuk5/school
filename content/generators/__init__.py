"""Реестр генераторов заданий."""
from __future__ import annotations

from .base import REGISTRY, gen, plural, rnd, shuffle_options, task
from . import grade3, grade4  # noqa: F401  (регистрация при импорте)

__all__ = [
    "REGISTRY",
    "gen",
    "task",
    "plural",
    "rnd",
    "shuffle_options",
    "get_generator",
    "generators_for_topic",
    "all_generator_keys",
]


def get_generator(key: str):
    """Получить функцию-генератор по ключу 'topic.generator'."""
    return REGISTRY.get(key)


def generators_for_topic(topic_slug: str) -> list[str]:
    """Список ключей генераторов темы."""
    return sorted(k for k in REGISTRY if k.startswith(f"{topic_slug}."))


def all_generator_keys() -> list[str]:
    return sorted(REGISTRY)
