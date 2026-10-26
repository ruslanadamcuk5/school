"""Пароль администратора по умолчанию и его переопределение через окружение."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("APP_ENV", "testing")
os.environ["DATABASE_PATH"] = os.path.join(
    tempfile.gettempdir(), "edu_math_admin_default_test.db"
)
os.environ["SECRET_KEY"] = "test-secret"

import seed  # noqa: E402
from database import init_db, query_all, query_one, reset_database  # noqa: E402
from services import auth  # noqa: E402


class TestAdminDefaultPassword(unittest.TestCase):

    def setUp(self):
        self.previous = os.environ.get("ADMIN_PASSWORD")
        os.environ.pop("ADMIN_PASSWORD", None)
        init_db()
        reset_database()

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("ADMIN_PASSWORD", None)
        else:
            os.environ["ADMIN_PASSWORD"] = self.previous

    def _admin(self):
        return query_one("SELECT * FROM users WHERE role = ?", (auth.ROLE_ADMIN,))

    def test_default_password_is_math2025(self):
        created = seed.ensure_admin()

        self.assertEqual(seed.DEFAULT_ADMIN_PASSWORD, "math2025")
        self.assertEqual(created, "math2025")
        admin = self._admin()
        self.assertIsNotNone(admin)
        self.assertEqual(admin["login"], "admin")
        self.assertTrue(auth.verify_password("math2025", admin["password_hash"]))

    def test_existing_admin_is_not_recreated(self):
        seed.ensure_admin()

        self.assertEqual(seed.ensure_admin(), "")
        rows = query_all("SELECT id FROM users WHERE role = ?", (auth.ROLE_ADMIN,))
        self.assertEqual(len(rows), 1)

    def test_env_password_overrides_default(self):
        os.environ["ADMIN_PASSWORD"] = "StrongPass!42"

        created = seed.ensure_admin()

        self.assertEqual(created, "StrongPass!42")
        admin = self._admin()
        self.assertTrue(auth.verify_password("StrongPass!42", admin["password_hash"]))
        self.assertFalse(auth.verify_password("math2025", admin["password_hash"]))


if __name__ == "__main__":
    unittest.main()
