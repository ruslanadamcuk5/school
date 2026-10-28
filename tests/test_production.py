"""Дымовой тест: запуск в production-режиме с чистой базой данных."""
from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DB = os.path.join(tempfile.gettempdir(), "edu_math_prod_test.db")


def _clean_db() -> None:
    for suffix in ("", "-wal", "-shm"):
        path = _TMP_DB + suffix
        if os.path.exists(path):
            os.remove(path)


class TestProductionBoot(unittest.TestCase):
    _ENV_KEYS = ("APP_ENV", "DATABASE_PATH", "SECRET_KEY")

    def setUp(self):
        _clean_db()
        self._previous_env = {key: os.environ.get(key) for key in self._ENV_KEYS}
        os.environ["APP_ENV"] = "production"
        os.environ["DATABASE_PATH"] = _TMP_DB
        os.environ["SECRET_KEY"] = "production-test-secret"
        for module in ("wsgi", "app"):
            sys.modules.pop(module, None)
        import wsgi

        self.app = wsgi.app
        self.client = self.app.test_client()

    def tearDown(self):
        _clean_db()
        for key, value in self._previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for module in ("wsgi", "app"):
            sys.modules.pop(module, None)

    def test_boot_and_main_flow(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

        html = self.client.get("/").get_data(as_text=True)
        token = re.search('name="csrf-token" content="([^"]+)"', html).group(1)

        response = self.client.post(
            "/learners",
            data={"name": "Проверка", "avatar": "🦊", "grade": "3", "csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)

        page = self.client.get("/map").get_data(as_text=True)
        self.assertEqual(page.count("topic-card__title"), 12)

        self.client.get("/play/numbers_1000")
        self.assertEqual(self.client.get("/play/numbers_1000/task").status_code, 200)
        self.assertEqual(self.client.get("/textbook").status_code, 200)
        self.assertEqual(self.client.get("/parent").status_code, 200)

    def test_secret_key_is_used_from_environment(self):
        self.assertEqual(self.app.config["SECRET_KEY"], "production-test-secret")


if __name__ == "__main__":
    unittest.main(verbosity=2)
