"""Основные страницы: профиль, карта тем, объяснения, учебник."""
from __future__ import annotations

import json
import re
import secrets

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

from content.answer import check_answer
from content.curriculum import TOPICS, topic_by_slug, widget_spec
from database import query_all, query_one
from services import learners as learners_service
from services import orgs
from services import progress as progress_service
from services import reading_quiz
from services import release as release_service
from services import rewards as rewards_service
from services import rounds as rounds_service
from services import textbooks as textbooks_service
from services import topics as topics_service

bp = Blueprint("main", __name__)


def _topics_for(grade: int) -> list[dict]:
    return [t for t in TOPICS if t["grade"] == grade]


def _visible_slugs(learner, subject_id: int) -> set[str]:
    """Темы, которые учитель включил в курсах класса (пусто = показываем все)."""
    if not learner["user_id"]:
        return set()
    slugs = orgs.course_topic_slugs_for_student(
        learner["user_id"], subject_id, learner["grade"]
    )
    return set(slugs)


def _topic_cards(learner, visible: set[str] | None = None) -> list[dict]:
    """Данные для карты тем: прогресс, звёзды, доступность."""
    level = progress_service.level_for_xp(learner["xp"] or 0)
    tp = progress_service.topic_progress_map(learner["id"])
    mp = progress_service.method_progress_map(learner["id"])
    cards = []
    for topic in TOPICS:
        if topic["grade"] != learner["grade"]:
            continue
        if visible and topic["slug"] not in visible:
            continue
        row = tp.get(topic["slug"])
        stars = (row["stars"] if row else 0) or 0
        attempts = (row["attempts"] if row else 0) or 0
        correct = (row["correct"] if row else 0) or 0
        methods_state = [
            {
                "slug": m["slug"],
                "name": m["name"],
                "mastered": bool((mp.get((topic["slug"], m["slug"])) or {"mastered": 0})["mastered"]),
            }
            for m in topic["methods"]
        ]
        cards.append({
            "topic": topic,
            "stars": stars,
            "attempts": attempts,
            "correct": correct,
            "accuracy": round(correct / attempts * 100) if attempts else 0,
            "boss_cleared": bool((row["boss_cleared"] if row else 0)),
            "locked": False,
            "advanced": topic["min_level"] > 1,
            "min_level": topic["min_level"],
            "methods": methods_state,
            "methods_mastered": sum(1 for m in methods_state if m["mastered"]),
        })
    return cards


@bp.route("/")
def welcome():
    # Показываем только профили своей семьи: ключ семьи лежит в подписанной
    # сессии и создаётся при первом создании профиля.
    learners = learners_service.family_learners()
    current = learners_service.current_learner()
    if current:
        return redirect(url_for("main.map_page"))
    return render_template(
        "welcome.html",
        learners=learners,
        grades=list(range(1, 12)),
        app_release=release_service.info(),
    )


@bp.route("/map")
def map_page():
    learner = learners_service.current_learner()
    if not learner:
        return redirect(url_for("main.welcome"))

    subjects = orgs.list_subjects(active_only=True)
    if not subjects:
        subjects = orgs.list_subjects()
    requested = (request.args.get("subject") or "").strip()
    subject = next((s for s in subjects if s["slug"] == requested), None)
    if subject is None:
        subject = next((s for s in subjects if s["slug"] == "math"), subjects[0] if subjects else None)
    if subject is None:
        abort(404)

    grade_topics = topics_service.list_topics(grade=learner["grade"])
    counts: dict[int, int] = {}
    for row in grade_topics:
        counts[row["subject_id"]] = counts.get(row["subject_id"], 0) + 1
    visible = _visible_slugs(learner, subject["id"])

    stats = progress_service.learner_stats(learner["id"])
    tp = progress_service.topic_progress_map(learner["id"])
    cards: list[dict] = []
    reading_cards: list[dict] = []

    if subject["slug"] == "math":
        cards = _topic_cards(learner, visible)
        # Дополнительные темы (1–2 и 5–11 классы) хранятся в БД и изучаются
        # по описанию/ИИ, а не через генераторы базовой программы.
        extra_rows = [
            row for row in topics_service.list_topics(
                subject_id=subject["id"], grade=learner["grade"]
            )
            if (row["source"] or "") != "curriculum"
            and (not visible or row["slug"] in visible)
        ]
        extra_books = textbooks_service.books_for_topics(
            [row["slug"] for row in extra_rows]
        )
        for row in extra_rows:
            progress_row = tp.get(row["slug"])
            reading_cards.append({
                "topic": row,
                "books": extra_books.get(row["slug"], []),
                "stars": (progress_row["stars"] if progress_row else 0) or 0,
                "read": bool(progress_row and (progress_row["stars"] or 0) > 0),
            })
        stats["topics_total"] = len(cards) + len(reading_cards)
    else:
        rows = topics_service.list_topics(subject_id=subject["id"], grade=learner["grade"])
        if visible:
            rows = [row for row in rows if row["slug"] in visible]
        books = textbooks_service.books_for_topics([row["slug"] for row in rows])
        for row in rows:
            progress_row = tp.get(row["slug"])
            topic_books = books.get(row["slug"], [])
            reading_cards.append({
                "topic": row,
                "books": topic_books,
                "stars": (progress_row["stars"] if progress_row else 0) or 0,
                "read": bool(progress_row and (progress_row["stars"] or 0) > 0),
            })
        stats["topics_total"] = len(reading_cards)

    daily = rewards_service.daily_status(learner["id"])
    next_grade = learner["grade"] + 1 if learner["grade"] < 11 else None
    can_upgrade = next_grade and stats["level"] >= 3

    # Подсказка о рекомендованной литературе: только если профиль ребёнка
    # связан с аккаунтом ученика (иначе рекомендаций у него быть не может).
    library_hint: list[dict] = []
    account = query_one(
        "SELECT user_id FROM learner_accounts WHERE learner_id = ?",
        (int(learner["id"]),),
    )
    if account is not None:
        try:
            from services import library as library_service

            library_hint = library_service.unread_for_student(int(account["user_id"]))[:3]
        except Exception:  # pragma: no cover - подсказка не должна ломать карту
            library_hint = []
    return render_template(
        "map.html",
        library_hint=library_hint,
        learner=learner,
        stats=stats,
        cards=cards,
        reading_cards=reading_cards,
        subjects=subjects,
        subject=subject,
        subject_counts=counts,
        daily=daily,
        daily_done=all(item["done"] for item in daily),
        badges=rewards_service.badge_list(learner["id"]),
        next_grade=next_grade,
        can_upgrade=can_upgrade,
    )


@bp.route("/learners", methods=["POST"])
def create_learner():
    name = (request.form.get("name") or "").strip()
    avatar = request.form.get("avatar") or "🦊"
    grade = request.form.get("grade") or "3"
    pin = (request.form.get("pin") or "").strip()
    if not name:
        flash("Введите имя ребёнка", "error")
        return redirect(url_for("main.welcome"))
    if pin and (not pin.isdigit() or len(pin) != 4):
        flash("PIN должен состоять из 4 цифр", "error")
        return redirect(url_for("main.welcome"))
    learner_id = learners_service.create_learner(
        name, avatar, int(grade), pin or None,
        family_key=learners_service.family_key(create=True),
    )
    learners_service.login(learner_id)
    flash(f"Привет, {name}! Выбирай тему и начинаем 🚀", "success")
    return redirect(url_for("main.map_page"))


@bp.route("/learners/<int:learner_id>/enter")
def enter_learner(learner_id: int):
    """Экран ввода PIN перед входом в профиль."""
    learner = learners_service.get_learner(learner_id)
    if not learner or not learners_service.owns(learner, learners_service.family_key()):
        # Не раскрываем существование чужих профилей.
        abort(404)
    if not learner["pin_hash"]:
        return redirect(url_for("main.welcome"))
    return render_template("learner_pin.html", learner=learner, error=None)


@bp.route("/learners/<int:learner_id>/login", methods=["POST"])
def login_learner(learner_id: int):
    learner = learners_service.get_learner(learner_id)
    key = learners_service.family_key()
    if not learner or not learners_service.owns(learner, key):
        abort(404)

    if learner["pin_hash"]:
        from services import rate_limit

        throttle_key = rate_limit.make_key(
            "learner-pin", rate_limit.client_ip(request), str(learner_id)
        )
        wait = rate_limit.blocked_for(throttle_key)
        if wait:
            return render_template(
                "learner_pin.html",
                learner=learner,
                error=f"Слишком много попыток. Подождите {wait} с.",
            ), 429
        pin = (request.form.get("pin") or "").strip()
        if not learners_service.verify_pin(pin, learner["pin_hash"]):
            locked = rate_limit.register_failure(throttle_key, lock_seconds=120)
            if locked:
                return render_template(
                    "learner_pin.html",
                    learner=learner,
                    error=f"Слишком много попыток. Подождите {locked} с.",
                ), 429
            return render_template(
                "learner_pin.html", learner=learner, error="Неверный PIN-код"
            ), 403
        rate_limit.clear(throttle_key)

    learners_service.login(learner_id)
    flash(f"С возвращением, {learner['name']}!", "success")
    return redirect(url_for("main.map_page"))


@bp.route("/logout", methods=["POST"])
def logout():
    learners_service.logout()
    flash("До встречи!", "info")
    return redirect(url_for("main.welcome"))


@bp.route("/profile")
def profile():
    learner = learners_service.current_learner()
    if not learner:
        return redirect(url_for("main.welcome"))
    stats = progress_service.learner_stats(learner["id"])
    owned = {b["badge_key"] for b in rewards_service.badge_list(learner["id"])}
    from content.achievements import ACHIEVEMENTS

    return render_template(
        "profile.html",
        learner=learner,
        stats=stats,
        owned=owned,
        catalog=ACHIEVEMENTS,
        accuracy=progress_service.topic_accuracy(learner["id"]),
    )


@bp.route("/learner/grade", methods=["POST"])
def change_grade():
    """Переход на программу следующего класса (доступен с 3 уровня)."""
    learner = learners_service.current_learner()
    if not learner:
        return redirect(url_for("main.welcome"))
    level = progress_service.level_for_xp(learner["xp"] or 0)
    grade = int(request.form.get("grade") or learner["grade"])
    if not 1 <= grade <= 11 or level < 3:
        flash("Этот класс пока не открыт. Нужно дорасти до 3 уровня.", "error")
        return redirect(url_for("main.map_page"))
    learners_service.update_learner(learner["id"], grade=grade)
    flash(f"Теперь программа {grade} класса! Удачи!", "success")
    return redirect(url_for("main.map_page"))


@bp.route("/topic/<slug>")
def topic_page(slug: str):
    learner = learners_service.current_learner()
    if not learner:
        return redirect(url_for("main.welcome"))
    topic = topic_by_slug(slug)
    if not topic:
        row = topics_service.get_topic(slug)
        if not row:
            abort(404)
        return _reading_topic_page(learner, row)

    tp = progress_service.topic_progress_map(learner["id"])
    mp = progress_service.method_progress_map(learner["id"])
    row = tp.get(slug)
    methods = []
    for method in topic["methods"]:
        state = mp.get((slug, method["slug"]))
        methods.append({
            **method,
            "mastered": bool(state and state["mastered"]),
            "attempts": (state["attempts"] if state else 0) or 0,
            "correct": (state["correct"] if state else 0) or 0,
        })
    books = textbooks_service.textbooks_for_topic(slug, grade=topic["grade"])
    return render_template(
        "topic.html",
        learner=learner,
        topic=topic,
        methods=methods,
        books=books,
        stars=(row["stars"] if row else 0) or 0,
        attempts=(row["attempts"] if row else 0) or 0,
        correct=(row["correct"] if row else 0) or 0,
        boss_cleared=bool(row and row["boss_cleared"]),
    )


def _reading_topic_page(learner, topic):
    """Тема без автогенератора: изучение по загруженному пособию."""
    if int(topic["grade"]) != int(learner["grade"]):
        abort(403)
    books = textbooks_service.textbooks_for_topic(
        topic["slug"], subject_id=topic["subject_id"], grade=topic["grade"]
    )
    progress_row = query_one(
        "SELECT * FROM topic_progress WHERE learner_id = ? AND topic_slug = ?",
        (learner["id"], topic["slug"]),
    )
    read = query_one(
        """SELECT id FROM attempts
            WHERE learner_id = ? AND topic_slug = ? AND mode = 'reading' AND correct = 1
            LIMIT 1""",
        (learner["id"], topic["slug"]),
    )
    siblings = topics_service.list_topics(
        subject_id=topic["subject_id"], grade=topic["grade"]
    )
    index = next((i for i, item in enumerate(siblings) if item["slug"] == topic["slug"]), None)
    previous_topic = siblings[index - 1] if index not in (None, 0) else None
    next_topic = siblings[index + 1] if index is not None and index + 1 < len(siblings) else None
    return render_template(
        "topic_reading.html",
        learner=learner,
        topic=topic,
        books=books,
        read=bool(read),
        stars=(progress_row["stars"] if progress_row else 0) or 0,
        previous_topic=previous_topic,
        next_topic=next_topic,
    )


@bp.route("/topic/<slug>/complete", methods=["POST"])
def complete_reading(slug: str):
    learner = learners_service.current_learner()
    if not learner:
        return redirect(url_for("main.welcome"))
    topic = topics_service.get_topic(slug)
    if not topic:
        abort(404)
    if topic["source"] == "curriculum" or topic["kind"] == "practice":
        abort(400)
    if int(topic["grade"]) != int(learner["grade"]):
        abort(403)
    result = progress_service.mark_topic_read(learner["id"], slug)
    if result["already"]:
        flash("Эта тема уже отмечена как изученная ⭐", "info")
    else:
        flash(
            f"Тема изучена! +{result['xp']} XP и +{result['coins']} монет ⭐",
            "success",
        )
    return redirect(url_for("main.topic_page", slug=slug))


@bp.route("/topic/quiz/photo/<int:review_id>/<path:filename>")
def quiz_photo(review_id: int, filename: str):
    """Фото ответов самодельного теста: только владельцу профиля."""
    from services import quiz_review

    learner = learners_service.current_learner()
    review = quiz_review.get_review(review_id)
    if review is None:
        abort(404)
    if learner is None or int(review["learner_id"]) != int(learner["id"]):
        abort(403)
    for relative in json.loads(review["photos"] or "[]"):
        if relative.split("/")[-1] == filename:
            path = quiz_review.absolute_path(relative)
            if path:
                return send_file(path, max_age=0)
    abort(404)


@bp.route("/topic/<slug>/quiz", methods=["GET", "POST"])
def topic_quiz(slug: str):
    learner = learners_service.current_learner()
    if not learner:
        return redirect(url_for("main.welcome"))
    topic = topics_service.get_topic(slug)
    if not topic:
        abort(404)
    if topic["source"] == "curriculum" or topic["kind"] == "practice":
        abort(400)
    if int(topic["grade"]) != int(learner["grade"]):
        abort(403)

    if request.method == "GET":
        questions = reading_quiz.build_questions(
            topic, 8, user_id=int(learner["user_id"]) if learner["user_id"] else None
        )
        if not questions:
            flash(
                "По этой теме пока не удалось составить вопросы. "
                "Проверьте, что к ней привязано пособие с текстом, "
                "или включите ИИ в разделе «Админ → ИИ».",
                "error",
            )
            return redirect(url_for("main.topic_page", slug=slug))
        session["reading_quiz"] = {
            "slug": slug,
            "token": secrets.token_urlsafe(16),
            "items": [
                {"question": item["question"], "answer": item["answer"]}
                for item in questions
            ],
        }
        return render_template(
            "topic_quiz.html",
            learner=learner,
            topic=topic,
            questions=questions,
        )

    stored = session.pop("reading_quiz", None) or {}
    if stored.get("slug") != slug or not stored.get("items"):
        flash("Проверочная работа устарела. Начните заново.", "info")
        return redirect(url_for("main.topic_quiz", slug=slug))

    uploads = [
        item for item in request.files.getlist("photos")
        if getattr(item, "filename", "")
    ]
    if uploads:
        from services import quiz_review

        token = stored.get("token") or secrets.token_urlsafe(12)
        try:
            photos = quiz_review.save_photos(uploads, int(learner["id"]), token)
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("main.topic_quiz", slug=slug))
        review = quiz_review.review_with_photos(
            stored["items"],
            photos,
            topic["title"],
            user_id=int(learner["user_id"]) if learner["user_id"] else None,
        )
        review_id = quiz_review.save_review(
            int(learner["id"]), slug, token, photos, review
        )
        results = review.get("details") or []
        correct_count = int(review.get("score") or 0)
        for entry in results:
            progress_service.record_attempt(
                learner["id"], slug, None, "reading.quiz", bool(entry["correct"]),
                entry.get("given") or "", entry.get("answer") or "", 0, 0,
                mode="reading_quiz_photo",
            )
        stars = (
            progress_service.apply_round_result(
                learner["id"], slug, correct_count, len(results)
            )
            if review.get("ai_status") == "checked" and results
            else 0
        )
        if review.get("ai_status") == "checked":
            flash(
                f"ИИ проверил фото: верно {correct_count} из {len(results)}.",
                "success" if correct_count == len(results) else "info",
            )
        elif review.get("ai_status") == "disabled":
            flash("Фото сохранены, но ИИ не подключён — проверка недоступна.", "info")
        else:
            flash("Не удалось проверить фото. Попробуйте позже.", "error")
        return render_template(
            "topic_quiz_result.html",
            learner=learner,
            topic=topic,
            results=results,
            correct_count=correct_count,
            stars=stars,
            review=review,
            photos=photos,
            review_id=review_id,
        )

    legacy = request.form.getlist("answer")
    results = []
    correct_count = 0
    for index, item in enumerate(stored["items"]):
        answer = request.form.get(f"answer_{index}")
        if answer is None:
            answer = legacy[index] if index < len(legacy) else ""
        correct, expected = check_answer(
            answer, {"answer": item["answer"], "answer_type": "choice"}
        )
        if correct:
            correct_count += 1
        progress_service.record_attempt(
            learner["id"], slug, None, "reading.quiz", correct,
            answer, expected, 0, 0, mode="reading_quiz",
        )
        results.append({
            "question": item["question"],
            "given": answer,
            "expected": expected,
            "correct": correct,
        })
    stars = progress_service.apply_round_result(
        learner["id"], slug, correct_count, len(results)
    )
    if correct_count == len(results):
        flash("Отлично! Все ответы верные.", "success")
    elif correct_count:
        flash(f"Верно {correct_count} из {len(results)}. Можно попробовать ещё раз!", "info")
    else:
        flash("Пока ни одного верного ответа. Прочитай тему и попробуй снова.", "error")
    return render_template(
        "topic_quiz_result.html",
        learner=learner,
        topic=topic,
        results=results,
        correct_count=correct_count,
        stars=stars,
    )


@bp.route("/topic/<slug>/explain/<method_slug>")
def explain(slug: str, method_slug: str):
    learner = learners_service.current_learner()
    if not learner:
        return redirect(url_for("main.welcome"))
    topic = topic_by_slug(slug)
    if not topic:
        abort(404)
    method = next((m for m in topic["methods"] if m["slug"] == method_slug), None)
    if not method:
        abort(404)

    generator_key = rounds_service.generator_for(slug, method_slug)
    example = rounds_service.build_task(generator_key, 1)
    variables = example.get("variables", {})
    explanation = _fill(method.get("explanation", ""), variables)
    steps = [_fill_step(step, variables) for step in method.get("steps", [])]
    spec = widget_spec(method.get("widget", "none"), variables, example.get("widget"))
    return render_template(
        "explain.html",
        learner=learner,
        topic=topic,
        method=method,
        example=example,
        explanation=explanation,
        steps=steps,
        widget=spec,
        method_index=topic["methods"].index(method),
        methods_total=len(topic["methods"]),
        next_method=rounds_service.next_method_slug(slug, method_slug),
    )


def _fill(template: str, variables: dict) -> str:
    """Подставить значения в шаблон объяснения (поддерживает форматы вида {m:02d})."""

    def repl(match: "re.Match[str]") -> str:
        name = match.group(1)
        spec = match.group(2)
        if name not in variables:
            return match.group(0)
        value = variables[name]
        if spec:
            try:
                return format(value, spec.lstrip(":"))
            except (ValueError, TypeError):
                return str(value)
        return str(value)

    return re.sub(r"\{(\w+)(:[^}]*)?\}", repl, template or "")


def _fill_step(step: dict, variables: dict) -> dict:
    filled = dict(step)
    filled["text"] = _fill(step.get("text", ""), variables)
    return filled


@bp.route("/textbook")
def textbook():
    learner = learners_service.current_learner()
    if learner:
        rows = textbooks_service.textbooks_for_grade(learner["grade"])
    else:
        rows = textbooks_service.list_textbooks()
    books = []
    for row in rows:
        item = dict(row)
        item["links"] = textbooks_service.textbook_topics(row["id"])
        books.append(item)
    return render_template("textbook.html", learner=learner, books=books)


@bp.route("/daily")
def daily():
    learner = learners_service.current_learner()
    if not learner:
        return redirect(url_for("main.welcome"))
    tasks = rewards_service.daily_status(learner["id"])
    return render_template("daily.html", learner=learner, tasks=tasks)


@bp.route("/family")
def family():
    """Результаты своей семьи (профили других семей не показываем)."""
    learners = learners_service.family_learners()
    rows = []
    for learner in learners:
        stats = progress_service.learner_stats(learner["id"])
        rows.append({
            "learner": learner,
            "xp": stats.get("xp", 0),
            "level": stats.get("level", 1),
            "correct": stats.get("total_correct", 0),
            "streak": stats.get("streak_days", 0),
            "stars": sum(
                (r["stars"] or 0)
                for r in query_all(
                    "SELECT stars FROM topic_progress WHERE learner_id = ?", (learner["id"],)
                )
            ),
        })
    rows.sort(key=lambda r: r["xp"], reverse=True)
    return render_template("family.html", rows=rows)
