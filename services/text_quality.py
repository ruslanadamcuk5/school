"""Проверка качества текста, извлечённого из PDF.

Часть учебников свёрстана шрифтами без корректной таблицы Unicode: вместо
кириллицы из PDF приходят «ɁȿɆɅə» или «£Ò ½¿¹Ã». Такой текст нельзя ни
показывать ребёнку, ни отдавать модели ИИ и ни превращать в задания —
поэтому перед использованием проверяем, что буквы действительно образуют
слова нужного языка.
"""
from __future__ import annotations

import re

_CYR = re.compile(r"[А-Яа-яЁёІіЎў]")
_LAT = re.compile(r"[A-Za-z]")

# Доля «своих» букв, ниже которой текст считаем мусором.
MIN_RATIO = 0.55
# Слишком короткие фрагменты (подписи, колонцифры) не проверяем и не используем.
MIN_LETTERS = 40


def letter_counts(text: str) -> tuple[int, int, int]:
    """(всего букв, кириллических, латинских) в тексте."""
    total = cyr = lat = 0
    for char in text or "":
        if not char.isalpha():
            continue
        total += 1
        if _CYR.match(char):
            cyr += 1
        elif _LAT.match(char):
            lat += 1
    return total, cyr, lat


def readable(text: str, script: str = "cyr", min_letters: int = MIN_LETTERS,
             min_ratio: float = MIN_RATIO) -> bool:
    """Похож ли текст на связный текст нужного языка.

    `script`: «cyr» для русскоязычных предметов, «lat» для английского.
    Текст с «битыми» глифами (ɁȿɆɅə, £Ò ½¿¹Ã) не проходит проверку.
    """
    total, cyr, lat = letter_counts(text)
    if total < min_letters:
        return False
    if script == "lat":
        return lat / total >= min_ratio
    return cyr / total >= min_ratio


def usable_text(text: str, script: str = "cyr") -> bool:
    """Псевдоним для читаемости: удобно читать в вызывающем коде."""
    return readable(text, script)
