"""API: администрирование — пользователи, организации, темы, пособия, ИИ."""
from __future__ import annotations

from flask import jsonify, request

from database import execute, query_all, query_one
from services import ai as ai_service
from services import auth as auth_service
from services import learners as learners_service
from services import map_settings as map_settings_service
from services import orgs
from services import textbooks as textbooks_service
from services import topics as topics_service
from services import youtube as youtube_service

from . import bp
from .deps import current_user, fail, json_body, require_user, row_dict, user_payload

ROLES = (
    auth_service.ROLE_ADMIN,
    auth_service.ROLE_TEACHER,
    auth_service.ROLE_STUDENT,
    auth_service.ROLE_PARENT,
)
MAX_GRADE = 11


def _log(action: str, entity: str = "", entity_id: str = "", details: str = "") -> None:
    user = current_user()
    execute(
        "INSERT INTO audit_log (user_id, action, entity, entity_id, details) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            int(user["id"]) if user else None,
            action,
            entity,
            entity_id,
            details,
        ),
    )


def _count(sql: str, params=()) -> int:
    row = query_one(sql, params)
    return int(row["c"] or 0) if row else 0


@bp.get("/admin/stats")
@require_user("admin")
def stats():
    by_role = {
        role: _count("SELECT COUNT(*) AS c FROM users WHERE role = ?", (role,))
        for role in ROLES
    }
    ai_stats = {}
    try:
        ai_stats = ai_service.stats()
    except Exception:  # noqa: BLE001 - таблицы ИИ может не быть
        ai_stats = {}
    return jsonify(
        {
            "ok": True,
            "stats": {
                "users": _count("SELECT COUNT(*) AS c FROM users"),
                "students": by_role.get(auth_service.ROLE_STUDENT, 0),
                "teachers": by_role.get(auth_service.ROLE_TEACHER, 0),
                "parents": by_role.get(auth_service.ROLE_PARENT, 0),
                "admins": by_role.get(auth_service.ROLE_ADMIN, 0),
                "cities": _count("SELECT COUNT(*) AS c FROM cities"),
                "schools": _count("SELECT COUNT(*) AS c FROM schools"),
                "classes": _count("SELECT COUNT(*) AS c FROM school_classes"),
                "topics": _count("SELECT COUNT(*) AS c FROM topics"),
                "textbooks": _count("SELECT COUNT(*) AS c FROM textbooks"),
                "library_books": _count("SELECT COUNT(*) AS c FROM library_books"),
                "assignments": _count("SELECT COUNT(*) AS c FROM assignments"),
                "attempts": _count("SELECT COUNT(*) AS c FROM attempts"),
                "learners": _count("SELECT COUNT(*) AS c FROM learners"),
            },
            "by_role": by_role,
            "ai": ai_stats,
            "recent_users": [
                user_payload(row)
                for row in query_all(
                    "SELECT * FROM users ORDER BY id DESC LIMIT 8"
                )
            ],
            "recent_audit": [
                row_dict(row)
                for row in query_all(
                    "SELECT * FROM audit_log ORDER BY id DESC LIMIT 10"
                )
            ],
        }
    )


# ------------------------------------------------------------------ пользователи
@bp.get("/admin/users")
@require_user("admin")
def users():
    role = (request.args.get("role") or "").strip() or None
    if role and role not in ROLES:
        fail(400, "bad_role", "Неизвестная роль")
    search = (request.args.get("search") or "").strip()
    rows = auth_service.list_users(role=role, search=search)
    return jsonify(
        {
            "ok": True,
            "users": [user_payload(row) for row in rows],
            "roles": ROLES,
        }
    )


@bp.post("/admin/users")
@require_user("admin")
def create_user():
    data = json_body()
    login = auth_service.normalize_login(str(data.get("login") or ""))
    password = str(data.get("password") or "")
    role = str(data.get("role") or auth_service.ROLE_STUDENT)
    if not login or len(login) < 3:
        fail(400, "bad_login", "Логин — не короче 3 символов")
    if auth_service.login_taken(login):
        fail(409, "login_taken", "Такой логин уже занят")
    if len(password) < 6:
        fail(400, "bad_password", "Пароль — не короче 6 символов")
    if role not in ROLES:
        fail(400, "bad_role", "Неизвестная роль")

    user_id = auth_service.create_user(
        login=login,
        password=password,
        role=role,
        first_name=str(data.get("first_name") or ""),
        last_name=str(data.get("last_name") or ""),
        email=str(data.get("email") or "") or None,
        avatar=str(data.get("avatar") or "🦊")[:8],
        city_id=_optional_int(data.get("city_id")),
        school_id=_optional_int(data.get("school_id")),
    )
    user = auth_service.get_user(user_id)
    if role == auth_service.ROLE_STUDENT:
        learners_service.ensure_learner_for_user(user)
        class_id = _optional_int(data.get("class_id"))
        if class_id:
            orgs.add_student_to_class(class_id, user_id)
    _log("create", "user", str(user_id), login)
    return jsonify(
        {"ok": True, "user": user_payload(auth_service.get_user(user_id))}
    ), 201


@bp.patch("/admin/users/<int:user_id>")
@require_user("admin")
def update_user(user_id: int):
    target = auth_service.get_user(user_id)
    if target is None:
        fail(404, "not_found", "Пользователь не найден")

    data = json_body()
    fields: dict = {}
    for key in ("first_name", "last_name"):
        if key in data:
            fields[key] = str(data.get(key) or "")
    for key in ("email", "phone"):
        if key in data:
            fields[key] = str(data.get(key) or "") or None
    if "avatar" in data:
        fields["avatar"] = str(data.get("avatar") or "🦊")[:8]
    for key in ("city_id", "school_id"):
        if key in data:
            fields[key] = _optional_int(data.get(key))
    if "is_active" in data:
        fields["is_active"] = 1 if data.get("is_active") else 0
    if "role" in data:
        role = str(data.get("role") or "")
        if role not in ROLES:
            fail(400, "bad_role", "Неизвестная роль")
        fields["role"] = role
    if "login" in data:
        login = auth_service.normalize_login(str(data.get("login") or ""))
        if len(login) < 3:
            fail(400, "bad_login", "Логин — не короче 3 символов")
        other = auth_service.get_user_by_login(login)
        if other and int(other["id"]) != user_id:
            fail(409, "login_taken", "Такой логин уже занят")
        fields["login"] = login

    if fields:
        auth_service.update_user(user_id, **fields)
    _log("update", "user", str(user_id), ", ".join(fields))
    return jsonify(
        {"ok": True, "user": user_payload(auth_service.get_user(user_id))}
    )


@bp.post("/admin/users/<int:user_id>/password")
@require_user("admin")
def set_password(user_id: int):
    if auth_service.get_user(user_id) is None:
        fail(404, "not_found", "Пользователь не найден")
    data = json_body()
    password = str(data.get("password") or "")
    if len(password) < 6:
        fail(400, "bad_password", "Пароль — не короче 6 символов")
    auth_service.set_password(user_id, password)
    _log("password", "user", str(user_id))
    return jsonify({"ok": True})


@bp.delete("/admin/users/<int:user_id>")
@require_user("admin")
def delete_user(user_id: int):
    user = current_user()
    if int(user["id"]) == user_id:
        fail(400, "self_delete", "Нельзя удалить свой аккаунт")
    if auth_service.get_user(user_id) is None:
        fail(404, "not_found", "Пользователь не найден")
    try:
        auth_service.delete_user(user_id)
    except Exception as exc:  # noqa: BLE001 - связанные записи
        fail(409, "delete_failed", f"Не удалось удалить: {exc}")
    _log("delete", "user", str(user_id))
    return jsonify({"ok": True})


# ------------------------------------------------------------------ организации
@bp.get("/admin/orgs")
@require_user("admin")
def orgs_view():
    cities = [row_dict(row) for row in orgs.list_cities()]
    schools = [row_dict(row) for row in orgs.list_schools()]
    classes = []
    for row in orgs.list_classes():
        data = row_dict(row)
        data["title"] = orgs.class_title(row)
        data["students_count"] = _count(
            "SELECT COUNT(*) AS c FROM class_students WHERE class_id = ?",
            (int(row["id"]),),
        )
        classes.append(data)
    return jsonify(
        {
            "ok": True,
            "cities": cities,
            "schools": schools,
            "classes": classes,
            "subjects": [row_dict(row) for row in orgs.list_subjects()],
            "teachers": [
                user_payload(row)
                for row in auth_service.list_users(role=auth_service.ROLE_TEACHER)
            ],
        }
    )


@bp.post("/admin/cities")
@require_user("admin")
def create_city():
    data = json_body()
    name = str(data.get("name") or "").strip()
    if not name:
        fail(400, "bad_name", "Введите название города")
    city_id = orgs.create_city(name, str(data.get("region") or ""))
    _log("create", "city", str(city_id), name)
    return jsonify({"ok": True, "id": city_id}), 201


@bp.post("/admin/schools")
@require_user("admin")
def create_school():
    data = json_body()
    city_id = _optional_int(data.get("city_id"))
    name = str(data.get("name") or "").strip()
    if not city_id or not name:
        fail(400, "bad_parameter", "Нужны город и название школы")
    school_id = orgs.create_school(
        city_id, name, str(data.get("address") or ""), str(data.get("director") or "")
    )
    _log("create", "school", str(school_id), name)
    return jsonify({"ok": True, "id": school_id}), 201


@bp.patch("/admin/schools/<int:school_id>")
@require_user("admin")
def update_school(school_id: int):
    if orgs.get_school(school_id) is None:
        fail(404, "not_found", "Школа не найдена")
    data = json_body()
    fields = {
        key: data[key]
        for key in ("city_id", "name", "short_name", "address", "director")
        if key in data
    }
    orgs.update_school(school_id, **fields)
    _log("update", "school", str(school_id))
    return jsonify({"ok": True})


@bp.delete("/admin/schools/<int:school_id>")
@require_user("admin")
def delete_school(school_id: int):
    try:
        orgs.delete_school(school_id)
    except Exception as exc:  # noqa: BLE001
        fail(409, "delete_failed", f"Не удалось удалить школу: {exc}")
    _log("delete", "school", str(school_id))
    return jsonify({"ok": True})


@bp.post("/admin/classes")
@require_user("admin")
def create_class():
    data = json_body()
    school_id = _optional_int(data.get("school_id"))
    grade = _optional_int(data.get("grade"))
    if not school_id or not grade or not 1 <= grade <= MAX_GRADE:
        fail(400, "bad_parameter", "Нужны школа и класс (1–11)")
    class_id = orgs.create_class(
        school_id,
        grade,
        str(data.get("letter") or ""),
        teacher_id=_optional_int(data.get("teacher_id")),
        year=str(data.get("year") or "2025/2026"),
        title=str(data.get("title") or ""),
    )
    _log("create", "class", str(class_id))
    return jsonify({"ok": True, "id": class_id}), 201


@bp.patch("/admin/classes/<int:class_id>")
@require_user("admin")
def update_class(class_id: int):
    if orgs.get_class(class_id) is None:
        fail(404, "not_found", "Класс не найден")
    data = json_body()
    fields = {
        key: data[key]
        for key in ("school_id", "grade", "letter", "title", "teacher_id", "year")
        if key in data
    }
    if "grade" in fields:
        try:
            grade = int(fields["grade"])
        except (TypeError, ValueError):
            fail(400, "bad_grade", "Класс должен быть числом")
        if not 1 <= grade <= MAX_GRADE:
            fail(400, "bad_grade", f"Класс — от 1 до {MAX_GRADE}")
        fields["grade"] = grade
    orgs.update_class(class_id, **fields)
    _log("update", "class", str(class_id))
    return jsonify({"ok": True})


@bp.delete("/admin/classes/<int:class_id>")
@require_user("admin")
def delete_class(class_id: int):
    try:
        orgs.delete_class(class_id)
    except Exception as exc:  # noqa: BLE001
        fail(409, "delete_failed", f"Не удалось удалить класс: {exc}")
    _log("delete", "class", str(class_id))
    return jsonify({"ok": True})


@bp.post("/admin/classes/<int:class_id>/students")
@require_user("admin")
def class_students(class_id: int):
    if orgs.get_class(class_id) is None:
        fail(404, "not_found", "Класс не найден")
    data = json_body()
    student_id = _optional_int(data.get("student_id"))
    if not student_id:
        fail(400, "bad_student", "Укажите student_id")
    if data.get("remove"):
        orgs.remove_student_from_class(class_id, student_id)
        _log("remove_student", "class", str(class_id), str(student_id))
    else:
        orgs.add_student_to_class(class_id, student_id)
        _log("add_student", "class", str(class_id), str(student_id))
    return jsonify(
        {
            "ok": True,
            "students": [
                row_dict(row)
                for row in query_all(
                    """SELECT u.id, u.login, u.first_name, u.last_name
                         FROM class_students cs
                         JOIN users u ON u.id = cs.student_id
                        WHERE cs.class_id = ?
                        ORDER BY u.last_name, u.first_name""",
                    (class_id,),
                )
            ],
        }
    )


# ------------------------------------------------------------------ темы
@bp.get("/admin/topics")
@require_user("admin")
def admin_topics():
    subject_id = request.args.get("subject_id", type=int)
    grade = request.args.get("grade", type=int)
    search = (request.args.get("search") or "").strip()
    rows = topics_service.list_topics(
        subject_id=subject_id, grade=grade, search=search
    )
    return jsonify(
        {
            "ok": True,
            "topics": [row_dict(row, exclude={"content_json"}) for row in rows],
            "subjects": [row_dict(row) for row in orgs.list_subjects()],
        }
    )


@bp.post("/admin/topics")
@require_user("admin")
def create_topic():
    data = json_body()
    subject_id = _optional_int(data.get("subject_id"))
    grade = _optional_int(data.get("grade"))
    title = str(data.get("title") or "").strip()
    if not subject_id or not grade or not title:
        fail(400, "bad_parameter", "Нужны предмет, класс и название")
    if not 1 <= grade <= MAX_GRADE:
        fail(400, "bad_grade", f"Класс — от 1 до {MAX_GRADE}")
    slug = topics_service.create_topic(
        subject_id=subject_id,
        grade=grade,
        title=title,
        description=str(data.get("description") or ""),
        icon=str(data.get("icon") or "") or None,
        color=str(data.get("color") or "") or None,
        source=str(data.get("source") or "manual"),
        textbook_id=_optional_int(data.get("textbook_id")),
        order_index=_optional_int(data.get("order_index")),
    )
    _log("create", "topic", str(slug), title)
    return jsonify({"ok": True, "slug": slug}), 201


@bp.patch("/admin/topics/<slug>")
@require_user("admin")
def update_topic(slug: str):
    if topics_service.get_topic(slug) is None:
        fail(404, "not_found", "Тема не найдена")
    data = json_body()
    fields = {
        key: data[key]
        for key in (
            "title",
            "grade",
            "description",
            "icon",
            "color",
            "order_index",
            "page_start",
            "page_end",
        )
        if key in data
    }
    topics_service.update_topic(slug, **fields)
    _log("update", "topic", slug)
    return jsonify(
        {
            "ok": True,
            "topic": row_dict(
                topics_service.get_topic(slug), exclude={"content_json"}
            ),
        }
    )


@bp.delete("/admin/topics/<slug>")
@require_user("admin")
def delete_topic(slug: str):
    try:
        topics_service.delete_topic(slug)
    except Exception as exc:  # noqa: BLE001
        fail(409, "delete_failed", f"Не удалось удалить тему: {exc}")
    _log("delete", "topic", slug)
    return jsonify({"ok": True})


# ------------------------------------------------------------------ пособия
@bp.get("/admin/textbooks")
@require_user("admin")
def admin_textbooks():
    rows = textbooks_service.list_textbooks(
        subject_id=request.args.get("subject_id", type=int),
        grade=request.args.get("grade", type=int),
        search=(request.args.get("search") or "").strip(),
    )
    return jsonify(
        {
            "ok": True,
            "textbooks": [
                {
                    **row_dict(row),
                    "topics_count": len(textbooks_service.textbook_topics(row["id"])),
                }
                for row in rows
            ],
        }
    )


@bp.delete("/admin/textbooks/<int:textbook_id>")
@require_user("admin")
def delete_textbook(textbook_id: int):
    try:
        textbooks_service.purge_textbook_topics(textbook_id)
        textbooks_service.delete_textbook(textbook_id)
    except Exception as exc:  # noqa: BLE001
        fail(409, "delete_failed", f"Не удалось удалить пособие: {exc}")
    _log("delete", "textbook", str(textbook_id))
    return jsonify({"ok": True})


# ------------------------------------------------------------------ ИИ
@bp.get("/admin/ai")
@require_user("admin")
def ai_status():
    settings = ai_service.get_settings()
    return jsonify(
        {
            "ok": True,
            "settings": {
                "enabled": bool(settings.get("enabled")),
                "provider": settings.get("provider"),
                "provider_name": ai_service.provider_name(
                    settings.get("provider") or ai_service.DEFAULT_PROVIDER
                ),
                "base_url": settings.get("base_url"),
                "model": settings.get("model"),
                "temperature": settings.get("temperature"),
                "max_tokens": settings.get("max_tokens"),
                "system_note": settings.get("system_note"),
                "has_key": bool((settings.get("api_key") or "").strip()),
            },
            "providers": [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "base_url": item["base_url"],
                    "keys_url": item.get("keys_url", ""),
                    "models": list(item.get("models", ())),
                    "note": item.get("note", ""),
                }
                for item in ai_service.PROVIDERS
            ],
            "stats": ai_service.stats(),
        }
    )


@bp.post("/admin/ai/test")
@require_user("admin")
def ai_test():
    """Проверить связь с выбранной моделью (как кнопка на сайте)."""
    ok, message = ai_service.test_connection()
    _log("ai_test", "ai", "", message)
    return jsonify({"ok": ok, "message": message})


@bp.put("/admin/ai")
@require_user("admin")
def ai_save():
    data = json_body()
    current = ai_service.get_settings()
    payload = {
        "enabled": data.get("enabled", current.get("enabled")),
        "provider": data.get("provider", current.get("provider")),
        "base_url": data.get("base_url", current.get("base_url")),
        "model": data.get("model", current.get("model")),
        "temperature": data.get("temperature", current.get("temperature")),
        "max_tokens": data.get("max_tokens", current.get("max_tokens")),
        "system_note": data.get("system_note", current.get("system_note")),
        "api_key": data.get("api_key", ""),
    }
    keep_key = bool(data.get("keep_key"))
    ai_service.save_settings(payload, keep_key=keep_key)
    _log("update", "ai_settings")
    settings = ai_service.get_settings()
    return jsonify(
        {
            "ok": True,
            "settings": {
                "enabled": bool(settings.get("enabled")),
                "provider": settings.get("provider"),
                "provider_name": ai_service.provider_name(
                    settings.get("provider") or ai_service.DEFAULT_PROVIDER
                ),
                "base_url": settings.get("base_url"),
                "model": settings.get("model"),
                "has_key": bool((settings.get("api_key") or "").strip()),
            },
        }
    )


# ------------------------------------------------------------------- карты
@bp.get("/admin/map-settings")
@require_user("admin")
def map_settings_get():
    return jsonify(
        {
            "ok": True,
            "settings": map_settings_service.get_settings(),
            "presets": map_settings_service.presets(),
        }
    )


@bp.put("/admin/map-settings")
@require_user("admin")
def map_settings_save():
    data = json_body()
    try:
        saved = map_settings_service.save_settings(data)
    except map_settings_service.MapSettingsError as exc:
        fail(400, "bad_map_settings", str(exc))
    _log(
        "map_settings", "map", "",
        f"provider={saved['provider']} crs={saved['crs']}",
    )
    return jsonify(
        {
            "ok": True,
            "settings": saved,
            "presets": map_settings_service.presets(),
            "message": "Настройки карты сохранены",
        }
    )


# ----------------------------------------------------------------- YouTube
def _youtube_settings_payload(settings: dict | None = None) -> dict:
    values = settings or youtube_service.get_settings()
    return {
        "enabled": bool(values.get("enabled")),
        "has_key": bool((values.get("api_key") or "").strip()),
        "region_code": values.get("region_code") or "BY",
        "relevance_language": values.get("relevance_language") or "ru",
        "max_per_topic": int(values.get("max_per_topic") or 3),
        "min_duration": int(values.get("min_duration") or 60),
        "max_duration": int(values.get("max_duration") or 3600),
        "cache_days": int(values.get("cache_days") or 14),
        "ai_ranking": bool(values.get("ai_ranking")),
        "updated_at": values.get("updated_at"),
    }


def _youtube_payload() -> dict:
    return {
        "ok": True,
        "settings": _youtube_settings_payload(),
        "status": youtube_service.status(),
        "stats": youtube_service.stats(),
        "limits": {
            "warm": youtube_service.MAX_WARM_TOPICS,
            "manual_per_topic": youtube_service.MAX_MANUAL_PER_TOPIC,
        },
    }


@bp.get("/admin/youtube")
@require_user("admin")
def youtube_admin_status():
    search = (request.args.get("search") or "").strip()
    payload = _youtube_payload()
    payload["topics"] = youtube_service.topic_rows(limit=300, search=search)
    payload["manual"] = youtube_service.manual_rows(limit=100)
    payload["search"] = search
    return jsonify(payload)


@bp.put("/admin/youtube")
@require_user("admin")
def youtube_admin_save():
    data = json_body()
    current = youtube_service.get_settings()
    raw_key = str(data.get("api_key") or "").strip()
    clear_key = data.get("clear_key") is True or data.get("clear_key") == "1"
    if clear_key:
        raw_key = ""
        keep_key = False
    elif "keep_key" in data:
        keep_key = bool(data.get("keep_key"))
    else:
        keep_key = raw_key == ""

    payload = {
        "enabled": data.get("enabled", bool(current.get("enabled"))),
        "api_key": raw_key,
        "region_code": data.get("region_code", current.get("region_code")),
        "relevance_language": data.get(
            "relevance_language", current.get("relevance_language")
        ),
        "max_per_topic": data.get("max_per_topic", current.get("max_per_topic")),
        "min_duration": data.get("min_duration", current.get("min_duration")),
        "max_duration": data.get("max_duration", current.get("max_duration")),
        "cache_days": data.get("cache_days", current.get("cache_days")),
        "ai_ranking": data.get("ai_ranking", bool(current.get("ai_ranking"))),
    }
    saved = youtube_service.save_settings(payload, keep_key=keep_key)
    _log(
        "youtube_save", "youtube", "",
        f"enabled={saved.get('enabled')} region={saved.get('region_code')}",
    )
    message = "Настройки YouTube сохранены"
    if saved.get("enabled") and not youtube_service.is_enabled():
        message = "Сохранено, но YouTube ещё не готов: укажите ключ API."
    result = _youtube_payload()
    result["message"] = message
    return jsonify(result)


@bp.post("/admin/youtube/test")
@require_user("admin")
def youtube_admin_test():
    ok, message = youtube_service.test_connection()
    _log("youtube_test", "youtube", "", message)
    return jsonify({"ok": ok, "message": message})


@bp.post("/admin/youtube/clear-cache")
@require_user("admin")
def youtube_admin_clear_cache():
    removed = youtube_service.clear_cache()
    _log(
        "youtube_clear_cache", "youtube", "",
        f"видео: {removed['videos']}, тем: {removed['topics']}",
    )
    return jsonify(
        {
            "ok": True,
            "removed": removed,
            "message": (
                f"Кэш очищен: удалено автоматических видео — {removed['videos']}, "
                f"записей по темам — {removed['topics']}. Ручные ссылки сохранены."
            ),
        }
    )


@bp.post("/admin/youtube/warm")
@require_user("admin")
def youtube_admin_warm():
    data = json_body()
    try:
        limit = int(data.get("limit") or youtube_service.MAX_WARM_TOPICS)
    except (TypeError, ValueError):
        limit = youtube_service.MAX_WARM_TOPICS
    user = current_user()
    result = youtube_service.warm_topics(
        limit, user_id=int(user["id"]) if user else None
    )
    _log("youtube_warm", "youtube", "", f"обработано {result['processed']}")
    return jsonify(
        {
            "ok": True,
            "processed": result["processed"],
            "results": result["results"],
            "stopped": result.get("stopped") or "",
            "message": f"Обработано тем: {result['processed']}.",
        }
    )


@bp.post("/admin/youtube/refresh-topic")
@require_user("admin")
def youtube_admin_refresh_topic():
    data = json_body()
    slug = str(data.get("slug") or data.get("topic_slug") or "").strip()
    if not slug:
        fail(400, "slug_required", "Укажите тему")
    user = current_user()
    count, error = youtube_service.refresh_all_topic_cache(
        slug, user_id=int(user["id"]) if user else None
    )
    _log("youtube_refresh_topic", "topic", slug, error or f"видео: {count}")
    if error:
        fail(400, "youtube_refresh_failed", error)
    return jsonify(
        {
            "ok": True,
            "slug": slug,
            "count": count,
            "message": f"Подобрано видео: {count}.",
        }
    )


@bp.post("/admin/youtube/manual")
@require_user("admin")
def youtube_admin_manual_add():
    data = json_body()
    slug = str(data.get("slug") or data.get("topic_slug") or "").strip()
    value = str(data.get("video_url") or data.get("url") or "").strip()
    if not slug:
        fail(400, "slug_required", "Укажите тему")
    if not value:
        fail(400, "url_required", "Укажите ссылку на YouTube")
    video, error = youtube_service.add_manual_video(slug, value)
    _log(
        "youtube_manual_add", "topic", slug,
        error or (video or {}).get("video_id", ""),
    )
    if error:
        fail(400, "youtube_manual_failed", error)
    return jsonify(
        {
            "ok": True,
            "video": video,
            "message": f"Видео добавлено: {(video or {}).get('title') or ''}".strip(),
        }
    )


@bp.delete("/admin/youtube/videos/<int:video_row_id>")
@require_user("admin")
def youtube_admin_block_video(video_row_id: int):
    ok, message = youtube_service.block_video(video_row_id)
    _log("youtube_block_video", "video", str(video_row_id), message)
    if not ok:
        fail(404, "video_not_found", message)
    return jsonify({"ok": True, "message": message})


@bp.post("/admin/youtube/videos/<int:video_row_id>/unblock")
@require_user("admin")
def youtube_admin_unblock_video(video_row_id: int):
    ok, message = youtube_service.unblock_video(video_row_id)
    _log("youtube_unblock_video", "video", str(video_row_id), message)
    if not ok:
        fail(404, "video_not_found", message)
    return jsonify({"ok": True, "message": message})


# ------------------------------------------------------------------ журнал
@bp.get("/admin/audit")
@require_user("admin")
def audit():
    limit = request.args.get("limit", type=int) or 200
    limit = max(1, min(500, limit))
    rows = query_all(
        """SELECT a.*, u.login, u.first_name, u.last_name
             FROM audit_log a
        LEFT JOIN users u ON u.id = a.user_id
            ORDER BY a.id DESC LIMIT ?""",
        (limit,),
    )
    return jsonify({"ok": True, "entries": [row_dict(row) for row in rows]})


def _optional_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
