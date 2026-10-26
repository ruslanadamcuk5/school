"""Тесты приложения: генераторы, ответы, маршруты.

Запуск:  python -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DB = os.path.join(tempfile.gettempdir(), "edu_math_test.db")
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_PATH"] = _TMP_DB
os.environ["SECRET_KEY"] = "test-secret"

from content.answer import check_answer, normalize_number, normalize_text, normalize_time  # noqa: E402
from content.curriculum import TOPICS, widget_spec  # noqa: E402
from content.generators import REGISTRY, generators_for_topic  # noqa: E402
from services import rounds  # noqa: E402
from services.pdf_text import repair_text  # noqa: E402
from services.pdf_topics import _is_junk_outline_title, parse_contents_text  # noqa: E402


class TestGenerators(unittest.TestCase):
    def test_every_topic_has_generators(self):
        for topic in TOPICS:
            keys = generators_for_topic(topic["slug"])
            self.assertTrue(keys, f"Нет генераторов для {topic['slug']}")
            for key in keys:
                self.assertIn(key, REGISTRY)

    def test_every_topic_has_methods(self):
        for topic in TOPICS:
            self.assertGreaterEqual(len(topic["methods"]), 3, topic["slug"])

    def test_method_example_is_registered(self):
        for topic in TOPICS:
            for method in topic["methods"]:
                if method.get("example"):
                    self.assertIn(method["example"], REGISTRY, f"{topic['slug']}.{method['slug']}")

    def test_generator_output_is_complete(self):
        for key, fn in REGISTRY.items():
            for difficulty in (1, 3):
                task = fn(difficulty)
                self.assertIn("question", task, key)
                self.assertIn("answer", task, key)
                self.assertTrue(str(task["question"]).strip(), key)
                self.assertTrue(str(task["answer"]).strip(), key)
                self.assertIsInstance(task.get("hints", []), list, key)
                self.assertTrue(task.get("hints"), f"{key}: нет подсказок")
                if task.get("answer_type") == "choice":
                    self.assertIn(task["answer"], task["choices"], key)

    def test_explanation_templates_have_known_variables(self):
        """В шаблонах объяснений не должно быть незаполненных плейсхолдеров."""
        for topic in TOPICS:
            for method in topic["methods"]:
                example_key = method.get("example")
                if not example_key:
                    continue
                task = REGISTRY[example_key](1)
                variables = task.get("variables", {})
                text = method.get("explanation", "") + " " + " ".join(
                    step.get("text", "") for step in method.get("steps", [])
                )
                names = {
                    match.group(1)
                    for match in re.finditer(r"\{(\w+)(?::[^}]*)?\}", text)
                }
                for name in sorted(names):
                    self.assertIn(
                        name, variables,
                        f"{topic['slug']}.{method['slug']}: переменная {{{name}}} отсутствует",
                    )


class TestAnswers(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(normalize_number("12"), 12)
        self.assertEqual(normalize_number("12,5"), 12.5)
        self.assertEqual(normalize_number("1/2"), 0.5)
        self.assertEqual(normalize_number("3 : 4"), 0.75)
        self.assertIsNone(normalize_number("abc"))

    def test_time(self):
        self.assertEqual(normalize_time("3:05"), "3:05")
        self.assertEqual(normalize_time("3.5"), "3:05")
        self.assertEqual(normalize_time("305"), "3:05")
        self.assertEqual(normalize_time("12:30"), "12:30")
        self.assertIsNone(normalize_time("25:70"))

    def test_text_normalisation(self):
        self.assertEqual(normalize_text(" 12 см "), "12")
        self.assertEqual(normalize_text("12см"), "12")

    def test_check_answer_types(self):
        ok, _ = check_answer("12", {"answer": "12", "answer_type": "number"})
        self.assertTrue(ok)
        ok, _ = check_answer("1/2", {"answer": "0.5", "answer_type": "number"})
        self.assertTrue(ok)
        ok, _ = check_answer("2 1/2", {"answer": "5/2", "answer_type": "fraction"})
        self.assertTrue(ok)
        ok, _ = check_answer("3:05", {"answer": "3:05", "answer_type": "time"})
        self.assertTrue(ok)
        ok, _ = check_answer("нет", {"answer": "да", "answer_type": "choice", "choices": ["да", "нет"]})
        self.assertFalse(ok)


class TestPdfTopics(unittest.TestCase):
    def test_wrapped_titles_are_merged(self):
        text = (
            "Змест\n"
            "Паўтарэнне ............................. 3\n"
            "Словы, аднолькавыя па гучанні, розныя па\n"
            " значэнні  ............................. 102\n"
            "СКЛАД СЛОВА\n"
            "Роднасныя (аднакаранёвыя) словы. Корань\n"
            " слова .................................. 109\n"
        )
        entries = dict(parse_contents_text(text))
        self.assertEqual(entries["Паўтарэнне"], 3)
        self.assertEqual(
            entries["Словы, аднолькавыя па гучанні, розныя па значэнні"], 102
        )
        self.assertEqual(
            entries["Роднасныя (аднакаранёвыя) словы. Корань слова"], 109
        )
        self.assertNotIn("значэнні", entries)
        self.assertNotIn("слова", entries)

    def test_column_layout_pairs_pages_in_order(self):
        text = (
            "С О Д Е Р Ж А Н И Е\n"
            "Дорогие друзья! .................................\n"
            "ЖИВОЕ НАРОДНОЕ СЛОВО ...........................\n"
            "Песни-веснянки, жнивные песни .........\n"
            "«Сестрица Алёнушка и братец Ивануш-\n"
            "ка» (русская народная сказка) ........\n"
            "«Два брата» (латышская народная сказка)\n"
            "3\n"
            "5\n"
            "7\n"
            "8\n"
            "12\n"
            "146\n"
        )
        entries = parse_contents_text(text)
        self.assertEqual(
            entries,
            [
                ("Дорогие друзья!", 3),
                ("ЖИВОЕ НАРОДНОЕ СЛОВО", 5),
                ("Песни-веснянки, жнивные песни", 7),
                ("«Сестрица Алёнушка и братец Ивануш-ка» (русская народная сказка)", 8),
                ("«Два брата» (латышская народная сказка)", 12),
            ],
        )

    def test_cp437_glyphs_are_repaired(self):
        broken = "Раздел".encode("cp1251").decode("cp437")
        self.assertNotEqual(broken, "Раздел")
        self.assertEqual(repair_text(broken), "Раздел")

    def test_layout_artifacts_are_not_topics(self):
        for title in (
            "1: ОК",
            "3кл_Жуковiч_Лiт чыт_ч2_2017+",
            "Обложка_Жукович_15версия",
            "Жукович#maket_NEW_уменш",
            "форз1",
            "Страница 2",
            "Пустая страница",
        ):
            self.assertTrue(_is_junk_outline_title(title), title)
        self.assertFalse(_is_junk_outline_title("НАРОДНЫЕ ПЕСНИ"))


class TestRounds(unittest.TestCase):
    def test_generator_for_method(self):
        topic = TOPICS[0]
        method = topic["methods"][0]
        key = rounds.generator_for(topic["slug"], method["slug"])
        self.assertIn(key, REGISTRY)

    def test_next_method_cycles(self):
        topic = TOPICS[0]
        first = topic["methods"][0]["slug"]
        second = rounds.next_method_slug(topic["slug"], first)
        self.assertNotEqual(first, second)
        self.assertIn(second, [m["slug"] for m in topic["methods"]])

    def test_widget_spec(self):
        spec = widget_spec("fraction_circle", {"den": 4, "num": 2})
        self.assertEqual(spec["type"], "fraction_circle")
        self.assertEqual(spec["den"], 4)


class TestRoutes(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app("testing")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def _csrf(self, path="/"):
        html = self.client.get(path).get_data(as_text=True)
        marker = 'name="csrf-token" content="'
        idx = html.find(marker)
        self.assertGreater(idx, -1, "CSRF-токен не найден")
        start = idx + len(marker)
        return html[start:html.find('"', start)]

    def test_health(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_welcome_and_create_learner(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        token = self._csrf("/")
        response = self.client.post(
            "/learners",
            data={"name": "Тестовый", "avatar": "🦊", "grade": "3", "csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.get("/map")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Карта тем", response.get_data(as_text=True))

    def test_csrf_required(self):
        response = self.client.post("/learners", data={"name": "X"})
        self.assertEqual(response.status_code, 400)

    def test_root_redirects_to_map_for_logged_in_learner(self):
        token = self._csrf("/")
        self.client.post(
            "/learners",
            data={"name": "Тестовый", "avatar": "🦊", "grade": "3", "csrf_token": token},
        )
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/map"))

    def test_full_round_flow(self):
        token = self._csrf("/")
        self.client.post(
            "/learners",
            data={"name": "Тестовый", "avatar": "🦊", "grade": "3", "csrf_token": token},
        )
        topic = TOPICS[0]
        response = self.client.get(f"/play/{topic['slug']}")
        self.assertEqual(response.status_code, 302)

        response = self.client.get(f"/play/{topic['slug']}/task")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("answer-form", html)

        headers = {"X-CSRFToken": token}
        response = self.client.post("/api/hint", json={}, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["hint"])

    def test_parent_gate(self):
        response = self.client.get("/parent")
        self.assertEqual(response.status_code, 200)
        response = self.client.post("/parent/unlock", data={"pin": "0000", "csrf_token": self._csrf("/parent")})
        self.assertEqual(response.status_code, 302)

    def test_404_page(self):
        response = self.client.get("/no-such-page")
        self.assertEqual(response.status_code, 404)

    def test_explain_pages(self):
        token = self._csrf("/")
        self.client.post(
            "/learners",
            data={"name": "Тестовый", "avatar": "🦊", "grade": "3", "csrf_token": token},
        )
        for topic in TOPICS:
            for method in topic["methods"]:
                response = self.client.get(f"/topic/{topic['slug']}/explain/{method['slug']}")
                self.assertEqual(response.status_code, 200, f"{topic['slug']}/{method['slug']}")
                html = response.get_data(as_text=True)
                self.assertNotIn("{", html.split("data-widget")[0][-200:], "Незаполненный плейсхолдер")

    def test_full_round_gives_stars_and_xp(self):
        """Полный раунд: 8 заданий, правильные ответы, звёзды и опыт."""
        import json

        from database import query_one

        token = self._csrf("/")
        self.client.post(
            "/learners",
            data={"name": "Тестовый", "avatar": "🦊", "grade": "3", "csrf_token": token},
        )
        topic = TOPICS[0]
        self.client.get(f"/play/{topic['slug']}")
        headers = {"X-CSRFToken": token}

        for _ in range(20):
            self.client.get(f"/play/{topic['slug']}/task")
            row = query_one("SELECT round_state FROM play_sessions ORDER BY id DESC LIMIT 1")
            state = json.loads(row["round_state"])
            if state.get("index", 0) >= state.get("total", 0):
                break
            answer = state["items"][state["index"]]["task"]["answer"]
            response = self.client.post("/api/answer", json={"answer": answer}, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.get_json()["correct"])

        response = self.client.get(f"/play/{topic['slug']}/result")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Разбор заданий", html)

        learner = query_one("SELECT xp, coins FROM learners ORDER BY id DESC LIMIT 1")
        self.assertGreater(learner["xp"], 0)
        self.assertGreater(learner["coins"], 0)

        progress = query_one(
            "SELECT stars FROM topic_progress WHERE topic_slug = ? ORDER BY updated_at DESC LIMIT 1",
            (topic["slug"],),
        )
        self.assertEqual(progress["stars"], 3)

    def test_wrong_answer_allows_retry(self):
        token = self._csrf("/")
        self.client.post(
            "/learners",
            data={"name": "Тестовый", "avatar": "🦊", "grade": "3", "csrf_token": token},
        )
        topic = TOPICS[0]
        self.client.get(f"/play/{topic['slug']}")
        self.client.get(f"/play/{topic['slug']}/task")
        headers = {"X-CSRFToken": token}
        data = self.client.post("/api/answer", json={"answer": "-999"}, headers=headers).get_json()
        self.assertFalse(data["correct"])
        self.assertTrue(data["retry"])
        self.assertTrue(data["hint"])
        data = self.client.post("/api/answer", json={"answer": "-998"}, headers=headers).get_json()
        self.assertFalse(data["retry"])

    def test_switch_method(self):
        token = self._csrf("/")
        self.client.post(
            "/learners",
            data={"name": "Тестовый", "avatar": "🦊", "grade": "3", "csrf_token": token},
        )
        topic = TOPICS[0]
        self.client.get(f"/play/{topic['slug']}")
        self.client.get(f"/play/{topic['slug']}/task")
        data = self.client.post(
            "/api/switch-method", json={}, headers={"X-CSRFToken": token}
        ).get_json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["name"])


class TestLibraryAndTheme(unittest.TestCase):
    """Библиотека, рекомендации учителя и выбор темы оформления."""

    def setUp(self):
        from app import create_app

        self.app = create_app("testing")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.suffix = str(int(time.time() * 1000))[-8:]

    def _csrf(self, path="/"):
        html = self.client.get(path).get_data(as_text=True)
        marker = 'name="csrf-token" content="'
        idx = html.find(marker)
        self.assertGreater(idx, -1, "CSRF-токен не найден")
        start = idx + len(marker)
        return html[start:html.find('"', start)]

    def _login(self, login: str, password: str = "math2025"):
        token = self._csrf("/login")
        return self.client.post(
            "/login",
            data={"csrf_token": token, "login": login, "password": password},
            follow_redirects=True,
        )

    def _make_user(self, login: str, role: str, password: str = "math2025"):
        from services import auth as auth_service

        auth_service.create_user(login, password, role, first_name=login)
        return auth_service.get_user_by_login(login)

    # --------------------------------------------------- защита от BuildError
    def test_base_page_survives_missing_endpoint(self):
        """Старый процесс без нового маршрута не должен ронять все страницы."""
        original = self.app.jinja_env.globals.get("safe_url")
        self.app.jinja_env.globals["safe_url"] = lambda endpoint, fallback="/": ""
        try:
            response = self.client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("Моя библиотека", response.get_data(as_text=True))
        finally:
            if original is not None:
                self.app.jinja_env.globals["safe_url"] = original

    def test_safe_url_returns_path_or_empty(self):
        with self.app.app_context():
            from flask import current_app

            safe_url = current_app.jinja_env.globals["safe_url"]
            self.assertTrue(safe_url("library.library"))
            self.assertEqual(safe_url("no.such.endpoint", ""), "")

    # ------------------------------------------------------------- темы
    def test_teacher_and_admin_use_adult_theme(self):
        for login, role in (
            (f"th_{self.suffix}", "teacher"),
            (f"ad_{self.suffix}", "admin"),
        ):
            self._make_user(login, role)
            self._login(login)
            html = self.client.get("/").get_data(as_text=True)
            self.assertIn('class="theme-adult"', html, login)
            self.client.get("/logout")

    def test_young_learner_keeps_playful_theme(self):
        from services import learners as learners_service

        learner_id = learners_service.create_learner("Малыш", "🦊", 3)
        with self.client.session_transaction() as sess:
            sess["learner_id"] = learner_id
        html = self.client.get("/map").get_data(as_text=True)
        self.assertIn('class="theme-playful"', html)

    def test_older_learner_gets_strict_theme(self):
        from services import learners as learners_service

        learner_id = learners_service.create_learner("Старшеклассник", "🦊", 6)
        with self.client.session_transaction() as sess:
            sess["learner_id"] = learner_id
        html = self.client.get("/map").get_data(as_text=True)
        self.assertIn('class="theme-strict"', html)

    # --------------------------------------------------------- библиотека
    def _make_school_class(self, teacher_id, grade=3, letter=""):
        """Город → школа → класс с учителем."""
        from services import orgs

        city_id = orgs.create_city(f"Город {self.suffix}-{letter or 'X'}")
        school_id = orgs.create_school(city_id, f"Школа {self.suffix}-{letter or 'X'}")
        class_id = orgs.create_class(school_id, grade, letter, teacher_id=teacher_id)
        return school_id, class_id

    @staticmethod
    def _upload_pdf():
        import io

        return io.BytesIO(
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
            b"trailer\n<<>>\n%%EOF\n"
        )

    def test_teacher_uploads_book_and_grants_class_access(self):
        """Учитель загружает книгу и открывает доступ своему классу."""
        from database import query_one
        from services import library as library_service, orgs

        teacher = self._make_user(f"th_{self.suffix}", "teacher")
        school_id, class_id = self._make_school_class(teacher["id"], 3, "А")
        subject = query_one("SELECT id FROM subjects ORDER BY id LIMIT 1")
        title = f"Книга библиотеки {self.suffix}"
        book = None
        try:
            self._login(teacher["login"])
            token = self._csrf("/library/")
            response = self.client.post(
                "/library/upload",
                data={
                    "csrf_token": token,
                    "title": title,
                    "subject_id": str(subject["id"]),
                    "grade": "3",
                    "class_ids": str(class_id),
                    "file": (self._upload_pdf(), "book.pdf"),
                },
                content_type="multipart/form-data",
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)
            book = query_one("SELECT * FROM library_books WHERE title = ?", (title,))
            self.assertIsNotNone(book, "книга не создана")
            self.assertEqual(library_service.book_class_ids(book["id"]), [class_id])
            html = response.get_data(as_text=True)
            self.assertIn("Кому доступна книга", html)
            self.assertIn(title, html)
        finally:
            if book:
                library_service.delete_book(book["id"])
            orgs.delete_school(school_id)
            from database import execute

            execute("DELETE FROM users WHERE login = ?", (teacher["login"],))

    def test_student_sees_only_books_of_own_class(self):
        """Книга видна только ученикам тех классов, которым открыт доступ."""
        from database import execute, query_one
        from services import library as library_service, orgs

        teacher = self._make_user(f"th_{self.suffix}", "teacher")
        student_a = self._make_user(f"sa_{self.suffix}", "student")
        student_b = self._make_user(f"sb_{self.suffix}", "student")
        school_a, class_a = self._make_school_class(teacher["id"], 3, "А")
        school_b, class_b = self._make_school_class(teacher["id"], 3, "Б")
        subject = query_one("SELECT id FROM subjects ORDER BY id LIMIT 1")
        title = f"Только для 3А {self.suffix}"
        textbook_id = execute(
            """INSERT INTO textbooks (subject_id, grade, title, filename, pages)
               VALUES (?, 3, ?, ?, 10)""",
            (subject["id"], title, f"scope_{self.suffix}.pdf"),
        )
        book_id = library_service.create_book(
            teacher["id"], textbook_id, subject["id"], 3, title, class_ids=[class_a]
        )
        try:
            orgs.add_student_to_class(class_a, student_a["id"])
            orgs.add_student_to_class(class_b, student_b["id"])
            titles_a = [b["title"] for b in library_service.list_books_for_student(student_a["id"])]
            titles_b = [b["title"] for b in library_service.list_books_for_student(student_b["id"])]
            self.assertIn(title, titles_a)
            self.assertNotIn(title, titles_b)
            self.assertTrue(library_service.can_access_book(student_a, book_id))
            self.assertFalse(library_service.can_access_book(student_b, book_id))

            self._login(student_a["login"])
            html = self.client.get("/library/").get_data(as_text=True)
            self.assertIn(title, html)
            self.client.get("/logout")
            self._login(student_b["login"])
            html_b = self.client.get("/library/").get_data(as_text=True)
            self.assertNotIn(title, html_b)
        finally:
            execute("DELETE FROM library_books WHERE id = ?", (book_id,))
            execute("DELETE FROM textbooks WHERE id = ?", (textbook_id,))
            orgs.delete_school(school_a)
            orgs.delete_school(school_b)
            execute(
                "DELETE FROM users WHERE login IN (?, ?, ?)",
                (teacher["login"], student_a["login"], student_b["login"]),
            )

    def test_topic_recommendation_reaches_class_and_can_be_marked_done(self):
        """Рекомендация темы классу видна ученикам; отметка — персональная."""
        from database import execute, query_one
        from services import library as library_service, orgs

        teacher = self._make_user(f"th_{self.suffix}", "teacher")
        student_a = self._make_user(f"sa_{self.suffix}", "student")
        student_b = self._make_user(f"sb_{self.suffix}", "student")
        school_a, class_a = self._make_school_class(teacher["id"], 3, "А")
        school_b, class_b = self._make_school_class(teacher["id"], 3, "Б")
        subject = query_one("SELECT id FROM subjects ORDER BY id LIMIT 1")
        title = f"Книга с темой {self.suffix}"
        textbook_id = execute(
            """INSERT INTO textbooks (subject_id, grade, title, filename, pages)
               VALUES (?, 3, ?, ?, 10)""",
            (subject["id"], title, f"rec_{self.suffix}.pdf"),
        )
        topic_slug = f"test-topic-{self.suffix}"
        execute(
            """INSERT INTO topics (slug, title, grade, subject_id, source, kind, page_start, page_end)
               VALUES (?, 'Глава 1. Осень', 3, ?, 'pdf', 'reading', 5, 9)""",
            (topic_slug, subject["id"]),
        )
        execute(
            "INSERT INTO textbook_topics (textbook_id, topic_slug, page, page_end) VALUES (?, ?, 5, 9)",
            (textbook_id, topic_slug),
        )
        book_id = library_service.create_book(
            teacher["id"], textbook_id, subject["id"], 3, title, class_ids=[class_a]
        )
        try:
            orgs.add_student_to_class(class_a, student_a["id"])
            orgs.add_student_to_class(class_b, student_b["id"])
            result = library_service.recommend(
                teacher["id"], book_id, topic_slug=topic_slug,
                class_ids=[class_a], note="Прочитать к пятнице",
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["created"], 1)

            recs_a = library_service.recommendations_for_student(student_a["id"])
            self.assertEqual(len(recs_a), 1)
            self.assertEqual(recs_a[0]["topic_title"], "Глава 1. Осень")
            self.assertEqual(recs_a[0]["page"], 5)
            self.assertFalse(recs_a[0]["done"])
            self.assertEqual(library_service.recommendations_for_student(student_b["id"]), [])

            # повторная рекомендация не создаёт дубль
            again = library_service.recommend(
                teacher["id"], book_id, topic_slug=topic_slug, class_ids=[class_a]
            )
            self.assertEqual(again["created"], 0)
            self.assertEqual(again["skipped"], 1)

            self.assertTrue(
                library_service.mark_recommendation_done(recs_a[0]["id"], student_a["id"])
            )
            done_recs = library_service.recommendations_for_student(student_a["id"])
            self.assertTrue(done_recs[0]["done"])
            # чужой ученик не может отметить чужую рекомендацию
            self.assertFalse(
                library_service.mark_recommendation_done(recs_a[0]["id"], student_b["id"])
            )

            # ученик видит рекомендацию на странице библиотеки
            self._login(student_a["login"])
            html = self.client.get("/library/").get_data(as_text=True)
            self.assertIn("Глава 1. Осень", html)
            self.assertIn("Прочитать к пятнице", html)
        finally:
            execute("DELETE FROM library_books WHERE id = ?", (book_id,))
            execute("DELETE FROM textbook_topics WHERE topic_slug = ?", (topic_slug,))
            execute("DELETE FROM topics WHERE slug = ?", (topic_slug,))
            execute("DELETE FROM textbooks WHERE id = ?", (textbook_id,))
            orgs.delete_school(school_a)
            orgs.delete_school(school_b)
            execute(
                "DELETE FROM users WHERE login IN (?, ?, ?)",
                (teacher["login"], student_a["login"], student_b["login"]),
            )

    def test_upload_without_file_reports_error(self):
        """Загрузка без файла не должна падать."""
        from database import execute

        teacher = self._make_user(f"th_{self.suffix}", "teacher")
        try:
            self._login(teacher["login"])
            token = self._csrf("/library/")
            response = self.client.post(
                "/library/upload",
                data={"csrf_token": token, "title": "Без файла", "subject_id": "1", "grade": "3"},
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("Выберите файл книги", response.get_data(as_text=True))
        finally:
            execute("DELETE FROM users WHERE login = ?", (teacher["login"],))

    def test_global_library_is_gone(self):
        """Онлайн-каталог и личные полки больше не существуют."""
        from database import query_all
        from services import library as library_service

        self.assertFalse(hasattr(library_service, "search_online_books"))
        self.assertFalse(hasattr(library_service, "search_catalog"))
        tables = {
            row["name"]
            for row in query_all("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        for gone in ("user_books", "book_recommendations", "library_covers"):
            self.assertNotIn(gone, tables)


class TestAi(unittest.TestCase):
    """Облачный ИИ: скрыт без настройки, включается администратором."""

    def setUp(self):
        from app import create_app

        self.app = create_app("testing")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.slug = TOPICS[0]["slug"]
        self.suffix = str(int(time.time() * 1000))[-8:]
        self.admin_login = None
        self._reset_ai()

    def tearDown(self):
        from database import execute

        self._reset_ai()
        execute("DELETE FROM ai_explanations WHERE topic_slug = ?", (self.slug,))
        if self.admin_login:
            try:
                execute("DELETE FROM users WHERE login = ?", (self.admin_login,))
            except Exception:  # pragma: no cover - журнал может ссылаться на пользователя
                pass

    # ------------------------------------------------------------ помощники
    def _make_admin(self, password="math2025"):
        from services import auth as auth_service

        self.admin_login = f"ad_{self.suffix}"
        auth_service.create_user(
            self.admin_login, password, auth_service.ROLE_ADMIN, first_name="Админ"
        )
        return self.admin_login

    def _reset_ai(self):
        from services import ai as ai_service

        ai_service.save_settings(
            {
                "enabled": False,
                "provider": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": "",
                "model": "openai/gpt-4o-mini",
                "temperature": 0.3,
                "max_tokens": 900,
                "system_note": "",
            }
        )

    def _enable_ai(self, model="test/model", key="test-key"):
        from services import ai as ai_service

        ai_service.save_settings(
            {
                "enabled": True,
                "provider": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": key,
                "model": model,
                "temperature": 0.3,
                "max_tokens": 700,
                "system_note": "",
            }
        )
        return ai_service

    def _csrf(self, path="/"):
        html = self.client.get(path).get_data(as_text=True)
        marker = 'name="csrf-token" content="'
        idx = html.find(marker)
        self.assertGreater(idx, -1, "CSRF-токен не найден")
        start = idx + len(marker)
        return html[start:html.find('"', start)]

    def _login(self, login, password="math2025"):
        token = self._csrf("/login")
        return self.client.post(
            "/login",
            data={"csrf_token": token, "login": login, "password": password},
            follow_redirects=True,
        )

    def _new_learner(self, grade=3):
        from services import learners as learners_service

        learner_id = learners_service.create_learner("Ай Ти", "🦊", grade)
        with self.client.session_transaction() as sess:
            sess["learner_id"] = learner_id
        return learner_id

    # ----------------------------------------------------------------- тесты
    def test_ai_is_off_by_default(self):
        """По умолчанию функций ИИ нет: маршруты 404, JS не подключается."""
        from services import ai as ai_service

        self.assertFalse(ai_service.is_enabled())
        self.assertEqual(self.client.get("/ai/assistant").status_code, 404)
        self.assertEqual(self.client.get(f"/ai/explain/{self.slug}").status_code, 404)
        ask = self.client.post(
            "/ai/assistant/ask",
            json={"question": "привет"},
            headers={"X-CSRFToken": self._csrf("/")},
        )
        self.assertEqual(ask.status_code, 404)
        html = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("ai_assistant.js", html)

        self._new_learner()
        html = self.client.get(f"/topic/{self.slug}").get_data(as_text=True)
        self.assertNotIn("Объяснить с ИИ", html)
        self.assertNotIn("ai_assistant.js", html)

    def test_ai_hidden_for_anonymous_visitor(self):
        """Даже включённый ИИ не виден анонимному посетителю без профиля."""
        ai_service = self._enable_ai()
        try:
            self.assertTrue(ai_service.is_enabled())
            html = self.client.get("/").get_data(as_text=True)
            self.assertNotIn("ai_assistant.js", html)
            self.assertEqual(self.client.get("/ai/assistant").status_code, 404)
        finally:
            self._reset_ai()

    def test_admin_can_enable_ai(self):
        """Администратор включает модель — помощник и виджет появляются."""
        self._make_admin()
        self._login(self.admin_login)
        page = self.client.get("/admin/ai")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Искусственный интеллект", page.get_data(as_text=True))
        self.assertIn("/admin/ai", self.client.get("/admin/").get_data(as_text=True))

        token = self._csrf("/admin/ai")
        response = self.client.post(
            "/admin/ai",
            data={
                "csrf_token": token,
                "action": "save",
                "enabled": "1",
                "provider": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": "secret-key-1",
                "model": "openai/gpt-4o-mini",
                "temperature": "0.4",
                "max_tokens": "800",
                "system_note": "",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        from services import ai as ai_service

        self.assertTrue(ai_service.is_enabled())
        status = ai_service.status()
        self.assertEqual(status["provider"], "openrouter")
        self.assertTrue(status["has_key"])

        html = self.client.get("/").get_data(as_text=True)
        self.assertIn("ai_assistant.js", html)
        self.assertEqual(self.client.get("/ai/assistant").status_code, 200)

    def test_enabled_without_key_is_not_ready(self):
        """Включено, но без ключа — приложение остаётся без ИИ."""
        self._enable_ai(key="")
        from services import ai as ai_service

        self.assertFalse(ai_service.is_enabled())
        self.assertEqual(self.client.get("/ai/assistant").status_code, 404)

    def test_admin_key_is_kept_when_field_is_empty(self):
        """Пустое поле ключа не стирает сохранённый ключ."""
        from services import ai as ai_service

        self._enable_ai(key="keep-me")
        self._make_admin()
        self._login(self.admin_login)
        page_token = self._csrf("/admin/ai")
        self.client.post(
            "/admin/ai",
            data={
                "csrf_token": page_token,
                "action": "save",
                "enabled": "1",
                "provider": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "api_key": "",
                "model": "openai/gpt-4o-mini",
                "temperature": "0.3",
                "max_tokens": "800",
            },
            follow_redirects=True,
        )
        self.assertEqual(ai_service.get_settings()["api_key"], "keep-me")

    def test_topic_explanation_is_cached(self):
        """Объяснение темы генерируется один раз и берётся из кэша."""
        ai_service = self._enable_ai()
        calls = {"n": 0}
        original = ai_service.chat

        def fake_chat(messages, **kwargs):
            calls["n"] += 1
            return "## Разбор\n- первый шаг\n**важно**", None

        ai_service.chat = fake_chat
        try:
            self._new_learner()
            first = self.client.get(f"/ai/explain/{self.slug}")
            self.assertEqual(first.status_code, 200)
            body = first.get_data(as_text=True)
            self.assertIn("Разбор", body)
            self.assertIn("<strong>важно</strong>", body)
            self.assertEqual(calls["n"], 1)

            self.client.get(f"/ai/explain/{self.slug}")
            self.assertEqual(calls["n"], 1, "кэш не использовался")
            self.assertIsNotNone(ai_service.cached_explanation(self.slug))

            token = self._csrf(f"/ai/explain/{self.slug}")
            self.client.post(
                f"/ai/explain/{self.slug}/refresh",
                data={"csrf_token": token},
                follow_redirects=True,
            )
            self.assertEqual(calls["n"], 2, "обновление не обратилось к модели")
        finally:
            ai_service.chat = original
            self._reset_ai()

    def test_assistant_json_and_form(self):
        """Помощник отвечает и на странице, и через JSON-виджет."""
        ai_service = self._enable_ai()
        original = ai_service.chat
        ai_service.chat = lambda messages, **kwargs: ("Просто открой карту тем.", None)
        try:
            self._new_learner()
            token = self._csrf("/ai/assistant")
            response = self.client.post(
                "/ai/assistant",
                data={"csrf_token": token, "question": "Как пройти тест?"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("Просто открой карту тем", response.get_data(as_text=True))

            response = self.client.post(
                "/ai/assistant/ask",
                json={"question": "Как пройти тест?"},
                headers={"X-CSRFToken": self._csrf("/ai/assistant")},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload["ok"])
            self.assertIn("карту тем", payload["answer"])
            self.assertIn("<p>", payload["html"])

            empty = self.client.post(
                "/ai/assistant/ask",
                json={"question": "  "},
                headers={"X-CSRFToken": self._csrf("/ai/assistant")},
            )
            self.assertEqual(empty.status_code, 400)
        finally:
            ai_service.chat = original
            self._reset_ai()

    def test_chat_error_is_reported_not_raised(self):
        """Ошибка запроса к модели возвращается строкой, а не падением.

        Заодно проверяется, что заголовки OpenRouter собираются без
        нелатинских символов (иначе urllib бросает UnicodeEncodeError).
        """
        from services import ai as ai_service

        ai_service.save_settings(
            {
                "enabled": True,
                "provider": "openrouter",
                "base_url": "http://127.0.0.1:9/v1",  # закрытый порт — быстрый отказ
                "api_key": "test-key",
                "model": "test/model",
                "temperature": 0.3,
                "max_tokens": 100,
            }
        )
        text, error = ai_service.chat(
            [{"role": "user", "content": "Привет, объясни тему"}], timeout=5
        )
        self.assertEqual(text, "")
        self.assertTrue(error)
        self.assertIn(error.split(":")[0], error)
        self._reset_ai()

    def test_render_ai_text_escapes_html(self):
        from services.ai import render_ai_text

        html = render_ai_text('## Заголовок\n<script>alert("x")</script>\n- **жирный**\n- пункт')
        self.assertIn("<h3>Заголовок</h3>", html)
        self.assertIn("<strong>жирный</strong>", html)
        self.assertIn("<ul>", html)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_ai_tables_exist(self):
        from database import query_all

        tables = {
            row["name"]
            for row in query_all("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        for name in ("ai_settings", "ai_explanations", "ai_requests"):
            self.assertIn(name, tables)


class TestApiV1(unittest.TestCase):
    """JSON API для Android: вход, семейные профили, раунды, работы."""

    def setUp(self):
        from app import create_app
        from services import auth as auth_service

        self.app = create_app("testing")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.auth = auth_service
        self.suffix = str(int(time.time() * 1000))[-7:]
        self.device = f"dev-{self.suffix}"

    # ------------------------------------------------------------- helpers
    def _user(self, prefix: str, role: str, password: str = "api-pass-123"):
        login = f"{prefix}_{self.suffix}"
        self.auth.create_user(login, password, role, first_name=login)
        return login, password

    def _login(self, login: str, password: str) -> str:
        response = self.client.post(
            "/api/v1/auth/login", json={"login": login, "password": password}
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()["token"]

    def _headers(self, token: str | None = None, device: str | None = None) -> dict:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if device:
            headers["X-Device-Id"] = device
        return headers

    def _family(self, name: str = "Ребёнок", pin: str | None = None) -> dict:
        payload = {"name": f"{name}-{self.suffix}", "grade": 3}
        if pin:
            payload["pin"] = pin
        response = self.client.post(
            "/api/v1/learners",
            headers=self._headers(device=self.device),
            json=payload,
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()

    # --------------------------------------------------------------- tests
    def test_health_and_meta_are_public(self):
        health = self.client.get("/api/v1/health")
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.get_json()["db"])

        meta = self.client.get("/api/v1/meta")
        self.assertEqual(meta.status_code, 200)
        body = meta.get_json()
        self.assertTrue(body["ok"])
        self.assertIn("subjects", body)
        self.assertEqual(body["grades"], list(range(1, 12)))
        self.assertIn("enabled", body["ai"])

    def test_admin_ai_test_endpoint_reports_disabled_model(self):
        login, password = self._user("api_admin_ai", "admin")
        token = self._login(login, password)
        response = self.client.post(
            "/api/v1/admin/ai/test", headers=self._headers(token)
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertFalse(body["ok"])
        self.assertTrue(body["message"])

    def test_topics_catalog_requires_login_and_returns_metadata(self):
        self.assertEqual(self.client.get("/api/v1/topics").status_code, 401)

        login, password = self._user("api_catalog", "teacher")
        token = self._login(login, password)
        response = self.client.get(
            "/api/v1/topics?grade=3", headers=self._headers(token)
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["topics"])
        self.assertTrue(body["subjects"])
        first = body["topics"][0]
        self.assertTrue(first["slug"])
        self.assertEqual(first["grade"], 3)
        self.assertNotIn("content_json", first)

    def test_topic_text_includes_book_links_for_reader(self):
        from database import query_one

        row = query_one(
            "SELECT slug FROM topics WHERE grade = 3 ORDER BY slug LIMIT 1"
        )
        if row is None:
            self.skipTest("в тестовой базе нет тем для 3 класса")

        token = self._family()["token"]
        response = self.client.get(
            f"/api/v1/topics/{row['slug']}/text", headers=self._headers(token)
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertIn("books", body["topic"])
        self.assertIsInstance(body["pages"], list)

    def test_family_library_is_readable_without_account(self):
        family = self._family("Библиотека")
        response = self.client.get(
            "/api/v1/library", headers=self._headers(family["token"])
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertIsInstance(body["books"], list)
        self.assertEqual(body["stats"]["books"], len(body["books"]))
        for book in body["books"]:
            self.assertEqual(book["grade"], 3)
            self.assertGreater(book["textbook_id"], 0)

    def test_login_me_logout(self):
        login, password = self._user("api_teacher", "teacher")
        token = self._login(login, password)
        me = self.client.get("/api/v1/auth/me", headers=self._headers(token))
        self.assertEqual(me.status_code, 200)
        body = me.get_json()
        self.assertEqual(body["user"]["role"], "teacher")
        self.assertEqual(body["theme"], "adult")
        self.assertIsInstance(body["user"]["is_active"], bool)
        self.assertTrue(body["user"]["is_active"])

        self.assertEqual(
            self.client.post(
                "/api/v1/auth/logout", headers=self._headers(token)
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/auth/me", headers=self._headers(token)
            ).status_code,
            401,
        )

    def test_login_returns_boolean_user_flags(self):
        login, password = self._user("api_flags", "teacher")
        response = self.client.post(
            "/api/v1/auth/login", json={"login": login, "password": password}
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        user = response.get_json()["user"]
        self.assertIsInstance(user["is_active"], bool)
        self.assertTrue(user["is_active"])

    def test_family_profiles_are_device_scoped_and_pin_protected(self):
        created = self._family("Семейный", pin="4321")
        learner_id = created["learner"]["id"]
        self.assertTrue(created["token"])
        self.assertTrue(created["learner"]["has_pin"])

        listed = self.client.get(
            "/api/v1/learners", headers={"X-Device-Id": self.device}
        ).get_json()
        self.assertEqual([item["id"] for item in listed["learners"]], [learner_id])

        foreign = self.client.get(
            "/api/v1/learners", headers={"X-Device-Id": "other-device"}
        ).get_json()
        self.assertEqual(foreign["learners"], [])

        no_pin = self.client.post(
            f"/api/v1/learners/{learner_id}/login",
            headers={"X-Device-Id": self.device},
            json={},
        )
        self.assertEqual(no_pin.status_code, 401)

        bad_pin = self.client.post(
            f"/api/v1/learners/{learner_id}/login",
            headers={"X-Device-Id": self.device},
            json={"pin": "0000"},
        )
        self.assertEqual(bad_pin.status_code, 403)

        ok_pin = self.client.post(
            f"/api/v1/learners/{learner_id}/login",
            headers={"X-Device-Id": self.device},
            json={"pin": "4321"},
        )
        self.assertEqual(ok_pin.status_code, 200)
        self.assertTrue(ok_pin.get_json()["token"])

        foreign_login = self.client.post(
            f"/api/v1/learners/{learner_id}/login",
            headers={"X-Device-Id": "other-device"},
            json={"pin": "4321"},
        )
        self.assertEqual(foreign_login.status_code, 404)

    def test_play_round_hides_answers_and_completes(self):
        import json as jsonlib

        from database import query_one

        token = self._family()["token"]
        headers = self._headers(token)

        map_body = self.client.get("/api/v1/map", headers=headers).get_json()
        self.assertTrue(map_body["topics"])
        slug = map_body["topics"][0]["slug"]

        detail = self.client.get(f"/api/v1/topics/{slug}", headers=headers)
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.get_json()["can_play"])

        start = self.client.post(
            "/api/v1/play/start", headers=headers, json={"topic_slug": slug}
        )
        self.assertEqual(start.status_code, 200, start.get_data(as_text=True))
        body = start.get_json()
        round_id = body["round_id"]
        self.assertTrue(body["task"]["question"])
        self.assertNotIn("answer", body["task"])
        widget = body["task"]["widget"]
        self.assertTrue(widget is None or isinstance(widget, dict))

        correct = 0
        for _ in range(14):
            current = self.client.get(
                f"/api/v1/play/{round_id}", headers=headers
            ).get_json()
            if current["done"]:
                break
            row = query_one(
                "SELECT round_state FROM play_sessions WHERE id = ?", (round_id,)
            )
            state = jsonlib.loads(row["round_state"])
            index = state["index"]
            answer = state["items"][index]["task"]["answer"]
            response = self.client.post(
                f"/api/v1/play/{round_id}/answer",
                headers=headers,
                json={"answer": str(answer)},
            )
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            payload = response.get_json()
            self.assertTrue(payload["correct"])
            correct += 1

        result = self.client.get(
            f"/api/v1/play/{round_id}/result", headers=headers
        )
        self.assertEqual(result.status_code, 200)
        result_body = result.get_json()
        self.assertEqual(result_body["correct"], correct)
        self.assertGreaterEqual(result_body["stars"], 1)
        for item in result_body["items"]:
            self.assertIn("answer", item)
            self.assertIn("correct", item)

        again = self.client.get(
            f"/api/v1/play/{round_id}/result", headers=headers
        ).get_json()
        self.assertEqual(again["stars"], result_body["stars"])

    def test_play_widget_serializes_as_object(self):
        """Android ждёт widget объектом; строка или число ломают запуск теста."""
        token = self._family("Виджет")["token"]
        start = self.client.post(
            "/api/v1/play/start",
            headers=self._headers(token),
            json={"topic_slug": "numbers_1000", "method": "compare_by_place"},
        )
        self.assertEqual(start.status_code, 200, start.get_data(as_text=True))
        widget = start.get_json()["task"]["widget"]
        self.assertIsInstance(widget, dict)
        self.assertTrue(widget.get("type"))

    def test_teacher_assignment_and_student_submission(self):
        from content.curriculum import TOPICS
        from services import orgs

        teacher_login, teacher_password = self._user("api_t2", "teacher")
        student_login, student_password = self._user("api_s2", "student")
        teacher = self.auth.get_user_by_login(teacher_login)
        student = self.auth.get_user_by_login(student_login)

        city_id = orgs.create_city(f"Город {self.suffix}")
        school_id = orgs.create_school(city_id, f"Школа {self.suffix}")
        class_id = orgs.create_class(school_id, 3, "А", teacher_id=teacher["id"])
        orgs.add_student_to_class(class_id, student["id"])

        teacher_token = self._login(teacher_login, teacher_password)
        student_token = self._login(student_login, student_password)
        topic_slug = TOPICS[0]["slug"]

        created = self.client.post(
            "/api/v1/teacher/assignments",
            headers=self._headers(teacher_token),
            json={
                "title": f"Работа {self.suffix}",
                "class_id": class_id,
                "topic_slugs": [topic_slug],
                "questions_count": 3,
            },
        )
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        assignment_id = created.get_json()["assignment"]["id"]

        listing = self.client.get(
            "/api/v1/assignments", headers=self._headers(student_token)
        ).get_json()
        self.assertIn(assignment_id, [item["id"] for item in listing["assignments"]])

        detail = self.client.get(
            f"/api/v1/assignments/{assignment_id}",
            headers=self._headers(student_token),
        ).get_json()
        self.assertFalse(detail["submitted"])
        self.assertEqual(len(detail["questions"]), 3)
        for question in detail["questions"]:
            self.assertNotIn("answer", question)

        answers = [
            (question["choices"][0] if question["choices"] else "0")
            for question in detail["questions"]
        ]
        submitted = self.client.post(
            f"/api/v1/assignments/{assignment_id}/submit",
            headers=self._headers(student_token),
            json={"answers": answers},
        )
        self.assertEqual(submitted.status_code, 200, submitted.get_data(as_text=True))
        self.assertIsNotNone(submitted.get_json()["result"])

        results = self.client.get(
            f"/api/v1/teacher/assignments/{assignment_id}/results",
            headers=self._headers(teacher_token),
        )
        self.assertEqual(results.status_code, 200)
        rows = results.get_json()["results"]
        self.assertTrue(any(row["result"] for row in rows))

    def test_roles_and_guest_access(self):
        token = self._family()["token"]
        self.assertEqual(self.client.get("/api/v1/map").status_code, 401)
        self.assertEqual(
            self.client.get(
                "/api/v1/admin/stats", headers=self._headers(token)
            ).status_code,
            401,
        )

        student_login, student_password = self._user("api_s3", "student")
        student_token = self._login(student_login, student_password)
        self.assertEqual(
            self.client.get(
                "/api/v1/teacher/dashboard", headers=self._headers(student_token)
            ).status_code,
            403,
        )

    def test_admin_stats_and_users(self):
        login, password = self._user("api_admin", "admin")
        token = self._login(login, password)
        headers = self._headers(token)

        stats = self.client.get("/api/v1/admin/stats", headers=headers)
        self.assertEqual(stats.status_code, 200)
        keys = stats.get_json()["stats"]
        for key in ("users", "classes", "topics", "textbooks", "attempts"):
            self.assertIn(key, keys)

        users = self.client.get("/api/v1/admin/users", headers=headers)
        self.assertEqual(users.status_code, 200)
        self.assertTrue(users.get_json()["users"])

        created = self.client.post(
            "/api/v1/admin/users",
            headers=headers,
            json={
                "login": f"api_new_{self.suffix}",
                "password": "new-pass-123",
                "role": "student",
                "first_name": "Новый",
            },
        )
        self.assertEqual(created.status_code, 201)
        self.assertNotIn("password_hash", created.get_json()["user"])

        orgs_body = self.client.get("/api/v1/admin/orgs", headers=headers).get_json()
        self.assertIn("cities", orgs_body)
        self.assertIn("subjects", orgs_body)

    def test_book_access_is_checked(self):
        admin_login, admin_password = self._user("api_admin2", "admin")
        student_login, student_password = self._user("api_s4", "student")
        admin_token = self._login(admin_login, admin_password)
        student_token = self._login(student_login, student_password)

        missing = self.client.get(
            "/api/v1/books/999999", headers=self._headers(admin_token)
        )
        self.assertEqual(missing.status_code, 404)

        forbidden = self.client.get(
            "/api/v1/books/999999", headers=self._headers(student_token)
        )
        self.assertEqual(forbidden.status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
