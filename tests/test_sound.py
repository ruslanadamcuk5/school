"""Тесты звукового вызова: команда родителя, опрос телефона, ответ и истечение."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DB = os.path.join(tempfile.gettempdir(), "edu_math_sound_test.db")
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_PATH"] = _TMP_DB
os.environ["SECRET_KEY"] = "sound-test-secret"


from database import execute, init_db, query_one  # noqa: E402
from services import auth, learners  # noqa: E402


class SoundCallTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._previous_db = os.environ.get("DATABASE_PATH")
        super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._previous_db is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = cls._previous_db
        super().tearDownClass()

    def setUp(self) -> None:
        os.environ["DATABASE_PATH"] = _TMP_DB
        for suffix in ("", "-wal", "-shm"):
            path = _TMP_DB + suffix
            if os.path.exists(path):
                os.remove(path)
        init_db()
        from app import create_app

        self.app = create_app("testing")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.driver = self._user("sound_parent", "parent", "Мама")
        self.child = self._user("sound_child", "student", "Миша")
        self.child_id = auth.get_user_by_login(self.child[0])["id"]
        auth.link_parent_child(
            auth.get_user_by_login(self.driver[0])["id"], self.child_id
        )
        self.learner_id = learners.ensure_learner_for_user(
            auth.get_user_by_login(self.child[0])
        )

    # ------------------------------------------------------------- helpers
    def _user(self, prefix: str, role: str, first: str) -> tuple[str, str]:
        login = f"{prefix}_{int(__import__('time').time() * 1000) % 10_000_000}"
        password = "sound-pass-123"
        auth.create_user(login, password, role, first_name=first)
        return login, password

    def _headers(self, login: str, password: str) -> dict:
        response = self.client.post(
            "/api/v1/auth/login", json={"login": login, "password": password}
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return {"Authorization": f"Bearer {response.get_json()['token']}"}

    def _ring(self, headers: dict):
        return self.client.post(
            f"/api/v1/parent/children/{self.learner_id}/sound",
            headers=headers,
        )

    def _command(self, headers: dict, after_id: int = 0):
        return self.client.get(
            f"/api/v1/sound/command?after_id={after_id}", headers=headers
        )

    # --------------------------------------------------------------- сценарий
    def test_full_sound_flow(self):
        parent = self._headers(*self.driver)
        child = self._headers(*self.child)

        sent = self._ring(parent)
        self.assertEqual(sent.status_code, 200, sent.get_data(as_text=True))
        payload = sent.get_json()
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["already"])
        command = payload["command"]
        self.assertEqual(command["status"], "pending")
        command_id = command["id"]

        incoming = self._command(child)
        self.assertEqual(incoming.status_code, 200)
        self.assertEqual(incoming.get_json()["command"]["id"], command_id)

        ringing = self.client.post(
            f"/api/v1/sound/command/{command_id}/ack",
            json={"status": "ringing", "mode": "alarm"},
            headers=child,
        )
        self.assertEqual(ringing.status_code, 200, ringing.get_data(as_text=True))
        self.assertEqual(ringing.get_json()["command"]["status"], "ringing")
        self.assertEqual(ringing.get_json()["command"]["mode"], "alarm")

        # После подтверждения команда не приходит повторно.
        again = self._command(child)
        self.assertIsNone(again.get_json()["command"])

        done = self.client.post(
            f"/api/v1/sound/command/{command_id}/ack",
            json={"status": "done", "mode": "alarm", "detail": "stopped"},
            headers=child,
        )
        self.assertEqual(done.status_code, 200)
        self.assertEqual(done.get_json()["command"]["status"], "done")
        self.assertEqual(done.get_json()["command"]["detail"], "stopped")

        status = self.client.get(
            f"/api/v1/parent/children/{self.learner_id}/sound", headers=parent
        )
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.get_json()["command"]["id"], command_id)

    def test_second_press_returns_same_command(self):
        parent = self._headers(*self.driver)
        first = self._ring(parent).get_json()
        second = self._ring(parent).get_json()
        self.assertTrue(second["already"])
        self.assertEqual(first["command"]["id"], second["command"]["id"])

    def test_old_command_expires(self):
        parent = self._headers(*self.driver)
        child = self._headers(*self.child)
        command_id = self._ring(parent).get_json()["command"]["id"]
        execute(
            "UPDATE sound_commands SET created_at = datetime('now', '-3 minutes') "
            "WHERE id = ?",
            (command_id,),
        )
        incoming = self._command(child)
        self.assertEqual(incoming.status_code, 200)
        self.assertIsNone(incoming.get_json()["command"])
        row = query_one("SELECT status FROM sound_commands WHERE id = ?", (command_id,))
        self.assertEqual(row["status"], "expired")

    def test_stranger_cannot_ring_child(self):
        stranger = self._user("sound_stranger", "parent", "Чужой")
        response = self._ring(self._headers(*stranger))
        self.assertEqual(response.status_code, 404)

    def test_student_cannot_ring(self):
        response = self._ring(self._headers(*self.child))
        self.assertEqual(response.status_code, 403)

    def test_parent_cannot_poll_child_command(self):
        parent = self._headers(*self.driver)
        response = self._command(parent)
        self.assertEqual(response.status_code, 403)


class SoundSchemaTestCase(unittest.TestCase):
    def test_table_exists(self):
        init_db()
        row = query_one(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("sound_commands",),
        )
        self.assertIsNotNone(row)
