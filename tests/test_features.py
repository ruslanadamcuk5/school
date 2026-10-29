"""Тесты новых возможностей: уведомления, литература, фото-проверка, e-padruchnik.

Сеть и ИИ здесь всегда подменяются: тесты должны проходить без интернета и без
ключа модели. База — отдельный файл, как в остальных наборах.
"""
from __future__ import annotations

import io
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DB = os.path.join(tempfile.gettempdir(), "edu_math_features_test.db")
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_PATH"] = _TMP_DB
os.environ["SECRET_KEY"] = "features-test-secret"
os.environ["UPLOAD_DIR"] = os.path.join(tempfile.gettempdir(), "edu_math_features_upload")

from database import execute, init_db, query_one  # noqa: E402
from services import auth, library as library_service, notifications, orgs  # noqa: E402
from services import padruchnik, quiz_review, textbooks  # noqa: E402


class FeatureTestCase(unittest.TestCase):
    """Возвращает DATABASE_PATH других наборов после своих тестов."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._previous_db = os.environ.get("DATABASE_PATH")
        cls._previous_upload = os.environ.get("UPLOAD_DIR")
        super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._previous_db is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = cls._previous_db
        if cls._previous_upload is None:
            os.environ.pop("UPLOAD_DIR", None)
        else:
            os.environ["UPLOAD_DIR"] = cls._previous_upload
        super().tearDownClass()


def fresh_db() -> None:
    # Другие наборы тоже меняют DATABASE_PATH при импорте — возвращаем свой.
    os.environ["DATABASE_PATH"] = _TMP_DB
    os.environ["UPLOAD_DIR"] = os.path.join(
        tempfile.gettempdir(), "edu_math_features_upload"
    )
    for suffix in ("", "-wal", "-shm"):
        path = _TMP_DB + suffix
        if os.path.exists(path):
            os.remove(path)
    init_db()
    execute(
        "INSERT OR IGNORE INTO subjects (name, slug, icon) VALUES ('Математика','math','🔢')"
    )


def app_client():
    from app import create_app

    application = create_app("testing")
    application.config["TESTING"] = True
    return application, application.test_client()


def make_user(login: str, role: str, first: str = "", last: str = "") -> int:
    return auth.create_user(
        login, "pass12345", role, first or login, last or "Тестов"
    )


_class_counter = 0


def make_class(teacher_id: int, grade: int = 3):
    global _class_counter
    _class_counter += 1
    city_id = orgs.create_city(f"Город-{teacher_id}-{_class_counter}")
    school_id = orgs.create_school(city_id, f"Школа-{teacher_id}-{_class_counter}")
    return orgs.create_class(school_id, grade, "А", teacher_id=teacher_id)


def make_textbook(title: str = "Учебник", grade: int = 3) -> int:
    subject = query_one("SELECT id FROM subjects WHERE slug = 'math'")["id"]
    return textbooks.create_textbook(
        subject, grade, title, f"{title.replace(' ', '_')}.pdf", pages=10
    )


class TestNotificationCore(FeatureTestCase):
    def setUp(self):
        fresh_db()

    def test_dedup_key_prevents_repeats_but_allows_messages(self):
        user_id = make_user("dedup", auth.ROLE_STUDENT)
        notifications.push(
            user_id, notifications.KIND_NEW, "Новая работа", "Текст",
            assignment_id=1, dedup_key=notifications.dedup(notifications.KIND_NEW, user_id, 1),
        )
        notifications.push(
            user_id, notifications.KIND_NEW, "Новая работа", "Текст",
            assignment_id=1, dedup_key=notifications.dedup(notifications.KIND_NEW, user_id, 1),
        )
        self.assertEqual(
            query_one(
                "SELECT COUNT(*) AS n FROM app_notifications WHERE user_id = ?",
                (user_id,),
            )["n"],
            1,
        )
        # Произвольные сообщения без ключа не схлопываются.
        notifications.send_message(None, [user_id], "Первое")
        notifications.send_message(None, [user_id], "Второе")
        self.assertEqual(
            query_one(
                "SELECT COUNT(*) AS n FROM app_notifications WHERE kind = ?",
                (notifications.KIND_MESSAGE,),
            )["n"],
            2,
        )

    def test_notification_can_target_family_learner(self):
        learner_id = execute(
            "INSERT INTO learners (name, grade) VALUES ('Ваня', 3)"
        )
        notifications.push(
            0, notifications.KIND_MESSAGE, "Сообщение", "Для семьи",
            learner_id=learner_id,
        )
        self.assertEqual(
            notifications.unread_count_for_learner(learner_id), 1
        )
        row = notifications.list_for_learner(learner_id)[0]
        notifications.mark_read_for_learner(learner_id, int(row["id"]))
        self.assertEqual(
            notifications.unread_count_for_learner(learner_id), 0
        )

    def test_legacy_table_is_migrated_without_losing_rows(self):
        """Старая UNIQUE-таблица пересобирается, строки получают legacy-ключи."""
        from database import _migrate_notifications

        for suffix in ("", "-wal", "-shm"):
            path = _TMP_DB + suffix
            if os.path.exists(path):
                os.remove(path)
        conn = sqlite3.connect(_TMP_DB)
        conn.executescript(
            """
            CREATE TABLE app_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                assignment_id INTEGER NOT NULL DEFAULT 0,
                student_id INTEGER NOT NULL DEFAULT 0,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, kind, assignment_id, student_id)
            );
            INSERT INTO app_notifications (user_id, kind, title)
            VALUES (7, 'assignment_new', 'Старое');
            """
        )
        conn.commit()
        _migrate_notifications(conn)
        conn.commit()
        columns = [row[1] for row in conn.execute("PRAGMA table_info(app_notifications)")]
        self.assertTrue({"dedup_key", "learner_id", "read_at", "link"} <= set(columns))
        row = dict(zip(columns, conn.execute("SELECT * FROM app_notifications").fetchone()))
        self.assertEqual(row["title"], "Старое")
        self.assertTrue(str(row["dedup_key"]).startswith("legacy:"))
        conn.close()


class TestLibraryNotifications(FeatureTestCase):
    def setUp(self):
        fresh_db()
        self.teacher = make_user("teacher_lib", auth.ROLE_TEACHER, "Мария")
        self.student = make_user("student_lib", auth.ROLE_STUDENT, "Петя")
        self.parent = make_user("parent_lib", auth.ROLE_PARENT, "Ольга")
        self.class_id = make_class(self.teacher)
        orgs.add_student_to_class(self.class_id, self.student)
        execute(
            "INSERT INTO parent_children (parent_id, child_id, relation) VALUES (?, ?, 'мама')",
            (self.parent, self.student),
        )
        self.textbook_id = make_textbook("Математика 3")
        textbooks.link_topic(self.textbook_id, "addition", 3, 5)
        self.book = library_service.ensure_book_for_textbook(
            self.teacher, self.textbook_id, [self.class_id]
        )

    def test_recommendation_notifies_student_and_parent(self):
        result = library_service.recommend(
            self.teacher,
            int(self.book["id"]),
            topic_slug="addition",
            class_ids=[self.class_id],
            note="Прочитайте к пятнице",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["created"], 1)
        for user_id in (self.student, self.parent):
            row = query_one(
                """SELECT * FROM app_notifications
                    WHERE user_id = ? AND kind = ?""",
                (user_id, notifications.KIND_LIBRARY_NEW),
            )
            self.assertIsNotNone(row, f"нет уведомления для {user_id}")
            self.assertIn("Математика 3", row["body"])
            self.assertIn("Прочитайте к пятнице", row["body"])
            self.assertEqual(row["link"], "/library/")
        # Повторная рекомендация не создаёт дубль и не шлёт второй push.
        again = library_service.recommend(
            self.teacher,
            int(self.book["id"]),
            topic_slug="addition",
            class_ids=[self.class_id],
        )
        self.assertEqual(again["created"], 0)
        self.assertEqual(
            query_one(
                "SELECT COUNT(*) AS n FROM app_notifications WHERE kind = ?",
                (notifications.KIND_LIBRARY_NEW,),
            )["n"],
            2,
        )

    def test_unread_library_reminder_is_sent_once(self):
        library_service.recommend(
            self.teacher,
            int(self.book["id"]),
            topic_slug="addition",
            class_ids=[self.class_id],
        )
        rec = query_one("SELECT id FROM library_recommendations")["id"]
        execute(
            "UPDATE library_recommendations SET created_at = datetime('now', '-30 hours') WHERE id = ?",
            (rec,),
        )
        sent = library_service.sync_library_unread()
        self.assertGreaterEqual(sent, 2)
        self.assertEqual(
            query_one(
                "SELECT COUNT(*) AS n FROM app_notifications WHERE kind = ?",
                (notifications.KIND_LIBRARY_READ,),
            )["n"],
            2,
        )
        # Второй прогон ничего не добавляет.
        library_service.sync_library_unread()
        self.assertEqual(
            query_one(
                "SELECT COUNT(*) AS n FROM app_notifications WHERE kind = ?",
                (notifications.KIND_LIBRARY_READ,),
            )["n"],
            2,
        )

    def test_unread_hint_hides_done_recommendations(self):
        library_service.recommend(
            self.teacher, int(self.book["id"]), class_ids=[self.class_id]
        )
        rec = query_one("SELECT id FROM library_recommendations")["id"]
        self.assertEqual(len(library_service.unread_for_student(self.student)), 1)
        library_service.mark_recommendation_done(rec, self.student)
        self.assertEqual(library_service.unread_for_student(self.student), [])

    def test_adding_textbook_to_library_twice_keeps_one_book(self):
        before = query_one(
            "SELECT COUNT(*) AS n FROM library_books WHERE owner_id = ?",
            (self.teacher,),
        )["n"]
        second_class = make_class(self.teacher, grade=4)
        book = library_service.ensure_book_for_textbook(
            self.teacher, self.textbook_id, [second_class]
        )
        self.assertEqual(int(book["id"]), int(self.book["id"]))
        self.assertEqual(
            query_one(
                "SELECT COUNT(*) AS n FROM library_books WHERE owner_id = ?",
                (self.teacher,),
            )["n"],
            before,
        )
        self.assertIn(second_class, library_service.book_class_ids(int(book["id"])))
        self.assertIsNotNone(
            library_service.find_book_for_textbook(self.teacher, self.textbook_id)
        )


class TestQuizPhotoReview(FeatureTestCase):
    def setUp(self):
        fresh_db()
        self.learner_id = execute(
            "INSERT INTO learners (name, grade) VALUES ('Ваня', 3)"
        )

    def _write_photo(self) -> str:
        root = quiz_review.photos_root()
        os.makedirs(root, exist_ok=True)
        name = "photo-test.jpg"
        with open(os.path.join(root, name), "wb") as handle:
            handle.write(b"\xff\xd8\xff\xe0 test")
        return name

    def test_review_with_photos_uses_ai_and_saves_details(self):
        items = [
            {"question": "2 + 2", "answer": "4"},
            {"question": "3 + 1", "answer": "4"},
        ]
        photo = self._write_photo()
        fake = {
            "ok": True,
            "items": [
                {"index": 0, "correct": True, "comment": "Верно"},
                {"index": 1, "correct": False, "comment": "Проверьте сложение"},
            ],
            "summary": "Одна ошибка",
            "model": "test-model",
            "score_percent": 50,
        }
        with mock.patch.object(quiz_review.ai_service, "is_enabled", return_value=True), \
                mock.patch.object(quiz_review.ai_service, "review_submission", return_value=fake):
            review = quiz_review.review_with_photos(
                items, [photo], "Сложение", user_id=1
            )
        self.assertTrue(review["ok"])
        self.assertEqual(review["score"], 1)
        self.assertEqual(review["max_score"], 2)
        self.assertTrue(review["details"][0]["correct"])
        review_id = quiz_review.save_review(
            self.learner_id, "addition", "token", [photo], review
        )
        row = quiz_review.get_review(review_id)
        self.assertEqual(row["score"], 1)
        self.assertEqual(row["ai_model"], "test-model")
        self.assertIn("Проверьте сложение", row["details"])

    def test_ai_disabled_returns_explanation_not_exception(self):
        items = [{"question": "2 + 2", "answer": "4"}]
        photo = self._write_photo()
        with mock.patch.object(quiz_review.ai_service, "is_enabled", return_value=False):
            review = quiz_review.review_with_photos(items, [photo], "Сложение")
        self.assertFalse(review["ok"])
        self.assertEqual(review["ai_status"], "disabled")
        self.assertTrue(review["ai_feedback"])

    def test_missing_photo_is_reported(self):
        review = quiz_review.review_with_photos(
            [{"question": "2 + 2", "answer": "4"}], ["../../etc/passwd"], "Тема"
        )
        self.assertFalse(review["ok"])
        self.assertIn("Фото", review["error"])

    def test_absolute_path_cannot_escape_photos_root(self):
        self.assertIsNone(quiz_review.absolute_path("../../etc/passwd"))


class TestPadruchnikParsing(unittest.TestCase):
    """Сеть подменяется: проверяем разбор выдачи и импорт без PDF."""

    def test_search_skips_empty_filters(self):
        page = """
        <table><tr book-id="1217">
          <td>I (1-4кл.)</td><td>3</td><td>2026</td><td>Русский</td>
          <td colspan="2"><b>Математика (ч.1)</b><br>Муравьёва, Урбан</td>
        </tr></table>
        """
        captured = {}

        def fake_post(data, url=padruchnik.BASE_URL):
            captured.update(data)
            return page

        with mock.patch.dict(os.environ, {"PADRUCHNIK_MODE": "live"}):
            with mock.patch.object(padruchnik, "_post", side_effect=fake_post):
                result = padruchnik.search("Математика", grade=3)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["items"]), 1)
        item = result["items"][0]
        self.assertEqual(item["id"], 1217)
        self.assertEqual(item["grade"], 3)
        self.assertEqual(item["year"], "2026")
        self.assertIn("Математика", item["title"])
        self.assertNotIn("category", captured)
        self.assertNotIn("lang", captured)
        self.assertNotIn("year", captured)

    def test_book_reads_pdf_link_from_getbookurl(self):
        card = """
        <table><tr><th colspan="2">Математика (ч.1): учебное пособие</th></tr>
        <tr><th>Авторы книги</th><td>Муравьёва Г.Л.</td></tr>
        <tr><th>Год издания</th><td>2026</td></tr>
        <tr><th>Язык обучения</th><td>Русский</td></tr>
        <tr><th>Класс</th><td>3</td></tr>
        <tr><th>Уровень</th><td>I (1-4кл.)</td></tr></table>
        <div>Все права защищены.</div>
        """
        calls = []

        def fake_post(data, url=padruchnik.BASE_URL):
            calls.append((data, url))
            if url.endswith("getbookurl.php"):
                return "book-viewer\\web\\viewer.html?file=https://e-padruchnik.adu.by/books/m.pdf"
            return card

        with mock.patch.dict(os.environ, {"PADRUCHNIK_MODE": "live"}):
            with mock.patch.object(padruchnik, "_post", side_effect=fake_post):
                padruchnik._cache.clear()
                meta = padruchnik.book(1217)
        self.assertEqual(meta["title"], "Математика (ч.1): учебное пособие")
        self.assertEqual(meta["grade"], 3)
        self.assertEqual(
            meta["pdf_url"], "https://e-padruchnik.adu.by/books/m.pdf"
        )
        self.assertTrue(any(url.endswith("getbookurl.php") for _, url in calls))

    def test_catalog_search_works_without_network(self):
        def boom(*args, **kwargs):
            raise OSError("network down")

        with mock.patch.dict(os.environ, {"PADRUCHNIK_MODE": "auto"}):
            with mock.patch.object(padruchnik, "_post", side_effect=boom):
                result = padruchnik.search("Математика", grade=3)
        self.assertTrue(result["ok"])
        self.assertEqual(result["source"], "catalog")
        self.assertTrue(any(item["id"] == 1217 for item in result["items"]))
        self.assertTrue(all(item["pdf_url"] for item in result["items"]))

    def test_catalog_folds_belarusian_spelling(self):
        with mock.patch.dict(os.environ, {"PADRUCHNIK_MODE": "auto"}):
            result = padruchnik.search("Информатика", grade=8)
        self.assertTrue(result["ok"])
        self.assertTrue(
            any("нфармат" in item["title"].lower() for item in result["items"])
        )

    def test_catalog_book_has_pdf_link(self):
        with mock.patch.dict(os.environ, {"PADRUCHNIK_MODE": "auto"}):
            padruchnik._cache.clear()
            meta = padruchnik.book(1217)
        self.assertEqual(meta["grade"], 3)
        self.assertTrue(meta["pdf_url"].endswith(".pdf"))
        self.assertEqual(meta["source"], "catalog")

    def test_save_pdf_bytes_rejects_non_pdf(self):
        with self.assertRaises(ValueError):
            padruchnik.save_pdf_bytes(b"not a pdf", tempfile.gettempdir())

    def test_save_pdf_bytes_keeps_pdf(self):
        data = b"%PDF-1.4\n1 0 obj<</Type /Page>>endobj\n%%EOF"
        folder = tempfile.mkdtemp(prefix="padruchnik_")
        name, size = padruchnik.save_pdf_bytes(data, folder)
        self.assertTrue(name.endswith(".pdf"))
        self.assertEqual(size, len(data))
        self.assertTrue(os.path.exists(os.path.join(folder, name)))

    def test_download_rejects_foreign_domain(self):
        with self.assertRaises(ValueError):
            padruchnik.download_pdf(
                "https://evil.example/file.pdf", tempfile.gettempdir()
            )

    def test_import_book_reports_portal_error(self):
        with mock.patch.object(
            padruchnik, "book", return_value={"error": "Портал недоступен"}
        ):
            result = padruchnik.import_book(1, 1, 3)
        self.assertFalse(result["ok"])
        self.assertIn("Портал", result["error"])


class TestFeatureRoutes(FeatureTestCase):
    def setUp(self):
        fresh_db()
        self.application, self.client = app_client()
        self.teacher = make_user("teacher_route", auth.ROLE_TEACHER, "Мария")
        self.class_id = make_class(self.teacher)
        self.student = make_user("student_route", auth.ROLE_STUDENT, "Петя")
        orgs.add_student_to_class(self.class_id, self.student)

    def _login(self, login: str) -> None:
        self.token = self._csrf("/login")
        response = self.client.post(
            "/login",
            data={"login": login, "password": "pass12345", "csrf_token": self.token},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))

    def _csrf(self, path: str = "/login") -> str:
        html = self.client.get(path).get_data(as_text=True)
        marker = 'name="csrf-token" content="'
        index = html.find(marker)
        self.assertGreater(index, -1, "CSRF-токен не найден")
        start = index + len(marker)
        return html[start:html.find('"', start)]

    def test_notification_feed_requires_login(self):
        self.assertEqual(self.client.get("/notifications/feed").status_code, 401)

    def test_notification_feed_returns_items_and_marks_read(self):
        self._login("student_route")
        notifications.push(
            self.student,
            notifications.KIND_MESSAGE,
            "Сообщение от родителя",
            "Сделай уроки",
            link="/student/assignments",
        )
        feed = self.client.get("/notifications/feed").get_json()
        self.assertTrue(feed["ok"])
        self.assertEqual(feed["unread"], 1)
        item = feed["items"][0]
        self.assertEqual(item["icon"], "💬")
        response = self.client.post(
            "/notifications/feed/read",
            json={"id": item["id"]},
            headers={"X-CSRFToken": self.token},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["unread"], 0)

    def test_teacher_padruchnik_page_renders_search_results(self):
        self._login("teacher_route")
        fake = {
            "ok": True,
            "items": [
                {
                    "id": 1217,
                    "title": "Математика (ч.1)",
                    "author": "Муравьёва",
                    "grade": 3,
                    "year": "2026",
                    "level": "I",
                    "language": "Русский",
                }
            ],
            "page": 0,
            "has_next": False,
            "error": "",
        }
        with mock.patch.object(padruchnik, "search", return_value=fake):
            response = self.client.get("/teacher/padruchnik?q=Математика&grade=3")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Математика (ч.1)", html)
        self.assertIn("Добавить в пособия", html)

    def test_admin_padruchnik_page_is_admin_only(self):
        self._login("teacher_route")
        self.assertEqual(self.client.get("/admin/padruchnik").status_code, 403)

    def test_textbook_to_library_route_creates_book_for_classes(self):
        self._login("teacher_route")
        textbook_id = make_textbook("Пособие для класса")
        token = self.token
        response = self.client.post(
            f"/teacher/textbooks/{textbook_id}/library",
            data={"csrf_token": token, "class_id": [str(self.class_id)]},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        book = library_service.find_book_for_textbook(self.teacher, textbook_id)
        self.assertIsNotNone(book)
        self.assertEqual(library_service.book_class_ids(int(book["id"])), [self.class_id])

    def test_textbook_to_library_requires_class(self):
        self._login("teacher_route")
        textbook_id = make_textbook("Без класса")
        token = self.token
        response = self.client.post(
            f"/teacher/textbooks/{textbook_id}/library",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(
            library_service.find_book_for_textbook(self.teacher, textbook_id)
        )
        self.assertIn("Выберите хотя бы один класс", response.get_data(as_text=True))

    def test_padruchnik_api_rejects_anonymous(self):
        self.assertEqual(
            self.client.get("/api/v1/padruchnik/search?q=Математика").status_code,
            401,
        )

    def test_padruchnik_api_search_for_teacher(self):
        login = self.client.post(
            "/api/v1/auth/login",
            json={"login": "teacher_route", "password": "pass12345"},
        )
        self.assertEqual(login.status_code, 200, login.get_data(as_text=True))
        token = login.get_json()["token"]
        fake = {"ok": True, "items": [{"id": 1, "title": "Книга"}], "page": 0,
                "has_next": False, "error": ""}
        with mock.patch.object(padruchnik, "search", return_value=fake):
            response = self.client.get(
                "/api/v1/padruchnik/search?q=Математика&grade=3",
                headers={"Authorization": f"Bearer {token}"},
            )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["items"][0]["title"], "Книга")

    def test_padruchnik_upload_accepts_pdf(self):
        login = self.client.post(
            "/api/v1/auth/login",
            json={"login": "teacher_route", "password": "pass12345"},
        )
        self.assertEqual(login.status_code, 200, login.get_data(as_text=True))
        token = login.get_json()["token"]
        subject = query_one("SELECT id FROM subjects ORDER BY id LIMIT 1")
        pdf = b"%PDF-1.4\n1 0 obj<</Type /Page>>endobj\n%%EOF"
        response = self.client.post(
            "/api/v1/padruchnik/upload",
            data={
                "book_id": "1217",
                "subject_id": str(subject["id"]),
                "grade": "3",
                "class_ids": str(self.class_id),
                "file": (io.BytesIO(pdf), "book.pdf"),
            },
            content_type="multipart/form-data",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertGreater(body["textbook_id"], 0)

    def test_parent_can_message_child(self):
        parent = make_user("parent_route", auth.ROLE_PARENT, "Ольга")
        execute(
            "INSERT INTO parent_children (parent_id, child_id, relation) VALUES (?, ?, 'мама')",
            (parent, self.student),
        )
        self._login("parent_route")
        token = self.token
        response = self.client.post(
            "/parent/messages",
            data={
                "csrf_token": token,
                "action": "message",
                "child_id": [str(self.student)],
                "text": "Проверь задания",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        row = query_one(
            "SELECT * FROM app_notifications WHERE user_id = ? AND kind = ?",
            (self.student, notifications.KIND_MESSAGE),
        )
        self.assertIsNotNone(row)
        self.assertIn("Проверь задания", row["body"])
        self.assertEqual(row["sender_id"], parent)


if __name__ == "__main__":
    unittest.main()
