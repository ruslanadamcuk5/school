"""Тесты геолокации: согласие, точки, трек, часовой пояс и доступ родителей."""
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
from services import notifications as notifications_service  # noqa: E402


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

    def test_sharing_is_off_by_default(self):
        info = locations_service.settings(self.learner_id)
        self.assertFalse(info["enabled"])
        self.assertEqual(info["retention_days"], 14)
        with self.assertRaises(locations_service.LocationError) as ctx:
            locations_service.record_points(
                self.learner_id,
                [{"lat": 53.9, "lon": 27.5, "recorded_at": now_iso()}],
            )
        self.assertEqual(ctx.exception.code, "sharing_off")
        self.assertEqual(ctx.exception.status, 409)

    def test_enable_record_dedupe_and_clear(self):
        locations_service.set_sharing(self.learner_id, True)
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

        removed = locations_service.clear_history(self.learner_id)
        self.assertEqual(removed, 1)
        self.assertIsNone(locations_service.latest_point(self.learner_id))

    def test_validation_and_limits(self):
        locations_service.set_sharing(self.learner_id, True)
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
        # 22:30 UTC — это уже следующий день при поясе +03:00.
        self.assertEqual(locations_service._local_label("2026-10-30 22:30:00", 180), "01:30")
        self.assertEqual(locations_service.clamp_tz(9999), 840)

    def test_trail_only_returns_selected_day(self):
        locations_service.set_sharing(self.learner_id, True)
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
    def test_status_and_consent_flow(self):
        _, child_token, _ = self._pair()
        status = self.client.get("/api/v1/location/status", headers=self._headers(child_token))
        self.assertEqual(status.status_code, 200, status.get_data(as_text=True))
        self.assertFalse(status.get_json()["enabled"])

        blocked = self.client.post(
            "/api/v1/location/points",
            headers=self._headers(child_token),
            json={"points": [{"lat": 53.9, "lon": 27.5, "recorded_at": now_iso()}]},
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.get_json()["error"], "sharing_off")

        enabled = self.client.put(
            "/api/v1/location/status",
            headers=self._headers(child_token),
            json={"enabled": True},
        )
        self.assertEqual(enabled.status_code, 200, enabled.get_data(as_text=True))
        self.assertTrue(enabled.get_json()["enabled"])

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

        cleared = self.client.delete(
            "/api/v1/location/history", headers=self._headers(child_token)
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.get_json()["removed"], 1)

    def test_parent_sees_track_and_other_parent_cannot(self):
        parent_token, child_token, learner_id = self._pair()
        self.client.put(
            "/api/v1/location/status",
            headers=self._headers(child_token),
            json={"enabled": True},
        )
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
        children = overview.get_json()["children"]
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0]["last_point"])

        today = locations_service.today_for_tz(180).isoformat()
        track = self.client.get(
            f"/api/v1/parent/children/{learner_id}/location?date={today}&tz=180",
            headers=self._headers(parent_token),
        )
        self.assertEqual(track.status_code, 200, track.get_data(as_text=True))
        body = track.get_json()
        self.assertEqual(len(body["points"]), 1)
        self.assertTrue(body["points"][0]["time"])

        _, _, other_id = self._user("loc_other", "parent")
        other_token = self._login(f"loc_other_{self.suffix}", "api-pass-123")
        forbidden = self.client.get(
            f"/api/v1/parent/children/{learner_id}/location?tz=180",
            headers=self._headers(other_token),
        )
        self.assertEqual(forbidden.status_code, 404)

        requested = self.client.post(
            f"/api/v1/parent/children/{learner_id}/location/request",
            headers=self._headers(parent_token),
        )
        self.assertEqual(requested.status_code, 200, requested.get_data(as_text=True))
        rows = query_all(
            "SELECT * FROM app_notifications WHERE kind = 'location_request'"
        )
        self.assertTrue(rows)

    def test_bad_date_and_bad_coordinates(self):
        parent_token, child_token, learner_id = self._pair()
        self.client.put(
            "/api/v1/location/status",
            headers=self._headers(child_token),
            json={"enabled": True},
        )
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

    def test_web_pages(self):
        parent_token, child_token, learner_id = self._pair()
        parent_login = f"loc_p_{self.suffix}"
        parent = auth_service.get_user_by_login(parent_login)
        self.client.put(
            "/api/v1/location/status",
            headers=self._headers(child_token),
            json={"enabled": True},
        )
        with self.client.session_transaction() as session:
            session["user_id"] = int(parent["id"])
            session["_csrf_token"] = "test-csrf"
        page = self.client.get("/parent/map")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"leaflet.js", page.data)
        data = self.client.get(
            f"/parent/map/data?learner_id={learner_id}&tz=180"
        )
        self.assertEqual(data.status_code, 200, data.get_data(as_text=True))
        self.assertTrue(data.get_json()["ok"])
        overview = self.client.get("/parent/map/overview?tz=180")
        self.assertEqual(overview.status_code, 200)
        self.assertTrue(overview.get_json()["children"])

        # Страница ребёнка: согласие уже включено, интерфейс открывается.
        with self.client.session_transaction() as session:
            session.pop("user_id", None)
            session["learner_id"] = learner_id
        child_page = self.client.get("/location")
        self.assertEqual(child_page.status_code, 200)
        self.assertIn(b"child_location.js", child_page.data)
        status = self.client.get("/location/status")
        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.get_json()["enabled"])


if __name__ == "__main__":
    unittest.main()
