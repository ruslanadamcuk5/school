"""API-вход через Google для Android: ID token, регистрация и токены."""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DB = os.path.join(tempfile.gettempdir(), "edu_math_google_api_test.db")
_TMP_UPLOAD = os.path.join(tempfile.gettempdir(), "edu_math_google_api_upload")
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_PATH"] = _TMP_DB
os.environ["SECRET_KEY"] = "google-api-test-secret"

for suffix in ("", "-wal", "-shm"):
    if os.path.exists(_TMP_DB + suffix):
        os.remove(_TMP_DB + suffix)

from services import auth, google_auth  # noqa: E402

CLIENT_ID = "test-client.apps.googleusercontent.com"
NONCE = "nonce-0123456789abcdef"


def make_client(**config):
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
    app.config.update(config)
    return app.test_client()


def fresh_db():
    for suffix in ("", "-wal", "-shm"):
        path = _TMP_DB + suffix
        if os.path.exists(path):
            os.remove(path)


def google_profile(**overrides):
    profile = {
        "sub": "google-api-user-1",
        "email": "ivan@example.com",
        "email_verified": True,
        "first_name": "Иван",
        "last_name": "Петров",
        "picture": "https://lh3.googleusercontent.com/a/test",
    }
    profile.update(overrides)
    return profile


class GoogleApiTestCase(unittest.TestCase):
    def setUp(self):
        self._previous_env = {
            key: os.environ.get(key) for key in ("DATABASE_PATH", "UPLOAD_DIR")
        }
        os.environ["DATABASE_PATH"] = _TMP_DB
        os.environ["UPLOAD_DIR"] = _TMP_UPLOAD
        fresh_db()
        self.client = make_client()

    def tearDown(self):
        fresh_db()
        for key, value in self._previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def google_login(self, profile=None, **overrides):
        profile = profile or google_profile()
        body = {"id_token": "id-token", "nonce": NONCE}
        body.update(overrides)
        with mock.patch(
            "services.google_auth.verify_id_token", return_value=profile
        ):
            return self.client.post("/api/v1/auth/google", json=body)


class TestGoogleApiLogin(GoogleApiTestCase):
    def test_new_user_gets_signup_offer(self):
        response = self.google_login()
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["needs_signup"])
        self.assertTrue(data["signup_token"])
        self.assertEqual(data["email"], "ivan@example.com")
        self.assertEqual(data["first_name"], "Иван")
        self.assertEqual(data["suggested_login"], "ivan")
        self.assertIsNone(auth.get_user_by_google_sub("google-api-user-1"))

    def test_finish_signup_creates_account_and_token(self):
        data = self.google_login().get_json()
        response = self.client.post(
            "/api/v1/auth/google/finish",
            json={
                "signup_token": data["signup_token"],
                "role": "parent",
                "login": "ivan",
                "first_name": "Иван",
                "last_name": "Петров",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["token"])
        self.assertEqual(payload["user"]["role"], "parent")
        user = auth.get_user_by_login("ivan")
        self.assertEqual(user["google_sub"], "google-api-user-1")
        self.assertFalse(auth.has_password(user))

        me = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {payload['token']}"},
        )
        self.assertEqual(me.status_code, 200)

    def test_second_login_returns_token_without_signup(self):
        data = self.google_login().get_json()
        self.client.post(
            "/api/v1/auth/google/finish",
            json={
                "signup_token": data["signup_token"],
                "role": "student",
                "login": "student1",
                "first_name": "Иван",
            },
        )
        response = self.google_login()
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload.get("needs_signup"))
        self.assertTrue(payload["token"])
        self.assertEqual(payload["user"]["login"], "student1")

    def test_existing_email_is_linked(self):
        user_id = auth.create_user(
            "teacher1", "secret123", auth.ROLE_TEACHER,
            "Мария", "Сидорова", email="ivan@example.com",
        )
        response = self.google_login()
        payload = response.get_json()
        self.assertTrue(payload["token"])
        self.assertFalse(payload.get("needs_signup"))
        self.assertEqual(auth.get_user(user_id)["google_sub"], "google-api-user-1")

    def test_inactive_user_is_rejected(self):
        user_id = auth.create_user("blocked", "secret123", auth.ROLE_STUDENT, "Иван")
        auth.update_user(user_id, google_sub="google-api-user-1")
        auth.update_user(user_id, is_active=0)
        response = self.google_login()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "inactive")

    def test_missing_nonce_is_rejected(self):
        response = self.client.post(
            "/api/v1/auth/google", json={"id_token": "id-token"}
        )
        self.assertEqual(response.status_code, 400)

    def test_invalid_token_is_rejected(self):
        with mock.patch(
            "services.google_auth.verify_id_token",
            side_effect=google_auth.GoogleAuthError("bad token"),
        ) as verify:
            response = self.client.post(
                "/api/v1/auth/google",
                json={"id_token": "id-token", "nonce": NONCE},
            )
        verify.assert_called_once()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "google_token_invalid")

    def test_google_disabled_returns_503(self):
        client = make_client(GOOGLE_CLIENT_ID="", GOOGLE_CLIENT_SECRET="")
        response = client.post(
            "/api/v1/auth/google", json={"id_token": "id-token", "nonce": NONCE}
        )
        self.assertEqual(response.status_code, 503)


class TestGoogleApiFinish(GoogleApiTestCase):
    def _signup_token(self):
        return self.google_login().get_json()["signup_token"]

    def test_login_collision_is_reported(self):
        auth.create_user("ivan", "secret123", auth.ROLE_STUDENT, "Иван")
        response = self.client.post(
            "/api/v1/auth/google/finish",
            json={
                "signup_token": self._signup_token(),
                "role": "student",
                "login": "ivan",
                "first_name": "Иван",
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "login_taken")

    def test_admin_role_is_rejected(self):
        response = self.client.post(
            "/api/v1/auth/google/finish",
            json={
                "signup_token": self._signup_token(),
                "role": "admin",
                "login": "ivan",
                "first_name": "Иван",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "bad_role")

    def test_tampered_signup_token_is_rejected(self):
        response = self.client.post(
            "/api/v1/auth/google/finish",
            json={
                "signup_token": "forged-token",
                "role": "student",
                "login": "ivan",
                "first_name": "Иван",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "signup_expired")

    def test_parent_links_child_by_code(self):
        child_id = auth.create_user("child1", "secret123", auth.ROLE_STUDENT, "Петя")
        child = auth.get_user(child_id)
        response = self.client.post(
            "/api/v1/auth/google/finish",
            json={
                "signup_token": self._signup_token(),
                "role": "parent",
                "login": "parent1",
                "first_name": "Иван",
                "child_code": child["child_code"],
            },
        )
        self.assertEqual(response.status_code, 200)
        parent_id = auth.get_user_by_login("parent1")["id"]
        children = auth.children_of(parent_id)
        self.assertEqual([row["id"] for row in children], [child_id])


class TestVerifyIdToken(unittest.TestCase):
    def claims(self, **overrides):
        now = int(time.time())
        data = {
            "aud": CLIENT_ID,
            "iss": "https://accounts.google.com",
            "exp": now + 600,
            "sub": "google-api-user-1",
            "email": "ivan@example.com",
            "email_verified": "true",
            "given_name": "Иван",
            "nonce": NONCE,
        }
        data.update(overrides)
        return data

    def verify(self, claims, nonce=NONCE):
        with mock.patch(
            "services.google_auth._request_json", return_value=claims
        ):
            return google_auth.verify_id_token("id-token", nonce)

    def test_valid_token_returns_profile(self):
        from app import create_app

        app = create_app("testing")
        app.config.update(
            GOOGLE_CLIENT_ID=CLIENT_ID, GOOGLE_CLIENT_SECRET="test-secret"
        )
        with app.app_context():
            profile = self.verify(self.claims())
        self.assertEqual(profile["sub"], "google-api-user-1")
        self.assertEqual(profile["email"], "ivan@example.com")

    def test_wrong_audience(self):
        from app import create_app

        app = create_app("testing")
        app.config.update(
            GOOGLE_CLIENT_ID=CLIENT_ID, GOOGLE_CLIENT_SECRET="test-secret"
        )
        with app.app_context(), self.assertRaises(google_auth.GoogleAuthError):
            self.verify(self.claims(aud="other-client"))

    def test_expired_token(self):
        from app import create_app

        app = create_app("testing")
        app.config.update(
            GOOGLE_CLIENT_ID=CLIENT_ID, GOOGLE_CLIENT_SECRET="test-secret"
        )
        with app.app_context(), self.assertRaises(google_auth.GoogleAuthError):
            self.verify(self.claims(exp=int(time.time()) - 120))

    def test_nonce_mismatch(self):
        from app import create_app

        app = create_app("testing")
        app.config.update(
            GOOGLE_CLIENT_ID=CLIENT_ID, GOOGLE_CLIENT_SECRET="test-secret"
        )
        with app.app_context(), self.assertRaises(google_auth.GoogleAuthError):
            self.verify(self.claims(nonce="other-nonce"))

    def test_hashed_nonce_is_accepted(self):
        """Google может вернуть SHA-256 от nonce, который передал Android."""
        import hashlib

        from app import create_app

        hashed = hashlib.sha256(NONCE.encode("utf-8")).hexdigest()
        app = create_app("testing")
        app.config.update(
            GOOGLE_CLIENT_ID=CLIENT_ID, GOOGLE_CLIENT_SECRET="test-secret"
        )
        with app.app_context():
            profile = self.verify(self.claims(nonce=hashed))
        self.assertEqual(profile["email"], "ivan@example.com")

    def test_unverified_email(self):
        from app import create_app

        app = create_app("testing")
        app.config.update(
            GOOGLE_CLIENT_ID=CLIENT_ID, GOOGLE_CLIENT_SECRET="test-secret"
        )
        with app.app_context(), self.assertRaises(google_auth.GoogleAuthError):
            self.verify(self.claims(email_verified="false"))


if __name__ == "__main__":
    unittest.main()
