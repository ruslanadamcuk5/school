"""Публикация APK: метаданные, проверка обновлений и скачивание."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from routes.app_release import bp as release_bp
from services import release as release_service


class TestRelease(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.previous = os.environ.get("RELEASE_DIR")
        os.environ["RELEASE_DIR"] = str(self.root)
        self.app = Flask(__name__)
        self.app.register_blueprint(release_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("RELEASE_DIR", None)
        else:
            os.environ["RELEASE_DIR"] = self.previous
        self.tmp.cleanup()

    def _publish(self, version_code: int = 2, version_name: str = "1.1") -> None:
        apk = self.root / "uchus-debug.apk"
        apk.write_bytes(b"test apk payload")
        metadata = {
            "version_code": version_code,
            "version_name": version_name,
            "file_name": apk.name,
            "notes": "Проверка обновлений",
            "published_at": "2026-10-26T12:00:00+00:00",
        }
        (self.root / "version.json").write_text(
            json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
        )

    def test_no_release_returns_404(self):
        self.assertEqual(self.client.get("/api/v1/app/version").status_code, 404)
        self.assertEqual(self.client.get("/download/android").status_code, 404)

    def test_version_is_public_and_contains_download_url(self):
        self._publish()
        response = self.client.get("/api/v1/app/version")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["version_code"], 2)
        self.assertEqual(body["version_name"], "1.1")
        self.assertEqual(body["size"], len(b"test apk payload"))
        self.assertEqual(len(body["sha256"]), 64)
        self.assertTrue(body["download_url"].endswith("/download/android"))

    def test_apk_is_downloaded_with_versioned_name(self):
        self._publish()
        response = self.client.get("/download/android")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.mimetype, "application/vnd.android.package-archive"
        )
        self.assertIn("uchus-1.1.apk", response.headers["Content-Disposition"])
        self.assertEqual(response.data, b"test apk payload")
        response.close()

    def test_path_traversal_is_rejected(self):
        (self.root / "version.json").write_text(
            json.dumps(
                {
                    "version_code": 2,
                    "version_name": "1.1",
                    "file_name": "../secret.apk",
                }
            ),
            encoding="utf-8",
        )
        self.assertIsNone(release_service.info())
