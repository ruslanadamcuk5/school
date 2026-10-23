"""Библиотека: книги учителя, доступ классам, чтение и рекомендации.

Библиотека принадлежит школе, но наполняет её учитель:

* учитель загружает книгу в библиотеку и отмечает классы, которым она доступна;
* книга разбивается на темы по оглавлению, учитель видит темы и страницы;
* учитель рекомендует нужную тему (или книгу целиком) классам и ученикам;
* ученики видят доступные книги и рекомендации в своей библиотеке.
"""
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

from database import query_all
from services import auth, library as library_service, orgs, textbooks as textbooks_service

bp = Blueprint("library", __name__, url_prefix="/library")


def _current_user():
    return auth.current_user()


def _class_list(user) -> list:
    """Классы, которыми распоряжается пользователь (администратор — все)."""
    if user["role"] == auth.ROLE_ADMIN:
        return orgs.list_classes()
    return orgs.classes_of_teacher(user["id"])


def _student_list(user) -> list:
    """Ученики, которым можно отправлять рекомендации."""
    if user["role"] == auth.ROLE_ADMIN:
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


def _form_ids(name: str) -> list[int]:
    return [int(value) for value in request.form.getlist(name) if value.isdigit()]


# --------------------------------------------------------------- моя библиотека
@bp.route("/")
@auth.login_required
def library():
    user = _current_user()
    role = user["role"]
    if role in (auth.ROLE_TEACHER, auth.ROLE_ADMIN):
        return _teacher_library(user)
    if role == auth.ROLE_STUDENT:
        return _student_library(user, user, readonly=False)
    return _parent_library(user)


def _teacher_library(user):
    search = (request.args.get("search") or "").strip()
    grade = request.args.get("grade", type=int)
    subject_id = request.args.get("subject_id", type=int)
    books = library_service.list_books(
        owner_id=None if user["role"] == auth.ROLE_ADMIN else user["id"],
        search=search, grade=grade, subject_id=subject_id,
    )
    stats = (
        {"books": len(books), "classes": 0, "recommendations": 0}
        if user["role"] == auth.ROLE_ADMIN
        else library_service.teacher_stats(user["id"])
    )
    return render_template(
        "library/library.html",
        user=user,
        books=books,
        stats=stats,
        classes=_class_list(user),
        subjects=orgs.list_subjects(active_only=True),
        search=search,
        selected_grade=grade,
        selected_subject=subject_id,
    )


def _student_library(user, student, readonly: bool, children=None, child=None):
    books = library_service.list_books_for_student(student["id"])
    recommendations = library_service.recommendations_for_student(student["id"])
    stats = {
        "books": len(books),
        "active": sum(1 for rec in recommendations if not rec["done"]),
        "done": sum(1 for rec in recommendations if rec["done"]),
    }
    return render_template(
        "library/student.html",
        user=user,
        student=student,
        readonly=readonly,
        children=children or [],
        child=child,
        books=books,
        recommendations=recommendations,
        stats=stats,
    )


def _parent_library(user):
    children = [child for child in auth.children_of(user["id"])
                if child["role"] == auth.ROLE_STUDENT]
    if not children:
        return render_template(
            "library/student.html",
            user=user, student=None, readonly=True, children=[], child=None,
            books=[], recommendations=[],
            stats={"books": 0, "active": 0, "done": 0},
        )
    child_id = request.args.get("child_id", type=int)
    if child_id:
        child = next((c for c in children if int(c["id"]) == child_id), None)
        if not child:
            abort(403)
    else:
        child = children[0]
    return _student_library(user, child, readonly=True, children=children, child=child)


# --------------------------------------------------------------- загрузка книги
@bp.route("/upload", methods=["POST"])
@auth.role_required(auth.ROLE_TEACHER, auth.ROLE_ADMIN)
def upload():
    user = _current_user()
    file_storage = request.files.get("file")
    title = (request.form.get("title") or "").strip()
    subject_id = request.form.get("subject_id", type=int)
    grade = request.form.get("grade", type=int) or 0
    author = (request.form.get("author") or "").strip()
    description = (request.form.get("description") or "").strip()

    if not file_storage or not file_storage.filename:
        flash("Выберите файл книги (PDF)", "error")
        return redirect(url_for("library.library"))
    if not title:
        title = os.path.splitext(os.path.basename(file_storage.filename))[0]
    if not subject_id:
        flash("Выберите предмет книги", "error")
        return redirect(url_for("library.library"))
    if grade not in range(1, 12):
        flash("Укажите класс книги (1–11)", "error")
        return redirect(url_for("library.library"))

    try:
        filename, size = textbooks_service.save_upload(file_storage, subject_id, grade, title)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("library.library"))

    path = os.path.join(textbooks_service.upload_dir(), filename)
    pages = textbooks_service.count_pdf_pages(path)
    textbook_id = textbooks_service.create_textbook(
        subject_id, grade, title, filename,
        original_name=file_storage.filename, size_bytes=size, pages=pages,
        author=author, description=description, uploaded_by=user["id"],
    )
    # Книга сразу разбивается на темы по оглавлению.
    imported = textbooks_service.import_topics_from_pdf(textbook_id)

    allowed = _allowed_class_ids(user)
    class_ids = [cid for cid in _form_ids("class_ids") if cid in allowed]
    book_id = library_service.create_book(
        owner_id=user["id"],
        textbook_id=textbook_id,
        subject_id=subject_id,
        grade=grade,
        title=title,
        author=author,
        description=description,
        class_ids=class_ids,
    )
    if imported["linked"]:
        flash(
            f"Книга «{title}» загружена: {pages} стр., тем из оглавления — "
            f"{imported['linked']} (новых: {imported['created']}).",
            "success",
        )
    else:
        flash(
            f"Книга «{title}» загружена ({pages} стр.), но оглавление распознать "
            "не удалось — добавьте темы вручную на странице книги.",
            "info",
        )
    if not class_ids:
        flash("Книга пока никому не видна: выберите классы на странице книги.", "info")
    return redirect(url_for("library.book", book_id=book_id))


# --------------------------------------------------------------- страница книги
@bp.route("/<int:book_id>")
@auth.login_required
def book(book_id: int):
    user = _current_user()
    item = library_service.get_book(book_id)
    if not item:
        abort(404)
    if not library_service.can_access_book(user, book_id):
        abort(403)
    topics = library_service.book_topics(book_id)

    is_manager = user["role"] == auth.ROLE_ADMIN or int(item["owner_id"]) == int(user["id"])
    if user["role"] in (auth.ROLE_TEACHER, auth.ROLE_ADMIN) and is_manager:
        classes = _class_list(user)
        current_class_ids = set(library_service.book_class_ids(book_id))
        students = _student_list(user)
        return render_template(
            "library/book.html",
            user=user,
            item=item,
            topics=topics,
            classes=classes,
            current_class_ids=current_class_ids,
            students=students,
            open_url=url_for("library.open_textbook", textbook_id=item["textbook_id"]),
        )

    recommendations = []
    if user["role"] == auth.ROLE_STUDENT:
        recommendations = [
            rec for rec in library_service.recommendations_for_student(user["id"])
            if int(rec["book_id"]) == int(book_id)
        ]
    return render_template(
        "library/reader.html",
        user=user,
        item=item,
        topics=topics,
        recommendations=recommendations,
        open_url=url_for("library.open_textbook", textbook_id=item["textbook_id"]),
    )


@bp.route("/<int:book_id>/access", methods=["POST"])
@auth.role_required(auth.ROLE_TEACHER, auth.ROLE_ADMIN)
def set_access(book_id: int):
    user = _current_user()
    item = library_service.get_book(book_id)
    if not item:
        abort(404)
    if user["role"] != auth.ROLE_ADMIN and int(item["owner_id"]) != int(user["id"]):
        abort(403)
    allowed = _allowed_class_ids(user)
    class_ids = [cid for cid in _form_ids("class_ids") if cid in allowed]
    library_service.set_book_classes(book_id, class_ids)
    flash(
        "Доступ обновлён: книгу видят "
        + (f"классов — {len(class_ids)}" if class_ids else "никто (классы не выбраны)"),
        "success",
    )
    return redirect(url_for("library.book", book_id=book_id))


@bp.route("/<int:book_id>/delete", methods=["POST"])
@auth.role_required(auth.ROLE_TEACHER, auth.ROLE_ADMIN)
def delete(book_id: int):
    user = _current_user()
    item = library_service.get_book(book_id)
    if not item:
        abort(404)
    if user["role"] != auth.ROLE_ADMIN and int(item["owner_id"]) != int(user["id"]):
        abort(403)
    result = library_service.delete_book(book_id)
    if result["ok"]:
        flash(f"Книга «{result['title']}» удалена из библиотеки", "info")
    else:
        flash(result.get("error", "Не удалось удалить книгу"), "error")
    return redirect(url_for("library.library"))


@bp.route("/<int:book_id>/topics/add", methods=["POST"])
@auth.role_required(auth.ROLE_TEACHER, auth.ROLE_ADMIN)
def add_topics(book_id: int):
    from services import pdf_topics

    user = _current_user()
    item = library_service.get_book(book_id)
    if not item:
        abort(404)
    if user["role"] != auth.ROLE_ADMIN and int(item["owner_id"]) != int(user["id"]):
        abort(403)
    entries = pdf_topics.parse_manual_topics(request.form.get("manual_topics", ""))
    if not entries:
        flash("Не удалось разобрать список. Формат: «Название — 12»", "error")
    else:
        result = textbooks_service.add_topics_manually(item["textbook_id"], entries)
        flash(f"Добавлено тем: {result['linked']} (новых: {result['created']})", "success")
    return redirect(url_for("library.book", book_id=book_id))


@bp.route("/<int:book_id>/topics/import", methods=["POST"])
@auth.role_required(auth.ROLE_TEACHER, auth.ROLE_ADMIN)
def import_topics(book_id: int):
    user = _current_user()
    item = library_service.get_book(book_id)
    if not item:
        abort(404)
    if user["role"] != auth.ROLE_ADMIN and int(item["owner_id"]) != int(user["id"]):
        abort(403)
    imported = textbooks_service.import_topics_from_pdf(item["textbook_id"])
    if imported["linked"]:
        flash(f"Темы из оглавления обновлены: {imported['linked']}", "success")
    else:
        flash("Оглавление в PDF не найдено — добавьте темы вручную.", "error")
    return redirect(url_for("library.book", book_id=book_id))


@bp.route("/<int:book_id>/topics/<path:topic_slug>/remove", methods=["POST"])
@auth.role_required(auth.ROLE_TEACHER, auth.ROLE_ADMIN)
def remove_topic(book_id: int, topic_slug: str):
    user = _current_user()
    item = library_service.get_book(book_id)
    if not item:
        abort(404)
    if user["role"] != auth.ROLE_ADMIN and int(item["owner_id"]) != int(user["id"]):
        abort(403)
    if library_service.remove_book_topic(book_id, topic_slug):
        flash("Тема убрана из книги", "info")
    return redirect(url_for("library.book", book_id=book_id))


# --------------------------------------------------------------- рекомендации
@bp.route("/<int:book_id>/recommend", methods=["POST"])
@auth.role_required(auth.ROLE_TEACHER, auth.ROLE_ADMIN)
def recommend(book_id: int):
    user = _current_user()
    item = library_service.get_book(book_id)
    if not item:
        abort(404)
    if user["role"] != auth.ROLE_ADMIN and int(item["owner_id"]) != int(user["id"]):
        abort(403)

    topic_slug = (request.form.get("topic_slug") or "").strip() or None
    note = (request.form.get("note") or "").strip()
    allowed_classes = _allowed_class_ids(user)
    allowed_students = _allowed_student_ids(user)
    class_ids = [cid for cid in _form_ids("class_ids") if cid in allowed_classes]
    student_ids = [sid for sid in _form_ids("student_ids") if sid in allowed_students]

    if not class_ids and not student_ids:
        flash("Выберите хотя бы один класс или ученика", "error")
        return redirect(url_for("library.book", book_id=book_id))

    result = library_service.recommend(
        teacher_id=user["id"],
        book_id=book_id,
        topic_slug=topic_slug,
        class_ids=class_ids,
        student_ids=student_ids,
        note=note,
    )
    if not result["ok"]:
        flash(result.get("error", "Не удалось отправить рекомендацию"), "error")
    else:
        message = f"Рекомендация отправлена: {result['created']}"
        if result["skipped"]:
            message += f", уже была отправлена ранее — {result['skipped']}"
        flash(message, "success")
    return redirect(url_for("library.book", book_id=book_id))


@bp.route("/recommendations")
@auth.role_required(auth.ROLE_TEACHER, auth.ROLE_ADMIN)
def recommendations():
    user = _current_user()
    recs = library_service.recommendations_by_teacher(user["id"])
    return render_template("library/recommendations.html", user=user, recs=recs)


@bp.route("/recommendations/<int:rec_id>/revoke", methods=["POST"])
@auth.role_required(auth.ROLE_TEACHER, auth.ROLE_ADMIN)
def revoke(rec_id: int):
    user = _current_user()
    if library_service.revoke_recommendation(rec_id, user["id"]):
        flash("Рекомендация отозвана", "info")
    else:
        flash("Рекомендация не найдена", "error")
    return redirect(url_for("library.recommendations"))


@bp.route("/recommendations/<int:rec_id>/done", methods=["POST"])
@auth.role_required(auth.ROLE_STUDENT)
def done(rec_id: int):
    user = _current_user()
    if library_service.mark_recommendation_done(rec_id, user["id"]):
        flash("Отмечено как прочитанное ✅", "success")
    else:
        flash("Рекомендация не найдена", "error")
    return redirect(request.referrer or url_for("library.library"))


# --------------------------------------------------------------- чтение книги
@bp.route("/open/<int:textbook_id>")
@auth.login_required
def open_textbook(textbook_id: int):
    """Выдать PDF книги: только тем, кому она доступна."""
    user = _current_user()
    books = query_all("SELECT id FROM library_books WHERE textbook_id = ?", (textbook_id,))
    if not any(library_service.can_access_book(user, int(row["id"])) for row in books):
        abort(403)
    row = textbooks_service.get_textbook(textbook_id)
    if not row:
        abort(404)
    path = textbooks_service.file_path(row)
    if not os.path.exists(path):
        abort(404)
    return send_file(path, mimetype="application/pdf", as_attachment=False)
