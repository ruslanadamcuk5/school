"""Проверка ответов ребёнка: нормализация и сравнение."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

SUPERSCRIPT = str.maketrans({"²": "2", "³": "3"})


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text or ""))
    return text.translate(SUPERSCRIPT).strip().lower()


def normalize_text(text: str) -> str:
    """Приводит ответ к «каноническому» виду для текстового сравнения."""
    text = _clean(text).replace(",", ".")
    text = text.replace("−", "-").replace("–", "-")
    text = re.sub(r"(руб|р\.|р\b|коп|коп\.|шт|см|м|кг|г|мин|ч|км|см2|см²|кв\.?\s*см|см3|см³|м2|м²|км2|км²|га)", "", text)
    text = re.sub(r"[!\"#$%&'()*+,:;<=>?@\[\\\]^_`{|}~]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_number(text: str) -> float | None:
    """Пытается разобрать число (в т.ч. дробь и смешанное число) из строки."""
    raw = _clean(text).replace(",", ".").replace("−", "-")
    raw = re.sub(r"(руб|р\.|р\b|коп|коп\.|шт|см|м|кг|г|мин|ч|км)", "", raw).strip()
    if not raw:
        return None

    # смешанное число: «2 1/2»
    m = re.fullmatch(r"(-?\d+)\s+(\d+)\s*/\s*(\d+(?:\.\d+)?)", raw)
    if m:
        whole, num, den = int(m.group(1)), int(m.group(2)), float(m.group(3))
        if den:
            sign = -1 if whole < 0 else 1
            return sign * (abs(whole) + num / den)

    # дробь: «1/2», «1 : 2»
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*[:/]\s*(\d+(?:\.\d+)?)", raw)
    if m:
        num, den = float(m.group(1)), float(m.group(2))
        return num / den if den else None

    # целое или десятичное
    raw = raw.replace(" ", "")
    m = re.fullmatch(r"-?\d+(?:\.\d+)?", raw)
    if m:
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def normalize_time(text: str) -> str | None:
    """'3:05', '3.05', '305', '3 05' -> '3:05'."""
    text = _clean(text).replace(".", ":").replace(",", ":")
    text = re.sub(r"[^\d:]", "", text)
    if not text:
        return None
    if ":" in text:
        parts = text.split(":")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            return None
        h, m = int(parts[0]), int(parts[1])
    else:
        if len(text) == 3:
            h, m = int(text[0]), int(text[1:])
        elif len(text) == 4:
            h, m = int(text[:2]), int(text[2:])
        elif len(text) == 1 or len(text) == 2:
            h, m = int(text), 0
        else:
            return None
    if m > 59:
        return None
    return f"{h}:{m:02d}"


def _equal_floats(a: float, b: float) -> bool:
    return abs(a - b) < 1e-6


def check_answer(user_answer: Any, task: dict[str, Any]) -> tuple[bool, str]:
    """Проверить ответ. Возвращает (верно ли, ожидаемый ответ для показа)."""
    expected = str(task.get("answer", ""))
    kind = task.get("answer_type", "number")
    given = "" if user_answer is None else str(user_answer)

    if kind == "choice":
        ok = normalize_text(given) == normalize_text(expected)
        return ok, expected

    if kind == "time":
        g, e = normalize_time(given), normalize_time(expected)
        ok = g is not None and g == e
        return ok, expected

    if kind in ("number", "fraction", "mixed"):
        g = normalize_number(given)
        e = normalize_number(expected)
        if g is not None and e is not None:
            if _equal_floats(g, e):
                return True, expected
        # текстовые варианты (например «2 1/2» записано словами не принимаем)
        if normalize_text(given) == normalize_text(expected):
            return True, expected
        for alt in task.get("accept", []):
            if normalize_text(given) == normalize_text(alt):
                return True, expected
        return False, expected

    # text
    if normalize_text(given) == normalize_text(expected):
        return True, expected
    for alt in task.get("accept", []):
        if normalize_text(given) == normalize_text(alt):
            return True, expected
    return False, expected


def expected_display(task: dict[str, Any]) -> str:
    """Красивое представление правильного ответа."""
    kind = task.get("answer_type", "number")
    answer = str(task.get("answer", ""))
    if kind == "fraction":
        return answer.replace("/", " / ")
    if kind == "mixed":
        return answer
    if kind == "time":
        return answer
    return answer
