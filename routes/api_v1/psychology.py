"""API: школьная психология для ученика, семейного профиля и родителя."""
from __future__ import annotations

from flask import jsonify, request

from database import query_all, query_one
from services import auth as auth_service
from services import learners as learners_service
from services import orgs
from services import psychology as psych
from services import psychology_catalog as catalog

from . import bp
from .deps import (
    current_learner,
    current_user,
    fail,
    json_body,
    learner,
    require_learner,
    require_user,
)


# ------------------------------------------------------------------ помощники
def _learner_of_user(user_id: int):
    row = query_one(
        """SELECT l.* FROM learner_accounts la
             JOIN learners l ON l.id = la.learner_id
            WHERE la.user_id = ?""",
        (int(user_id),),
    )
    if row is not None:
        return row
    return query_one("SELECT * FROM learners WHERE user_id = ?", (int(user_id),))


def _owner_id(learner_row) -> int | None:
    try:
        if learner_row["user_id"]:
            return int(learner_row["user_id"])
    except (KeyError, TypeError):
        pass
    row = query_one(
        "SELECT user_id FROM learner_accounts WHERE learner_id = ?",
        (int(learner_row["id"]),),
    )
    return int(row["user_id"]) if row and row["user_id"] else None


def _grade_for(learner_row) -> int:
    owner = _owner_id(learner_row)
    if owner:
        try:
            classes = orgs.classes_of_student(owner)
        except Exception:  # pragma: no cover - классы не должны ломать раздел
            classes = []
        if classes:
            return int(classes[0]["grade"])
    try:
        return int(learner_row["grade"] or 3)
    except (KeyError, TypeError, ValueError):
        return 3


def _own_child(user, learner_id: int):
    """Профиль ребёнка, принадлежащий родителю, либо 404."""
    child_ids = {
        int(row["child_id"])
        for row in query_all(
            "SELECT child_id FROM parent_children WHERE parent_id = ?",
            (int(user["id"]),),
        )
    }
    learner_row = learners_service.get_learner(int(learner_id))
    if learner_row is None:
        fail(404, "not_found", "Профиль не найден")
    owner = _owner_id(learner_row)
    if owner is None or owner not in child_ids:
        fail(404, "not_found", "Профиль не найден")
    return learner_row


def _result_row(result_id: int):
    row = query_one("SELECT * FROM psych_results WHERE id = ?", (int(result_id),))
    if row is None:
        fail(404, "not_found", "Результат не найден")
    return row


def _public_learner(learner_row) -> dict:
    return {
        "id": int(learner_row["id"]),
        "name": learner_row["name"] or "Ученик",
        "avatar": learner_row["avatar"] or "🦊",
        "grade": _grade_for(learner_row),
    }


def _public_user(user) -> dict:
    return {
        "id": int(user["id"]),
        "login": user["login"] or "",
        "first_name": user["first_name"] or "",
        "last_name": user["last_name"] or "",
        "avatar": user["avatar"] or "👤",
    }


def _band_payload(grade: int) -> dict:
    band = catalog.band_for_grade(grade)
    return {
        "key": band["key"],
        "title": band["title"],
        "age": band["age"],
        "note": band["note"],
        "grades": list(band["grades"]),
    }


def _test_public(test: dict) -> dict:
    return {
        "slug": test["slug"],
        "title": test["title"],
        "subtitle": test["subtitle"],
        "description": test["description"],
        "category": test["category"],
        "category_title": catalog.category_info(test["category"])["title"],
        "category_icon": catalog.category_info(test["category"])["icon"],
        "category_color": catalog.category_info(test["category"])["color"],
        "duration": test["duration"],
        "questions": len(test["questions"]),
        "band": test["band"],
        "grades": list(
            next(
                (
                    band["grades"]
                    for band in catalog.BANDS
                    if band["key"] == test["band"]
                ),
                (),
            )
        ),
        "source": test["source"],
    }


def _questions_public(test: dict) -> list[dict]:
    return [
        {
            "id": index,
            "text": question["text"],
            "options": [option["label"] for option in question["options"]],
        }
        for index, question in enumerate(test["questions"])
    ]


def _parent_children(user) -> list:
    out = []
    for child in auth_service.children_of(int(user["id"])):
        if child["role"] != auth_service.ROLE_STUDENT:
            continue
        learner_row = _learner_of_user(int(child["id"]))
        if learner_row is None:
            continue
        out.append((child, learner_row))
    return out


# ------------------------------------------------------------------ ученик
@bp.get("/psychology/tests")
@require_learner
def psychology_tests():
    learner_row = learner()
    grade = _grade_for(learner_row)
    rows = psych.latest_by_test(int(learner_row["id"]))
    latest = {row["test_slug"]: row for row in rows}
    cards = psych.test_cards(grade, latest)
    # Количество прохождений по каждому тесту.
    attempts = {
        row["test_slug"]: int(row["n"])
        for row in query_all(
            """SELECT test_slug, COUNT(*) AS n FROM psych_results
                WHERE learner_id = ? GROUP BY test_slug""",
            (int(learner_row["id"]),),
        )
    }
    for card in cards:
        card["attempts"] = attempts.get(card["slug"], 0)
    return jsonify(
        {
            "ok": True,
            "grade": grade,
            "band": _band_payload(grade),
            "tests": cards,
            "history": psych.history(psych.latest_results(int(learner_row["id"]), 30)),
            "disclaimer": catalog.DISCLAIMER,
            "source": catalog.SOURCE_NOTE,
        }
    )


@bp.get("/psychology/tests/<slug>")
@require_learner
def psychology_test(slug: str):
    learner_row = learner()
    grade = _grade_for(learner_row)
    test = catalog.get_test(slug)
    if test is None:
        fail(404, "not_found", "Тест не найден")
    if grade not in next(
        (band["grades"] for band in catalog.BANDS if band["key"] == test["band"]),
        (),
    ):
        fail(403, "wrong_grade", "Этот тест не для вашего класса")
    latest = query_one(
        """SELECT id FROM psych_results
            WHERE learner_id = ? AND test_slug = ?
            ORDER BY created_at DESC, id DESC LIMIT 1""",
        (int(learner_row["id"]), test["slug"]),
    )
    return jsonify(
        {
            "ok": True,
            "test": _test_public(test),
            "questions": _questions_public(test),
            "latest_result_id": int(latest["id"]) if latest else None,
            "disclaimer": catalog.DISCLAIMER,
        }
    )


@bp.post("/psychology/tests/<slug>")
@require_learner
def psychology_submit(slug: str):
    learner_row = learner()
    grade = _grade_for(learner_row)
    test = catalog.get_test(slug)
    if test is None:
        fail(404, "not_found", "Тест не найден")
    if grade not in next(
        (band["grades"] for band in catalog.BANDS if band["key"] == test["band"]),
        (),
    ):
        fail(403, "wrong_grade", "Этот тест не для вашего класса")

    body = json_body()
    answers = body.get("answers")
    if answers is None:
        fail(400, "no_answers", "Ответы не переданы")
    try:
        result = psych.evaluate(test, answers, grade)
    except ValueError as exc:
        fail(400, "bad_answers", str(exc))

    ai_text, ai_model, ai_error = "", "", ""
    try:
        ai_text, ai_model, ai_error = psych.ai_review(test, grade, result)
    except Exception as exc:  # pragma: no cover - ИИ не должен ломать тест
        ai_error = str(exc)[:200]

    result_id = psych.save_result(
        learner_row, test, grade, answers, result, ai_text, ai_model
    )
    link = f"/app/psychology/result/{int(result_id)}"
    try:
        psych.notify_result(result_id, learner_row, test, result, link)
    except Exception:  # pragma: no cover
        pass

    row = query_one("SELECT * FROM psych_results WHERE id = ?", (int(result_id),))
    payload = psych.result_payload(row, "student")
    payload["learner_name"] = learner_row["name"] or ""
    response = {
        "ok": True,
        "result": payload,
        "ai_error": ai_error if ai_error and ai_error != "disabled" else "",
    }
    return jsonify(response)


@bp.get("/psychology/results/<int:result_id>")
@require_learner
def psychology_result(result_id: int):
    learner_row = learner()
    row = _result_row(result_id)
    if int(row["learner_id"]) != int(learner_row["id"]):
        fail(404, "not_found", "Результат не найден")
    payload = psych.result_payload(row, "student")
    payload["learner_name"] = learner_row["name"] or ""
    return jsonify({"ok": True, "result": payload})


# ------------------------------------------------------------------ родитель
@bp.get("/psychology/parent/overview")
@require_user("parent")
def psychology_parent_overview():
    user = current_user()
    children = []
    for child, learner_row in _parent_children(user):
        rows = psych.latest_by_test(int(learner_row["id"]))
        results = [psych.result_card(row) for row in rows]
        results.sort(key=lambda item: str(item["created_at"] or ""), reverse=True)
        recommendations: list[dict] = []
        for row in sorted(rows, key=lambda item: str(item["created_at"] or ""), reverse=True):
            recommendations.extend(psych.recommendations_for(row))
        priority = {"attention": 0, "growth": 1, "interest": 2, "strength": 3}
        recommendations.sort(key=lambda item: priority.get(item["kind"], 9))
        strengths = sum(1 for item in recommendations if item["kind"] in ("strength", "interest"))
        attention = sum(1 for item in recommendations if item["kind"] == "attention")
        children.append(
            {
                "learner": _public_learner(learner_row),
                "user": _public_user(child),
                "grade": _grade_for(learner_row),
                "stats": {
                    "tests": len(rows),
                    "strengths": strengths,
                    "attention": attention,
                    "last_at": results[0]["created_at"] if results else "",
                },
                "results": results,
                "recommendations": recommendations[:10],
            }
        )
    return jsonify(
        {
            "ok": True,
            "children": children,
            "disclaimer": catalog.DISCLAIMER,
            "source": catalog.SOURCE_NOTE,
        }
    )


@bp.get("/psychology/parent/results/<int:result_id>")
@require_user("parent")
def psychology_parent_result(result_id: int):
    user = current_user()
    row = _result_row(result_id)
    learner_row = _own_child(user, int(row["learner_id"]))
    payload = psych.result_payload(row, "parent")
    payload["learner"] = _public_learner(learner_row)
    return jsonify({"ok": True, "result": payload})


@bp.get("/psychology/status")
def psychology_status():
    """Публичная справка о разделе (без персональных данных)."""
    return jsonify(
        {
            "ok": True,
            "enabled": True,
            "bands": [
                {
                    "key": band["key"],
                    "title": band["title"],
                    "ages": band["age"],
                    "grades": list(band["grades"]),
                }
                for band in catalog.BANDS
            ],
            "categories": [
                {"key": key, **value} for key, value in catalog.CATEGORIES.items()
            ],
            "disclaimer": catalog.DISCLAIMER,
            "source": catalog.SOURCE_NOTE,
        }
    )
