"""API: кабинет родителя — дети, прогресс, привязка по коду."""
from __future__ import annotations

from flask import jsonify

from database import query_all, query_one
from services import auth as auth_service
from services import learners as learners_service
from services import orgs
from services import progress as progress_service

from . import bp
from .deps import current_user, fail, json_body, require_user, row_dict, user_payload

MAX_GRADE = 11


def _learner_of_user(user_id: int):
    row = query_one(
        """SELECT l.* FROM learner_accounts la
             JOIN learners l ON l.id = la.learner_id
            WHERE la.user_id = ?""",
        (user_id,),
    )
    if row is not None:
        return row
    return query_one("SELECT * FROM learners WHERE user_id = ?", (user_id,))


def _children(user) -> list[dict]:
    out = []
    for child in auth_service.children_of(int(user["id"])):
        if child["role"] != auth_service.ROLE_STUDENT:
            continue
        learner = _learner_of_user(int(child["id"]))
        classes = orgs.classes_of_student(int(child["id"]))
        grade = int(classes[0]["grade"]) if classes else (
            int(learner["grade"]) if learner else 3
        )
        stats = progress_service.learner_stats(int(learner["id"])) if learner else {}
        out.append(
            {
                "user": user_payload(child),
                "learner": row_dict(learner) if learner else None,
                "classes": [row_dict(klass) for klass in classes],
                "grade": grade,
                "stats": {
                    "level": stats.get("level", 1),
                    "xp": stats.get("xp", 0),
                    "coins": stats.get("coins", 0),
                    "stars": stats.get("topics_three_stars", 0),
                    "accuracy": stats.get("accuracy", 0),
                    "attempts": stats.get("total_attempts", 0),
                    "streak_days": stats.get("streak_days", 0),
                    "daily_done": stats.get("daily_done", 0),
                },
            }
        )
    return out


def _own_learner(user, learner_id: int):
    learner = learners_service.get_learner(learner_id)
    if learner is None:
        fail(404, "not_found", "Профиль не найден")
    child_ids = {int(child["id"]) for child in auth_service.children_of(int(user["id"]))}
    owner_id = learner["user_id"]
    if owner_id is None:
        row = query_one(
            "SELECT user_id FROM learner_accounts WHERE learner_id = ?", (learner_id,)
        )
        owner_id = row["user_id"] if row else None
    if owner_id is None or int(owner_id) not in child_ids:
        fail(404, "not_found", "Профиль не найден")
    return learner


@bp.get("/parent/dashboard")
@require_user("parent")
def parent_dashboard():
    user = current_user()
    children = _children(user)
    total_stars = sum(child["stats"]["stars"] for child in children)
    total_attempts = sum(child["stats"]["attempts"] for child in children)
    return jsonify(
        {
            "ok": True,
            "children": children,
            "stats": {
                "children": len(children),
                "stars": total_stars,
                "attempts": total_attempts,
            },
        }
    )


@bp.get("/parent/children")
@require_user("parent")
def children():
    user = current_user()
    return jsonify({"ok": True, "children": _children(user)})


@bp.get("/parent/children/<int:learner_id>")
@require_user("parent")
def child_detail(learner_id: int):
    user = current_user()
    learner = _own_learner(user, learner_id)
    child_user = None
    owner = query_one(
        "SELECT user_id FROM learner_accounts WHERE learner_id = ?", (learner_id,)
    )
    if owner is not None:
        child_user = query_one("SELECT * FROM users WHERE id = ?", (owner["user_id"],))
    elif learner["user_id"]:
        child_user = query_one("SELECT * FROM users WHERE id = ?", (learner["user_id"],))

    stats = progress_service.learner_stats(learner_id) or {}
    topic_rows = query_all(
        "SELECT * FROM topic_progress WHERE learner_id = ? ORDER BY attempts DESC",
        (learner_id,),
    )
    results = []
    if child_user is not None:
        results = query_all(
            """SELECT r.*, a.title, a.kind
                 FROM assignment_results r
                 JOIN assignments a ON a.id = r.assignment_id
                WHERE r.student_id = ?
                ORDER BY r.completed_at DESC""",
            (int(child_user["id"]),),
        )

    return jsonify(
        {
            "ok": True,
            "learner": row_dict(learner),
            "user": user_payload(child_user) if child_user else None,
            "classes": [row_dict(klass) for klass in orgs.classes_of_student(int(child_user["id"]))]
            if child_user
            else [],
            "stats": stats,
            "topics": [
                {
                    "slug": row["topic_slug"],
                    "stars": row["stars"],
                    "attempts": row["attempts"],
                    "correct": row["correct"],
                    "boss_cleared": bool(row["boss_cleared"]),
                }
                for row in topic_rows
            ],
            "weekly": progress_service.weekly_activity(learner_id),
            "results": [
                {
                    "assignment_id": row["assignment_id"],
                    "title": row["title"],
                    "kind": row["kind"],
                    "score": row["score"],
                    "max_score": row["max_score"],
                    "completed_at": row["completed_at"],
                }
                for row in results
            ],
        }
    )


@bp.patch("/parent/children/<int:learner_id>")
@require_user("parent")
def update_child(learner_id: int):
    user = current_user()
    child = _own_learner(user, learner_id)
    data = json_body()

    fields: dict = {}
    if "name" in data:
        name = str(data.get("name") or "").strip()
        if not name:
            fail(400, "bad_name", "Имя не может быть пустым")
        fields["name"] = name[:60]
    if "avatar" in data:
        fields["avatar"] = str(data.get("avatar") or "🦊")[:8]
    if "grade" in data:
        try:
            grade = int(data.get("grade"))
        except (TypeError, ValueError):
            fail(400, "bad_grade", "Класс должен быть числом")
        if not 1 <= grade <= MAX_GRADE:
            fail(400, "bad_grade", f"Класс — от 1 до {MAX_GRADE}")
        fields["grade"] = grade
    if "sound_on" in data:
        fields["sound_on"] = 1 if data.get("sound_on") else 0
    if "voice_on" in data:
        fields["voice_on"] = 1 if data.get("voice_on") else 0
    if "daily_limit" in data:
        try:
            fields["daily_limit"] = max(0, int(data.get("daily_limit") or 0))
        except (TypeError, ValueError):
            fail(400, "bad_limit", "Лимит должен быть числом")

    if fields:
        learners_service.update_learner(learner_id, **fields)
    return jsonify(
        {"ok": True, "learner": row_dict(learners_service.get_learner(learner_id))}
    )


@bp.post("/parent/children/<int:learner_id>/reset")
@require_user("parent")
def reset_child(learner_id: int):
    user = current_user()
    _own_learner(user, learner_id)
    data = json_body()
    if str(data.get("confirm") or "").strip().lower() not in ("yes", "true", "1"):
        fail(400, "confirm_required", "Подтвердите сброс прогресса")
    learners_service.reset_progress(learner_id)
    return jsonify({"ok": True})


@bp.post("/parent/link")
@require_user("parent")
def link_child():
    user = current_user()
    data = json_body()
    code = str(data.get("code") or "").strip()
    if not code:
        fail(400, "no_code", "Введите код ребёнка")
    child = auth_service.find_child_by_code(code)
    if child is None:
        fail(404, "not_found", "Код не найден. Проверьте его в профиле ребёнка.")
    if not auth_service.link_parent_child(int(user["id"]), int(child["id"])):
        fail(400, "link_failed", "Не удалось привязать ребёнка")
    return jsonify(
        {
            "ok": True,
            "child": user_payload(child),
            "children": _children(user),
        }
    )


@bp.get("/parent/children/<int:learner_id>/export")
@require_user("parent")
def export_child(learner_id: int):
    user = current_user()
    learner = _own_learner(user, learner_id)
    rows = query_all(
        """SELECT created_at, topic_slug, mode, correct, given, expected,
                  hints_used, time_ms
             FROM attempts WHERE learner_id = ?
            ORDER BY id""",
        (learner_id,),
    )
    return jsonify(
        {
            "ok": True,
            "learner": row_dict(learner),
            "attempts": [row_dict(row) for row in rows],
        }
    )
