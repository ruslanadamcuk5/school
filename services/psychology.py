"""Школьная психология: оценка тестов, результаты, ИИ и уведомления.

Логика отделена от каталога вопросов (``psychology_catalog``). Здесь:

* подсчёт баллов по шкалам и определение уровня;
* сборка заключения и рекомендаций для ученика и родителя;
* ИИ-заключение с кэшем в ``ai_explanations``;
* сохранение результата и уведомления родителям.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Iterable

from database import execute, query_all, query_one
from services import auth as auth_service
from services import notifications as notifications_service
from services import psychology_catalog as catalog

AI_CACHE_VERSION = "v1"
AI_TIMEOUT = 25
AI_MAX_TOKENS = 800

PSY_SYSTEM = (
    "Ты — опытный школьный психолог из Беларуси. Пишешь по-русски, тактично и "
    "просто, без канцелярита. Ты не ставишь диагнозы и не навешиваешь ярлыки. "
    "Опираешься на результаты мягкого скрининга и даёшь практичные шаги, "
    "которые семья может сделать сама. Если трудности выражены, советуешь "
    "обратиться к школьному психологу. Не используй имена детей."
)

PSY_PROMPT = """Результаты психологического скрининга.

Тест: {title}
Класс: {grade}
Категория: {category}
Что измеряли: {description}

Показатели по шкалам:
{scales}

Предварительные выводы:
{conclusions}

Подготовь заключение строго по разделам, без вступления:
## Кратко
2–3 предложения о том, что показывают результаты.
## Сильные стороны
2–3 пункта.
## Что можно сделать
3–5 конкретных шагов для семьи, без общих слов.
## Совет ученику
1–2 предложения, дружелюбно и по делу.

Не ставь диагнозов. Не пугай. Не используй имена. Пиши кратко и по существу."""


# ------------------------------------------------------------------ ответы
def _answer_index(answers: Any, index: int) -> int | None:
    """Достать выбранный вариант из словаря или списка ответов."""
    value = None
    if isinstance(answers, dict):
        value = answers.get(str(index), answers.get(index))
    elif isinstance(answers, (list, tuple)) and index < len(answers):
        value = answers[index]
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < 0 or number > 3:
        return None
    return number


def _level_key(percent: int, good_high: bool) -> str:
    if good_high:
        if percent < 40:
            return "low"
        if percent < 70:
            return "mid"
        return "high"
    if percent < 34:
        return "low"
    if percent < 60:
        return "mid"
    return "high"


def _overall(scales: Iterable[dict[str, Any]]) -> int:
    values = [int(scale.get("percent") or 0) for scale in scales]
    return round(sum(values) / len(values)) if values else 0


# ------------------------------------------------------------------ оценка
def evaluate(test: dict[str, Any], answers: Any, grade: int) -> dict[str, Any]:
    """Посчитать шкалы, заключение и рекомендации по ответам."""
    totals = {key: {"total": 0, "max": 0} for key in test["scales"]}
    for index, question in enumerate(test["questions"]):
        choice = _answer_index(answers, index)
        if choice is None:
            raise ValueError(f"Нет ответа на вопрос {index + 1}")
        option = question["options"][choice]
        for scale, value in option["scores"].items():
            bucket = totals.setdefault(scale, {"total": 0, "max": 0})
            bucket["total"] += int(value)
            bucket["max"] += 3

    scales: list[dict[str, Any]] = []
    for key in test["scales"]:
        info = catalog.scale_info(key)
        if not info:
            continue
        bucket = totals.get(key) or {"total": 0, "max": 0}
        percent = round(bucket["total"] / bucket["max"] * 100) if bucket["max"] else 0
        level_key = _level_key(percent, bool(info["good_high"]))
        level = info["levels"][level_key]
        scales.append(
            {
                "key": key,
                "label": info["label"],
                "icon": info["icon"],
                "percent": percent,
                "level": level_key,
                "level_label": level["label"],
                "good_high": bool(info["good_high"]),
                "parent": level["parent"],
                "student": level["student"],
                "advice": list(level["advice"]),
                "title": level["title"],
            }
        )

    category = test["category"]
    headline, summary, recommendations = _conclusions(category, scales)
    return {
        "test_slug": test["slug"],
        "test_title": test["title"],
        "test_subtitle": test["subtitle"],
        "category": category,
        "category_title": catalog.category_info(category)["title"],
        "category_icon": catalog.category_info(category)["icon"],
        "category_color": catalog.category_info(category)["color"],
        "description": test["description"],
        "duration": test["duration"],
        "source": test["source"],
        "grade": int(grade),
        "band": test["band"],
        "headline": headline,
        "summary": summary,
        "overall": _overall(scales),
        "scales": scales,
        "recommendations": recommendations,
        "disclaimer": catalog.DISCLAIMER,
    }


def _rec(scale: dict[str, Any], kind: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "scale": scale["key"],
        "title": scale["title"],
        "parent": scale["parent"],
        "student": scale["student"],
        "advice": list(scale["advice"]),
        "percent": scale["percent"],
        "level": scale["level"],
    }


def _join_labels(items: Iterable[dict[str, Any]], limit: int = 3) -> str:
    labels = [str(item["label"]).lower() for item in items][:limit]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + " и " + labels[-1]


def _conclusions(
    category: str, scales: list[dict[str, Any]]
) -> tuple[str, str, list[dict[str, Any]]]:
    """Заключение и рекомендации зависят от категории теста."""
    ordered = sorted(scales, key=lambda item: item["percent"], reverse=True)
    if not ordered:
        return "Результат готов.", "Ответы сохранены.", []
    top = ordered[0]
    bottom = ordered[-1]

    if category == "problems":
        risky = [item for item in ordered if item["level"] == "high"]
        watch = [item for item in ordered if item["level"] == "mid"]
        calm = [item for item in ordered if item["level"] == "low"]
        recommendations = [_rec(item, "attention") for item in risky]
        if not risky:
            recommendations += [_rec(item, "attention") for item in watch[:2]]
        if not risky and not watch and calm:
            recommendations.append(_rec(calm[0], "strength"))
        if risky:
            headline = risky[0]["title"]
            summary = (
                f"Наибольшего внимания просит: {_join_labels(risky)}. "
                "Остальные показатели стоит держать в поле зрения, но они не "
                "выглядят критичными."
            )
        elif watch:
            headline = "Есть на что обратить внимание, но без тревоги."
            summary = (
                f"Временами даёт о себе знать: {_join_labels(watch)}. "
                "Это хороший повод спокойно поговорить и поддержать ребёнка."
            )
        else:
            headline = "Эмоциональное состояние выглядит благополучным."
            summary = (
                "Выраженных признаков тревоги, перегрузки или трудностей в "
                "общении не видно. Продолжайте поддерживать режим и открытый "
                "разговор о школе."
            )
        return headline, summary, recommendations

    if category == "activities":
        interests = [item for item in ordered if item["percent"] >= 50]
        recommendations = [_rec(item, "interest") for item in interests[:3]]
        if not recommendations:
            recommendations = [_rec(top, "interest")]
        if interests:
            headline = f"Сильнее всего проявляется {interests[0]['label'].lower()}."
            extra = ""
            if len(interests) > 1:
                extra = f" Также откликается {_join_labels(interests[1:2])}."
            summary = (
                f"Наибольший интерес — {interests[0]['label'].lower()} "
                f"({interests[0]['percent']}%).{extra}"
            )
        else:
            headline = "Ярких интересов пока не выявлено."
            summary = (
                "Это нормально: интерес часто появляется, когда ребёнок пробует "
                "разные занятия. Попробуйте вместе выбрать 1–2 кружка без "
                "давления и сравнить впечатления."
            )
        return headline, summary, recommendations

    # abilities и development
    strengths = [item for item in ordered if item["level"] == "high"]
    growth = [item for item in ordered if item["level"] == "low"]
    recommendations = [_rec(item, "strength") for item in strengths[:2]]
    recommendations += [_rec(item, "growth") for item in growth[:2]]
    if not recommendations:
        recommendations = [_rec(top, "strength")]

    if strengths:
        headline = strengths[0]["title"]
        summary = f"Сильнее всего проявляется {_join_labels(strengths)}."
        if growth:
            summary += f" Поддержки просит {_join_labels(growth)}."
        else:
            summary += " Показатели достаточно ровные, есть на что опереться."
        return headline, summary, recommendations

    if top["percent"] >= 50:
        headline = f"Ближе всего к сильной стороне — {top['label'].lower()}."
        summary = (
            f"Пока наиболее заметно {top['label'].lower()} ({top['percent']}%). "
            "Это можно развивать спокойно, без сравнения с другими."
        )
    else:
        headline = "Показатели развиваются неравномерно — это нормально."
        summary = (
            "Ярких сильных сторон тест пока не выделил. Ошибки и разный темп "
            "развития в этом возрасте естественны; важны поддержка и практика."
        )
    if bottom["level"] == "low" and bottom is not top:
        summary += f" Отдельно стоит поддержать {bottom['label'].lower()}."
    return headline, summary, recommendations


# ------------------------------------------------------------------ ИИ
def _cache_key(test: dict[str, Any], grade: int, scales: list[dict[str, Any]]) -> str:
    signature = "|".join(f"{item['key']}={item['percent']}" for item in scales)
    digest = hashlib.md5(
        f"{AI_CACHE_VERSION}:{test['slug']}:{int(grade)}:{signature}".encode("utf-8")
    ).hexdigest()
    return f"psych:{test['slug']}:{int(grade)}:{digest}"


def ai_review(
    test: dict[str, Any],
    grade: int,
    result: dict[str, Any],
) -> tuple[str, str, str]:
    """Вернуть (текст, модель, ошибка). При выключенном ИИ — пустой текст."""
    from services import ai as ai_service

    if not ai_service.is_enabled():
        return "", "", "disabled"

    scales = result.get("scales") or []
    cache_key = _cache_key(test, grade, scales)
    try:
        cached = query_one(
            "SELECT content, model FROM ai_explanations WHERE topic_slug = ?",
            (cache_key,),
        )
    except Exception:  # pragma: no cover - кэш не должен ломать тест
        cached = None
    if cached and cached["content"]:
        return cached["content"], cached["model"] or "", ""

    lines = "\n".join(
        f"- {item['label']}: {item['percent']}% ({item['level_label']})"
        for item in scales
    )
    conclusions = "\n".join(
        f"- {item['title']}: {item['parent']}" for item in result.get("recommendations", [])
    ) or f"- {result.get('headline')}"
    prompt = PSY_PROMPT.format(
        title=test["title"],
        grade=int(grade),
        category=result.get("category_title") or test["category"],
        description=test["description"],
        scales=lines,
        conclusions=conclusions,
    )
    text, error = ai_service.chat(
        [
            {"role": "system", "content": PSY_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.35,
        max_tokens=AI_MAX_TOKENS,
        timeout=AI_TIMEOUT,
    )
    if error or not text:
        return "", "", error or "empty"
    model = (ai_service.get_settings().get("model") or "").strip()
    try:
        execute(
            """INSERT INTO ai_explanations (topic_slug, grade, model, content)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(topic_slug) DO UPDATE SET
                   content = excluded.content,
                   model = excluded.model,
                   grade = excluded.grade,
                   created_at = datetime('now')""",
            (cache_key, int(grade), model, text),
        )
    except Exception:  # pragma: no cover - сохранение кэша необязательно
        pass
    return text, model, ""


# ------------------------------------------------------------------ сохранение
def save_result(
    learner: Any,
    test: dict[str, Any],
    grade: int,
    answers: Any,
    result: dict[str, Any],
    ai_text: str = "",
    ai_model: str = "",
) -> int:
    user_id = None
    try:
        user_id = learner["user_id"]
    except (KeyError, TypeError):
        user_id = None
    return execute(
        """INSERT INTO psych_results
               (learner_id, user_id, test_slug, test_title, category, grade,
                answers_json, scores_json, result_json, ai_summary, ai_model)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            int(learner["id"]),
            int(user_id) if user_id else None,
            test["slug"],
            test["title"],
            test["category"],
            int(grade),
            json.dumps(answers, ensure_ascii=False),
            json.dumps(
                {item["key"]: item["percent"] for item in result.get("scales", [])},
                ensure_ascii=False,
            ),
            json.dumps(result, ensure_ascii=False),
            ai_text or "",
            ai_model or "",
        ),
    )


def latest_results(learner_id: int, limit: int = 40) -> list[Any]:
    """История результатов, новые сверху."""
    return query_all(
        """SELECT * FROM psych_results
            WHERE learner_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?""",
        (int(learner_id), max(1, min(200, int(limit)))),
    )


def latest_by_test(learner_id: int) -> list[Any]:
    """Последний результат по каждому тесту."""
    seen: set[str] = set()
    out = []
    for row in latest_results(learner_id, limit=200):
        key = row["test_slug"]
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def history(rows: Iterable[Any]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        try:
            payload = json.loads(row["result_json"] or "{}")
        except (ValueError, TypeError):
            payload = {}
        out.append(
            {
                "id": int(row["id"]),
                "test_slug": row["test_slug"],
                "test_title": row["test_title"],
                "category": row["category"],
                "category_title": catalog.category_info(row["category"])["title"],
                "created_at": row["created_at"],
                "headline": payload.get("headline") or "",
            }
        )
    return out


def result_payload(row: Any, audience: str = "student") -> dict[str, Any]:
    """Готовый JSON результата для ученика или родителя."""
    try:
        data = json.loads(row["result_json"] or "{}")
    except (ValueError, TypeError):
        data = {}
    data["id"] = int(row["id"])
    data["created_at"] = row["created_at"]
    data["ai"] = {
        "text": row["ai_summary"] or "",
        "model": row["ai_model"] or "",
    }
    data["audience"] = audience

    for scale in data.get("scales") or []:
        scale["text"] = scale.pop("parent" if audience == "parent" else "student", "")
        scale.pop("parent", None)
        scale.pop("student", None)
    for item in data.get("recommendations") or []:
        item["text"] = item.pop("parent" if audience == "parent" else "student", "")
        item.pop("parent", None)
        item.pop("student", None)
    return data


def test_cards(grade: int, latest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Карточки тестов для класса с отметкой о последнем результате."""
    latest = latest or {}
    cards = []
    for test in catalog.tests_for_grade(grade):
        category = catalog.category_info(test["category"])
        row = latest.get(test["slug"])
        card: dict[str, Any] = {
            "slug": test["slug"],
            "title": test["title"],
            "subtitle": test["subtitle"],
            "description": test["description"],
            "category": test["category"],
            "category_title": category["title"],
            "category_icon": category["icon"],
            "category_color": category["color"],
            "duration": test["duration"],
            "questions": len(test["questions"]),
            "grades": list(next(
                (band["grades"] for band in catalog.BANDS if band["key"] == test["band"]),
                (),
            )),
            "band": test["band"],
            "source": test["source"],
            "completed": bool(row),
            "attempts": 0,
            "latest": None,
        }
        if row is not None:
            try:
                payload = json.loads(row["result_json"] or "{}")
            except (ValueError, TypeError):
                payload = {}
            card["latest"] = {
                "id": int(row["id"]),
                "created_at": row["created_at"],
                "headline": payload.get("headline") or "",
                "percent": int(payload.get("overall") or 0),
                "category_title": category["title"],
                "ai": bool(row["ai_summary"]),
            }
        cards.append(card)
    return cards


def result_card(row: Any) -> dict[str, Any]:
    """Короткая карточка результата для списков."""
    try:
        payload = json.loads(row["result_json"] or "{}")
    except (ValueError, TypeError):
        payload = {}
    category = catalog.category_info(row["category"])
    return {
        "id": int(row["id"]),
        "test_slug": row["test_slug"],
        "test_title": row["test_title"],
        "category": row["category"],
        "category_title": category["title"],
        "created_at": row["created_at"],
        "headline": payload.get("headline") or "",
        "percent": int(payload.get("overall") or 0),
        "has_ai": bool(row["ai_summary"]),
    }


def recommendations_for(row: Any) -> list[dict[str, Any]]:
    """Рекомендации из сохранённого результата (для родительской ленты)."""
    try:
        payload = json.loads(row["result_json"] or "{}")
    except (ValueError, TypeError):
        return []
    out = []
    for item in payload.get("recommendations") or []:
        out.append(
            {
                "kind": item.get("kind") or "attention",
                "title": item.get("title") or "",
                "text": item.get("parent") or "",
                "advice": item.get("advice") or [],
                "scale": item.get("scale") or "",
                "percent": int(item.get("percent") or 0),
                "result_id": int(row["id"]),
                "test_title": row["test_title"],
                "category": row["category"],
                "created_at": row["created_at"],
            }
        )
    return out


# ------------------------------------------------------------------ доступ
def parents_of_learner(learner: Any) -> list[Any]:
    """Аккаунты родителей, привязанные к профилю ребёнка."""
    owner_id = None
    try:
        owner_id = learner["user_id"]
    except (KeyError, TypeError):
        owner_id = None
    if not owner_id:
        row = query_one(
            "SELECT user_id FROM learner_accounts WHERE learner_id = ?",
            (int(learner["id"]),),
        )
        owner_id = row["user_id"] if row else None
    if not owner_id:
        return []
    try:
        return [
            parent
            for parent in auth_service.parents_of(int(owner_id))
            if parent["is_active"]
        ]
    except Exception:  # pragma: no cover - уведомления не должны ломать тест
        return []


def _child_name(learner: Any) -> str:
    try:
        name = (learner["name"] or "").strip()
    except (KeyError, TypeError):
        name = ""
    return name or "Ребёнок"


def notify_result(
    result_id: int,
    learner: Any,
    test: dict[str, Any],
    result: dict[str, Any],
    audience_link: str,
) -> None:
    """Сообщить родителям о пройденном тесте и новых рекомендациях."""
    child = _child_name(learner)
    grade = result.get("grade")
    headline = (result.get("headline") or test["title"]).strip()
    for parent in parents_of_learner(learner):
        parent_id = int(parent["id"])
        try:
            notifications_service.push(
                parent_id,
                notifications_service.KIND_PSYCH_RESULT,
                "Психологический тест пройден",
                f"«{test['title']}» — {child}, {grade} класс. "
                "Результаты уже в разделе «Школьная психология».",
                link=audience_link,
                dedup_key=f"psych_result:{parent_id}:{int(result_id)}",
            )
            notifications_service.push(
                parent_id,
                notifications_service.KIND_PSYCH_RECOMMENDATION,
                f"Новые рекомендации для {child}",
                f"{headline}. Откройте раздел «Школьная психология», чтобы "
                "увидеть, что можно сделать дома.",
                link=audience_link,
                dedup_key=f"psych_recommendation:{parent_id}:{int(result_id)}",
            )
        except Exception:  # pragma: no cover - уведомление не должно ломать ответ
            continue

    # Ученику с аккаунтом — короткое подтверждение и ссылка на результат.
    owner_id = None
    try:
        owner_id = learner["user_id"]
    except (KeyError, TypeError):
        owner_id = None
    if owner_id:
        try:
            notifications_service.push(
                int(owner_id),
                notifications_service.KIND_PSYCH_RESULT,
                "Психологический тест пройден",
                f"«{test['title']}». Результат и рекомендации готовы.",
                link=f"/app/psychology/result/{int(result_id)}",
                dedup_key=f"psych_result_student:{int(owner_id)}:{int(result_id)}",
            )
        except Exception:  # pragma: no cover
            pass


def submitted_at() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
