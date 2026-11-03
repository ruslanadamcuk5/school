"""Тесты удалённой помощи родителю: запрос, экран, команды, доступ."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DB = os.path.join(tempfile.gettempdir(), "edu_math_remote_test.db")
_TMP_UPLOAD = os.path.join(tempfile.gettempdir(), "edu_math_remote_upload")
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_PATH"] = _TMP_DB
os.environ["SECRET_KEY"] = "remote-test-secret"
os.environ["UPLOAD_DIR"] = _TMP_UPLOAD

from database import execute, init_db, query_one  # noqa: E402
from services import auth, learners  # noqa: E402


class RemoteHelpTestCase(unittest.TestCase):
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

    def setUp(self) -> None:
        os.environ["DATABASE_PATH"] = _TMP_DB
        os.environ["UPLOAD_DIR"] = _TMP_UPLOAD
        for suffix in ("", "-wal", "-shm"):
            path = _TMP_DB + suffix
            if os.path.exists(path):
                os.remove(path)
        init_db()
        from app import create_app

        self.app = create_app("testing")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.driver = self._user("remote_parent", "parent", "Мама")
        self.child = self._user("remote_child", "student", "Миша")
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
        password = "remote-pass-123"
        auth.create_user(login, password, role, first_name=first)
        return login, password

    def _token(self, login: str, password: str) -> str:
        response = self.client.post(
            "/api/v1/auth/login", json={"login": login, "password": password}
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()["token"]

    def _headers(self, login: str, password: str) -> dict:
        return {"Authorization": f"Bearer {self._token(login, password)}"}

    def _start(self, headers: dict):
        return self.client.post(
            "/api/v1/remote/start",
            json={"learner_id": self.learner_id},
            headers=headers,
        )

    def _session(self, response) -> dict:
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()["session"]

    # --------------------------------------------------------------- сценарий
    def test_full_help_flow(self):
        parent = self._headers(*self.driver)
        child = self._headers(*self.child)

        session = self._session(self._start(parent))
        self.assertEqual(session["status"], "pending")
        self.assertEqual(session["child_name"], "Миша")
        session_id = session["id"]

        incoming = self.client.get("/api/v1/remote/incoming", headers=child)
        self.assertEqual(incoming.status_code, 200)
        pending = incoming.get_json()["session"]
        self.assertEqual(pending["id"], session_id)
        self.assertEqual(pending["status"], "pending")
        self.assertEqual(pending["parent_name"], "Мама")

        accepted = self.client.post(
            "/api/v1/remote/accept",
            json={"session_id": session_id, "can_control": True},
            headers=child,
        )
        self.assertEqual(accepted.status_code, 200, accepted.get_data(as_text=True))
        self.assertEqual(accepted.get_json()["session"]["status"], "active")
        self.assertTrue(accepted.get_json()["session"]["can_control"])

        # Кадр экрана: сервер принимает JPEG и отдаёт его родителю.
        frame = b"\xff\xd8" + b"fake-jpeg" * 10 + b"\xff\xd9"
        upload = self.client.post(
            f"/api/v1/remote/frame?session_id={session_id}&width=640&height=360",
            data=frame,
            headers={**child, "Content-Type": "image/jpeg"},
        )
        self.assertEqual(upload.status_code, 200, upload.get_data(as_text=True))
        self.assertTrue(upload.get_json()["session"]["has_frame"])

        picture = self.client.get(
            f"/api/v1/remote/frame?session_id={session_id}", headers=parent
        )
        self.assertEqual(picture.status_code, 200)
        self.assertEqual(picture.data, frame)
        self.assertEqual(picture.mimetype, "image/jpeg")

        # Нажатие родителя доходит до ребёнка ровно один раз.
        command = self.client.post(
            "/api/v1/remote/command",
            json={
                "session_id": session_id,
                "kind": "tap",
                "x": 0.25,
                "y": 0.75,
            },
            headers=parent,
        )
        self.assertEqual(command.status_code, 200, command.get_data(as_text=True))

        commands = self.client.get(
            f"/api/v1/remote/commands?session_id={session_id}&after_id=0",
            headers=child,
        )
        self.assertEqual(commands.status_code, 200)
        items = commands.get_json()["commands"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["kind"], "tap")
        self.assertAlmostEqual(items[0]["x"], 0.25)
        again = self.client.get(
            f"/api/v1/remote/commands?session_id={session_id}&after_id=0",
            headers=child,
        )
        self.assertEqual(again.get_json()["commands"], [])

        stopped = self.client.post(
            "/api/v1/remote/stop",
            json={"session_id": session_id},
            headers=parent,
        )
        self.assertEqual(stopped.status_code, 200)
        self.assertEqual(stopped.get_json()["session"]["status"], "ended")
        gone = self.client.get(
            f"/api/v1/remote/frame?session_id={session_id}", headers=parent
        )
        self.assertEqual(gone.status_code, 409)

    def test_child_can_decline(self):
        parent = self._headers(*self.driver)
        child = self._headers(*self.child)
        session_id = self._session(self._start(parent))["id"]
        declined = self.client.post(
            "/api/v1/remote/decline",
            json={"session_id": session_id},
            headers=child,
        )
        self.assertEqual(declined.status_code, 200)
        self.assertEqual(declined.get_json()["session"]["status"], "declined")
        current = self.client.get(
            f"/api/v1/remote/current?learner_id={self.learner_id}", headers=parent
        )
        self.assertEqual(current.get_json()["session"]["status"], "declined")

    def test_second_parent_gets_busy(self):
        parent = self._headers(*self.driver)
        self._session(self._start(parent))

        other = self._user("remote_other", "parent", "Папа")
        other_id = auth.get_user_by_login(other[0])["id"]
        auth.link_parent_child(other_id, self.child_id)
        response = self._start(self._headers(*other))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "busy")

    def test_control_requires_child_permission(self):
        parent = self._headers(*self.driver)
        child = self._headers(*self.child)
        session_id = self._session(self._start(parent))["id"]
        self.client.post(
            "/api/v1/remote/accept",
            json={"session_id": session_id, "can_control": False},
            headers=child,
        )
        response = self.client.post(
            "/api/v1/remote/command",
            json={"session_id": session_id, "kind": "tap", "x": 0.5, "y": 0.5},
            headers=parent,
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "no_control")

    def test_stranger_cannot_watch_child(self):
        stranger = self._user("remote_stranger", "parent", "Чужой")
        response = self._start(self._headers(*stranger))
        self.assertEqual(response.status_code, 404)

    def test_student_cannot_start_session(self):
        response = self._start(self._headers(*self.child))
        self.assertEqual(response.status_code, 403)

    def test_frame_rejected_outside_session(self):
        child = self._headers(*self.child)
        response = self.client.post(
            "/api/v1/remote/frame?session_id=999&width=100&height=100",
            data=b"\xff\xd8fake",
            headers=child,
        )
        self.assertEqual(response.status_code, 404)

    def test_non_jpeg_rejected(self):
        parent = self._headers(*self.driver)
        child = self._headers(*self.child)
        session_id = self._session(self._start(parent))["id"]
        self.client.post(
            "/api/v1/remote/accept",
            json={"session_id": session_id, "can_control": False},
            headers=child,
        )
        response = self.client.post(
            f"/api/v1/remote/frame?session_id={session_id}&width=100&height=100",
            data=b"not-an-image",
            headers=child,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "bad_frame")


class RemoteSchemaTestCase(unittest.TestCase):
    def test_tables_exist(self):
        init_db()
        for table in ("remote_sessions", "remote_commands"):
            row = query_one(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            )
            self.assertIsNotNone(row, table)
        execute("SELECT 1")