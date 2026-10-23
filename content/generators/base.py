"""Базовые примитивы для генераторов заданий."""
from __future__ import annotations

import random
from typing import Any, Callable

REGISTRY: dict[str, Callable[[int], dict[str, Any]]] = {}


def gen(topic: str, key: str):
    """Регистратор генератора: @gen("topic_slug", "key")."""

    def deco(fn: Callable[[int], dict[str, Any]]):
        full = f"{topic}.{key}"
        REGISTRY[full] = fn
        fn.gen_key = full  # type: ignore[attr-defined]
        fn.topic = topic  # type: ignore[attr-defined]
        return fn

    return deco


def task(
    question: str,
    answer: str,
    *,
    accept: list[str] | None = None,
    answer_type: str = "number",
    choices: list[str] | None = None,
    variables: dict[str, Any] | None = None,
    hints: list[str] | None = None,
    solution: str = "",
    widget: dict[str, Any] | None = None,
    difficulty: int = 1,
) -> dict[str, Any]:
    """Собрать задание единого формата."""
    return {
        "question": question,
        "answer": str(answer),
        "accept": accept or [],
        "answer_type": answer_type,
        "choices": choices or [],
        "variables": variables or {},
        "hints": hints or [],
        "solution": solution,
        "widget": widget,
        "difficulty": difficulty,
    }


def digits_of(number: int) -> list[int]:
    return [int(d) for d in str(abs(number))]


def plural(n: int, one: str, few: str, many: str) -> str:
    """Русское склонение числительных: 1 коробка, 2 коробки, 5 коробок."""
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def shuffle_options(options: list[str]) -> list[str]:
    out = list(options)
    random.shuffle(out)
    return out


def rnd(lo: int, hi: int) -> int:
    return random.randint(lo, hi)
