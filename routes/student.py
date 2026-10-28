"""Кабинет ученика: работы, пособия, расписание, прогресс."""
from __future__ import annotations

import json
import time

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from database import execute, query_all
from services import assignment_photos
from services import assignments as assignments_service
from services import auth, learners as learners_service, orgs, progress, textbooks

bp = Blueprint("student", __name__, url_prefix="/student")


def _student_id() -> int:
    user = auth.current_user()
    return user["id"] if user else 0


def _collect_answers(tasks: list[dict], form) -> list[str]:
    """Ответы по номерам заданий.

    Раньше все варианты ответа имели одинаковое имя `answer`, поэтому браузер
    отправлял только один выбранный вариант на всю работу, а остальные задания
    проверялись как пустые. Новые формы используют `answer_0`, `answer_1`, …;
    старый вариант оставлен для совместимости.
    """
    legacy = form.getlist("answer")
    answers = []
    for index in range(len(tasks)):
        value = form.get(f"answer_{index}")
        if value is None:
            value = legacy[index] if index < len(legacy) else ""
        answers.append(value)
    return answers


def _can_open_assignment(user, assignment) -> bool:
    if assignment["status"] != "опубликована":
        return False
    if assignment["student_id"]:
        return int(assignment["student_id"]) == int(user["id"])
    if assignment["class_id"]:
        classes = orgs.classes_of_student(user["id"])
        return assignment["class_id"] in [klass["id"] for klass in classes]
    return False


@bp.route("/")
@auth.role_required(auth.ROLE_STUDENT)
def dashboard():
    user = auth.current_user()
    classes = orgs.classes_of_student(user["id"])
    works = assignments_service.list_assignments(student_id=user["id"], status="опубликована")
    learner = learners_service.current_learner()
    stats = progress.learner_stats(learner["id"]) if learner else {}
    done = [w for w in works if assignments_service.get_result(w["id"], user["id"])]
    pending = [w for w in works if w not in done]
    grade = classes[0]["grade"] if classes else (learner["grade"] if learner else 3)
    return render_template(
        "student/dashboard.html",
        user=user,
        classes=classes,
        works=works,
        pending=pending,
        done=done,
        stats=stats,
        textbooks=textbooks.textbooks_for_grade(grade),
        subjects=orgs.list_subjects(active_only=True),
    )


@bp.route("/works")
@auth.role_required(auth.ROLE_STUDENT)
def works():
    user = auth.current_user()
    rows = []
    for row in assignments_service.list_assignments(
        student_id=user["id"], status="опубликована"
    ):
        item = dict(row)
        item["result"] = assignments_service.get_result(row["id"], user["id"])
        rows.append(item)
    return render_template("student/works.html", user=user, works=rows)


@bp.route("/works/<int:assignment_id>")
@auth.role_required(auth.ROLE_STUDENT)
def work_detail(assignment_id: int):
    user = auth.current_user()
    assignment = assignments_service.get_assignment(assignment_id)
    if not assignment:
        abort(404)
    if not _can_open_assignment(user, assignment):
        abort(403)
    topics = assignments_service.assignment_topics(assignment)
    result = assignments_service.get_result(assignment_id, user["id"])
    if result:
        details = json.loads(result["answers"] or "[]")
        return render_template(
            "student/work_result.html",
            user=user,
            assignment=assignment,
            result=result,
            details=details,
            photos=assignments_service.result_photos(result),
            grade=assignments_service.grade_for_percent(
                round(result["score"] / result["max_score"] * 100) if result["max_score"] else 0
            ),
        )
    tasks = assignments_service.assignment_tasks(assignment)
    return render_template(
        "student/work.html",
        user=user,
        assignment=assignment,
        topics=topics,
        tasks=tasks,
    )


@bp.route("/works/<int:assignment_id>/submit", methods=["POST"])
@auth.role_required(auth.ROLE_STUDENT)
def work_submit(assignment_id: int):
    user = auth.current_user()
    assignment = assignments_service.get_assignment(assignment_id)
    if not assignment:
        abort(404)
    if not _can_open_assignment(user, assignment):
        abort(403)

    tasks = assignments_service.assignment_tasks(assignment)
    given = _collect_answers(tasks, request.form)
    uploads = request.files.getlist("photos")
    has_text = any(str(value or "").strip() for value in given)
    if uploads and not assignment["allow_photo"]:
        flash("В этой работе нельзя отвечать фотографией.", "error")
        return redirect(url_for("student.work_detail", assignment_id=assignment_id))
    if has_text and not assignment["allow_text"]:
        flash("В этой работе нельзя отвечать текстом — прикрепите фото.", "error")
        return redirect(url_for("student.work_detail", assignment_id=assignment_id))
    try:
        photos = assignment_photos.save_photos(
            uploads, assignment_id, user["id"]
        )
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("student.work_detail", assignment_id=assignment_id))
    duration = int(request.form.get("duration") or 0)
    result = assignments_service.evaluate_submission(
        assignment, tasks, given, photos, user_id=user["id"]
    )
    assignments_service.save_result(
        assignment_id,
        user["id"],
        result["score"],
        result["max_score"],
        result["details"],
        duration,
        submission_type=result["submission_type"],
        photos=result["photos"],
        ai_status=result["ai_status"],
        ai_feedback=result["ai_feedback"],
        ai_model=result["ai_model"],
        ai_score=result["ai_score"],
    )
    if result["ai_status"] == "failed":
        flash("Работа сохранена, но ИИ не смог её проверить. Учитель увидит ответ.", "info")
    elif result["ai_status"] == "checked":
        flash("Работа отправлена, ИИ проверил ответы и указал на ошибки.", "success")
    else:
        flash("Работа отправлена учителю!", "success")
    return redirect(url_for("student.work_detail", assignment_id=assignment_id))


@bp.route("/works/<int:assignment_id>/retry", methods=["POST"])
@auth.role_required(auth.ROLE_STUDENT)
def work_retry(assignment_id: int):
    user = auth.current_user()
    assignment = assignments_service.get_assignment(assignment_id)
    if not assignment:
        abort(404)
    if not _can_open_assignment(user, assignment):
        abort(403)
    old = assignments_service.get_result(assignment_id, user["id"])
    if old:
        assignment_photos.delete_photos(assignments_service.result_photos(old))
    execute(
        "DELETE FROM assignment_results WHERE assignment_id = ? AND student_id = ?",
        (assignment_id, user["id"]),
    )
    flash("Работу можно пройти заново.", "info")
    return redirect(url_for("student.work_detail", assignment_id=assignment_id))


@bp.route(
    "/works/<int:assignment_id>/photo/<int:student_id>/<path:filename>"
)
@auth.login_required
def work_photo(assignment_id: int, student_id: int, filename: str):
    """Фото письменного ответа: доступно ученику, учителю и родителю."""
    user = auth.current_user()
    assignment = assignments_service.get_assignment(assignment_id)
    if not assignment:
        abort(404)
    allowed = False
    if user["role"] == auth.ROLE_ADMIN:
        allowed = True
    elif user["role"] == auth.ROLE_STUDENT:
        allowed = int(user["id"]) == int(student_id) and _can_open_assignment(user, assignment)
    elif user["role"] == auth.ROLE_TEACHER:
        allowed = int(assignment["teacher_id"] or 0) == int(user["id"])
    elif user["role"] == auth.ROLE_PARENT:
        allowed = any(
            int(child["id"]) == int(student_id) for child in auth.children_of(user["id"])
        )
    if not allowed:
        abort(403)
    path = assignment_photos.absolute_path(
        f"{assignment_id}/{student_id}/{filename}"
    )
    if not path:
        abort(404)
    return send_file(path, conditional=True)


@bp.route("/textbooks")
@auth.role_required(auth.ROLE_STUDENT)
def textbooks_page():
    user = auth.current_user()
    classes = orgs.classes_of_student(user["id"])
    learner = learners_service.current_learner()
    grades = sorted({c["grade"] for c in classes}) or [learner["grade"] if learner else 3]
    grade = request.args.get("grade", type=int) or grades[0]
    subject_id = request.args.get("subject_id", type=int)
    rows = textbooks.textbooks_for_grade(grade, subject_id)
    enriched = []
    for row in rows:
        item = dict(row)
        item["links"] = textbooks.textbook_topics(row["id"])
        enriched.append(item)
    return render_template(
        "student/textbooks.html",
        user=user,
        textbooks=enriched,
        subjects=orgs.list_subjects(active_only=True),
        grades=grades,
        selected_grade=grade,
        selected_subject=subject_id,
    )


@bp.route("/schedule")
@auth.role_required(auth.ROLE_STUDENT)
def schedule():
    user = auth.current_user()
    items = orgs.schedule_for_student(user["id"])
    grid = {}
    for item in items:
        grid.setdefault(item["weekday"], []).append(item)
    return render_template(
        "student/schedule.html",
        user=user,
        grid=grid,
        weekdays=orgs.WEEKDAYS_LIST,
    )


@bp.route("/badges")
@auth.role_required(auth.ROLE_STUDENT)
def badges():
    from content.achievements import ACHIEVEMENTS
    from services.rewards import badge_list

    user = auth.current_user()
    owned = {b["badge_key"] for b in badge_list(user["id"])}
    return render_template(
        "student/badges.html",
        user=user,
        catalog=ACHIEVEMENTS,
        owned=owned,
    )
