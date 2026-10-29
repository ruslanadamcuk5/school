"""Вход через Google в браузере телефона и возврат в Android-приложение."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DB = os.path.join(tempfile.gettempdir(), "edu_math_google_browser_test.db")
_TMP_UPLOAD = os.path.join(tempfile.gettempdir(), "edu_math_google_browser_upload")
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_PATH"] = _TMP_DB
os.environ["SECRET_KEY"] = "google-browser-test-secret"

for suffix in ("", "-wal", "-shm"):
    if os.path.exists(_TMP_DB + suffix):
        os.remove(_TMP_DB + suffix)

from services import auth, google_auth  # noqa: E402

CLIENT_ID = "test-client.apps.googleusercontent.com"
VERIFIER = "test-verifier-0123456789abcdefghijklmnop"
CHALLENGE = google_auth.challenge_for(VERIFIER)


def fresh_db():
    for suffix in ("", "-wal", "-shm"):
        path = _TMP_DB + suffix
        if os.path.exists(path):
            os.remove(path)


def google_profile(**overrides):
    profile = {
        "sub": "google-browser-user-1",
        "email": "olga@example.com",
        "email_verified": True,
        "first_name": "Ольга",
        "last_name": "Иванова",
        "picture": "",
    }
    profile.update(overrides)
    return profile


class BrowserFlowTestCase(unittest.TestCase):
    def setUp(self):
        self._previous_env = {
            key: os.environ.get(key) for key in ("DATABASE_PATH", "UPLOAD_DIR")
        }
        os.environ["DATABASE_PATH"] = _TMP_DB
        os.environ["UPLOAD_DIR"] = _TMP_UPLOAD
        fresh_db()
        from app import create_app

        app = create_app("testing")
        app.config["TESTING"] = True
        app.config.update(
            {
                "GOOGLE_CLIENT_ID": CLIENT_ID,
                "GOOGLE_CLIENT_SECRET": "test-secret",
                "GOOGLE_REDIRECT_URI": "https://school.test/auth/google/callback",
            }
        )
        self.app = app
        self.client = app.test_client()

    def tearDown(self):
        fresh_db()
        for key, value in self._previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def start(self, profile=None, challenge=CHALLENGE):
        """Сделать вид, что браузер уже вернулся от Google."""
        with self.client.session_transaction() as sess:
            sess["google_oauth"] = {
                "state": "state-1",
                "mode": "login",
                "next": None,
                "client": "android",
                "challenge": challenge,
            }

    def callback(self, profile=None, extra=""):
        profile = profile or google_profile()
        self.start()
        with mock.patch(
            "services.google_auth.exchange_code",
            return_value={"access_token": "access-token"},
        ), mock.patch(
            "services.google_auth.fetch_userinfo", return_value={}
        ), mock.patch(
            "services.google_auth.profile_from_userinfo", return_value=profile
        ):
            return self.client.get(f"/auth/google/callback?state=state-1&code=abc{extra}")

    def exchange(self, code, verifier=VERIFIER):
        return self.client.post(
            "/api/v1/auth/google/exchange",
            json={"code": code, "verifier": verifier},
        )

    @staticmethod
    def app_code(response):
        location = response.headers["Location"]
        assert location.startswith("uchus://auth?"), location
        return parse_qs(urlsplit(location).query)["code"][0]

    def test_challenge_is_checked(self):
        response = self.client.get(
            "/auth/google?client=android&challenge=short"
        )
        self.assertEqual(response.status_code, 400)

    def test_existing_user_returns_code_and_token(self):
        user_id = auth.create_user(
            "olga", "secret123", auth.ROLE_TEACHER, "Ольга", email="olga@example.com"
        )
        auth.update_user(user_id, google_sub="google-browser-user-1")
        response = self.callback()
        self.assertEqual(response.status_code, 302)
        code = self.app_code(response)

        exchanged = self.exchange(code)
        self.assertEqual(exchanged.status_code, 200, exchanged.get_data(as_text=True))
        payload = exchanged.get_json()
        self.assertTrue(payload["token"])
        self.assertEqual(payload["user"]["login"], "olga")

        me = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {payload['token']}"},
        )
        self.assertEqual(me.status_code, 200)

    def test_new_user_finishes_signup_in_browser(self):
        response = self.callback()
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/google/finish", response.headers["Location"])

        page = self.client.get("/auth/google/finish")
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        marker = 'name="csrf-token" content="'
        start = html.find(marker) + len(marker)
        csrf = html[start:html.find('"', start)]

        created = self.client.post(
            "/auth/google/finish",
            data={
                "csrf_token": csrf,
                "role": "student",
                "login": "olga1",
                "first_name": "Ольга",
                "last_name": "Иванова",
            },
        )
        self.assertEqual(created.status_code, 302)
        code = self.app_code(created)

        exchanged = self.exchange(code)
        self.assertEqual(exchanged.status_code, 200, exchanged.get_data(as_text=True))
        payload = exchanged.get_json()
        self.assertTrue(payload["token"])
        self.assertEqual(payload["user"]["role"], "student")
        self.assertEqual(auth.get_user_by_login("olga1")["google_sub"], "google-browser-user-1")

    def test_wrong_verifier_is_rejected(self):
        user_id = auth.create_user("olga", "secret123", auth.ROLE_PARENT, "Ольга")
        auth.update_user(user_id, google_sub="google-browser-user-1")
        code = self.app_code(self.callback())
        response = self.exchange(code, verifier="x" * 43)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "bad_verifier")

    def test_forged_code_is_rejected(self):
        response = self.exchange("forged-code")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "code_expired")

    def test_expired_code_is_rejected(self):
        user_id = auth.create_user("olga", "secret123", auth.ROLE_PARENT, "Ольга")
        auth.update_user(user_id, google_sub="google-browser-user-1")
        code = self.app_code(self.callback())
        with mock.patch("services.google_auth.LOGIN_CODE_MAX_AGE", -1):
            response = self.exchange(code)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "code_expired")

    def test_cancel_returns_to_app(self):
        self.start()
        response = self.client.get(
            "/auth/google/callback?state=state-1&error=access_denied"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["Location"], "uchus://auth?error=cancelled"
        )

    def test_inactive_user_returns_error(self):
        user_id = auth.create_user("olga", "secret123", auth.ROLE_STUDENT, "Ольга")
        auth.update_user(user_id, google_sub="google-browser-user-1", is_active=0)
        response = self.callback()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "uchus://auth?error=inactive")


if __name__ == "__main__":
    unittest.main()
