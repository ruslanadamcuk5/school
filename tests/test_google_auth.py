"""Вход и регистрация через Google: OAuth-состояние, привязка и роли."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DB = os.path.join(tempfile.gettempdir(), "edu_math_google_test.db")
_TMP_UPLOAD = os.path.join(tempfile.gettempdir(), "edu_math_google_upload")
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_PATH"] = _TMP_DB
os.environ["SECRET_KEY"] = "google-test-secret"

for suffix in ("", "-wal", "-shm"):
    if os.path.exists(_TMP_DB + suffix):
        os.remove(_TMP_DB + suffix)

from services import auth  # noqa: E402

CLIENT_ID = "test-client.apps.googleusercontent.com"
REDIRECT_URI = "https://school.test/auth/google/callback"


def make_app(**config):
    from app import create_app

    app = create_app("testing")
    app.config["TESTING"] = True
    app.config.update(config)
    return app


def make_client(**config):
    settings = {
        "GOOGLE_CLIENT_ID": CLIENT_ID,
        "GOOGLE_CLIENT_SECRET": "test-secret",
        "GOOGLE_REDIRECT_URI": REDIRECT_URI,
    }
    settings.update(config)
    app = make_app(**settings)
    return app, app.test_client()


def fresh_db():
    for suffix in ("", "-wal", "-shm"):
        path = _TMP_DB + suffix
        if os.path.exists(path):
            os.remove(path)


def csrf(client, path="/"):
    html = client.get(path).get_data(as_text=True)
    marker = 'name="csrf-token" content="'
    index = html.find(marker)
    if index < 0:
        return ""
    start = index + len(marker)
    return html[start:html.find('"', start)]


def start_google(client, url="/auth/google"):
    response = client.get(url)
    assert response.status_code == 302, response.status_code
    location = response.headers["Location"]
    query = parse_qs(urlparse(location).query)
    return location, query["state"][0]


def google_profile(**overrides):
    profile = {
        "sub": "google-user-1",
        "email": "ivan@example.com",
        "email_verified": True,
        "given_name": "Иван",
        "family_name": "Петров",
        "picture": "https://lh3.googleusercontent.com/a/test",
    }
    profile.update(overrides)
    return profile


class GoogleAuthTestCase(unittest.TestCase):
    def setUp(self):
        # Другие наборы тоже меняют DATABASE_PATH при импорте — возвращаем свой.
        self._previous_env = {
            key: os.environ.get(key) for key in ("DATABASE_PATH", "UPLOAD_DIR")
        }
        os.environ["DATABASE_PATH"] = _TMP_DB
        os.environ["UPLOAD_DIR"] = _TMP_UPLOAD
        fresh_db()
        self.app, self.client = make_client()

    def tearDown(self):
        fresh_db()
        for key, value in self._previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def callback(self, profile=None, state=None, extra=""):
        profile = profile or google_profile()
        if state is None:
            _, state = start_google(self.client)
        with mock.patch(
            "services.google_auth.exchange_code",
            return_value={"access_token": "token", "id_token": "id"},
        ), mock.patch(
            "services.google_auth.fetch_userinfo", return_value=profile
        ):
            return self.client.get(
                f"/auth/google/callback?code=abc&state={state}{extra}"
            )


class TestGoogleConfiguration(GoogleAuthTestCase):
    def test_disabled_without_credentials(self):
        app = make_app(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="")
        client = app.test_client()
        self.assertEqual(client.get("/auth/google").status_code, 404)
        page = client.get("/login").get_data(as_text=True)
        self.assertNotIn("Войти через Google", page)

    def test_login_page_shows_google_button(self):
        page = self.client.get("/login").get_data(as_text=True)
        self.assertIn("Войти через Google", page)

    def test_credentials_from_json_file(self):
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "google_oauth.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(
                    {"client_id": "file-client", "client_secret": "file-secret"},
                    handle,
                )
            previous = os.environ.get("GOOGLE_CREDENTIALS_FILE")
            os.environ["GOOGLE_CREDENTIALS_FILE"] = path
            try:
                app = make_app(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="")
                client = app.test_client()
                self.assertIn(
                    "Войти через Google",
                    client.get("/login").get_data(as_text=True),
                )
                response = client.get("/auth/google")
                self.assertEqual(response.status_code, 302)
                self.assertIn("client_id=file-client", response.headers["Location"])
            finally:
                if previous is None:
                    os.environ.pop("GOOGLE_CREDENTIALS_FILE", None)
                else:
                    os.environ["GOOGLE_CREDENTIALS_FILE"] = previous

    def test_authorize_redirect_contains_state_and_redirect_uri(self):
        location, state = start_google(self.client)
        parsed = urlparse(location)
        self.assertEqual(parsed.netloc, "accounts.google.com")
        query = parse_qs(parsed.query)
        self.assertTrue(state)
        self.assertEqual(query["client_id"][0], CLIENT_ID)
        self.assertEqual(query["redirect_uri"][0], REDIRECT_URI)
        self.assertEqual(query["response_type"][0], "code")
        self.assertIn("openid", query["scope"][0])


class TestGoogleLogin(GoogleAuthTestCase):
    def test_new_user_finishes_signup(self):
        response = self.callback()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/auth/google/finish"))

        page = self.client.get("/auth/google/finish").get_data(as_text=True)
        self.assertIn("ivan@example.com", page)
        self.assertIn("Иван", page)

        token = csrf(self.client, "/auth/google/finish")
        response = self.client.post(
            "/auth/google/finish",
            data={
                "csrf_token": token,
                "role": "parent",
                "first_name": "Иван",
                "last_name": "Петров",
                "login": "ivan",
                "password": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/parent", response.headers["Location"])

        user = auth.get_user_by_login("ivan")
        self.assertIsNotNone(user)
        self.assertEqual(user["google_sub"], "google-user-1")
        self.assertEqual(user["email"], "ivan@example.com")
        self.assertEqual(user["role"], auth.ROLE_PARENT)
        self.assertFalse(auth.has_password(user))

    def test_second_login_goes_straight_to_cabinet(self):
        self.callback()
        token = csrf(self.client, "/auth/google/finish")
        self.client.post(
            "/auth/google/finish",
            data={
                "csrf_token": token,
                "role": "student",
                "first_name": "Иван",
                "login": "ivan2",
            },
        )
        self.client.get("/logout")
        response = self.callback()
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("/auth/google/finish", response.headers["Location"])
        self.assertIn("/student", response.headers["Location"])

    def test_existing_email_is_linked_automatically(self):
        user_id = auth.create_user(
            "teacher1", "secret123", auth.ROLE_TEACHER,
            "Мария", "Сидорова", email="ivan@example.com",
        )
        response = self.callback()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/teacher", response.headers["Location"])
        user = auth.get_user(user_id)
        self.assertEqual(user["google_sub"], "google-user-1")

    def test_unverified_email_is_rejected(self):
        response = self.callback(google_profile(email_verified=False))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])
        self.assertIsNone(auth.get_user_by_login("ivan"))

    def test_state_mismatch_is_rejected(self):
        start_google(self.client)
        with mock.patch("services.google_auth.exchange_code") as exchange:
            response = self.client.get(
                "/auth/google/callback?code=abc&state=wrong"
            )
        exchange.assert_not_called()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_google_error_does_not_create_account(self):
        _, state = start_google(self.client)
        response = self.client.get(
            f"/auth/google/callback?error=access_denied&state={state}"
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(auth.get_user_by_google_sub("google-user-1"))

    def test_login_name_collision_is_suffixed(self):
        auth.create_user("ivan", "secret123", auth.ROLE_STUDENT, "Иван")
        page = self.client.get("/auth/google/finish")
        self.assertEqual(page.status_code, 302)  # без pending — назад ко входу
        self.callback()
        page = self.client.get("/auth/google/finish").get_data(as_text=True)
        self.assertIn('value="ivan2"', page)


class TestGoogleLinking(GoogleAuthTestCase):
    def _login(self):
        user_id = auth.create_user(
            "parent1", "secret123", auth.ROLE_PARENT, "Ольга", email="ivan@example.com"
        )
        self.client.post(
            "/login",
            data={
                "csrf_token": csrf(self.client, "/login"),
                "login": "parent1",
                "password": "secret123",
            },
        )
        return user_id

    def test_link_from_profile(self):
        user_id = self._login()
        _, state = start_google(self.client, "/auth/google?link=1")
        with mock.patch(
            "services.google_auth.exchange_code",
            return_value={"access_token": "token"},
        ), mock.patch(
            "services.google_auth.fetch_userinfo", return_value=google_profile()
        ):
            response = self.client.get(
                f"/auth/google/callback?code=abc&state={state}"
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/profile/account", response.headers["Location"])
        self.assertEqual(auth.get_user(user_id)["google_sub"], "google-user-1")

    def test_link_requires_authentication(self):
        response = self.client.get("/auth/google?link=1")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_unlink_requires_password(self):
        self.callback()
        token = csrf(self.client, "/auth/google/finish")
        self.client.post(
            "/auth/google/finish",
            data={
                "csrf_token": token,
                "role": "student",
                "first_name": "Иван",
                "login": "ivan3",
            },
        )
        user = auth.get_user_by_login("ivan3")
        response = self.client.post(
            "/auth/google/unlink",
            data={"csrf_token": csrf(self.client, "/profile/account")},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(auth.get_user(user["id"])["google_sub"], "google-user-1")

    def test_unlink_with_password(self):
        user_id = self._login()
        auth.attach_google(user_id, "google-user-1", "ivan@example.com")
        response = self.client.post(
            "/auth/google/unlink",
            data={"csrf_token": csrf(self.client, "/profile/account")},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(auth.get_user(user_id)["google_sub"])


if __name__ == "__main__":
    unittest.main()
