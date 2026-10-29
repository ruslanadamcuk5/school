"""API: поиск и импорт пособий с e-padruchnik.adu.by (учитель/админ)."""
from __future__ import annotations

from flask import jsonify, request

from services import auth as auth_service
from services import orgs
from services import padruchnik as padruchnik_service
from services import textbooks as textbooks_service

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
            "source": result.get("source") or "",
            "total": result.get("total"),
            "generated_at": result.get("generated_at") or "",
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


def _class_ids(user) -> list[int]:
    """Разобрать class_ids из JSON-массива, повторяющихся полей или строки."""
    raw = request.form.getlist("class_ids")
    values: list[str] = []
    for chunk in raw:
        values.extend(part.strip() for part in str(chunk).split(",") if part.strip())
    classes = orgs.classes_of_teacher(user["id"]) if user["role"] == "teacher" else []
    allowed = {int(row["id"]) for row in classes}
    result: list[int] = []
    for value in values:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if user["role"] == "admin" or number in allowed:
            result.append(number)
    return result


@bp.post("/padruchnik/upload")
@require_user("teacher", "admin")
def padruchnik_upload():
    """Загрузить PDF пособия вручную, если сервер не может скачать его сам.

    Принимает multipart/form-data: ``file``, ``book_id``, ``subject_id``,
    ``grade`` и ``class_ids`` (повторяющееся поле или строка через запятую).
    """
    user = current_user()
    try:
        book_id = int(request.form.get("book_id") or 0)
        subject_id = int(request.form.get("subject_id") or 0)
        grade = int(request.form.get("grade") or 0)
    except (TypeError, ValueError):
        fail(400, "bad_request", "book_id, subject_id и grade должны быть числами")
    if not book_id or not subject_id:
        fail(400, "bad_request", "Нужны book_id и subject_id")
    upload = request.files.get("file") or request.files.get("pdf")
    if not upload or not upload.filename:
        fail(400, "file_required", "Прикрепите PDF-файл")
    class_ids = _class_ids(user)
    if user["role"] == "teacher" and not class_ids:
        fail(400, "classes_required", "Выберите хотя бы один класс")
    limit = 80 * 1024 * 1024
    data = upload.read(limit + 1)
    if len(data) > limit:
        fail(413, "file_too_large", "PDF больше 80 МБ — добавьте вручную на сайте")
    try:
        filename, size = padruchnik_service.save_pdf_bytes(
            data, textbooks_service.upload_dir()
        )
        result = padruchnik_service.import_saved_pdf(
            filename,
            size,
            book_id,
            subject_id,
            grade,
            uploaded_by=int(user["id"]),
            class_ids=class_ids,
            auto_link=True,
        )
    except ValueError as error:
        fail(400, "bad_file", str(error))
    if not result.get("ok"):
        return jsonify(
            {"ok": False, "error": "import_failed", "message": result.get("error")}
        ), 400
    result.pop("error", None)
    return jsonify({"ok": True, **result}), 201
