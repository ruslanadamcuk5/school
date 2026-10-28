"""Тесты безопасности: изоляция семей, PIN, права учителя, redirect, загрузки.

Эти сценарии раньше не покрывались и содержали реальные уязвимости:
* публичный список профилей детей;
* вход в чужой профиль без PIN;
* захват чужого класса при регистрации учителя;
* open redirect после входа.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.gettempdir(), "edu_math_test.db"))
os.environ.setdefault("SECRET_KEY", "test-secret")

from werkzeug.datastructures import FileStorage  # noqa: E402


class SecurityTestCase(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app("testing")
        self.app.config["TESTING"] = True

    def client_new(self):
        return self.app.test_client()

    def csrf(self, client, path="/"):
        html = client.get(path).get_data(as_text=True)
        marker = 'name="csrf-token" content="'
        index = html.find(marker)
        self.assertGreater(index, -1, f"CSRF-токен не найден на {path}")
        start = index + len(marker)
        return html[start:html.find('"', start)]

    def create_profile(self, client, name, pin=None, grade=3):
        token = self.csrf(client, "/")
        data = {"name": name, "avatar": "🦊", "grade": str(grade), "csrf_token": token}
        if pin:
            data["pin"] = pin
        response = client.post("/learners", data=data)
        self.assertEqual(response.status_code, 302, response.get_data(as_text=True))
        from database import query_one

        return query_one(
            "SELECT * FROM learners WHERE name = ? ORDER BY id DESC LIMIT 1", (name,)
        )


class TestFamilyIsolation(SecurityTestCase):
    def test_welcome_shows_only_own_family(self):
        name = f"Секрет-{uuid.uuid4().hex[:8]}"
        alice = self.client_new()
        learner = self.create_profile(alice, name)

        bob = self.client_new()
        html = bob.get("/").get_data(as_text=True)
        self.assertNotIn(name, html, "Профиль чужой семьи виден анонимному посетителю")

        response = bob.post(f"/learners/{learner['id']}/login", data={"csrf_token": self.csrf(bob, "/")})
        self.assertEqual(response.status_code, 404, "Чужой профиль можно открыть напрямую")

    def test_family_page_hides_other_families(self):
        name = f"Секрет-семья-{uuid.uuid4().hex[:8]}"
        alice = self.client_new()
        self.create_profile(alice, name)

        bob = self.client_new()
        html = bob.get("/family").get_data(as_text=True)
        self.assertNotIn(name, html)
        self.assertEqual(bob.get("/family").status_code, 200)

    def test_parent_zone_hides_other_families(self):
        from routes import parent as parent_routes

        pin = parent_routes.reset_parent_pin()

        name = f"Секрет-родитель-{uuid.uuid4().hex[:8]}"
        alice = self.client_new()
        self.create_profile(alice, name)

        bob = self.client_new()
        unlock = bob.post(
            "/parent/unlock",
            data={"pin": pin, "csrf_token": self.csrf(bob, "/parent")},
        )
        self.assertEqual(unlock.status_code, 302)
        html = bob.get("/parent/dashboard").get_data(as_text=True)
        self.assertNotIn(name, html, "Родительская зона показывает чужие профили")

    def test_parent_zone_rejects_foreign_learner_export(self):
        from routes import parent as parent_routes

        pin = parent_routes.reset_parent_pin()
        name = f"Секрет-экспорт-{uuid.uuid4().hex[:8]}"
        alice = self.client_new()
        learner = self.create_profile(alice, name)

        bob = self.client_new()
        bob.post("/parent/unlock", data={"pin": pin, "csrf_token": self.csrf(bob, "/parent")})
        self.assertEqual(
            bob.get(f"/parent/learner/{learner['id']}/export.csv").status_code, 403
        )
        self.assertEqual(
            bob.get(f"/parent/learner/{learner['id']}").status_code, 403
        )


class TestLearnerPin(SecurityTestCase):
    def test_login_requires_pin(self):
        name = f"Пин-{uuid.uuid4().hex[:8]}"
        client = self.client_new()
        learner = self.create_profile(client, name, pin="1234")

        with client.session_transaction() as session:
            session.pop("learner_id", None)

        response = client.post(
            f"/learners/{learner['id']}/login",
            data={"csrf_token": self.csrf(client, "/")},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("Неверный PIN", response.get_data(as_text=True))

        response = client.post(
            f"/learners/{learner['id']}/login",
            data={"csrf_token": self.csrf(client, "/"), "pin": "1234"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/map", response.headers["Location"])

    def test_pin_attempts_are_locked_server_side(self):
        name = f"Пин-лок-{uuid.uuid4().hex[:8]}"
        client = self.client_new()
        learner = self.create_profile(client, name, pin="4321")

        with client.session_transaction() as session:
            session.pop("learner_id", None)

        statuses = []
        for _ in range(5):
            response = client.post(
                f"/learners/{learner['id']}/login",
                data={"csrf_token": self.csrf(client, "/"), "pin": "0000"},
            )
            statuses.append(response.status_code)
        self.assertEqual(statuses[-1], 429, statuses)

        # Блокировка хранится на сервере: следующая попытка тоже отклоняется,
        # даже если бы клиент подделал счётчик в cookie.
        response = client.post(
            f"/learners/{learner['id']}/login",
            data={"csrf_token": self.csrf(client, "/"), "pin": "4321"},
        )
        self.assertEqual(response.status_code, 429)
        self.assertIn("Подождите", response.get_data(as_text=True))


class TestTeacherRegistration(SecurityTestCase):
    def _school_and_class(self, teacher_id=None):
        from services import orgs

        suffix = uuid.uuid4().hex[:6]
        city = orgs.create_city(f"Город-{suffix}")
        school = orgs.create_school(city, f"Школа-{suffix}")
        class_id = orgs.create_class(school, 5, "А", teacher_id=teacher_id)
        return school, class_id

    def test_cannot_claim_occupied_class(self):
        from services import orgs

        suffix = uuid.uuid4().hex[:6]
        school, class_id = self._school_and_class()

        owner = self.client_new()
        token = self.csrf(owner, "/register")
        response = owner.post(
            "/register",
            data={
                "role": "teacher",
                "login": f"owner_{suffix}",
                "password": "pass1234",
                "password2": "pass1234",
                "first_name": "Первый",
                "school_id": str(school),
                "class_ids": [str(class_id)],
                "csrf_token": token,
            },
        )
        self.assertEqual(response.status_code, 302)
        owner_id = orgs.get_class(class_id)["teacher_id"]
        self.assertIsNotNone(owner_id)

        other = self.client_new()
        token = self.csrf(other, "/register")
        response = other.post(
            "/register",
            data={
                "role": "teacher",
                "login": f"intruder_{suffix}",
                "password": "pass1234",
                "password2": "pass1234",
                "first_name": "Второй",
                "school_id": str(school),
                "class_ids": [str(class_id)],
                "csrf_token": token,
            },
        )
        self.assertEqual(response.status_code, 200, "Захват класса должен отклоняться")
        self.assertIn("уже ведёт другой учитель", response.get_data(as_text=True))
        self.assertEqual(orgs.get_class(class_id)["teacher_id"], owner_id)

    def test_class_from_other_school_rejected(self):
        suffix = uuid.uuid4().hex[:6]
        school_a, _ = self._school_and_class()
        school_b, class_b = self._school_and_class()

        client = self.client_new()
        response = client.post(
            "/register",
            data={
                "role": "teacher",
                "login": f"cross_{suffix}",
                "password": "pass1234",
                "password2": "pass1234",
                "first_name": "Кросс",
                "school_id": str(school_a),
                "class_ids": [str(class_b)],
                "csrf_token": self.csrf(client, "/register"),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("только классы выбранной школы", response.get_data(as_text=True))

    def test_public_class_list_requires_school(self):
        client = self.client_new()
        self.assertEqual(client.get("/api/org/classes").get_json(), {"classes": []})


class TestRedirects(SecurityTestCase):
    def _make_user(self, login):
        from services import auth

        if not auth.get_user_by_login(login):
            auth.create_user(login, "pass1234", auth.ROLE_TEACHER, "Тест", "Учитель")
        return login

    def test_external_next_is_ignored(self):
        login_name = f"redir_{uuid.uuid4().hex[:6]}"
        self._make_user(login_name)

        client = self.client_new()
        response = client.post(
            "/login?next=https://evil.example/steal",
            data={
                "login": login_name,
                "password": "pass1234",
                "csrf_token": self.csrf(client, "/login"),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("evil.example", response.headers["Location"])

    def test_protocol_relative_next_is_ignored(self):
        login_name = f"redir2_{uuid.uuid4().hex[:6]}"
        self._make_user(login_name)

        client = self.client_new()
        response = client.post(
            "/login?next=//evil.example/x",
            data={
                "login": login_name,
                "password": "pass1234",
                "csrf_token": self.csrf(client, "/login"),
            },
        )
        self.assertNotIn("evil.example", response.headers["Location"])

    def test_local_next_is_kept(self):
        login_name = f"redir3_{uuid.uuid4().hex[:6]}"
        self._make_user(login_name)

        client = self.client_new()
        response = client.post(
            "/login?next=/parent",
            data={
                "login": login_name,
                "password": "pass1234",
                "csrf_token": self.csrf(client, "/login"),
            },
        )
        self.assertTrue(response.headers["Location"].endswith("/parent"))


class TestUploadValidation(SecurityTestCase):
    def test_pdf_upload_rejects_non_pdf(self):
        from services import textbooks

        fake = FileStorage(stream=io.BytesIO(b"<html><script>alert(1)</script>"),
                           filename="book.pdf")
        with self.assertRaises(ValueError):
            textbooks.save_upload(fake, subject_id=1, grade=3, title="Подделка")

    def test_photo_upload_rejects_non_image(self):
        from services import assignment_photos

        fake = FileStorage(stream=io.BytesIO(b"<html>not an image</html>"),
                           filename="answer.png")
        with self.assertRaises(ValueError):
            assignment_photos.save_photos([fake], 999999, 999999)

    def test_pdf_signature_accepted_for_real_pdf(self):
        from services import filecheck

        self.assertTrue(filecheck.looks_like(".pdf", b"%PDF-1.7\n..."))
        self.assertFalse(filecheck.looks_like(".pdf", b"PK\x03\x04"))
        self.assertTrue(filecheck.looks_like(".png", b"\x89PNG\r\n\x1a\n\x00"))
        self.assertFalse(filecheck.looks_like(".png", b"<html>"))


if __name__ == "__main__":
    unittest.main()
