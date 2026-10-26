"""Вопросы по теме, которые составляет модель ИИ.

Задания строятся по выбранной теме: название, предмет, класс, описание и —
если у пособия есть читаемый текстовый слой — фрагмент текста. Модель обязана
вернуть строгий JSON, который мы проверяем сами:

* ровно один правильный вариант и он входит в список вариантов;
* варианты не повторяются;
* нет «вопросов» про страницы, авторов и предмет пособия;
* ответ сравнивается с вариантом после нормализации, поэтому проверка
  на сайте и в приложении даёт одинаковый результат.

Готовый набор кэшируется в таблице `ai_quizzes`, чтобы не тратить запросы
к модели на каждого ученика.
"""
from __future__ import annotations

import json
import re
from typing import Any

from content.answer import normalize_text
from content.generators.base import shuffle_options, task
from database import execute, query_one
from services import ai as ai_service

_SYSTEM = (
    "Ты — методист школьных учебников. Составляешь проверочные вопросы "
    "по конкретной теме так, чтобы они проверяли понимание содержания, "
    "а не память о страницах и названиях пособий. Отвечаешь только JSON."
)

_TEMPLATE = """Тема: {title}
Предмет: {subject}
Класс: {grade}
Краткое описание: {description}
{text_block}
Составь {count} вопросов с выбором одного правильного ответа по этой теме.
Требования:
- вопросы — по содержанию темы, без вопросов «на какой странице», «к какому
  предмету относится», «как называется пособие» и «кто автор учебника»;
- в каждом вопросе 4 варианта, ровно один верный, остальные правдоподобные;
- поле "answer" — точная копия одного из вариантов;
- объяснение ("explanation") — 1–2 предложения, почему ответ верный;
- без повторов и без вариантов «все перечисленное»;
- {language}
{text_rule}
Верни строго JSON-массив без пояснений и без markdown:
[{{"question": "…", "options": ["…", "…", "…", "…"], "answer": "…",
  "explanation": "…"}}]"""

_RU_LANGUAGE = "пиши вопросы и варианты по-русски, простыми словами для ученика."
_EN_LANGUAGE = "write the questions and options in English, simple school English."

# Вопросы про оформление пособия — не проверка знаний.
_META = re.compile(
    r"на\s+какой\s+страниц|страниц\w*\s+пособи|какому\s+предмету|"
    r"какой\s+это\s+предмет|как\s+называется\s+(?:тема|предмет|пособие)|"
    r"автор\w*\s+(?:учебник|пособи)|оглавлени",
    re.IGNORECASE,
)

MAX_QUESTION = 300
MAX_OPTION = 90
MAX_EXPLANATION = 400
OPTIONS_PER_QUESTION = 4


def _field(topic: Any, name: str, default: Any = "") -> Any:
    if isinstance(topic, dict):
        return topic.get(name, default)
    try:
        if name in topic.keys():
            return topic[name]
    except (AttributeError, TypeError):
        return default
    return default


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _extract_json(text: str) -> Any:
    """Достать JSON-массив из ответа модели (в т.ч. в ```-блоке)."""
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except (ValueError, TypeError):
        return None


def _answer_from_options(answer: Any, options: list[str]) -> str:
    """Найти вариант, совпадающий с ответом модели (с нормализацией)."""
    if isinstance(answer, int):
        return options[answer] if 0 <= answer < len(options) else ""
    raw = _clean(answer)
    if not raw:
        return ""
    for option in options:
        if normalize_text(option) == normalize_text(raw):
            return option
    if raw.isdigit():
        index = int(raw)
        if 0 <= index < len(options):
            return options[index]
    return ""


def _normalize_item(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    question = _clean(
        item.get("question") or item.get("q") or item.get("вопрос") or ""
    )
    options_raw = (
        item.get("options") or item.get("choices") or item.get("варианты") or []
    )
    answer_raw = (
        item.get("answer") or item.get("correct") or item.get("ответ") or ""
    )
    explanation = _clean(
        item.get("explanation") or item.get("why") or item.get("solution")
        or item.get("объяснение") or ""
    )

    if not isinstance(options_raw, list):
        return None
    options: list[str] = []
    seen: set[str] = set()
    for raw in options_raw:
        option = _clean(raw)
        if not option or len(option) > MAX_OPTION:
            continue
        key = normalize_text(option)
        if key in seen:
            continue
        seen.add(key)
        options.append(option)
    if len(options) != OPTIONS_PER_QUESTION:
        return None

    if not question or len(question) < 10 or len(question) > MAX_QUESTION:
        return None
    if _META.search(question):
        return None
    if not any(char.isalpha() for char in question):
        return None
    if question[-1] not in "?.!":
        question += "?"

    answer = _answer_from_options(answer_raw, options)
    if not answer:
        return None
    if not explanation or len(explanation) > MAX_EXPLANATION:
        explanation = f"Правильный ответ: {answer}."

    return {
        "question": question,
        "options": options,
        "answer": answer,
        "explanation": explanation,
    }


def validate(items: Any, limit: int = 12) -> list[dict[str, Any]]:
    """Проверить ответ модели и оставить только корректные вопросы."""
    if isinstance(items, dict):
        items = items.get("questions") or items.get("items") or []
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        clean = _normalize_item(item)
        if not clean:
            continue
        key = normalize_text(clean["question"])
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
        if len(result) >= limit:
            break
    return result


def _to_tasks(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for item in items:
        tasks.append(task(
            item["question"],
            item["answer"],
            answer_type="choice",
            choices=shuffle_options(list(item["options"])),
            solution=item["explanation"],
            difficulty=2,
        ))
    return tasks


# ------------------------------------------------------------------ кэш
def _load_cache(slug: str) -> list[dict[str, Any]] | None:
    try:
        row = query_one("SELECT payload FROM ai_quizzes WHERE topic_slug = ?", (slug,))
    except Exception:  # noqa: BLE001 - нет таблицы в старой БД
        return None
    if not row:
        return None
    try:
        return validate(json.loads(row["payload"]))
    except (ValueError, TypeError):
        return None


def _save_cache(topic: Any, items: list[dict[str, Any]]) -> None:
    try:
        execute(
            """INSERT INTO ai_quizzes (topic_slug, grade, model, payload)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(topic_slug) DO UPDATE SET
                   grade = excluded.grade,
                   model = excluded.model,
                   payload = excluded.payload,
                   created_at = datetime('now')""",
            (
                _field(topic, "slug"),
                _field(topic, "grade") or None,
                ai_service.get_settings().get("model") or "",
                json.dumps(items, ensure_ascii=False),
            ),
        )
    except Exception:  # noqa: BLE001 - кэш не должен ломать тест
        pass


def clear_cache(slug: str | None = None) -> int:
    """Удалить сохранённые вопросы (все или по одной теме)."""
    try:
        if slug:
            execute("DELETE FROM ai_quizzes WHERE topic_slug = ?", (slug,))
        else:
            execute("DELETE FROM ai_quizzes")
    except Exception:  # noqa: BLE001
        return 0
    return 1


# ------------------------------------------------------------------ генерация
def _text_block(text: str) -> tuple[str, str]:
    text = (text or "").strip()
    if not text:
        return "", (
            "Текста пособия нет — опирайся на школьную программу этого класса "
            "и на название темы."
        )
    return (
        f"\nФрагмент учебника:\n{text[:6000]}\n",
        "Опирайся на фрагмент учебника: вопросы должны проверять его содержание.",
    )


def _prompt(topic: Any, count: int, text: str, script: str) -> str:
    text_block, text_rule = _text_block(text)
    return _TEMPLATE.format(
        title=_field(topic, "title", _field(topic, "slug")),
        subject=_field(topic, "subject_name") or "школьный предмет",
        grade=_field(topic, "grade") or "",
        description=_clean(_field(topic, "description")) or "нет описания",
        text_block=text_block,
        count=count,
        language=_EN_LANGUAGE if script == "lat" else _RU_LANGUAGE,
        text_rule=text_rule,
    )


def questions(
    topic: Any,
    count: int = 8,
    *,
    text: str = "",
    script: str = "cyr",
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    """Вопросы по теме из кэша или от модели. Ошибки не ломают тест."""
    if not topic or count <= 0:
        return []
    slug = _field(topic, "slug")
    if not slug:
        return []
    cached = _load_cache(slug)
    if cached:
        return _to_tasks(cached[:count])
    if not ai_service.is_enabled():
        return []

    wanted = min(12, max(8, count + 4))
    answer, error = ai_service.chat(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _prompt(topic, wanted, text, script)},
        ],
        temperature=0.5,
        max_tokens=max(900, 220 * wanted),
    )
    if error:
        ai_service.log_request(user_id, "quiz", False, f"{slug}: {error}")
        return []
    items = validate(_extract_json(answer), wanted)
    if len(items) < 2:
        ai_service.log_request(
            user_id, "quiz", False, f"{slug}: модель вернула {len(items)} вопросов"
        )
        return []
    _save_cache(topic, items)
    ai_service.log_request(user_id, "quiz", True, f"{slug}: {len(items)} вопросов")
    return _to_tasks(items[:count])
