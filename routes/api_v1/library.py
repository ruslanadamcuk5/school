"""API: библиотека — книги учителя, доступ классам, чтение, рекомендации."""
from __future__ import annotations

import os

from flask import jsonify, request

from database import query_all
from services import auth as auth_service
from services import library as library_service
from services import orgs
from services import textbooks as textbooks_service

from . import bp
from .deps import (
    current_user,
    fail,
    json_body,
    learner_for_request,
    require_learner,
    require_user,
    row_dict,
    user_payload,
)


# ------------------------------------------------------------------ helpers
def _class_list(user) -> list:
    if user["role"] == auth_service.ROLE_ADMIN:
        return orgs.list_classes()
    return orgs.classes_of_teacher(user["id"])


def _student_list(user) -> list:
    if user["role"] == auth_service.ROLE_ADMIN:
        return query_all(
            """SELECT u.id, u.first_name, u.last_name, u.login,
                      sc.id AS class_id, sc.grade, sc.letter
                 FROM users u
                 JOIN class_students cs ON cs.student_id = u.id
                 JOIN school_classes sc ON sc.id = cs.class_id
                WHERE u.role = 'student' AND u.is_active = 1
                ORDER BY sc.grade, sc.letter, u.last_name, u.first_name"""
        )
    return library_service.teacher_students(user["id"])


def _allowed_class_ids(user) -> set[int]:
    return {int(row["id"]) for row in _class_list(user)}


def _allowed_student_ids(user) -> set[int]:
    return {int(row["id"]) for row in _student_list(user)}


def _managed(user, item) -> bool:
    return user["role"] == auth_service.ROLE_ADMIN or int(item["owner_id"]) == int(user["id"])


def _book_payload(item: dict) -> dict:
    return {
        "id": item["id"],
        "title": item.get("title", ""),
        "author": item.get("author", ""),
        "description": item.get("description", ""),
        "grade": item.get("grade"),
        "subject_id": item.get("subject_id"),
        "subject_name": item.get("subject_name"),
        "subject_icon": item.get("subject_icon"),
        "textbook_id": item.get("textbook_id"),
        "pages": item.get("pages", 0),
        "topics_count": item.get("topics_count", 0),
        "classes_count": item.get("classes_count", 0),
        "owner_name": " ".join(
            value
            for value in (item.get("owner_first"), item.get("owner_last"))
            if value
        ),
        "created_at": item.get("created_at"),
        "class_ids": item.get("class_ids", []),
    }


def _student_library_payload(user_id: int) -> dict:
    books = library_service.list_books_for_student(user_id)
    recommendations = library_service.recommendations_for_student(user_id)
    return {
        "ok": True,
        "books": [_book_payload(book) for book in books],
        "recommendations": [row_dict(rec) for rec in recommendations],
        "stats": {
            "books": len(books),
            "active": sum(1 for rec in recommendations if not rec["done"]),
            "done": sum(1 for rec in recommendations if rec["done"]),
        },
    }


# ------------------------------------------------------------------ ученик
def _family_library_payload(profile) -> dict:
    """Библиотека семейного профиля: пособия своего класса без аккаунта."""
    grade = int(profile["grade"])
    books = []
    for row in textbooks_service.textbooks_for_grade(grade):
        textbook_id = int(row["id"])
        books.append(
            {
                # Синтетический id: такие книги только для чтения.
                "id": -textbook_id,
                "owner_id": 0,
                "textbook_id": textbook_id,
                "subject_id": row["subject_id"],
                "grade": grade,
                "title": row["title"],
                "author": row["author"],
                "description": row["description"],
                "pages": row["pages"],
                "topics_count": len(textbooks_service.topics_for_textbook(textbook_id)),
                "classes_count": 0,
                "subject_name": row["subject_name"],
                "subject_icon": row["subject_icon"],
                "class_ids": [],
            }
        )
    return {
        "ok": True,
        "books": books,
        "recommendations": [],
        "stats": {"books": len(books), "active": 0, "done": 0},
    }


@bp.get("/library")
@require_learner
def student_library():
    user = current_user()
    if user is not None and user["role"] == auth_service.ROLE_STUDENT:
        return jsonify(_student_library_payload(int(user["id"])))
    return jsonify(_family_library_payload(learner_for_request()))


@bp.get("/library/books/<int:book_id>")
@require_user()
def library_book(book_id: int):
    user = current_user()
    item = library_service.get_book(book_id)
    if item is None:
        fail(404, "not_found", "Книга не найдена")
    if not library_service.can_access_book(user, book_id):
        fail(403, "forbidden", "Книга недоступна")

    topics = library_service.book_topics(book_id)
    recommendations = []
    if user["role"] == auth_service.ROLE_STUDENT:
        recommendations = [
            row_dict(rec)
            for rec in library_service.recommendations_for_student(int(user["id"]))
            if int(rec["book_id"]) == int(book_id)
        ]

    return jsonify(
        {
            "ok": True,
            "book": _book_payload({**item, "class_ids": library_service.book_class_ids(book_id)}),
            "topics": [
                {
                    "topic_slug": topic.get("topic_slug"),
                    "title": topic.get("title") or topic.get("topic_slug"),
                    "icon": topic.get("icon") or "📖",
                    "grade": topic.get("grade"),
                    "page": topic.get("page"),
                    "page_end": topic.get("page_end"),
                }
                for topic in topics
            ],
            "recommendations": recommendations,
            "manageable": _managed(user, item)
            if user["role"] in (auth_service.ROLE_TEACHER, auth_service.ROLE_ADMIN)
            else False,
        }
    )


@bp.post("/library/recommendations/<int:rec_id>/done")
@require_user("student")
def recommendation_done(rec_id: int):
    user = current_user()
    if not library_service.recommendation_visible_to(rec_id, int(user["id"])):
        fail(404, "not_found", "Рекомендация не найдена")
    library_service.mark_recommendation_done(rec_id, int(user["id"]))
    return jsonify({"ok": True})


# ------------------------------------------------------------------ родитель
@bp.get("/parent/library")
@require_user("parent")
def parent_library():
    user = current_user()
    children = [
        child
        for child in auth_service.children_of(user["id"])
        if child["role"] == auth_service.ROLE_STUDENT
    ]
    if not children:
        return jsonify(
            {
                "ok": True,
                "children": [],
                "child": None,
                "books": [],
                "recommendations": [],
                "stats": {"books": 0, "active": 0, "done": 0},
            }
        )

    requested = request.args.get("child_id", type=int)
    child = (
        next((item for item in children if int(item["id"]) == requested), None)
        if requested
        else children[0]
    )
    if child is None:
        fail(403, "forbidden", "Ребёнок не найден")

    payload = _student_library_payload(int(child["id"]))
    payload["children"] = [user_payload(item) for item in children]
    payload["child"] = user_payload(child)
    return jsonify(payload)


# ------------------------------------------------------------------ учитель
@bp.get("/teacher/library")
@require_user("teacher", "admin")
def teacher_library():
    user = current_user()
    search = (request.args.get("search") or "").strip()
    grade = request.args.get("grade", type=int)
    subject_id = request.args.get("subject_id", type=int)
    books = library_service.list_books(
        owner_id=None if user["role"] == auth_service.ROLE_ADMIN else int(user["id"]),
        search=search,
        grade=grade,
        subject_id=subject_id,
    )
    stats = (
        {"books": len(books), "classes": 0, "recommendations": 0}
        if user["role"] == auth_service.ROLE_ADMIN
        else library_service.teacher_stats(int(user["id"]))
    )
    return jsonify(
        {
            "ok": True,
            "books": [_book_payload(book) for book in books],
            "stats": stats,
            "classes": [row_dict(klass) for klass in _class_list(user)],
            "students": [user_payload(student) for student in _student_list(user)],
            "subjects": [row_dict(subject) for subject in orgs.list_subjects(active_only=True)],
        }
    )


@bp.post("/teacher/library")
@require_user("teacher", "admin")
def teacher_create_book():
    user = current_user()
    data = json_body()
    try:
        textbook_id = int(data.get("textbook_id"))
    except (TypeError, ValueError):
        fail(400, "bad_textbook", "Выберите пособие")

    textbook = textbooks_service.get_textbook(textbook_id)
    if textbook is None:
        fail(404, "not_found", "Пособие не найдено")

    allowed = _allowed_class_ids(user)
    class_ids = _int_list(data.get("class_ids") or data.get("classes"))
    class_ids = [class_id for class_id in class_ids if class_id in allowed]

    title = str(data.get("title") or textbook["title"]).strip()
    book_id = library_service.create_book(
        owner_id=int(user["id"]),
        textbook_id=textbook_id,
        subject_id=_optional_int(data.get("subject_id")) or textbook["subject_id"],
        grade=_optional_int(data.get("grade")) or textbook["grade"],
        title=title,
        author=str(data.get("author") or textbook["author"] or ""),
        description=str(data.get("description") or textbook["description"] or ""),
        class_ids=class_ids,
    )
    item = library_service.get_book(book_id)
    return jsonify(
        {
            "ok": True,
            "book": _book_payload({**item, "class_ids": library_service.book_class_ids(book_id)}),
        }
    ), 201


@bp.patch("/teacher/library/<int:book_id>")
@require_user("teacher", "admin")
def teacher_update_book(book_id: int):
    user = current_user()
    item = library_service.get_book(book_id)
    if item is None:
        fail(404, "not_found", "Книга не найдена")
    if not _managed(user, item):
        fail(403, "forbidden", "Это не ваша книга")

    data = json_body()
    fields = {
        key: data[key]
        for key in ("title", "author", "description", "subject_id", "grade")
        if key in data
    }
    if fields:
        library_service.update_book(book_id, **fields)
    if "class_ids" in data or "classes" in data:
        allowed = _allowed_class_ids(user)
        class_ids = [
            class_id
            for class_id in _int_list(data.get("class_ids") or data.get("classes"))
            if class_id in allowed
        ]
        library_service.set_book_classes(book_id, class_ids)

    updated = library_service.get_book(book_id)
    return jsonify(
        {
            "ok": True,
            "book": _book_payload(
                {**updated, "class_ids": library_service.book_class_ids(book_id)}
            ),
        }
    )


@bp.delete("/teacher/library/<int:book_id>")
@require_user("teacher", "admin")
def teacher_delete_book(book_id: int):
    user = current_user()
    item = library_service.get_book(book_id)
    if item is None:
        fail(404, "not_found", "Книга не найдена")
    if not _managed(user, item):
        fail(403, "forbidden", "Это не ваша книга")
    result = library_service.delete_book(book_id)
    if not result.get("ok"):
        fail(409, "delete_failed", result.get("error", "Не удалось удалить книгу"))
    return jsonify({"ok": True})


@bp.post("/teacher/library/<int:book_id>/recommend")
@require_user("teacher", "admin")
def teacher_recommend(book_id: int):
    user = current_user()
    item = library_service.get_book(book_id)
    if item is None:
        fail(404, "not_found", "Книга не найдена")
    if not _managed(user, item):
        fail(403, "forbidden", "Это не ваша книга")

    data = json_body()
    allowed_classes = _allowed_class_ids(user)
    allowed_students = _allowed_student_ids(user)
    class_ids = [
        class_id
        for class_id in _int_list(data.get("class_ids") or data.get("classes"))
        if class_id in allowed_classes
    ]
    student_ids = [
        student_id
        for student_id in _int_list(data.get("student_ids") or data.get("students"))
        if student_id in allowed_students
    ]
    topic_slug = str(data.get("topic_slug") or "").strip() or None
    if not class_ids and not student_ids:
        fail(400, "no_target", "Выберите класс или ученика")

    result = library_service.recommend(
        teacher_id=int(user["id"]),
        book_id=book_id,
        topic_slug=topic_slug,
        class_ids=class_ids,
        student_ids=student_ids,
        note=str(data.get("note") or ""),
    )
    if not result.get("ok"):
        fail(400, "recommend_failed", result.get("error", "Не удалось порекомендовать"))
    return jsonify({"ok": True, **result})


@bp.get("/teacher/library/recommendations")
@require_user("teacher", "admin")
def teacher_recommendations():
    user = current_user()
    if user["role"] == auth_service.ROLE_ADMIN:
        rows = query_all(
            """SELECT r.*, lb.title, lb.grade, t.pages, tp.title AS topic_title,
                      u.first_name AS teacher_first, u.last_name AS teacher_last,
                      sc.grade AS class_grade, sc.letter AS class_letter,
                      su.first_name AS student_first, su.last_name AS student_last
                 FROM library_recommendations r
                 JOIN library_books lb ON lb.id = r.book_id
                 JOIN textbooks t ON t.id = lb.textbook_id
            LEFT JOIN topics tp ON tp.slug = r.topic_slug
            LEFT JOIN users u ON u.id = r.teacher_id
            LEFT JOIN school_classes sc ON sc.id = r.class_id
            LEFT JOIN users su ON su.id = r.student_id
                ORDER BY r.created_at DESC"""
        )
    else:
        rows = library_service.recommendations_by_teacher(int(user["id"]))
    return jsonify({"ok": True, "recommendations": [row_dict(row) for row in rows]})


@bp.delete("/teacher/library/recommendations/<int:rec_id>")
@require_user("teacher", "admin")
def teacher_revoke(rec_id: int):
    user = current_user()
    if user["role"] == auth_service.ROLE_ADMIN:
        from database import execute

        execute("DELETE FROM library_recommendations WHERE id = ?", (rec_id,))
        return jsonify({"ok": True})
    if not library_service.revoke_recommendation(rec_id, int(user["id"])):
        fail(404, "not_found", "Рекомендация не найдена")
    return jsonify({"ok": True})


# ------------------------------------------------------------------ пособия
@bp.get("/teacher/textbooks")
@require_user("teacher", "admin")
def teacher_textbooks():
    subject_id = request.args.get("subject_id", type=int)
    grade = request.args.get("grade", type=int)
    search = (request.args.get("search") or "").strip()
    rows = textbooks_service.list_textbooks(
        subject_id=subject_id, grade=grade, search=search
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


@bp.get("/teacher/recommend/topics")
@require_user("teacher", "admin")
def teacher_recommend_topics():
    """Пособия с темами: рекомендации не ограничены своей библиотекой."""
    subject_id = request.args.get("subject_id", type=int)
    grade = request.args.get("grade", type=int)
    search = (request.args.get("search") or "").strip()
    textbooks = library_service.textbooks_with_topics(
        subject_id=subject_id, grade=grade, search=search
    )
    return jsonify(
        {
            "ok": True,
            "textbooks": [
                {
                    "id": item["id"],
                    "title": item.get("title"),
                    "author": item.get("author"),
                    "subject_id": item.get("subject_id"),
                    "subject_name": item.get("subject_name"),
                    "subject_icon": item.get("subject_icon"),
                    "grade": item.get("grade"),
                    "book_id": item.get("book_id"),
                    "topics": [
                        {
                            "slug": topic.get("topic_slug"),
                            "title": topic.get("title") or topic.get("topic_slug"),
                            "page": topic.get("page"),
                            "page_end": topic.get("page_end"),
                        }
                        for topic in item.get("topics", [])
                    ],
                }
                for item in textbooks
            ],
            "classes": [row_dict(klass) for klass in _class_list(current_user())],
            "students": [user_payload(student) for student in _student_list(current_user())],
            "subjects": [row_dict(subject) for subject in orgs.list_subjects(active_only=True)],
        }
    )


@bp.post("/teacher/recommend")
@require_user("teacher", "admin")
def teacher_recommend_textbook():
    user = current_user()
    data = json_body()
    textbook_id = _optional_int(data.get("textbook_id"))
    if not textbook_id:
        fail(400, "bad_textbook", "Выберите пособие")
    textbook = textbooks_service.get_textbook(textbook_id)
    if textbook is None:
        fail(404, "not_found", "Пособие не найдено")
    topic_slug = str(data.get("topic_slug") or "").strip() or None
    if topic_slug and not query_all(
        "SELECT 1 AS x FROM textbook_topics WHERE textbook_id = ? AND topic_slug = ?",
        (textbook_id, topic_slug),
    ):
        fail(400, "bad_topic", "Тема не относится к выбранному пособию")
    allowed_classes = _allowed_class_ids(user)
    allowed_students = _allowed_student_ids(user)
    class_ids = [
        class_id
        for class_id in _int_list(data.get("class_ids") or data.get("classes"))
        if class_id in allowed_classes
    ]
    student_ids = [
        student_id
        for student_id in _int_list(data.get("student_ids") or data.get("students"))
        if student_id in allowed_students
    ]
    if not class_ids and not student_ids:
        fail(400, "no_target", "Выберите класс или ученика")
    result = library_service.recommend_textbook_topic(
        teacher_id=int(user["id"]),
        textbook_id=textbook_id,
        topic_slug=topic_slug,
        class_ids=class_ids,
        student_ids=student_ids,
        note=str(data.get("note") or ""),
    )
    if not result.get("ok"):
        fail(400, "recommend_failed", result.get("error", "Не удалось порекомендовать"))
    return jsonify({"ok": True, **result})


@bp.post("/teacher/textbooks")
@require_user("teacher", "admin")
def teacher_upload_textbook():
    user = current_user()
    file_storage = request.files.get("file")
    if not file_storage or not file_storage.filename:
        fail(400, "no_file", "Выберите PDF-файл книги")

    form = request.form
    subject_id = _optional_int(form.get("subject_id"))
    grade = _optional_int(form.get("grade")) or 0
    title = (form.get("title") or "").strip()
    author = (form.get("author") or "").strip()
    description = (form.get("description") or "").strip()
    if not subject_id:
        fail(400, "no_subject", "Выберите предмет")
    if grade not in range(1, 12):
        fail(400, "bad_grade", "Укажите класс книги (1–11)")
    if not title:
        title = os.path.splitext(os.path.basename(file_storage.filename))[0]

    try:
        filename, size = textbooks_service.save_upload(
            file_storage, subject_id, grade, title
        )
    except ValueError as exc:
        fail(400, "upload_failed", str(exc))

    path = os.path.join(textbooks_service.upload_dir(), filename)
    pages = textbooks_service.count_pdf_pages(path)
    textbook_id = textbooks_service.create_textbook(
        subject_id,
        grade,
        title,
        filename,
        original_name=file_storage.filename,
        size_bytes=size,
        pages=pages,
        author=author,
        description=description,
        uploaded_by=int(user["id"]),
    )
    imported = textbooks_service.import_topics_from_pdf(textbook_id)

    class_ids = [
        class_id
        for class_id in _int_list(form.getlist("class_ids"))
        if class_id in _allowed_class_ids(user)
    ]
    book_id = library_service.create_book(
        owner_id=int(user["id"]),
        textbook_id=textbook_id,
        subject_id=subject_id,
        grade=grade,
        title=title,
        author=author,
        description=description,
        class_ids=class_ids,
    )
    return jsonify(
        {
            "ok": True,
            "textbook_id": textbook_id,
            "book_id": book_id,
            "pages": pages,
            "topics_linked": imported.get("linked", 0),
            "topics_created": imported.get("created", 0),
            "visible_to_classes": class_ids,
        }
    ), 201


# ------------------------------------------------------------------ утилиты
def _optional_int(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_list(value) -> list[int]:
    if isinstance(value, str):
        values = [item.strip() for item in value.split(",") if item.strip()]
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        return []
    out = []
    for item in values:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out
