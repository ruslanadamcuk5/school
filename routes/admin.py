"""Административная панель: организации, предметы, курсы, пользователи, пособия."""
from __future__ import annotations

import os

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from database import execute, query_all, query_one
from services import ai as ai_service
from services import assignments as assignments_service
from services import auth, learners as learners_service, orgs, pdf_topics, textbooks
from services import topics as topics_service

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _log(action: str, entity: str = "", entity_id: str = "", details: str = "") -> None:
    user = auth.current_user()
    execute(
        "INSERT INTO audit_log (user_id, action, entity, entity_id, details) VALUES (?, ?, ?, ?, ?)",
        (user["id"] if user else None, action, entity, str(entity_id), details),
    )


@bp.route("/")
@auth.admin_required
def dashboard():
    counts = {
        "users": query_one("SELECT COUNT(*) AS c FROM users")["c"],
        "teachers": query_one("SELECT COUNT(*) AS c FROM users WHERE role='teacher'")["c"],
        "students": query_one("SELECT COUNT(*) AS c FROM users WHERE role='student'")["c"],
        "parents": query_one("SELECT COUNT(*) AS c FROM users WHERE role='parent'")["c"],
        "cities": query_one("SELECT COUNT(*) AS c FROM cities")["c"],
        "schools": query_one("SELECT COUNT(*) AS c FROM schools")["c"],
        "classes": query_one("SELECT COUNT(*) AS c FROM school_classes")["c"],
        "subjects": query_one("SELECT COUNT(*) AS c FROM subjects")["c"],
        "courses": query_one("SELECT COUNT(*) AS c FROM courses")["c"],
        "textbooks": query_one("SELECT COUNT(*) AS c FROM textbooks")["c"],
        "assignments": query_one("SELECT COUNT(*) AS c FROM assignments")["c"],
    }
    activity = query_all(
        """SELECT date(created_at) AS day, COUNT(*) AS attempts,
                  COALESCE(SUM(correct), 0) AS correct
             FROM attempts WHERE created_at >= datetime('now', '-14 days')
            GROUP BY day ORDER BY day"""
    )
    by_school = query_all(
        """SELECT s.name AS school, c.name AS city,
                  (SELECT COUNT(*) FROM class_students cs
                     JOIN school_classes sc ON sc.id = cs.class_id
                    WHERE sc.school_id = s.id) AS students
             FROM schools s JOIN cities c ON c.id = s.city_id
            ORDER BY students DESC LIMIT 10"""
    )
    recent = query_all(
        """SELECT * FROM audit_log ORDER BY id DESC LIMIT 15"""
    )
    return render_template(
        "admin/dashboard.html",
        counts=counts,
        activity=activity,
        by_school=by_school,
        recent=recent,
    )


# ----------------------------------------------------------------- города
@bp.route("/cities", methods=["GET", "POST"])
@auth.admin_required
def cities():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            name = (request.form.get("name") or "").strip()
            if not name:
                flash("Введите название города", "error")
            else:
                try:
                    city_id = orgs.create_city(name, request.form.get("region", ""))
                    _log("create", "city", city_id, name)
                    flash(f"Город «{name}» добавлен", "success")
                except Exception:
                    flash("Такой город уже есть", "error")
        elif action == "delete":
            city_id = request.form.get("city_id", type=int)
            orgs.delete_city(city_id)
            _log("delete", "city", city_id)
            flash("Город удалён", "info")
        return redirect(url_for("admin.cities"))
    return render_template("admin/cities.html", cities=orgs.list_cities())


# ---------------------------------------------------------------- школы
@bp.route("/schools", methods=["GET", "POST"])
@auth.admin_required
def schools():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            name = (request.form.get("name") or "").strip()
            city_id = request.form.get("city_id", type=int)
            if not name or not city_id:
                flash("Укажите город и название школы", "error")
            else:
                school_id = orgs.create_school(
                    city_id, name, request.form.get("address", ""),
                    request.form.get("director", ""),
                )
                _log("create", "school", school_id, name)
                flash(f"Школа «{name}» добавлена", "success")
        elif action == "update":
            school_id = request.form.get("school_id", type=int)
            orgs.update_school(
                school_id,
                name=(request.form.get("name") or "").strip(),
                city_id=request.form.get("city_id", type=int),
                address=request.form.get("address", ""),
                director=request.form.get("director", ""),
            )
            _log("update", "school", school_id)
            flash("Школа обновлена", "success")
        elif action == "delete":
            school_id = request.form.get("school_id", type=int)
            orgs.delete_school(school_id)
            _log("delete", "school", school_id)
            flash("Школа удалена", "info")
        return redirect(url_for("admin.schools"))
    return render_template(
        "admin/schools.html",
        schools=orgs.list_schools(),
        cities=orgs.list_cities(),
    )


# ---------------------------------------------------------------- классы
@bp.route("/classes", methods=["GET", "POST"])
@auth.admin_required
def classes():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            school_id = request.form.get("school_id", type=int)
            grade = request.form.get("grade", type=int) or 3
            letter = (request.form.get("letter") or "").strip().upper()
            teacher_id = request.form.get("teacher_id", type=int)
            if not school_id:
                flash("Выберите школу", "error")
            else:
                class_id = orgs.create_class(
                    school_id, grade, letter, teacher_id,
                    year=request.form.get("year", "2025/2026"),
                )
                _log("create", "class", class_id, f"{grade}{letter}")
                flash("Класс создан", "success")
        elif action == "teacher":
            class_id = request.form.get("class_id", type=int)
            teacher_id = request.form.get("teacher_id", type=int)
            orgs.set_class_teacher(class_id, teacher_id)
            _log("update", "class", class_id, f"teacher={teacher_id}")
            flash("Учитель назначен", "success")
        elif action == "delete":
            class_id = request.form.get("class_id", type=int)
            orgs.delete_class(class_id)
            _log("delete", "class", class_id)
            flash("Класс удалён", "info")
        return redirect(url_for("admin.classes"))
    return render_template(
        "admin/classes.html",
        classes=orgs.list_classes(),
        schools=orgs.list_schools(),
        teachers=auth.list_users(role=auth.ROLE_TEACHER),
        years=["2025/2026", "2024/2025"],
    )


# -------------------------------------------------------------- предметы
@bp.route("/subjects", methods=["GET", "POST"])
@auth.admin_required
def subjects():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            name = (request.form.get("name") or "").strip()
            slug = (
                (request.form.get("slug") or "").strip().lower()
                or topics_service.slugify(name, 40)
            )
            if not name:
                flash("Введите название предмета", "error")
            else:
                try:
                    subject_id = orgs.create_subject(
                        slug, name, request.form.get("icon", "📘"),
                        request.form.get("color", "sky"),
                        request.form.get("description", ""),
                    )
                    _log("create", "subject", subject_id, name)
                    flash(f"Предмет «{name}» добавлен", "success")
                except Exception:
                    flash("Предмет с таким кодом уже существует", "error")
        elif action == "toggle":
            subject_id = request.form.get("subject_id", type=int)
            subject = orgs.get_subject(subject_id)
            if subject:
                orgs.update_subject(subject_id, is_active=0 if subject["is_active"] else 1)
                flash("Предмет обновлён", "success")
        elif action == "delete":
            subject_id = request.form.get("subject_id", type=int)
            orgs.delete_subject(subject_id)
            _log("delete", "subject", subject_id)
            flash("Предмет удалён", "info")
        return redirect(url_for("admin.subjects"))
    return render_template(
        "admin/subjects.html",
        subjects=orgs.list_subjects(),
        courses=orgs.list_courses(),
    )


@bp.route("/subjects/<int:subject_id>/topics", methods=["GET", "POST"])
@auth.admin_required
def subject_topics(subject_id: int):
    subject = orgs.get_subject(subject_id)
    if not subject:
        abort(404)
    if request.method == "POST":
        action = request.form.get("action", "add")
        slug = (request.form.get("topic_slug") or "").strip()
        if action == "add":
            title = (request.form.get("title") or "").strip()
            grade = request.form.get("grade", type=int) or 3
            if not title:
                flash("Введите название темы", "error")
            else:
                new_slug = topics_service.create_topic(
                    subject_id, grade, title,
                    description=request.form.get("description", ""),
                )
                _log("create", "topic", new_slug, title)
                flash(f"Тема «{title}» добавлена", "success")
        elif action == "update" and slug:
            title = (request.form.get("title") or "").strip()
            if title:
                topics_service.update_topic(
                    slug, title=title,
                    grade=request.form.get("grade", type=int) or 3,
                    description=request.form.get("description", ""),
                )
                flash("Тема обновлена", "success")
        elif action == "delete" and slug:
            topic = topics_service.get_topic(slug)
            if topic and topic["source"] == "curriculum":
                flash("Темы базовой программы удалять нельзя — их состав задаёт curriculum", "error")
            else:
                topics_service.delete_topic(slug)
                _log("delete", "topic", slug)
                flash("Тема удалена", "info")
        elif action == "move" and slug:
            direction = request.form.get("direction", type=int) or 0
            topics_service.reorder_topic(slug, direction)
        return redirect(url_for("admin.subject_topics", subject_id=subject_id))

    topics = topics_service.list_topics(subject_id=subject_id)
    return render_template(
        "admin/subject_topics.html",
        subject=subject,
        topics=topics,
        grades=[3, 4],
    )


# ----------------------------------------------------------------- курсы
@bp.route("/courses", methods=["GET", "POST"])
@auth.admin_required
def courses():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            subject_id = request.form.get("subject_id", type=int)
            title = (request.form.get("title") or "").strip()
            if not subject_id or not title:
                flash("Укажите предмет и название курса", "error")
            else:
                course_id = orgs.create_course(
                    subject_id, title, request.form.get("grade", type=int) or 3,
                    description=request.form.get("description", ""),
                    teacher_id=request.form.get("teacher_id", type=int),
                    school_id=request.form.get("school_id", type=int),
                )
                _log("create", "course", course_id, title)
                flash("Курс создан", "success")
        elif action == "delete":
            course_id = request.form.get("course_id", type=int)
            orgs.delete_course(course_id)
            _log("delete", "course", course_id)
            flash("Курс удалён", "info")
        return redirect(url_for("admin.courses"))
    return render_template(
        "admin/courses.html",
        courses=orgs.list_courses(),
        subjects=orgs.list_subjects(),
        schools=orgs.list_schools(),
        teachers=auth.list_users(role=auth.ROLE_TEACHER),
    )


@bp.route("/courses/<int:course_id>/topics", methods=["GET", "POST"])
@auth.admin_required
def course_topics(course_id: int):
    course = orgs.get_course(course_id)
    if not course:
        abort(404)
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
                _log("create", "topic", slug, title)
                flash(f"Тема «{title}» добавлена в курс", "success")
        else:
            selected = request.form.getlist("topic_slugs")
            valid = {
                row["slug"]
                for row in topics_service.list_topics(
                    subject_id=course["subject_id"], grade=course["grade"]
                )
            }
            ordered = [slug for slug in selected if slug in valid]
            orgs.set_course_topics(course_id, ordered)
            flash("Темы курса сохранены", "success")
        return redirect(url_for("admin.course_topics", course_id=course_id))
    available = topics_service.list_topics(
        subject_id=course["subject_id"], grade=course["grade"]
    )
    rows = [
        {"topic": topic, "enabled": bool(current.get(topic["slug"]) and current[topic["slug"]]["enabled"])}
        for topic in available
    ]
    return render_template(
        "admin/course_topics.html", course=course, rows=rows
    )


# ------------------------------------------------------------- пользователи
@bp.route("/users", methods=["GET", "POST"])
@auth.admin_required
def users():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            login_name = auth.normalize_login(request.form.get("login", ""))
            password = request.form.get("password", "")
            role = request.form.get("role", auth.ROLE_STUDENT)
            if not login_name or len(password) < auth.MIN_PASSWORD_LENGTH:
                flash("Нужен логин и пароль не короче 6 символов", "error")
            elif auth.login_taken(login_name):
                flash("Логин занят", "error")
            else:
                user_id = auth.create_user(
                    login_name, password, role,
                    request.form.get("first_name", ""),
                    request.form.get("last_name", ""),
                    request.form.get("email", "") or None,
                    avatar=request.form.get("avatar", "🦊"),
                    city_id=request.form.get("city_id", type=int),
                    school_id=request.form.get("school_id", type=int),
                )
                class_id = request.form.get("class_id", type=int)
                if class_id and role == auth.ROLE_STUDENT:
                    orgs.add_student_to_class(class_id, user_id)
                _log("create", "user", user_id, f"{role}:{login_name}")
                flash("Пользователь создан", "success")
        elif action == "toggle":
            user_id = request.form.get("user_id", type=int)
            user = auth.get_user(user_id)
            if user:
                if user_id == auth.current_user()["id"]:
                    flash("Нельзя отключить самого себя", "error")
                else:
                    auth.update_user(user_id, is_active=0 if user["is_active"] else 1)
                    _log("toggle", "user", user_id)
                    flash("Статус пользователя изменён", "success")
        elif action == "role":
            user_id = request.form.get("user_id", type=int)
            role = request.form.get("role", auth.ROLE_STUDENT)
            auth.update_user(user_id, role=role)
            _log("role", "user", user_id, role)
            flash("Роль изменена", "success")
        elif action == "password":
            user_id = request.form.get("user_id", type=int)
            password = request.form.get("password", "")
            if len(password) < auth.MIN_PASSWORD_LENGTH:
                flash("Пароль слишком короткий", "error")
            else:
                auth.set_password(user_id, password)
                _log("password", "user", user_id)
                flash("Пароль сброшен", "success")
        elif action == "delete":
            user_id = request.form.get("user_id", type=int)
            if user_id == auth.current_user()["id"]:
                flash("Нельзя удалить самого себя", "error")
            else:
                auth.delete_user(user_id)
                _log("delete", "user", user_id)
                flash("Пользователь удалён", "info")
        return redirect(url_for("admin.users"))
    role = request.args.get("role")
    search = request.args.get("q", "")
    return render_template(
        "admin/users.html",
        users=auth.list_users(role=role, search=search),
        role=role,
        search=search,
        cities=orgs.list_cities(),
        schools=orgs.list_schools(),
        classes=orgs.list_classes(),
        roles=auth.ROLES,
    )


@bp.route("/users/<int:user_id>", methods=["GET", "POST"])
@auth.admin_required
def user_detail(user_id: int):
    user = auth.get_user(user_id)
    if not user:
        abort(404)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "profile":
            auth.update_user(
                user_id,
                first_name=request.form.get("first_name", user["first_name"]),
                last_name=request.form.get("last_name", user["last_name"]),
                email=request.form.get("email", user["email"]),
                phone=request.form.get("phone", user["phone"]),
                role=request.form.get("role", user["role"]),
                city_id=request.form.get("city_id", type=int),
                school_id=request.form.get("school_id", type=int),
            )
            flash("Пользователь обновлён", "success")
            return redirect(url_for("admin.user_detail", user_id=user_id))
        elif action == "classes":
            orgs.remove_student_from_class(request.form.get("class_id", type=int) or 0, user_id)
            flash("Ученик убран из класса", "info")
            return redirect(url_for("admin.user_detail", user_id=user_id))
    children = auth.children_of(user_id) if user["role"] == auth.ROLE_PARENT else []
    parents = auth.parents_of(user_id) if user["role"] == auth.ROLE_STUDENT else []
    classes = orgs.classes_of_student(user_id) if user["role"] == auth.ROLE_STUDENT else []
    return render_template(
        "admin/user.html",
        user=user,
        children=children,
        parents=parents,
        classes=classes,
        cities=orgs.list_cities(),
        schools=orgs.list_schools(),
        roles=auth.ROLES,
        attempts=query_all(
            """SELECT a.*, t.title AS topic_title FROM attempts a
          LEFT JOIN topics t ON t.slug = a.topic_slug
              WHERE a.learner_id IN (SELECT learner_id FROM learner_accounts WHERE user_id = ?)
              ORDER BY a.id DESC LIMIT 30""",
            (user_id,),
        ),
    )


# ---------------------------------------------------------------- пособия
@bp.route("/textbooks", methods=["GET", "POST"])
@auth.admin_required
def textbooks_page():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "upload":
            file_storage = request.files.get("file")
            title = (request.form.get("title") or "").strip()
            subject_id = request.form.get("subject_id", type=int)
            grade = request.form.get("grade", type=int) or 3
            if not file_storage or not file_storage.filename:
                flash("Выберите файл PDF", "error")
                return redirect(url_for("admin.textbooks_page"))
            if not title:
                title = os.path.splitext(file_storage.filename)[0]
            if not subject_id:
                flash("Выберите предмет", "error")
                return redirect(url_for("admin.textbooks_page"))
            try:
                filename, size = textbooks.save_upload(file_storage, subject_id, grade, title)
            except ValueError as exc:
                flash(str(exc), "error")
                return redirect(url_for("admin.textbooks_page"))
            path = os.path.join(textbooks.upload_dir(), filename)
            pages = textbooks.count_pdf_pages(path)
            textbook_id = textbooks.create_textbook(
                subject_id, grade, title, filename,
                original_name=file_storage.filename, size_bytes=size, pages=pages,
                author=request.form.get("author", ""),
                publisher=request.form.get("publisher", ""),
                year=request.form.get("year", ""),
                description=request.form.get("description", ""),
                uploaded_by=auth.current_user()["id"],
            )
            if request.form.get("auto_link"):
                imported = textbooks.import_topics_from_pdf(textbook_id)
                if imported["linked"]:
                    flash(
                        f"Из содержания PDF сформировано тем: {imported['linked']} "
                        f"(новых: {imported['created']})",
                        "success",
                    )
                else:
                    flash(
                        "Темы в PDF не найдены (возможно, это скан). "
                        "Добавьте их вручную на странице пособия.",
                        "info",
                    )
            _log("upload", "textbook", textbook_id, title)
            flash(
                f"Пособие «{title}» загружено ({pages} стр.)", "success"
            )
            return redirect(url_for("admin.textbook_detail", textbook_id=textbook_id))
        elif action == "delete":
            textbook_id = request.form.get("textbook_id", type=int)
            textbooks.delete_textbook(textbook_id)
            _log("delete", "textbook", textbook_id)
            flash("Пособие удалено", "info")
        return redirect(url_for("admin.textbooks_page"))

    grade = request.args.get("grade", type=int)
    subject_id = request.args.get("subject_id", type=int)
    return render_template(
        "admin/textbooks.html",
        textbooks=textbooks.list_textbooks(subject_id=subject_id, grade=grade),
        subjects=orgs.list_subjects(),
        grades=[3, 4],
        selected_grade=grade,
        selected_subject=subject_id,
    )


@bp.route("/textbooks/<int:textbook_id>", methods=["GET", "POST"])
@auth.admin_required
def textbook_detail(textbook_id: int):
    row = textbooks.get_textbook(textbook_id)
    if not row:
        abort(404)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "meta":
            textbooks.update_textbook(
                textbook_id,
                title=request.form.get("title", row["title"]),
                author=request.form.get("author", ""),
                publisher=request.form.get("publisher", ""),
                year=request.form.get("year", ""),
                description=request.form.get("description", ""),
                subject_id=request.form.get("subject_id", type=int),
                grade=request.form.get("grade", type=int) or row["grade"],
            )
            flash("Сведения о пособии обновлены", "success")
        elif action == "link":
            mapping = {}
            page_ends = {}
            for key, value in request.form.items():
                if key.startswith("page_") and value.isdigit() and int(value) > 0:
                    mapping[key[5:]] = int(value)
                elif key.startswith("end_") and value.isdigit() and int(value) > 0:
                    page_ends[key[4:]] = int(value)
            textbooks.set_textbook_topics(textbook_id, mapping, page_ends)
            flash("Привязка тем сохранена", "success")
        elif action == "import_pdf":
            imported = textbooks.import_topics_from_pdf(textbook_id)
            if imported["linked"]:
                flash(
                    f"Сформировано тем: {imported['linked']} (новых: {imported['created']}). "
                    "Проверьте страницы и при необходимости поправьте.",
                    "success",
                )
            else:
                flash(
                    "В PDF не найдено оглавление. Добавьте темы вручную: "
                    "по одной строке «Название — страница».",
                    "error",
                )
        elif action == "manual_topics":
            entries = pdf_topics.parse_manual_topics(request.form.get("manual_topics", ""))
            if not entries:
                flash("Не удалось разобрать список. Формат: «Название — 12»", "error")
            else:
                result = textbooks.add_topics_manually(textbook_id, entries)
                flash(
                    f"Добавлено тем: {result['linked']} (новых: {result['created']})",
                    "success",
                )
        return redirect(url_for("admin.textbook_detail", textbook_id=textbook_id))

    row = textbooks.get_textbook(textbook_id)
    links = textbooks.topics_for_textbook(textbook_id)
    link_map = {link["topic_slug"]: link for link in links}
    available = topics_service.list_topics(subject_id=row["subject_id"], grade=row["grade"])
    topic_rows = []
    seen = set()
    for topic in available:
        link = link_map.get(topic["slug"])
        topic_rows.append({"topic": topic, "link": link})
        seen.add(topic["slug"])
    # на всякий случай показываем и старые привязки к темам другого класса/предмета
    for link in links:
        if link["topic_slug"] in seen:
            continue
        topic = topics_service.get_topic(link["topic_slug"])
        if topic:
            topic_rows.append({"topic": topic, "link": link})
    return render_template(
        "admin/textbook.html",
        textbook=row,
        links=links,
        topic_rows=topic_rows,
        subjects=orgs.list_subjects(),
    )


@bp.route("/textbooks/<int:textbook_id>/file")
@auth.admin_required
def textbook_file(textbook_id: int):
    row = textbooks.get_textbook(textbook_id)
    if not row:
        abort(404)
    path = textbooks.file_path(row)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype="application/pdf", as_attachment=False)


@bp.route("/textbooks/<int:textbook_id>/open")
def textbook_open(textbook_id: int):
    """Открыть пособие: сотрудникам — любое, ученикам — своего класса."""
    user = auth.current_user()
    learner = learners_service.current_learner()
    if not user and not learner:
        return redirect(url_for("auth.login"))
    row = textbooks.get_textbook(textbook_id)
    if not row:
        abort(404)
    if (not user or user["role"] == auth.ROLE_STUDENT) and learner:
        if int(row["grade"]) != int(learner["grade"]):
            abort(403)
    path = textbooks.file_path(row)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype="application/pdf", as_attachment=False)


# ----------------------------------------------------------------- журнал
@bp.route("/audit")
@auth.admin_required
def audit():
    rows = query_all(
        """SELECT a.*, u.login, u.first_name, u.last_name, u.role
             FROM audit_log a LEFT JOIN users u ON u.id = a.user_id
            ORDER BY a.id DESC LIMIT 200"""
    )
    return render_template("admin/audit.html", rows=rows)


# ----------------------------------------------------------------------- ИИ
@bp.route("/ai", methods=["GET", "POST"])
@auth.admin_required
def ai_settings():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "test":
            ok, message = ai_service.test_connection()
            _log("ai_test", "ai", "", message)
            flash(
                ("Связь с моделью работает ✅ " + message) if ok
                else ("Не удалось связаться с моделью: " + message),
                "success" if ok else "error",
            )
        elif action == "clear_cache":
            removed = ai_service.clear_explanations()
            from services import ai_quiz as ai_quiz_service

            ai_quiz_service.clear_cache()
            _log("ai_clear_cache", "ai", "", f"удалено {removed}")
            flash(
                f"Очищено готовых объяснений: {removed}. "
                "Вопросы по темам будут составлены заново.",
                "info",
            )
        else:
            current = ai_service.get_settings()
            raw_key = (request.form.get("api_key") or "").strip()
            clear_key = request.form.get("clear_key") == "1"
            keep_key = (
                not raw_key
                and bool((current.get("api_key") or "").strip())
                and not clear_key
            )
            data = {
                "enabled": request.form.get("enabled") == "1",
                "provider": request.form.get("provider"),
                "base_url": request.form.get("base_url"),
                "api_key": raw_key,
                "model": request.form.get("model"),
                "temperature": request.form.get("temperature"),
                "max_tokens": request.form.get("max_tokens"),
                "system_note": request.form.get("system_note"),
            }
            saved = ai_service.save_settings(data, keep_key=keep_key)
            _log(
                "ai_save", "ai", "",
                f"provider={saved['provider']} model={saved['model']} enabled={saved['enabled']}",
            )
            if saved["enabled"] and not ai_service.is_enabled():
                flash(
                    "Сохранено, но модель ещё не готова: укажите ключ доступа.",
                    "error",
                )
            else:
                flash("Настройки ИИ сохранены", "success")
        return redirect(url_for("admin.ai_settings"))

    settings = ai_service.get_settings()
    return render_template(
        "admin/ai.html",
        settings=settings,
        providers=ai_service.PROVIDERS,
        status=ai_service.status(),
        stats=ai_service.stats(),
    )
