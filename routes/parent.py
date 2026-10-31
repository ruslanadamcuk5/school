"""Родительская зона: статистика, управление профилями, экспорт."""
from __future__ import annotations

import csv
import io
import json
import secrets
import time
from flask import (
    Blueprint,
    Response,
    abort,
    jsonify,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from content.achievements import ACHIEVEMENTS
from database import execute, get_meta, query_all, query_one, set_meta
from services import assignments as assignments_service
from services import learners as learners_service
from services import map_settings as map_settings_service
from services import orgs
from services import progress as progress_service
from services import rewards as rewards_service
from services import topics as topics_service

bp = Blueprint("parent", __name__)

PIN_ATTEMPTS = "parent_pin_attempts"
PIN_LOCKED_UNTIL = "parent_pin_locked_until"
MAX_ATTEMPTS = 5
LOCK_SECONDS = 300


def _new_pin() -> str:
    """Криптостойкий 4-значный PIN (secrets, а не random)."""
    return f"{secrets.randbelow(9000) + 1000}"


def ensure_parent_pin() -> str:
    """Создать PIN родителя при первом запуске и вернуть его (только для лога)."""
    stored = get_meta("parent_pin_hash")
    if stored:
        return ""
    pin = _new_pin()
    from services.learners import hash_pin

    set_meta("parent_pin_hash", hash_pin(pin))
    return pin


def reset_parent_pin() -> str:
    from services.learners import hash_pin

    pin = _new_pin()
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


def _parent_throttle_key() -> str:
    from services import rate_limit

    return rate_limit.make_key("parent-pin", rate_limit.client_ip(request))


def _visible_learners(user) -> list:
    """Профили, которые можно показывать в родительской зоне.

    * администратор — все;
    * родитель с аккаунтом — только свои дети;
    * семейный режим — только профили своей семьи (ключ в сессии).
    """
    from services import auth

    if user and user["role"] == auth.ROLE_ADMIN:
        return list(learners_service.list_learners())
    if user and user["role"] == auth.ROLE_PARENT:
        result = []
        for child in auth.children_of(user["id"]):
            row = query_one(
                """SELECT l.* FROM learner_accounts la
                     JOIN learners l ON l.id = la.learner_id
                    WHERE la.user_id = ?""",
                (child["id"],),
            )
            if row:
                result.append(row)
        return result
    return learners_service.family_learners()


def _may_manage(learner_id: int) -> bool:
    from services import auth

    user = auth.current_user()
    if user and user["role"] == auth.ROLE_ADMIN:
        return True
    return any(int(row["id"]) == learner_id for row in _visible_learners(user))


@bp.route("/parent")
def gate():
    from services import auth

    user = auth.current_user()
    if user and user["role"] in (auth.ROLE_PARENT, auth.ROLE_ADMIN):
        return redirect(url_for("parent.dashboard"))
    if _is_unlocked():
        return redirect(url_for("parent.dashboard"))
    from services import rate_limit

    locked_until = session.get(PIN_LOCKED_UNTIL, 0)
    locked_for = max(
        0,
        int(locked_until - time.time()),
        rate_limit.blocked_for(_parent_throttle_key()),
    )
    return render_template(
        "parent/gate.html",
        attempts=session.get(PIN_ATTEMPTS, 0),
        max_attempts=MAX_ATTEMPTS,
        locked_for=locked_for,
    )


@bp.route("/parent/unlock", methods=["POST"])
def unlock():
    from services import learners as learners_service
    from services import rate_limit

    throttle_key = _parent_throttle_key()
    wait = rate_limit.blocked_for(throttle_key)
    if wait:
        flash(f"Слишком много попыток. Подождите {wait} с.", "error")
        return redirect(url_for("parent.gate"))

    pin = (request.form.get("pin") or "").strip()
    stored = get_meta("parent_pin_hash") or ""
    if learners_service.verify_pin(pin, stored):
        rate_limit.clear(throttle_key)
        session["parent_unlocked"] = True
        session.pop(PIN_ATTEMPTS, None)
        session.pop(PIN_LOCKED_UNTIL, None)
        flash("Родительская зона открыта", "success")
        return redirect(url_for("parent.dashboard"))

    attempts = session.get(PIN_ATTEMPTS, 0) + 1
    session[PIN_ATTEMPTS] = attempts
    locked = rate_limit.register_failure(
        throttle_key, max_attempts=MAX_ATTEMPTS, lock_seconds=LOCK_SECONDS
    )
    if locked or attempts >= MAX_ATTEMPTS:
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
    learners = _visible_learners(user)
    unclaimed = (
        learners_service.unclaimed_learners()
        if not (user and user["role"] in (auth.ROLE_PARENT, auth.ROLE_ADMIN))
        else []
    )

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
        unclaimed=unclaimed,
        catalog=ACHIEVEMENTS,
        school_mode=bool(user and user["role"] == auth.ROLE_PARENT),
    )


@bp.route("/parent/claim/<int:learner_id>", methods=["POST"])
def claim_profile(learner_id: int):
    """Привязать «старый» профиль (созданный до изоляции семей) к своей семье."""
    guard = _require_unlock()
    if guard:
        return guard
    from services import auth

    user = auth.current_user()
    if user and user["role"] in (auth.ROLE_PARENT, auth.ROLE_ADMIN):
        # Родитель с аккаунтом и так видит только своих детей.
        abort(403)
    key = learners_service.family_key(create=True)
    if learners_service.claim_learner(learner_id, key):
        flash("Профиль добавлен в вашу семью", "success")
    else:
        flash("Профиль уже привязан к другой семье", "error")
    return redirect(url_for("parent.dashboard"))


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
        task_type = request.form.get("task_type", "test")
        if task_type not in assignments_service.TASK_TYPES:
            task_type = "test"
        due_date = request.form.get("due_date", "")
        title = (request.form.get("title") or "").strip()
        description = (request.form.get("description") or "").strip()
        reference_text = (request.form.get("reference_text") or "").strip()
        audio_text = (request.form.get("audio_text") or "").strip()
        allow_photo = (
            "1" in request.form.getlist("allow_photo")
            or "allow_photo" not in request.form
        )
        allow_text = (
            "1" in request.form.getlist("allow_text")
            or "allow_text" not in request.form
        )
        if not chosen_children:
            flash("Выберите хотя бы одного ребёнка", "error")
        elif not allow_photo and not allow_text:
            flash("Разрешите хотя бы один способ ответа: текстом или фото.", "error")
        elif task_type in ("test", "read") and not topic_slugs:
            flash("Выберите хотя бы одну тему", "error")
        elif task_type == "dictation" and not reference_text and not topic_slugs:
            flash("Вставьте текст диктанта или выберите тему пособия.", "error")
        elif task_type == "other" and not description:
            flash("Опишите задание для ребёнка.", "error")
        else:
            created = 0
            for child in chosen_children:
                child_topics = [
                    topic["slug"] for topic in topics
                    if topic["slug"] in topic_slugs
                    and topic["grade"] == child["grade"]
                    and (not subject_id or topic["subject_id"] == subject_id)
                ]
                if task_type in ("test", "read") and not child_topics:
                    continue
                if task_type == "read":
                    child_topics = child_topics[:1]
                tasks = assignments_service.build_typed_tasks(
                    task_type,
                    child_topics,
                    count,
                    description=description,
                    reference_text=reference_text,
                    audio_text=audio_text,
                )
                if not tasks:
                    continue
                child_subject = subject_id
                if not child_subject and child_topics:
                    first = next(
                        (topic for topic in topics if topic["slug"] == child_topics[0]), None
                    )
                    child_subject = first["subject_id"] if first else None
                default_title = {
                    "test": "Домашнее задание от родителя",
                    "read": "Прочитать тему",
                    "dictation": "Диктант",
                    "other": "Задание от родителя",
                }.get(task_type, "Домашнее задание от родителя")
                assignments_service.create_assignment(
                    title=title or default_title,
                    kind=kind,
                    description=description,
                    subject_id=child_subject,
                    student_id=child["user"]["id"],
                    teacher_id=user["id"],
                    topic_slugs=child_topics,
                    questions_count=len(tasks),
                    time_limit=request.form.get("time_limit", type=int) or 0,
                    due_date=due_date,
                    status="опубликована",
                    tasks=tasks,
                    task_type=task_type,
                    reference_text=reference_text,
                    audio_text=audio_text,
                    allow_photo=allow_photo,
                    allow_text=allow_text,
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
                "photos": assignments_service.result_photos(result),
            })

    # Работы, которые задал учитель: родитель должен видеть их так же подробно.
    incoming: list[dict] = []
    if children:
        child_ids = [int(child["user"]["id"]) for child in children]
        marks = ",".join("?" for _ in child_ids)
        rows = query_all(
            f"""SELECT DISTINCT a.*, u.first_name AS author_first, u.last_name AS author_last
                  FROM assignments a
                  LEFT JOIN users u ON u.id = a.teacher_id
                 WHERE a.status IN ('опубликована', 'закрыта')
                   AND (a.student_id IN ({marks})
                        OR a.class_id IN (SELECT class_id FROM class_students
                                           WHERE student_id IN ({marks})))
                 ORDER BY a.created_at DESC, a.id DESC
                 LIMIT 60""",
            (*child_ids, *child_ids),
        )
        for assignment in rows:
            targets = [
                child for child in children
                if int(assignment["student_id"] or 0) == int(child["user"]["id"])
                or (
                    assignment["class_id"]
                    and query_one(
                        "SELECT 1 FROM class_students WHERE class_id = ? AND student_id = ?",
                        (assignment["class_id"], int(child["user"]["id"])),
                    )
                )
            ]
            for child in targets:
                result = query_one(
                    "SELECT * FROM assignment_results WHERE assignment_id = ? AND student_id = ?",
                    (assignment["id"], int(child["user"]["id"])),
                )
                details = []
                if result is not None:
                    try:
                        details = json.loads(result["answers"] or "[]")
                    except (ValueError, TypeError):
                        details = []
                if result is not None:
                    execute(
                        """INSERT INTO assignment_views
                               (assignment_id, student_id, viewer_id, role)
                           VALUES (?, ?, ?, 'parent')
                           ON CONFLICT(assignment_id, student_id, viewer_id)
                           DO UPDATE SET viewed_at = datetime('now')""",
                        (int(assignment["id"]), int(child["user"]["id"]), int(user["id"])),
                    )
                incoming.append({
                    "assignment": assignment,
                    "child": child,
                    "result": result,
                    "details": details,
                    "photos": assignments_service.result_photos(result),
                    "author": " ".join(
                        part for part in (assignment["author_first"], assignment["author_last"]) if part
                    ).strip(),
                })
    return render_template(
        "parent/assignments.html",
        user=user,
        children=children,
        groups=sorted(groups.values(), key=lambda item: item["name"]),
        subjects=orgs.list_subjects(active_only=True),
        kinds=assignments_service.KINDS,
        task_types=assignments_service.TASK_TYPES,
        sent=sent,
        incoming=incoming,
    )


@bp.route("/parent/learner/<int:learner_id>", methods=["GET", "POST"])
def learner_settings(learner_id: int):
    guard = _require_unlock()
    if guard:
        return guard
    # Доступ только к профилям своей семьи (или своим детям / админу).
    if not _may_manage(learner_id):
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
    if not _may_manage(learner_id):
        abort(403)
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
            from services import auth as auth_service

            for learner in _visible_learners(auth_service.current_user()):
                learners_service.reset_progress(learner["id"])
            flash("Прогресс семьи сброшен", "info")
        return redirect(url_for("parent.settings"))

    return render_template("parent/settings.html")


# ------------------------------------------------------------------ сообщения
def _pending_by_child(children: list) -> dict[int, list]:
    """Невыполненные задания по каждому ребёнку (для текста напоминания)."""
    result: dict[int, list] = {}
    for child in children:
        result[int(child["id"])] = query_all(
            """SELECT a.title, a.due_date FROM assignments a
                WHERE a.student_id = ? AND a.status = 'опубликована'
                  AND NOT EXISTS (
                      SELECT 1 FROM assignment_results r
                       WHERE r.assignment_id = a.id AND r.student_id = a.student_id)
                ORDER BY a.due_date, a.id""",
            (int(child["id"]),),
        )
    return result


@bp.route("/parent/messages", methods=["GET", "POST"])
def messages():
    guard = _require_unlock()
    if guard:
        return guard
    from services import auth as auth_service
    from services import notifications as notifications_service

    user = auth_service.current_user()
    school_mode = bool(user and user["role"] == auth_service.ROLE_PARENT)
    children = auth_service.children_of(int(user["id"])) if school_mode else []
    family = [row for row in _visible_learners(user)] if not school_mode else []
    pending = _pending_by_child(children) if school_mode else {}

    if request.method == "POST":
        action = request.form.get("action") or "message"
        kind = (
            notifications_service.KIND_REMINDER
            if action == "reminder"
            else notifications_service.KIND_MESSAGE
        )
        text = (request.form.get("text") or "").strip()
        chosen = request.form.getlist("child_id")
        title = (
            "Напоминание от родителя"
            if kind == notifications_service.KIND_REMINDER
            else "Сообщение от родителя"
        )

        if school_mode:
            allowed = {str(child["id"]): child for child in children}
            targets = [int(value) for value in chosen if value in allowed]
        else:
            allowed = {str(row["id"]): row for row in family}
            targets = [int(value) for value in chosen if value in allowed]

        if not targets:
            flash("Выберите хотя бы одного ребёнка", "error")
            return redirect(url_for("parent.messages"))
        if not text:
            if kind == notifications_service.KIND_REMINDER and school_mode:
                lines = []
                for target in targets:
                    for row in pending.get(target, [])[:5]:
                        due = f" до {row['due_date']}" if row["due_date"] else ""
                        lines.append(f"«{row['title']}»{due}")
                if lines:
                    text = "Не забудь выполнить: " + "; ".join(dict.fromkeys(lines)) + "."
            if not text:
                text = "Проверь, пожалуйста, задания в личном кабинете."

        if school_mode:
            sent = notifications_service.send_message(
                user,
                targets,
                text,
                kind=kind,
                title=title,
                index_link="/student/works",
            )
        else:
            sent = notifications_service.send_message(
                None,
                [],
                text,
                kind=kind,
                title=title,
                index_link="/map",
                learner_ids=targets,
            )
        flash(f"Отправлено: {sent}", "success")
        return redirect(url_for("parent.messages"))

    return render_template(
        "parent/messages.html",
        children=children,
        family=family,
        pending=pending,
        school_mode=school_mode,
    )


# ------------------------------------------------------------------ геолокация
def _map_tz() -> int:
    from services import locations as locations_service

    try:
        return locations_service.clamp_tz(int(request.args.get("tz") or 0))
    except (TypeError, ValueError):
        return 0


def _map_learner(learner_id: int | None):
    from services import auth as auth_service

    user = auth_service.current_user()
    learners = _visible_learners(user)
    if not learners:
        return None, learners
    if learner_id is None:
        return learners[0], learners
    for row in learners:
        if int(row["id"]) == int(learner_id):
            return row, learners
    return None, learners


@bp.route("/parent/map")
def map_page():
    guard = _require_unlock()
    if guard:
        return guard
    learner_id = request.args.get("learner_id", type=int)
    selected, learners = _map_learner(learner_id)
    return render_template(
        "parent/map.html",
        learners=learners,
        selected=selected,
        retention_days=14,
        map_settings=map_settings_service.public_settings(),
    )


@bp.route("/parent/map/data")
def map_data():
    guard = _require_unlock()
    if guard:
        return guard
    from services import locations as locations_service

    learner_id = request.args.get("learner_id", type=int)
    profile, _ = _map_learner(learner_id)
    if profile is None:
        return jsonify({"ok": False, "error": "not_found", "message": "Профиль не найден"}), 404
    tz_minutes = _map_tz()
    try:
        day = locations_service.parse_day(request.args.get("date"), tz_minutes)
    except locations_service.LocationError as exc:
        return jsonify({"ok": False, "error": exc.code, "message": exc.message}), exc.status
    data = locations_service.trail(int(profile["id"]), day, tz_minutes)
    return jsonify(
        {
            "ok": True,
            "learner": {
                "id": int(profile["id"]),
                "name": profile["name"],
                "avatar": profile["avatar"],
                "grade": int(profile["grade"] or 1),
            },
            **data,
            "today": locations_service.today_for_tz(tz_minutes).isoformat(),
            "retention_days": locations_service.RETENTION_DAYS,
            "map": map_settings_service.public_settings(),
        }
    )


@bp.route("/parent/map/overview")
def map_overview():
    guard = _require_unlock()
    if guard:
        return guard
    from services import auth as auth_service
    from services import locations as locations_service

    user = auth_service.current_user()
    learners = _visible_learners(user)
    tz_minutes = _map_tz()
    return jsonify(
        {
            "ok": True,
            "children": locations_service.overview(learners, tz_minutes),
            "date": locations_service.today_for_tz(tz_minutes).isoformat(),
            "retention_days": locations_service.RETENTION_DAYS,
            "map": map_settings_service.public_settings(),
        }
    )


@bp.route("/parent/map/force/<int:learner_id>", methods=["POST"])
def map_force_location(learner_id: int):
    guard = _require_unlock()
    if guard:
        return guard
    from services import locations as locations_service

    profile, _ = _map_learner(learner_id)
    if profile is None:
        return jsonify({"ok": False, "error": "not_found", "message": "Профиль не найден"}), 404
    from services import auth as auth_service

    user = auth_service.current_user()
    info = locations_service.force_request(
        int(profile["id"]), int(user["id"]) if user else 0
    )
    return jsonify(
        {
            "ok": True,
            "message": (
                f"Команда отправлена: {profile['name']} получит запрос "
                "и включит геолокацию на телефоне"
            ),
            "force_pending": info["force_pending"],
            "settings": info,
        }
    )


@bp.route("/parent/map/request/<int:learner_id>", methods=["POST"])
def map_request_location(learner_id: int):
    """Совместимость со старыми страницами: просьба теперь принудительная."""
    return map_force_location(learner_id)
