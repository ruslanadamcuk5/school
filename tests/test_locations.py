"""Тесты геолокации: постоянная передача, точки, трек, команда родителя и карта."""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DB = os.path.join(tempfile.gettempdir(), "edu_math_locations_test.db")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DATABASE_PATH", _TMP_DB)
os.environ.setdefault("SECRET_KEY", "locations-test-secret")

from database import init_db, query_all, query_one  # noqa: E402
from services import auth as auth_service  # noqa: E402
from services import learners as learners_service  # noqa: E402
from services import locations as locations_service  # noqa: E402
from services import map_settings as map_settings_service  # noqa: E402


def fresh_db() -> None:
    os.environ["DATABASE_PATH"] = _TMP_DB
    for suffix in ("", "-wal", "-shm"):
        path = _TMP_DB + suffix
        if os.path.exists(path):
            os.remove(path)
    init_db()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TestLocationService(unittest.TestCase):
    def setUp(self):
        fresh_db()
        self.learner_id = learners_service.create_learner("Точка", grade=3)

    def test_location_is_always_enabled(self):
        info = locations_service.settings(self.learner_id)
        self.assertTrue(info["enabled"])
        self.assertFalse(info["force_pending"])
        self.assertEqual(info["retention_days"], 14)
        result = locations_service.record_points(
            self.learner_id,
            [{"lat": 53.9, "lon": 27.5, "recorded_at": now_iso()}],
        )
        self.assertEqual(result["saved"], 1)

    def test_record_dedupe_and_latest(self):
        stamp = now_iso()
        point = {"lat": 53.9001, "lon": 27.5601, "accuracy": 8.5, "recorded_at": stamp}
        first = locations_service.record_points(self.learner_id, [point])
        self.assertEqual(first["saved"], 1)
        second = locations_service.record_points(self.learner_id, [point])
        self.assertEqual(second["saved"], 0)

        latest = locations_service.latest_point(self.learner_id)
        self.assertIsNotNone(latest)
        self.assertAlmostEqual(latest["lat"], 53.9001, places=4)
        self.assertEqual(latest["accuracy"], 8.5)

    def test_validation_and_limits(self):
        with self.assertRaises(locations_service.LocationError) as ctx:
            locations_service.record_points(
                self.learner_id, [{"lat": 120, "lon": 27.5, "recorded_at": now_iso()}]
            )
        self.assertEqual(ctx.exception.code, "bad_lat")

        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        with self.assertRaises(locations_service.LocationError) as ctx:
            locations_service.record_points(
                self.learner_id, [{"lat": 53.9, "lon": 27.5, "recorded_at": future}]
            )
        self.assertEqual(ctx.exception.code, "future_point")

        too_many = [
            {"lat": 53.9, "lon": 27.5, "recorded_at": now_iso()}
            for _ in range(locations_service.MAX_POINTS_PER_BATCH + 1)
        ]
        with self.assertRaises(locations_service.LocationError) as ctx:
            locations_service.record_points(self.learner_id, too_many)
        self.assertEqual(ctx.exception.code, "too_many_points")

    def test_timezone_day_bounds_and_labels(self):
        self.assertEqual(
            locations_service.day_bounds(date(2026, 10, 31), 180),
            ("2026-10-30 21:00:00", "2026-10-31 21:00:00"),
        )
        self.assertEqual(
            locations_service.day_bounds(date(2026, 10, 31), -300),
            ("2026-10-31 05:00:00", "2026-11-01 05:00:00"),
        )
        self.assertEqual(locations_service._local_label("2026-10-30 22:30:00", 180), "01:30")
        self.assertEqual(locations_service.clamp_tz(9999), 840)

    def test_trail_only_returns_selected_day(self):
        today = datetime.now(timezone.utc).replace(microsecond=0)
        inside = today - timedelta(minutes=5)
        yesterday = today - timedelta(days=1)
        locations_service.record_points(
            self.learner_id,
            [
                {"lat": 53.91, "lon": 27.51, "recorded_at": inside.isoformat()},
                {"lat": 53.92, "lon": 27.52, "recorded_at": yesterday.isoformat()},
            ],
        )
        trail = locations_service.trail(
            self.learner_id, locations_service.today_for_tz(180), 180
        )
        self.assertEqual(len(trail["points"]), 1)
        self.assertEqual(trail["summary"]["points"], 1)
        self.assertIn("time", trail["points"][0])

    def test_force_command_and_ack(self):
        sender_id = auth_service.create_user("force_parent", "secret123", "parent")
        info = locations_service.force_request(self.learner_id, sender_id)
        self.assertTrue(info["force_pending"])
        self.assertIsNotNone(info["force_requested_at"])
        rows = query_all("SELECT * FROM app_notifications WHERE kind = 'location_force'")
        self.assertTrue(rows)
        audit = query_all("SELECT * FROM audit_log WHERE action = 'location_force'")
        self.assertTrue(audit)

        acked = locations_service.ack_force(self.learner_id)
        self.assertFalse(acked["force_pending"])
        self.assertIsNotNone(acked["force_ack_at"])

    def test_parent_access_check(self):
        parent_id = auth_service.create_user("loc_parent", "secret123", "parent")
        other_id = auth_service.create_user("loc_other", "secret123", "parent")
        student_id = auth_service.create_user("loc_child", "secret123", "student")
        auth_service.link_parent_child(parent_id, student_id)
        learner_id = learners_service.ensure_learner_for_user(
            query_one("SELECT * FROM users WHERE id = ?", (student_id,))
        )
        self.assertTrue(locations_service.can_parent_see(parent_id, learner_id))
        self.assertFalse(locations_service.can_parent_see(other_id, learner_id))


class TestMapSettings(unittest.TestCase):
    def setUp(self):
        fresh_db()

    def test_defaults_and_yandex_preset(self):
        settings = map_settings_service.get_settings()
        self.assertEqual(settings["provider"], "osm")
        self.assertEqual(settings["crs"], "mercator")
        self.assertIn("openstreetmap", settings["tile_url"])

        saved = map_settings_service.save_settings(
            {
                "provider": "yandex",
                "tile_url": map_settings_service.presets()[1]["tile_url"],
                "attribution": "© Яндекс",
                "crs": "yandex",
                "min_zoom": 2,
                "max_zoom": 18,
                "center_lat": 53.9,
                "center_lon": 27.56,
                "zoom": 12,
            }
        )
        self.assertEqual(saved["provider"], "yandex")
        self.assertEqual(saved["crs"], "yandex")
        origins = map_settings_service.csp_origins()
        self.assertTrue(any("yandex" in origin for origin in origins))

    def test_invalid_settings_are_rejected(self):
        with self.assertRaises(map_settings_service.MapSettingsError):
            map_settings_service.save_settings(
                {
                    "provider": "custom",
                    "tile_url": "ftp://example.com/{z}/{x}/{y}.png",
                }
            )
        with self.assertRaises(map_settings_service.MapSettingsError):
            map_settings_service.save_settings(
                {
                    "provider": "custom",
                    "tile_url": "https://example.com/tiles.png",
                }
            )
        with self.assertRaises(map_settings_service.MapSettingsError):
            map_settings_service.save_settings(
                {
                    "provider": "unknown",
                    "tile_url": "https://example.com/{z}/{x}/{y}.png",
                }
            )


class TestLocationApi(unittest.TestCase):
    def setUp(self):
        fresh_db()
        from app import create_app

        self.app = create_app("testing")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.suffix = str(int(time.time() * 1000))[-7:]

    # ------------------------------------------------------------- helpers
    def _user(self, prefix: str, role: str, password: str = "api-pass-123"):
        login = f"{prefix}_{self.suffix}"
        user_id = auth_service.create_user(login, password, role, first_name=login)
        return login, password, user_id

    def _login(self, login: str, password: str) -> str:
        response = self.client.post(
            "/api/v1/auth/login", json={"login": login, "password": password}
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()["token"]

    def _headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def _pair(self):
        parent_login, parent_pass, parent_id = self._user("loc_p", "parent")
        child_login, child_pass, child_id = self._user("loc_c", "student")
        auth_service.link_parent_child(parent_id, child_id)
        learner_id = learners_service.ensure_learner_for_user(
            query_one("SELECT * FROM users WHERE id = ?", (child_id,))
        )
        return (
            self._login(parent_login, parent_pass),
            self._login(child_login, child_pass),
            learner_id,
        )

    # --------------------------------------------------------------- tests
    def test_status_and_points_without_consent(self):
        _, child_token, _ = self._pair()
        status = self.client.get("/api/v1/location/status", headers=self._headers(child_token))
        self.assertEqual(status.status_code, 200, status.get_data(as_text=True))
        self.assertTrue(status.get_json()["enabled"])
        self.assertFalse(status.get_json()["force_pending"])

        sent = self.client.post(
            "/api/v1/location/points",
            headers=self._headers(child_token),
            json={
                "points": [
                    {
                        "lat": 53.9,
                        "lon": 27.5,
                        "accuracy": 7,
                        "battery": 88,
                        "recorded_at": now_iso(),
                    }
                ]
            },
        )
        self.assertEqual(sent.status_code, 200, sent.get_data(as_text=True))
        self.assertEqual(sent.get_json()["saved"], 1)

        latest = self.client.get(
            "/api/v1/location/status", headers=self._headers(child_token)
        ).get_json()
        self.assertIsNotNone(latest["last_point"])
        self.assertEqual(latest["last_point"]["battery"], 88)

    def test_parent_sees_track_force_and_other_parent_cannot(self):
        parent_token, child_token, learner_id = self._pair()
        point = {
            "lat": 53.9,
            "lon": 27.5,
            "accuracy": 6,
            "recorded_at": now_iso(),
        }
        self.client.post(
            "/api/v1/location/points",
            headers=self._headers(child_token),
            json={"points": [point]},
        )

        overview = self.client.get(
            "/api/v1/parent/locations?tz=180", headers=self._headers(parent_token)
        )
        self.assertEqual(overview.status_code, 200, overview.get_data(as_text=True))
        body = overview.get_json()
        self.assertEqual(len(body["children"]), 1)
        self.assertIsNotNone(body["children"][0]["last_point"])
        self.assertEqual(body["map"]["provider"], "osm")

        today = locations_service.today_for_tz(180).isoformat()
        track = self.client.get(
            f"/api/v1/parent/children/{learner_id}/location?date={today}&tz=180",
            headers=self._headers(parent_token),
        )
        self.assertEqual(track.status_code, 200, track.get_data(as_text=True))
        self.assertEqual(len(track.get_json()["points"]), 1)
        self.assertTrue(track.get_json()["points"][0]["time"])

        forced = self.client.post(
            f"/api/v1/parent/children/{learner_id}/location/force",
            headers=self._headers(parent_token),
        )
        self.assertEqual(forced.status_code, 200, forced.get_data(as_text=True))
        self.assertTrue(forced.get_json()["force_pending"])
        rows = query_all(
            "SELECT * FROM app_notifications WHERE kind = 'location_force'"
        )
        self.assertTrue(rows)

        child_status = self.client.get(
            "/api/v1/location/status", headers=self._headers(child_token)
        ).get_json()
        self.assertTrue(child_status["force_pending"])
        acked = self.client.post(
            "/api/v1/location/force/ack", headers=self._headers(child_token)
        )
        self.assertEqual(acked.status_code, 200, acked.get_data(as_text=True))
        self.assertFalse(acked.get_json()["force_pending"])

        _, _, other_id = self._user("loc_other", "parent")
        other_token = self._login(f"loc_other_{self.suffix}", "api-pass-123")
        forbidden = self.client.get(
            f"/api/v1/parent/children/{learner_id}/location?tz=180",
            headers=self._headers(other_token),
        )
        self.assertEqual(forbidden.status_code, 404)
        forbidden_force = self.client.post(
            f"/api/v1/parent/children/{learner_id}/location/force",
            headers=self._headers(other_token),
        )
        self.assertEqual(forbidden_force.status_code, 404)

    def test_bad_date_and_bad_coordinates(self):
        parent_token, child_token, learner_id = self._pair()
        bad_date = self.client.get(
            f"/api/v1/parent/children/{learner_id}/location?date=31-10-2026",
            headers=self._headers(parent_token),
        )
        self.assertEqual(bad_date.status_code, 400)
        self.assertEqual(bad_date.get_json()["error"], "bad_date")

        bad_point = self.client.post(
            "/api/v1/location/points",
            headers=self._headers(child_token),
            json={"points": [{"lat": "нет", "lon": 27.5, "recorded_at": now_iso()}]},
        )
        self.assertEqual(bad_point.status_code, 400)
        self.assertEqual(bad_point.get_json()["error"], "bad_lat")

    def test_web_pages_and_admin_map_settings(self):
        parent_token, child_token, learner_id = self._pair()
        parent_login = f"loc_p_{self.suffix}"
        parent = auth_service.get_user_by_login(parent_login)
        admin_login, admin_pass, admin_id = self._user("loc_admin", "admin")

        with self.client.session_transaction() as session:
            session["user_id"] = int(parent["id"])
            session["_csrf_token"] = "test-csrf"
        page = self.client.get("/parent/map")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"leaflet.js", page.data)
        self.assertIn(b"geo-force", page.data)
        data = self.client.get(
            f"/parent/map/data?learner_id={learner_id}&tz=180"
        )
        self.assertEqual(data.status_code, 200, data.get_data(as_text=True))
        self.assertTrue(data.get_json()["ok"])
        self.assertIn("map", data.get_json())
        overview = self.client.get("/parent/map/overview?tz=180")
        self.assertEqual(overview.status_code, 200)
        self.assertTrue(overview.get_json()["children"])

        with self.client.session_transaction() as session:
            session.pop("user_id", None)
            session["learner_id"] = learner_id
            session["_csrf_token"] = "test-csrf"
        child_page = self.client.get("/location")
        self.assertEqual(child_page.status_code, 200)
        self.assertIn(b"child_location.js", child_page.data)
        status = self.client.get("/location/status")
        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.get_json()["enabled"])

        # Админка: страница и JSON API настроек карты.
        with self.client.session_transaction() as session:
            session.pop("learner_id", None)
            session["user_id"] = int(admin_id)
            session["_csrf_token"] = "test-csrf"
        admin_page = self.client.get("/admin/map")
        self.assertEqual(admin_page.status_code, 200, admin_page.get_data(as_text=True))
        self.assertIn(b"map-preview", admin_page.data)
        saved = self.client.post(
            "/admin/map",
            data={
                "csrf_token": "test-csrf",
                "provider": "yandex",
                "tile_url": "https://core-renderer-tiles.maps.yandex.net/tiles?l=map&x={x}&y={y}&z={z}&scale=1&lang=ru_RU",
                "attribution": "© Яндекс",
                "crs": "yandex",
                "min_zoom": "2",
                "max_zoom": "18",
                "center_lat": "53.9",
                "center_lon": "27.56",
                "zoom": "12",
            },
            follow_redirects=True,
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(map_settings_service.get_settings()["provider"], "yandex")

        admin_token = self._login(admin_login, admin_pass)
        api_saved = self.client.get(
            "/api/v1/admin/map-settings", headers=self._headers(admin_token)
        )
        self.assertEqual(api_saved.status_code, 200)
        self.assertEqual(api_saved.get_json()["settings"]["crs"], "yandex")

        parent_api_token = self._login(parent_login, "api-pass-123")
        forbidden = self.client.get(
            "/api/v1/admin/map-settings", headers=self._headers(parent_api_token)
        )
        self.assertEqual(forbidden.status_code, 403)


if __name__ == "__main__":
    unittest.main()
