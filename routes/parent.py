"""Родительская зона: статистика, управление профилями, экспорт."""
from __future__ import annotations

import csv
import io
import json
import os
import random
import time
from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from content.achievements import ACHIEVEMENTS
from database import get_meta, query_all, query_one, set_meta
from services import assignments as assignments_service
from services import learners as learners_service
from services import orgs
from services import progress as progress_service
from services import rewards as rewards_service
from services import topics as topics_service

bp = Blueprint("parent", __name__)

PIN_ATTEMPTS = "parent_pin_attempts"
PIN_LOCKED_UNTIL = "parent_pin_locked_until"
MAX_ATTEMPTS = 5
LOCK_SECONDS = 300


def ensure_parent_pin() -> str:
    """Создать PIN родителя при первом запуске и вернуть его (только для лога)."""
    stored = get_meta("parent_pin_hash")
    if stored:
        return ""
    pin = f"{random.randint(1000, 9999)}"
    from services.learners import hash_pin

    set_meta("parent_pin_hash", hash_pin(pin))
    return pin


def reset_parent_pin() -> str:
    from services.learners import hash_pin

    pin = f"{random.randint(1000, 9999)}"
    set_meta("parent_pin_hash", hash_pin(pin))
    return pin


def _is_unlocked() -> bool:
    from services import auth

    user = auth.current_user()
    if user and user["role"] in (auth.ROLE_PARENT, auth.ROLE_ADMIN):
        return True
    return bool(session.get("parent_unlocked"))


def _require_unlock():
    if not _is_unlocked():
        return redirect(url_for("parent.gate"))
    return None


@bp.route("/parent")
def gate():
    from services import auth

    user = auth.current_user()
    if user and user["role"] in (auth.ROLE_PARENT, auth.ROLE_ADMIN):
        return redirect(url_for("parent.dashboard"))
    if _is_unlocked():
        return redirect(url_for("parent.dashboard"))
    locked_until = session.get(PIN_LOCKED_UNTIL, 0)
    return render_template(
        "parent/gate.html",
        attempts=session.get(PIN_ATTEMPTS, 0),
        max_attempts=MAX_ATTEMPTS,
        locked_for=max(0, int(locked_until - time.time())),
    )


@bp.route("/parent/unlock", methods=["POST"])
def unlock():
    from services.learners import verify_pin

    locked_until = session.get(PIN_LOCKED_UNTIL, 0)
    if locked_until > time.time():
        return redirect(url_for("parent.gate"))

    pin = (request.form.get("pin") or "").strip()
    stored = get_meta("parent_pin_hash") or ""
    if verify_pin(pin, stored):
        session["parent_unlocked"] = True
        session.pop(PIN_ATTEMPTS, None)
        session.pop(PIN_LOCKED_UNTIL, None)
        flash("Родительская зона открыта", "success")
        return redirect(url_for("parent.dashboard"))

    attempts = session.get(PIN_ATTEMPTS, 0) + 1
    session[PIN_ATTEMPTS] = attempts
    if attempts >= MAX_ATTEMPTS:
        session[PIN_LOCKED_UNTIL] = time.time() + LOCK_SECONDS
        session[PIN_ATTEMPTS] = 0
        flash("Слишком много попыток. Подождите 5 минут", "error")
    else:
        flash("Неверный PIN", "error")
    return redirect(url_for("parent.gate"))


@bp.route("/parent/lock", methods=["POST"])
def lock():
    session.pop("parent_unlocked", None)
    flash("Родительская зона закрыта", "info")
    return redirect(url_for("main.welcome"))


@bp.route("/parent/dashboard")
def dashboard():
    guard = _require_unlock()
    if guard:
        return guard
    from services import auth

    user = auth.current_user()
    learners = []
    if user and user["role"] == auth.ROLE_PARENT:
        # школьный режим: показываем только своих детей
        for child in auth.children_of(user["id"]):
            row = query_one(
                """SELECT l.* FROM learner_accounts la
                     JOIN learners l ON l.id = la.learner_id
                    WHERE la.user_id = ?""",
                (child["id"],),
            )
            if row:
                learners.append(row)
    else:
        learners = list(learners_service.list_learners())

    cards = []
    for learner in learners:
        stats = progress_service.learner_stats(learner["id"])
        stats["topics_total"] = len(topics_service.list_topics(grade=learner["grade"]))
        cards.append({
            "learner": learner,
            "stats": stats,
            "accuracy": progress_service.topic_accuracy(learner["id"]),
            "activity": progress_service.weekly_activity(learner["id"], 14),
            "badges": rewards_service.badge_list(learner["id"]),
            "sessions": query_all(
                """SELECT topic_slug, mode, task_count, correct_count, xp_gained, started_at
                     FROM play_sessions WHERE learner_id = ?
                    ORDER BY id DESC LIMIT 10""",
                (learner["id"],),
            ),
        })
    return render_template(
        "parent/dashboard.html",
        cards=cards,
        catalog=ACHIEVEMENTS,
        school_mode=bool(user and user["role"] == auth.ROLE_PARENT),
    )


def _school_children(user) -> list[dict]:
    """Дети с аккаунтами учеников и их классами."""
    from services import auth

    if not user or user["role"] != auth.ROLE_PARENT:
        return []
    result = []
    for child in auth.children_of(user["id"]):
        if child["role"] != auth.ROLE_STUDENT:
            continue
        classes = orgs.classes_of_student(child["id"])
        learner = query_one(
            """SELECT l.* FROM learner_accounts la
                 JOIN learners l ON l.id = la.learner_id
                WHERE la.user_id = ?""",
            (child["id"],),
        )
        grade = classes[0]["grade"] if classes else (learner["grade"] if learner else 3)
        result.append({
            "user": child,
            "grade": grade,
            "classes": classes,
            "learner": learner,
        })
    return result


@bp.route("/parent/assignments", methods=["GET", "POST"])
def assignments_page():
    guard = _require_unlock()
    if guard:
        return guard
    from services import auth

    user = auth.current_user()
    children = _school_children(user)
    grades = {child["grade"] for child in children}
    topics = [
        topic for topic in topics_service.list_topics()
        if not grades or topic["grade"] in grades
    ]
    groups: dict[str, dict] = {}
    for topic in topics:
        key = topic["subject_name"] or "Другое"
        group = groups.setdefault(key, {
            "name": key,
            "icon": topic["subject_icon"] or "📚",
            "topics": [],
        })
        group["topics"].append(topic)

    if request.method == "POST":
        if not children:
            flash(
                "Чтобы отправлять задания, привяжите аккаунт ребёнка по коду "
                "в настройках родительской зоны.",
                "error",
            )
            return redirect(url_for("parent.assignments_page"))
        child_ids = {
            int(value) for value in request.form.getlist("child_ids")
            if value.isdigit()
        }
        chosen_children = [child for child in children if child["user"]["id"] in child_ids]
        subject_id = request.form.get("subject_id", type=int)
        topic_slugs = request.form.getlist("topic_slugs")
        count = max(1, min(40, request.form.get("questions_count", type=int) or 10))
        kind = request.form.get("kind", "домашняя")
        due_date = request.form.get("due_date", "")
        title = (request.form.get("title") or "").strip()
        if not chosen_children:
            flash("Выберите хотя бы одного ребёнка", "error")
        elif not topic_slugs:
            flash("Выберите хотя бы одну тему", "error")
        else:
            created = 0
            for child in chosen_children:
                child_topics = [
                    topic["slug"] for topic in topics
                    if topic["slug"] in topic_slugs
                    and topic["grade"] == child["grade"]
                    and (not subject_id or topic["subject_id"] == subject_id)
                ]
                if not child_topics:
                    continue
                tasks = assignments_service.build_tasks(child_topics, count)
                if not tasks:
                    continue
                child_subject = subject_id
                if not child_subject:
                    first = next(
                        (topic for topic in topics if topic["slug"] == child_topics[0]), None
                    )
                    child_subject = first["subject_id"] if first else None
                assignments_service.create_assignment(
                    title=title or "Домашнее задание от родителя",
                    kind=kind,
                    description=request.form.get("description", ""),
                    subject_id=child_subject,
                    student_id=child["user"]["id"],
                    teacher_id=user["id"],
                    topic_slugs=child_topics,
                    questions_count=count,
                    time_limit=request.form.get("time_limit", type=int) or 0,
                    due_date=due_date,
                    status="опубликована",
                    tasks=tasks,
                )
                created += 1
            if created:
                flash(f"Задание отправлено: {created} ученик(ов)", "success")
                return redirect(url_for("parent.assignments_page"))
            flash(
                "Не удалось подобрать темы для выбранного класса. "
                "Выберите темы нужного предмета и класса.",
                "error",
            )

    sent = []
    if children:
        for assignment in assignments_service.list_assignments(teacher_id=user["id"]):
            results = assignments_service.results_of(assignment["id"])
            result = results[0] if results else None
            details = []
            if result is not None:
                try:
                    details = json.loads(result["answers"] or "[]")
                except (ValueError, TypeError):
                    details = []
            sent.append({
                "assignment": assignment,
                "result": result,
                "details": details,
            })
    return render_template(
        "parent/assignments.html",
        user=user,
        children=children,
        groups=sorted(groups.values(), key=lambda item: item["name"]),
        subjects=orgs.list_subjects(active_only=True),
        kinds=assignments_service.KINDS,
        sent=sent,
    )


@bp.route("/parent/learner/<int:learner_id>", methods=["GET", "POST"])
def learner_settings(learner_id: int):
    guard = _require_unlock()
    if guard:
        return guard
    from services import auth

    user = auth.current_user()
    if user and user["role"] == auth.ROLE_PARENT:
        owned = set()
        for child in auth.children_of(user["id"]):
            row = query_one(
                "SELECT learner_id FROM learner_accounts WHERE user_id = ?", (child["id"],)
            )
            if row:
                owned.add(row["learner_id"])
        if learner_id not in owned:
            abort(403)
    learner = learners_service.get_learner(learner_id)
    if not learner:
        abort(404)

    if request.method == "POST":
        action = request.form.get("action")
        if action == "profile":
            name = (request.form.get("name") or "").strip()[:24] or learner["name"]
            avatar = request.form.get("avatar") or learner["avatar"]
            grade = int(request.form.get("grade") or learner["grade"])
            learners_service.update_learner(learner_id, name=name, avatar=avatar, grade=grade)
            flash("Профиль обновлён", "success")
        elif action == "pin":
            pin = (request.form.get("pin") or "").strip()
            if not (pin.isdigit() and len(pin) == 4):
                flash("PIN должен состоять из 4 цифр", "error")
            else:
                learners_service.set_pin(learner_id, pin)
                flash("PIN ребёнка обновлён", "success")
        elif action == "settings":
            sound = 1 if request.form.get("sound_on") else 0
            voice = 1 if request.form.get("voice_on") else 0
            limit = max(0, min(300, int(request.form.get("daily_limit") or 0)))
            learners_service.update_learner(
                learner_id, sound_on=sound, voice_on=voice, daily_limit=limit
            )
            flash("Настройки сохранены", "success")
        elif action == "reset":
            learners_service.reset_progress(learner_id)
            flash("Прогресс сброшен", "info")
        elif action == "delete":
            learners_service.delete_learner(learner_id)
            flash("Профиль удалён", "info")
            return redirect(url_for("parent.dashboard"))
        return redirect(url_for("parent.learner_settings", learner_id=learner_id))

    stats = progress_service.learner_stats(learner_id)
    return render_template(
        "parent/learner.html",
        learner=learner,
        stats=stats,
        avatars=learners_service.AVATARS,
        accuracy=progress_service.topic_accuracy(learner_id),
        activity=progress_service.weekly_activity(learner_id, 14),
    )


@bp.route("/parent/learner/<int:learner_id>/export.csv")
def export_csv(learner_id: int):
    guard = _require_unlock()
    if guard:
        return guard
    learner = learners_service.get_learner(learner_id)
    if not learner:
        abort(404)

    buffer = io.StringIO()
    buffer.write("\ufeff")  # BOM — чтобы Excel корректно открыл кириллицу
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["Дата и время", "Тема", "Способ", "Задание", "Ответ ребёнка", "Правильный ответ", "Верно", "Время, мс", "Подсказки"])
    rows = query_all(
        """SELECT created_at, topic_slug, method_slug, generator, given_answer, expected,
                  correct, time_ms, hints_used
             FROM attempts WHERE learner_id = ? ORDER BY id DESC LIMIT 5000""",
        (learner_id,),
    )
    for row in rows:
        writer.writerow([
            row["created_at"], row["topic_slug"], row["method_slug"] or "", row["generator"] or "",
            row["given_answer"], row["expected"], "да" if row["correct"] else "нет",
            row["time_ms"], row["hints_used"],
        ])
    filename = f"progress_{learner['name'].replace(' ', '_')}.csv"
    return Response(
        buffer.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.route("/parent/settings", methods=["GET", "POST"])
def settings():
    guard = _require_unlock()
    if guard:
        return guard
    if request.method == "POST":
        action = request.form.get("action")
        if action == "pin":
            from services.learners import verify_pin

            current = (request.form.get("current_pin") or "").strip()
            new_pin = (request.form.get("new_pin") or "").strip()
            stored = get_meta("parent_pin_hash") or ""
            if not verify_pin(current, stored):
                flash("Текущий PIN указан неверно", "error")
            elif not (new_pin.isdigit() and len(new_pin) == 4):
                flash("Новый PIN должен состоять из 4 цифр", "error")
            else:
                from services.learners import hash_pin

                set_meta("parent_pin_hash", hash_pin(new_pin))
                flash("PIN родителя обновлён", "success")
        elif action == "reset_parent_pin":
            pin = reset_parent_pin()
            flash(f"Новый PIN родителя: {pin}", "info")
        elif action == "reset_all":
            for learner in learners_service.list_learners():
                learners_service.reset_progress(learner["id"])
            flash("Весь прогресс сброшен", "info")
        return redirect(url_for("parent.settings"))

    return render_template("parent/settings.html")
