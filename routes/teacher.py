"""Кабинет учителя: классы, ученики, курсы, темы, работы, расписание."""
from __future__ import annotations

import json
from datetime import date

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from database import execute, query_all
from services import assignments as assignments_service
from services import auth, orgs, progress, textbooks
from services import topics as topics_service

bp = Blueprint("teacher", __name__, url_prefix="/teacher")


def _teacher_id() -> int:
    user = auth.current_user()
    return user["id"] if user else 0


def _own_classes() -> list:
    return orgs.classes_of_teacher(_teacher_id())


def _available_topics(user) -> list:
    """Темы предметов, доступные учителю (по классам, где он преподаёт)."""
    rows = topics_service.list_topics()
    if user and user["role"] == auth.ROLE_ADMIN:
        return rows
    grades = {klass["grade"] for klass in _own_classes()}
    if grades:
        rows = [row for row in rows if row["grade"] in grades]
    return rows


def _topic_groups(topics: list) -> list[dict]:
    groups: dict[str, dict] = {}
    for topic in topics:
        key = topic["subject_name"] or "Другое"
        group = groups.setdefault(key, {
            "name": key,
            "icon": topic["subject_icon"] or "📚",
            "topics": [],
        })
        group["topics"].append(topic)
    return sorted(groups.values(), key=lambda item: item["name"])


@bp.route("/")
@auth.teacher_required
def dashboard():
    user = auth.current_user()
    classes = _own_classes()
    class_ids = [c["id"] for c in classes]
    students = []
    for row in classes:
        for student in orgs.students_of_class(row["id"]):
            students.append({"student": student, "class": row})
    works = assignments_service.list_assignments(teacher_id=user["id"])[:8]
    courses = orgs.list_courses(teacher_id=user["id"])
    needs_attention = []
    for assignment in works:
        if assignment["status"] != "опубликована":
            continue
        done = assignment["done_count"] or 0
        total = assignment["students_count"] or 0
        if total and done < total:
            needs_attention.append({
                "assignment": assignment,
                "done": done,
                "total": total,
                "pending": total - done,
            })
    return render_template(
        "teacher/dashboard.html",
        user=user,
        classes=classes,
        students=students,
        works=works,
        courses=courses,
        needs_attention=needs_attention,
    )


@bp.route("/classes/<int:class_id>")
@auth.teacher_required
def class_detail(class_id: int):
    user = auth.current_user()
    row = orgs.get_class(class_id)
    if not row:
        abort(404)
    if user["role"] != auth.ROLE_ADMIN and row["teacher_id"] != user["id"]:
        abort(403)
    students = orgs.students_of_class(class_id)
    stats = []
    for student in students:
        learner = query_all(
            "SELECT learner_id FROM learner_accounts WHERE user_id = ?", (student["id"],)
        )
        item = {"student": student, "accuracy": None, "xp": 0, "attempts": 0}
        if learner:
            data = progress.learner_stats(learner[0]["learner_id"])
            item["accuracy"] = data.get("accuracy", 0)
            item["xp"] = data.get("xp", 0)
            item["attempts"] = data.get("total_attempts", 0)
        stats.append(item)
    works = assignments_service.list_assignments(class_id=class_id)
    schedule = orgs.list_schedule(class_id)
    courses = orgs.list_courses(class_id=class_id)
    return render_template(
        "teacher/class.html",
        user=user,
        klass=row,
        class_title=orgs.class_title(row),
        students=stats,
        works=works,
        schedule=schedule,
        courses=courses,
        weekdays=orgs.WEEKDAYS_LIST,
    )


@bp.route("/classes/<int:class_id>/students", methods=["POST"])
@auth.teacher_required
def manage_students(class_id: int):
    row = orgs.get_class(class_id)
    if not row:
        abort(404)
    action = request.form.get("action")
    if action == "add":
        student_id = request.form.get("student_id", type=int)
        login_name = (request.form.get("student_login") or "").strip()
        if not student_id and login_name:
            found = auth.get_user_by_login(auth.normalize_login(login_name))
            if not found:
                flash(f"Ученик с логином «{login_name}» не найден", "error")
                return redirect(url_for("teacher.class_detail", class_id=class_id))
            if found["role"] != auth.ROLE_STUDENT:
                flash("Это аккаунт не ученика", "error")
                return redirect(url_for("teacher.class_detail", class_id=class_id))
            student_id = found["id"]
        if student_id:
            orgs.add_student_to_class(class_id, student_id)
            flash("Ученик добавлен в класс", "success")
    elif action == "remove":
        student_id = request.form.get("student_id", type=int)
        if student_id:
            orgs.remove_student_from_class(class_id, student_id)
            flash("Ученик убран из класса", "info")
    return redirect(url_for("teacher.class_detail", class_id=class_id))


@bp.route("/students")
@auth.teacher_required
def students():
    user = auth.current_user()
    rows = []
    for klass in _own_classes():
        for student in orgs.students_of_class(klass["id"]):
            rows.append({"student": student, "class": klass})
    return render_template("teacher/students.html", user=user, rows=rows, classes=_own_classes())


# --------------------------------------------------------------- курсы
@bp.route("/courses")
@auth.teacher_required
def courses():
    user = auth.current_user()
    return render_template(
        "teacher/courses.html",
        user=user,
        courses=orgs.list_courses(teacher_id=user["id"]),
        subjects=orgs.list_subjects(active_only=True),
        classes=_own_classes(),
    )


@bp.route("/courses/new", methods=["GET", "POST"])
@auth.teacher_required
def course_new():
    user = auth.current_user()
    if request.method == "POST":
        subject_id = request.form.get("subject_id", type=int)
        title = (request.form.get("title") or "").strip()
        grade = request.form.get("grade", type=int) or 3
        if not subject_id or not title:
            flash("Укажите предмет и название курса", "error")
        else:
            course_id = orgs.create_course(
                subject_id, title, grade,
                description=request.form.get("description", ""),
                teacher_id=user["id"],
                school_id=request.form.get("school_id", type=int),
            )
            orgs.set_course_classes(course_id, [
                int(x) for x in request.form.getlist("class_ids") if x.isdigit()
            ])
            flash("Курс создан. Настройте темы.", "success")
            return redirect(url_for("teacher.course_topics", course_id=course_id))
    return render_template(
        "teacher/course_form.html",
        user=user,
        subjects=orgs.list_subjects(active_only=True),
        classes=_own_classes(),
        course=None,
    )


@bp.route("/courses/<int:course_id>/topics", methods=["GET", "POST"])
@auth.teacher_required
def course_topics(course_id: int):
    user = auth.current_user()
    course = orgs.get_course(course_id)
    if not course:
        abort(404)
    if user["role"] != auth.ROLE_ADMIN and course["teacher_id"] != user["id"]:
        abort(403)

    current = {row["topic_slug"]: row for row in orgs.course_topics(course_id)}
    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "add_topic":
            title = (request.form.get("title") or "").strip()
            if not title:
                flash("Введите название темы", "error")
            else:
                slug = topics_service.create_topic(
                    course["subject_id"], course["grade"], title,
                    description=request.form.get("description", ""),
                )
                orgs.set_course_topics(course_id, list(current) + [slug])
                flash(f"Тема «{title}» добавлена", "success")
        else:
            selected = request.form.getlist("topic_slugs")
            valid = {
                row["slug"]
                for row in topics_service.list_topics(
                    subject_id=course["subject_id"], grade=course["grade"]
                )
            }
            orgs.set_course_topics(course_id, [slug for slug in selected if slug in valid])
            flash("Состав тем курса сохранён", "success")
        return redirect(url_for("teacher.course_topics", course_id=course_id))

    available = topics_service.list_topics(
        subject_id=course["subject_id"], grade=course["grade"]
    )
    rows = []
    for topic in available:
        state = current.get(topic["slug"])
        rows.append({
            "topic": topic,
            "enabled": bool(state and state["enabled"]),
            "order": state["order_index"] if state else None,
        })
    return render_template(
        "teacher/course_topics.html",
        user=user,
        course=course,
        rows=rows,
        current_count=sum(1 for r in rows if r["enabled"]),
    )


@bp.route("/courses/<int:course_id>/delete", methods=["POST"])
@auth.teacher_required
def course_delete(course_id: int):
    course = orgs.get_course(course_id)
    if not course:
        abort(404)
    user = auth.current_user()
    if user["role"] != auth.ROLE_ADMIN and course["teacher_id"] != user["id"]:
        abort(403)
    orgs.delete_course(course_id)
    flash("Курс удалён", "info")
    return redirect(url_for("teacher.courses"))


# --------------------------------------------------------------- работы
@bp.route("/works")
@auth.teacher_required
def works():
    user = auth.current_user()
    return render_template(
        "teacher/works.html",
        user=user,
        works=assignments_service.list_assignments(teacher_id=user["id"]),
        classes=_own_classes(),
        courses=orgs.list_courses(teacher_id=user["id"]),
    )


@bp.route("/works/new", methods=["GET", "POST"])
@auth.teacher_required
def work_new():
    user = auth.current_user()
    topics = _available_topics(user)
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        kind = request.form.get("kind", "проверочная")
        task_type = request.form.get("task_type", "test")
        if task_type not in assignments_service.TASK_TYPES:
            task_type = "test"
        class_id = request.form.get("class_id", type=int)
        course_id = request.form.get("course_id", type=int)
        if class_id and user["role"] != auth.ROLE_ADMIN:
            if class_id not in {klass["id"] for klass in _own_classes()}:
                abort(403)
        valid_topics = {topic["slug"] for topic in topics}
        topic_slugs = [
            slug for slug in request.form.getlist("topic_slugs") if slug in valid_topics
        ]
        count = max(1, min(40, request.form.get("questions_count", type=int) or 10))
        selected = [topic for topic in topics if topic["slug"] in topic_slugs]
        subject_id = request.form.get("subject_id", type=int)
        if not subject_id and selected:
            subject_id = selected[0]["subject_id"]
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
        if not title:
            flash("Введите название работы", "error")
        elif not allow_photo and not allow_text:
            flash("Разрешите хотя бы один способ ответа: текстом или фото.", "error")
        elif task_type == "test" and not topic_slugs:
            flash("Выберите хотя бы одну тему — по ней будут сгенерированы задания.", "error")
        elif task_type == "read" and not topic_slugs:
            flash("Для чтения выберите тему из пособия.", "error")
        elif task_type == "read":
            topic_slugs = topic_slugs[:1]
        elif task_type == "dictation" and not reference_text and not topic_slugs:
            flash("Вставьте текст диктанта или выберите тему пособия.", "error")
        elif task_type == "other" and not description:
            flash("Опишите задание, которое должен выполнить ученик.", "error")
        else:
            tasks = assignments_service.build_typed_tasks(
                task_type,
                topic_slugs,
                count,
                description=description,
                reference_text=reference_text,
                audio_text=audio_text,
            )
            if not tasks:
                flash(
                    "Не удалось составить задание. Проверьте тему и текст задания.",
                    "error",
                )
            else:
                assignment_id = assignments_service.create_assignment(
                    title=title,
                    kind=kind,
                    description=description,
                    course_id=course_id,
                    subject_id=subject_id,
                    class_id=class_id,
                    teacher_id=user["id"],
                    topic_slugs=topic_slugs,
                    questions_count=len(tasks),
                    time_limit=request.form.get("time_limit", type=int) or 0,
                    due_date=request.form.get("due_date", ""),
                    status="черновик",
                    tasks=tasks,
                    task_type=task_type,
                    reference_text=reference_text,
                    audio_text=audio_text,
                    allow_photo=allow_photo,
                    allow_text=allow_text,
                )
                flash("Работа создана как черновик", "success")
                return redirect(url_for("teacher.work_detail", assignment_id=assignment_id))
    return render_template(
        "teacher/work_form.html",
        user=user,
        classes=_own_classes(),
        courses=orgs.list_courses(teacher_id=user["id"]),
        subjects=orgs.list_subjects(active_only=True),
        topics=topics,
        topic_groups=_topic_groups(topics),
        kinds=assignments_service.KINDS,
        task_types=assignments_service.TASK_TYPES,
    )


@bp.route("/works/<int:assignment_id>")
@auth.teacher_required
def work_detail(assignment_id: int):
    user = auth.current_user()
    assignment = assignments_service.get_assignment(assignment_id)
    if not assignment:
        abort(404)
    if user["role"] != auth.ROLE_ADMIN and assignment["teacher_id"] != user["id"]:
        abort(403)
    topics = assignments_service.assignment_topics(assignment)
    results = assignments_service.results_with_students(assignment_id)
    return render_template(
        "teacher/work.html",
        user=user,
        assignment=assignment,
        topics=topics,
        results=results,
        kinds=assignments_service.KINDS,
        task_types=assignments_service.TASK_TYPES,
    )


@bp.route("/works/<int:assignment_id>/publish", methods=["POST"])
@auth.teacher_required
def work_publish(assignment_id: int):
    assignment = assignments_service.get_assignment(assignment_id)
    if not assignment:
        abort(404)
    user = auth.current_user()
    if user["role"] != auth.ROLE_ADMIN and assignment["teacher_id"] != user["id"]:
        abort(403)
    action = request.form.get("action")
    if action == "publish":
        assignments_service.publish_assignment(assignment_id)
        flash("Работа опубликована — ученики её видят", "success")
    elif action == "close":
        assignments_service.close_assignment(assignment_id)
        flash("Работа закрыта", "info")
    elif action == "delete":
        assignments_service.delete_assignment(assignment_id)
        flash("Работа удалена", "info")
        return redirect(url_for("teacher.works"))
    return redirect(url_for("teacher.work_detail", assignment_id=assignment_id))


# ---------------------------------------------------------- расписание
@bp.route("/classes/<int:class_id>/schedule", methods=["GET", "POST"])
@auth.teacher_required
def schedule(class_id: int):
    user = auth.current_user()
    klass = orgs.get_class(class_id)
    if not klass:
        abort(404)
    if user["role"] != auth.ROLE_ADMIN and klass["teacher_id"] != user["id"]:
        abort(403)
    if request.method == "POST":
        if request.form.get("action") == "delete":
            orgs.delete_schedule_item(request.form.get("item_id", type=int) or 0)
        else:
            subject_id = request.form.get("subject_id", type=int)
            topic_slug = request.form.get("topic_slug", "")
            if topic_slug:
                topic = topics_service.get_topic(topic_slug)
                if not topic:
                    topic_slug = ""
                elif not subject_id:
                    subject_id = topic["subject_id"]
                elif int(topic["subject_id"]) != int(subject_id):
                    topic_slug = ""
            orgs.save_schedule_item(
                class_id,
                weekday=request.form.get("weekday", type=int) or 1,
                lesson_no=request.form.get("lesson_no", type=int) or 1,
                subject_id=subject_id,
                teacher_id=user["id"],
                time_start=request.form.get("time_start", ""),
                time_end=request.form.get("time_end", ""),
                topic_slug=topic_slug,
                note=request.form.get("note", ""),
            )
            flash("Урок добавлен в расписание", "success")
        return redirect(url_for("teacher.schedule", class_id=class_id))
    items = orgs.list_schedule(class_id)
    grid = {}
    for item in items:
        grid.setdefault(item["weekday"], []).append(item)
    return render_template(
        "teacher/schedule.html",
        user=user,
        klass=klass,
        class_title=orgs.class_title(klass),
        grid=grid,
        weekdays=orgs.WEEKDAYS_LIST,
        subjects=orgs.list_subjects(active_only=True),
        topics=topics_service.list_topics(),
    )


# ------------------------------------------------------------- пособия
@bp.route("/textbooks")
@auth.teacher_required
def textbooks_page():
    user = auth.current_user()
    grade = request.args.get("grade", type=int)
    subject_id = request.args.get("subject_id", type=int)
    rows = textbooks.list_textbooks(subject_id=subject_id, grade=grade)
    return render_template(
        "teacher/textbooks.html",
        user=user,
        textbooks=rows,
        subjects=orgs.list_subjects(active_only=True),
        grades=list(range(1, 12)),
        selected_grade=grade,
        selected_subject=subject_id,
    )
