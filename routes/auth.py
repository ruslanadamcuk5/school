"""Регистрация, вход и выход."""
from __future__ import annotations

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from database import query_all
from services import auth, orgs

bp = Blueprint("auth", __name__)

ROLE_HOME = {
    auth.ROLE_ADMIN: "admin.dashboard",
    auth.ROLE_TEACHER: "teacher.dashboard",
    auth.ROLE_STUDENT: "student.dashboard",
    auth.ROLE_PARENT: "parent.dashboard",
}


@bp.route("/login", methods=["GET", "POST"])
def login():
    if auth.current_user():
        return redirect(url_for("main.map_page"))
    if request.method == "POST":
        login_name = auth.normalize_login(request.form.get("login", ""))
        password = request.form.get("password", "")
        user = auth.get_user_by_login(login_name)
        if not user or not auth.verify_password(password, user["password_hash"]):
            flash("Неверный логин или пароль", "error")
            return render_template("auth/login.html", login=login_name)
        if not user["is_active"]:
            flash("Аккаунт отключён. Обратитесь к администратору.", "error")
            return render_template("auth/login.html", login=login_name)
        auth.login_user(user["id"])
        if user["role"] == auth.ROLE_STUDENT:
            from services.learners import ensure_learner_for_user

            session["learner_id"] = ensure_learner_for_user(user)
        flash(f"Здравствуйте, {user['first_name'] or user['login']}!", "success")
        target = request.args.get("next")
        return redirect(target or url_for(ROLE_HOME.get(user["role"], "main.map_page")))
    return render_template("auth/login.html", login="")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if auth.current_user():
        return redirect(url_for("main.map_page"))

    role = request.form.get("role", auth.ROLE_STUDENT)
    if request.method == "POST":
        login_name = auth.normalize_login(request.form.get("login", ""))
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip() or None

        errors = []
        if not login_name or len(login_name) < 3:
            errors.append("Логин должен содержать минимум 3 символа")
        if auth.login_taken(login_name):
            errors.append("Такой логин уже занят")
        if len(password) < auth.MIN_PASSWORD_LENGTH:
            errors.append(f"Пароль должен быть не короче {auth.MIN_PASSWORD_LENGTH} символов")
        if password != password2:
            errors.append("Пароли не совпадают")
        if not first_name:
            errors.append("Укажите имя")
        if role not in (auth.ROLE_STUDENT, auth.ROLE_TEACHER, auth.ROLE_PARENT):
            errors.append("Выберите роль")
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("auth/register.html", role=role, form=request.form)

        city_id = int(request.form.get("city_id") or 0) or None
        school_id = int(request.form.get("school_id") or 0) or None
        class_id = int(request.form.get("class_id") or 0) or None

        user_id = auth.create_user(
            login_name, password, role, first_name, last_name, email,
            avatar=request.form.get("avatar", "🦊"),
            city_id=city_id, school_id=school_id,
        )

        if role == auth.ROLE_STUDENT:
            if class_id:
                orgs.add_student_to_class(class_id, user_id)
            from services.learners import ensure_learner_for_user

            user = auth.get_user(user_id)
            session["learner_id"] = ensure_learner_for_user(user)
        elif role == auth.ROLE_TEACHER:
            for raw in request.form.getlist("class_ids"):
                if raw.isdigit():
                    orgs.set_class_teacher(int(raw), user_id)
            if school_id:
                auth.update_user(user_id, school_id=school_id)
        elif role == auth.ROLE_PARENT:
            code = (request.form.get("child_code", "") or "").strip().upper()
            child = auth.find_child_by_code(code)
            if child:
                auth.link_parent_child(user_id, child["id"],
                                       request.form.get("relation", "родитель"))
            elif code:
                flash(
                    f"Код {code} не найден. Сохраните его — можно привязать ребёнка позже.",
                    "info",
                )

        auth.login_user(user_id)
        flash(f"Аккаунт создан. Добро пожаловать, {first_name}!", "success")
        return redirect(url_for(ROLE_HOME.get(role, "main.map_page")))

    return render_template("auth/register.html", role=role, form={})


@bp.route("/logout")
def logout():
    from services import auth

    auth.logout_user()
    flash("Вы вышли из аккаунта", "info")
    return redirect(url_for("auth.login"))


@bp.route("/profile/account", methods=["GET", "POST"])
@auth.login_required
def account():
    user = auth.current_user()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "profile":
            auth.update_user(
                user["id"],
                first_name=request.form.get("first_name", user["first_name"]).strip()[:40],
                last_name=request.form.get("last_name", user["last_name"]).strip()[:40],
                email=request.form.get("email", user["email"]),
                phone=request.form.get("phone", user["phone"]),
                avatar=request.form.get("avatar", user["avatar"]),
            )
            flash("Профиль обновлён", "success")
        elif action == "password":
            current = request.form.get("current_password", "")
            new = request.form.get("new_password", "")
            if not auth.verify_password(current, user["password_hash"]):
                flash("Текущий пароль указан неверно", "error")
            elif len(new) < auth.MIN_PASSWORD_LENGTH:
                flash("Новый пароль слишком короткий", "error")
            else:
                auth.set_password(user["id"], new)
                flash("Пароль изменён", "success")
        return redirect(url_for("auth.account"))
    children = auth.children_of(user["id"]) if user["role"] == auth.ROLE_PARENT else []
    return render_template("auth/account.html", user=user, user_children=children)


@bp.route("/parent/children", methods=["POST"])
@auth.login_required
def link_child():
    user = auth.current_user()
    if user["role"] != auth.ROLE_PARENT:
        abort(403)
    code = (request.form.get("child_code", "") or "").strip().upper()
    child = auth.find_child_by_code(code)
    if not child:
        flash("Ребёнок с таким кодом не найден", "error")
    elif auth.link_parent_child(user["id"], child["id"]):
        flash(f"Ребёнок {child['first_name']} привязан", "success")
    return redirect(url_for("auth.account"))


@bp.route("/parent/children/<int:child_id>/delete", methods=["POST"])
@auth.login_required
def unlink_child(child_id: int):
    user = auth.current_user()
    if user["role"] != auth.ROLE_PARENT:
        abort(403)
    from database import execute

    execute("DELETE FROM parent_children WHERE parent_id = ? AND child_id = ?",
            (user["id"], child_id))
    flash("Связь удалена", "info")
    return redirect(url_for("auth.account"))


@bp.route("/api/org/cities")
def api_cities():
    return {"cities": [
        {"id": c["id"], "name": c["name"]} for c in orgs.list_cities()
    ]}


@bp.route("/api/org/schools")
def api_schools():
    city_id = request.args.get("city_id", type=int)
    return {"schools": [
        {"id": s["id"], "name": s["name"], "city_id": s["city_id"], "city_name": s["city_name"]}
        for s in orgs.list_schools(city_id=city_id)
    ]}


@bp.route("/api/org/classes")
def api_classes():
    school_id = request.args.get("school_id", type=int)
    rows = orgs.list_classes(school_id=school_id)
    return {"classes": [
        {
            "id": c["id"],
            "title": orgs.class_title(c),
            "grade": c["grade"],
            "letter": c["letter"],
            "school_id": c["school_id"],
            "teacher_id": c["teacher_id"],
            "teacher_first": c["teacher_first"],
            "teacher_last": c["teacher_last"],
            "teacher_name": " ".join(
                part for part in (c["teacher_first"], c["teacher_last"]) if part
            ) or None,
            "students_count": c["students_count"],
        }
        for c in rows
    ]}


@bp.route("/api/org/teachers")
def api_teachers():
    school_id = request.args.get("school_id", type=int)
    rows = query_all(
        """SELECT id, first_name, last_name FROM users
            WHERE role = 'teacher' AND (? IS NULL OR school_id = ?)
            ORDER BY last_name, first_name""",
        (school_id, school_id),
    )
    return {"teachers": [
        {"id": r["id"], "name": " ".join(p for p in (r["first_name"], r["last_name"]) if p)}
        for r in rows
    ]}
