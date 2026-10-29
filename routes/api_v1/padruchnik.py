"""API: поиск и импорт пособий с e-padruchnik.adu.by (учитель/админ)."""
from __future__ import annotations

from flask import jsonify, request

from services import auth as auth_service
from services import orgs
from services import padruchnik as padruchnik_service

from . import bp
from .deps import current_user, fail, json_body, require_user


@bp.get("/padruchnik/search")
@require_user("teacher", "admin")
def padruchnik_search():
    query = (request.args.get("q") or "").strip()
    grade = request.args.get("grade", type=int)
    page = request.args.get("page", type=int) or 0
    if not query and not grade:
        fail(400, "query_required", "Укажите название или класс")
    result = padruchnik_service.search(query=query, grade=grade, page=page)
    return jsonify(
        {
            "ok": bool(result.get("ok")),
            "items": result.get("items") or [],
            "page": page,
            "has_next": bool(result.get("has_next")),
            "error": result.get("error") or "",
        }
    )


@bp.get("/padruchnik/subjects")
@require_user("teacher", "admin")
def padruchnik_subjects():
    return jsonify({"ok": True, "subjects": [dict(row) for row in orgs.list_subjects(active_only=True)]})


@bp.post("/padruchnik/import")
@require_user("teacher", "admin")
def padruchnik_import():
    user = current_user()
    data = json_body()
    try:
        book_id = int(data.get("book_id") or 0)
        subject_id = int(data.get("subject_id") or 0)
        grade = int(data.get("grade") or 0)
    except (TypeError, ValueError):
        fail(400, "bad_request", "book_id, subject_id и grade должны быть числами")
    if not book_id or not subject_id:
        fail(400, "bad_request", "Нужны book_id и subject_id")
    classes = orgs.classes_of_teacher(user["id"]) if user["role"] == "teacher" else []
    allowed = {int(row["id"]) for row in classes}
    class_ids = []
    for raw in data.get("class_ids") or []:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if user["role"] == "admin" or value in allowed:
            class_ids.append(value)
    if user["role"] == "teacher" and not class_ids:
        fail(400, "classes_required", "Выберите хотя бы один класс")
    result = padruchnik_service.import_book(
        book_id,
        subject_id,
        grade,
        uploaded_by=int(user["id"]),
        class_ids=class_ids,
        auto_link=True,
    )
    if not result.get("ok"):
        return jsonify({"ok": False, "error": "import_failed", "message": result.get("error")}), 400
    return jsonify({"ok": True, **result}), 201
