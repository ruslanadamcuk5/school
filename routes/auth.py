"""Регистрация, вход и выход."""
from __future__ import annotations

import hmac
import logging
import re
from urllib.parse import urlsplit

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
from services import auth, google_auth, orgs, rate_limit

bp = Blueprint("auth", __name__)
log = logging.getLogger("edu-math.auth")

ROLE_HOME = {
    auth.ROLE_ADMIN: "admin.dashboard",
    auth.ROLE_TEACHER: "teacher.dashboard",
    auth.ROLE_STUDENT: "student.dashboard",
    auth.ROLE_PARENT: "parent.dashboard",
}


def _safe_next(target: str | None) -> str | None:
    """Разрешить только локальный путь: защита от open redirect."""
    if not target:
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return None
    if not target.startswith("/") or target.startswith("//"):
        return None
    return target


def _validate_org_choices(role: str, form, school_id: int | None) -> list[str]:
    """Проверить школу/классы, которые выбрал ученик или учитель."""
    errors: list[str] = []
    if role == auth.ROLE_TEACHER:
        for cid in [int(v) for v in form.getlist("class_ids") if v.isdigit()]:
            row = orgs.get_class(cid)
            if not row:
                errors.append("Выбранный класс не найден")
            elif school_id and int(row["school_id"]) != school_id:
                errors.append("Можно выбрать только классы выбранной школы")
            elif row["teacher_id"]:
                errors.append(f"Класс {orgs.class_title(row)} уже ведёт другой учитель")
    if role == auth.ROLE_STUDENT:
        class_id = int(form.get("class_id") or 0) or None
        if class_id:
            row = orgs.get_class(class_id)
            if not row:
                errors.append("Выбранный класс не найден")
            elif school_id and int(row["school_id"]) != school_id:
                errors.append("Можно выбрать только классы выбранной школы")
    return errors


def _apply_signup(user_id: int, role: str, form) -> None:
    """Общая часть после создания аккаунта (пароль и Google)."""
    if role == auth.ROLE_STUDENT:
        class_id = int(form.get("class_id") or 0) or None
        if class_id:
            orgs.add_student_to_class(class_id, user_id)
        from services.learners import ensure_learner_for_user

        user = auth.get_user(user_id)
        session["learner_id"] = ensure_learner_for_user(user)
    elif role == auth.ROLE_TEACHER:
        school_id = int(form.get("school_id") or 0) or None
        for cid in [int(v) for v in form.getlist("class_ids") if v.isdigit()]:
            orgs.set_class_teacher(cid, user_id)
        if school_id:
            auth.update_user(user_id, school_id=school_id)
    elif role == auth.ROLE_PARENT:
        code = (form.get("child_code", "") or "").strip().upper()
        child = auth.find_child_by_code(code)
        if child:
            auth.link_parent_child(user_id, child["id"],
                                   form.get("relation", "родитель"))
        elif code:
            flash(
                f"Код {code} не найден. Сохраните его — можно привязать ребёнка позже.",
                "info",
            )


def _enter_account(user, target: str | None = None):
    """Войти и перейти в кабинет роли (общая часть пароля и Google)."""
    auth.login_user(user["id"])
    if user["role"] == auth.ROLE_STUDENT:
        from services.learners import ensure_learner_for_user

        session["learner_id"] = ensure_learner_for_user(user)
    return redirect(target or url_for(ROLE_HOME.get(user["role"], "main.map_page")))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if auth.current_user():
        return redirect(url_for("main.map_page"))
    if request.method == "POST":
        login_name = auth.normalize_login(request.form.get("login", ""))
        password = request.form.get("password", "")
        throttle_key = rate_limit.make_key(
            "login", rate_limit.client_ip(request), login_name
        )
        wait = rate_limit.blocked_for(throttle_key)
        if wait:
            flash(
                f"Слишком много неудачных попыток. Повторите через {wait} с.",
                "error",
            )
            return render_template("auth/login.html", login=login_name), 429
        user = auth.get_user_by_login(login_name)
        if not user or not auth.verify_password(password, user["password_hash"]):
            rate_limit.register_failure(throttle_key)
            flash("Неверный логин или пароль", "error")
            return render_template("auth/login.html", login=login_name)
        if not user["is_active"]:
            flash("Аккаунт отключён. Обратитесь к администратору.", "error")
            return render_template("auth/login.html", login=login_name)
        rate_limit.clear(throttle_key)
        auth.login_user(user["id"])
        if user["role"] == auth.ROLE_STUDENT:
            from services.learners import ensure_learner_for_user

            session["learner_id"] = ensure_learner_for_user(user)
        flash(f"Здравствуйте, {user['first_name'] or user['login']}!", "success")
        target = _safe_next(request.args.get("next"))
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

        city_id = int(request.form.get("city_id") or 0) or None
        school_id = int(request.form.get("school_id") or 0) or None

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

        # Классы при регистрации: нельзя занять чужой класс или класс другой школы.
        errors.extend(_validate_org_choices(role, request.form, school_id))

        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("auth/register.html", role=role, form=request.form)

        user_id = auth.create_user(
            login_name, password, role, first_name, last_name, email,
            avatar=request.form.get("avatar", "🦊"),
            city_id=city_id, school_id=school_id,
        )

        _apply_signup(user_id, role, request.form)
        auth.login_user(user_id)
        flash(f"Аккаунт создан. Добро пожаловать, {first_name}!", "success")
        return redirect(url_for(ROLE_HOME.get(role, "main.map_page")))

    return render_template("auth/register.html", role=role, form={})


def _link_google_account(profile: dict) -> object:
    """Привязать Google к текущему пользователю (кнопка в профиле)."""
    user = auth.current_user()
    if not user:
        return redirect(url_for("auth.login"))
    owner = auth.get_user_by_google_sub(profile["sub"])
    linked_other = user["google_sub"] and user["google_sub"] != profile["sub"]
    if owner and owner["id"] != user["id"]:
        flash("Этот Google-аккаунт уже привязан к другой учётной записи.", "error")
    elif linked_other:
        flash("К аккаунту уже привязан другой Google-аккаунт. Сначала отвяжите его.", "error")
    else:
        auth.attach_google(user["id"], profile["sub"], profile["email"])
        log.info("Google attached to user %s", user["id"])
        flash("Вход через Google включён для этого аккаунта.", "success")
    return redirect(url_for("auth.account"))


@bp.get("/auth/google")
def google_login():
    """Начать вход (или привязку) через Google."""
    if not google_auth.is_configured():
        abort(404)
    mode = "link" if request.args.get("link") else "login"
    if mode == "link" and not auth.current_user():
        return redirect(url_for("auth.login", next=request.path))
    # Приложение открывает эту страницу в браузере (Custom Tabs) и ждёт
    # возврата по схеме uchus://auth. challenge — S256-хеш verifier (PKCE).
    client = "android" if request.args.get("client") == "android" else "web"
    challenge = str(request.args.get("challenge") or "").strip()
    if client == "android" and not re.fullmatch(r"[A-Za-z0-9_-]{43}", challenge):
        abort(400, "Некорректный challenge для входа из приложения")
    if client == "web":
        session.pop("google_android_challenge", None)
    state = google_auth.new_state()
    session["google_oauth"] = {
        "state": state,
        "mode": mode,
        "next": _safe_next(request.args.get("next")),
        "client": client,
        "challenge": challenge,
    }
    return redirect(google_auth.authorize_url(state))


@bp.get("/auth/google/callback")
def google_callback():
    """Вернуться от Google: проверить state, обменять код, войти."""
    if not google_auth.is_configured():
        abort(404)
    pending = session.pop("google_oauth", None) or {}
    state = str(pending.get("state") or "")
    given = request.args.get("state", "")
    if not state or not hmac.compare_digest(state, given):
        flash("Сессия входа через Google истекла. Попробуйте снова.", "error")
        return redirect(url_for("auth.login"))
    android = pending.get("client") == "android"
    if request.args.get("error"):
        if android:
            return google_auth.android_redirect(error="cancelled")
        flash("Вход через Google отменён.", "info")
        return redirect(url_for("auth.login"))
    code = request.args.get("code", "")
    if not code:
        if android:
            return google_auth.android_redirect(error="no_code")
        flash("Google не вернул код авторизации.", "error")
        return redirect(url_for("auth.login"))
    try:
        tokens = google_auth.exchange_code(code, google_auth.redirect_uri())
        info = google_auth.fetch_userinfo(tokens["access_token"])
        profile = google_auth.profile_from_userinfo(info)
    except google_auth.GoogleAuthError as exc:
        log.warning("Google login failed: %s", exc)
        if android:
            return google_auth.android_redirect(error="google_error")
        flash("Не удалось войти через Google. Попробуйте ещё раз.", "error")
        return redirect(url_for("auth.login"))

    if pending.get("mode") == "link":
        return _link_google_account(profile)

    user = auth.get_user_by_google_sub(profile["sub"])
    if user is None:
        accounts = auth.users_by_email(profile["email"])
        # Привязываем только при однозначном совпадении и если Google ещё нет:
        # почту Google он уже подтвердил.
        if len(accounts) == 1 and not accounts[0]["google_sub"]:
            user = accounts[0]
            auth.attach_google(user["id"], profile["sub"], profile["email"])
            log.info("Google linked by email to user %s", user["id"])
            flash(
                "Аккаунт с этой почтой уже был — привязали к нему вход через Google.",
                "info",
            )
    if user is not None:
        if not user["is_active"]:
            if android:
                return google_auth.android_redirect(error="inactive")
            flash("Аккаунт отключён. Обратитесь к администратору.", "error")
            return redirect(url_for("auth.login"))
        if android:
            return google_auth.android_redirect(
                code=google_auth.make_login_code(
                    user["id"], pending.get("challenge", "")
                )
            )
        return _enter_account(user, pending.get("next"))

    # Новый пользователь: роль и имя выберет сам на следующем шаге.
    session["google_pending"] = profile
    session["google_next"] = None if android else pending.get("next")
    if android:
        session["google_android_challenge"] = pending.get("challenge", "")
    else:
        # Не оставлять «хвост» от прерванного входа из приложения.
        session.pop("google_android_challenge", None)
    return redirect(url_for("auth.google_finish"))


@bp.route("/auth/google/finish", methods=["GET", "POST"])
def google_finish():
    """Завершение регистрации: роль, имя и логин для нового Google-пользователя."""
    pending = session.get("google_pending")
    if not pending:
        return redirect(url_for("auth.login"))
    if auth.current_user():
        session.pop("google_pending", None)
        return redirect(url_for("main.map_page"))

    suggested_login = auth.suggest_login(pending.get("email", ""))
    role = request.form.get("role", auth.ROLE_STUDENT)
    if request.method == "POST":
        login_name = auth.normalize_login(request.form.get("login", ""))
        password = request.form.get("password", "")
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        city_id = int(request.form.get("city_id") or 0) or None
        school_id = int(request.form.get("school_id") or 0) or None
        errors = []
        if role not in (auth.ROLE_STUDENT, auth.ROLE_TEACHER, auth.ROLE_PARENT):
            errors.append("Выберите роль")
        if not first_name:
            errors.append("Укажите имя")
        if not login_name or len(login_name) < 3:
            errors.append("Логин должен содержать минимум 3 символа")
        elif auth.login_taken(login_name):
            errors.append("Такой логин уже занят")
        if password and len(password) < auth.MIN_PASSWORD_LENGTH:
            errors.append(
                f"Пароль должен быть не короче {auth.MIN_PASSWORD_LENGTH} символов"
            )
        errors.extend(_validate_org_choices(role, request.form, school_id))
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template(
                "auth/google_finish.html",
                role=role,
                form=request.form,
                profile=pending,
                suggested_login=suggested_login,
            )

        linked = auth.get_user_by_google_sub(pending["sub"])
        if linked:
            session.pop("google_pending", None)
            challenge = session.pop("google_android_challenge", None)
            if challenge:
                return google_auth.android_redirect(
                    code=google_auth.make_login_code(linked["id"], challenge)
                )
            return _enter_account(linked)

        user_id = auth.create_user(
            login_name, password, role, first_name, last_name,
            email=pending.get("email"),
            avatar=request.form.get("avatar", "🦊"),
            city_id=city_id, school_id=school_id,
            google_sub=pending["sub"],
        )
        _apply_signup(user_id, role, request.form)
        session.pop("google_pending", None)
        challenge = session.pop("google_android_challenge", None)
        if challenge:
            return google_auth.android_redirect(
                code=google_auth.make_login_code(user_id, challenge)
            )
        target = _safe_next(session.pop("google_next", None))
        flash(f"Аккаунт создан. Добро пожаловать, {first_name}!", "success")
        return _enter_account(auth.get_user(user_id), target)

    render_form = {
        "first_name": pending.get("first_name", ""),
        "last_name": pending.get("last_name", ""),
        "login": suggested_login,
    }
    return render_template(
        "auth/google_finish.html",
        role=role,
        form=render_form,
        profile=pending,
        suggested_login=suggested_login,
    )


@bp.post("/auth/google/unlink")
@auth.login_required
def google_unlink():
    """Отключить вход через Google (нужен пароль, чтобы не потерять доступ)."""
    user = auth.current_user()
    if not user["google_sub"]:
        flash("Google-аккаунт не привязан.", "info")
    elif not auth.has_password(user):
        flash(
            "Сначала задайте пароль: иначе после отвязки не сможете войти.",
            "error",
        )
    else:
        auth.detach_google(user["id"])
        log.info("Google detached from user %s", user["id"])
        flash("Вход через Google отключён.", "info")
    return redirect(url_for("auth.account"))


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
            if auth.has_password(user) and not auth.verify_password(
                current, user["password_hash"]
            ):
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
    if not school_id:
        # Без школы список классов не отдаём: иначе это публичный справочник
        # всех классов платформы.
        return {"classes": []}
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
