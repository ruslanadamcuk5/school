"""YouTube: разбор ссылок, подбор видео, кэш, ИИ и выдача в API/на сайте."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DB = os.path.join(tempfile.gettempdir(), "edu_math_youtube_test.db")
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_PATH"] = _TMP_DB
os.environ["SECRET_KEY"] = "youtube-test-secret"

from database import execute, init_db, query_all, query_one  # noqa: E402
from services import youtube as youtube_service  # noqa: E402


class YouTubeTestCase(unittest.TestCase):
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

    def setUp(self):
        os.environ["DATABASE_PATH"] = _TMP_DB
        for suffix in ("", "-wal", "-shm"):
            path = _TMP_DB + suffix
            if os.path.exists(path):
                os.remove(path)
        init_db()
        subject_id = execute(
            "INSERT INTO subjects (name, slug, icon) VALUES ('Математика', 'math', '🔢')"
        )
        execute(
            """INSERT INTO topics
                   (slug, title, grade, subject_id, source, kind, description)
               VALUES ('fractions', 'Обыкновенные дроби', 5, ?, 'curriculum',
                       'practice', 'Доли, сравнение дробей, сложение дробей.')""",
            (subject_id,),
        )
        youtube_service.save_settings(
            {
                "enabled": True,
                "api_key": "test-youtube-key",
                "region_code": "BY",
                "relevance_language": "ru",
                "max_per_topic": 2,
                "min_duration": 60,
                "max_duration": 1800,
                "cache_days": 14,
                "ai_ranking": False,
            }
        )


def video(
    video_id: str,
    title: str,
    *,
    channel: str = "Школа",
    duration: str = "PT10M",
    embeddable: bool = True,
    privacy: str = "public",
    description: str = "",
) -> dict:
    return {
        "video_id": video_id,
        "title": title,
        "channel": channel,
        "description": description,
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        "duration": youtube_service.parse_duration(duration),
        "embeddable": embeddable,
        "privacy": privacy,
        "published_at": "2026-01-01T00:00:00Z",
        "region_blocked": False,
    }


class TestParsing(unittest.TestCase):
    def test_video_id_from_links(self):
        expected = "dQw4w9WgXcQ"
        for value in (
            expected,
            f"https://www.youtube.com/watch?v={expected}&t=10",
            f"https://youtu.be/{expected}?si=abc",
            f"https://m.youtube.com/watch?v={expected}",
            f"https://www.youtube.com/shorts/{expected}",
            f"https://www.youtube.com/embed/{expected}",
            f"https://www.youtube-nocookie.com/embed/{expected}",
        ):
            self.assertEqual(youtube_service.parse_video_id(value), expected, value)

    def test_bad_links(self):
        for value in ("", "https://example.com/watch?v=dQw4w9WgXcQ", "abc", "https://youtu.be/too-short"):
            self.assertEqual(youtube_service.parse_video_id(value), "", value)

    def test_duration(self):
        self.assertEqual(youtube_service.parse_duration("PT1H2M3S"), 3723)
        self.assertEqual(youtube_service.parse_duration("PT12M"), 720)
        self.assertEqual(youtube_service.parse_duration("PT45S"), 45)
        self.assertEqual(youtube_service.parse_duration("bad"), 0)
        self.assertEqual(youtube_service.format_duration(3723), "1:02:03")
        self.assertEqual(youtube_service.format_duration(725), "12:05")


class TestSelection(YouTubeTestCase):
    def test_only_relevant_public_embeddable_videos_are_saved(self):
        candidates = [
            video("good0000001", "Обыкновенные дроби — объяснение для 5 класса", duration="PT9M"),
            video("cats0000001", "Смешные коты и приколы", channel="Развлечения"),
            video("grade000001", "Дроби 6 класс: сложение дробей", duration="PT8M"),
            video("private0001", "Дроби 5 класс", privacy="private"),
            video("noembed0001", "Дроби 5 класс", embeddable=False),
        ]
        with mock.patch.object(youtube_service, "_ai_available", return_value=False):
            with mock.patch.object(
                youtube_service, "_search", return_value=([c["video_id"] for c in candidates], None)
            ):
                with mock.patch.object(
                    youtube_service, "_fetch_details", return_value=(candidates, None)
                ):
                    videos, error = youtube_service.refresh_topic_videos(
                        "fractions", settings=youtube_service.get_settings()
                    )

        self.assertIsNone(error)
        self.assertEqual([item["video_id"] for item in videos], ["good0000001"])
        rows = query_all("SELECT * FROM topic_videos WHERE topic_slug = 'fractions'")
        self.assertEqual([row["video_id"] for row in rows], ["good0000001"])
        cache = query_one("SELECT * FROM topic_video_cache WHERE topic_slug = 'fractions'")
        self.assertEqual(cache["status"], "ok")
        self.assertGreater(cache["selected"], 0)

    def test_cached_videos_are_returned_without_second_search(self):
        good = video("good0000002", "Обыкновенные дроби, урок для 5 класса")
        with mock.patch.object(youtube_service, "_ai_available", return_value=False):
            with mock.patch.object(youtube_service, "_search", return_value=(["good0000002"], None)) as search:
                with mock.patch.object(
                    youtube_service, "_fetch_details", return_value=([good], None)
                ):
                    first = youtube_service.videos_for_topic("fractions")
                    after_first = search.call_count
                    second = youtube_service.videos_for_topic("fractions")
        self.assertTrue(first["youtube_enabled"])
        self.assertEqual(first["videos"][0]["video_id"], "good0000002")
        self.assertEqual(second["videos"], first["videos"])
        # Первый подбор может сделать до двух поисковых запросов (если
        # релевантных роликов меньше нужного). Второй обязан брать кэш.
        self.assertEqual(search.call_count, after_first)

    def test_ai_cannot_invent_video_ids(self):
        candidates = [video("good0000003", "Дроби 5 класс — простое объяснение")]
        with mock.patch("services.ai.chat", return_value=(
            '{"video_ids": ["fake0000001", "good0000003"]}', None
        )):
            chosen = youtube_service._ai_rank(
                {"slug": "fractions", "title": "Обыкновенные дроби", "grade": 5},
                candidates,
                2,
            )
        self.assertEqual(chosen, ["good0000003"])

    def test_error_keeps_old_cache_and_is_retried_soon(self):
        good = video("good0000004", "Дроби 5 класс объяснение")
        with mock.patch.object(youtube_service, "_ai_available", return_value=False):
            with mock.patch.object(youtube_service, "_search", return_value=(["good0000004"], None)):
                with mock.patch.object(
                    youtube_service, "_fetch_details", return_value=([good], None)
                ):
                    youtube_service.refresh_topic_videos(
                        "fractions", settings=youtube_service.get_settings()
                    )
            with mock.patch.object(
                youtube_service, "_search", return_value=([], "YouTube API 403: quotaExceeded")
            ):
                videos, error = youtube_service.refresh_topic_videos(
                    "fractions", settings=youtube_service.get_settings()
                )
        self.assertIn("quota", error.lower())
        self.assertEqual(videos[0]["video_id"], "good0000004")
        cache = query_one("SELECT * FROM topic_video_cache WHERE topic_slug = 'fractions'")
        self.assertEqual(cache["status"], "error")


class TestManualAndAdmin(YouTubeTestCase):
    def test_manual_video_has_priority_and_is_not_removed_by_cache_clear(self):
        manual = video("manual00001", "Дроби: объяснение учителя", channel="Наш класс")
        with mock.patch.object(
            youtube_service, "_fetch_details", return_value=([manual], None)
        ):
            added, error = youtube_service.add_manual_video(
                "fractions", "https://youtu.be/manual00001"
            )
        self.assertIsNone(error)
        self.assertEqual(added["video_id"], "manual00001")
        self.assertEqual(youtube_service.cached_videos("fractions")[0]["video_id"], "manual00001")

        removed = youtube_service.clear_cache()
        self.assertEqual(removed["videos"], 0)
        self.assertEqual(youtube_service.cached_videos("fractions")[0]["video_id"], "manual00001")

    def test_manual_video_rejects_non_embeddable(self):
        not_embeddable = video("manual00002", "Дроби", embeddable=False)
        with mock.patch.object(
            youtube_service, "_fetch_details", return_value=([not_embeddable], None)
        ):
            added, error = youtube_service.add_manual_video(
                "fractions", "https://youtu.be/manual00002"
            )
        self.assertIsNone(added)
        self.assertIn("встраивание", error)

    def test_blocked_auto_video_does_not_return_after_refresh(self):
        good = video("good0000005", "Обыкновенные дроби 5 класс")
        with mock.patch.object(youtube_service, "_ai_available", return_value=False):
            with mock.patch.object(youtube_service, "_search", return_value=(["good0000005"], None)):
                with mock.patch.object(
                    youtube_service, "_fetch_details", return_value=([good], None)
                ):
                    youtube_service.refresh_topic_videos(
                        "fractions", settings=youtube_service.get_settings()
                    )
        row = query_one("SELECT * FROM topic_videos WHERE video_id = 'good0000005'")
        youtube_service.block_video(row["id"])
        with mock.patch.object(youtube_service, "_ai_available", return_value=False):
            with mock.patch.object(youtube_service, "_search", return_value=(["good0000005"], None)):
                with mock.patch.object(
                    youtube_service, "_fetch_details", return_value=([good], None)
                ):
                    videos, _ = youtube_service.refresh_topic_videos(
                        "fractions", settings=youtube_service.get_settings()
                    )
        self.assertEqual(videos, [])


class TestWebAndApi(YouTubeTestCase):
    def setUp(self):
        super().setUp()
        from app import create_app

        self.app = create_app("testing")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.csrf = self._csrf()
        response = self.client.post(
            "/learners",
            data={
                "name": "Третьеклашка",
                "avatar": "🦊",
                "grade": "3",
                "csrf_token": self.csrf,
            },
        )
        self.assertEqual(response.status_code, 302)

        # Мобильный API не использует cookie-сессию: создаём семейный профиль
        # по X-Device-Id и дальше передаём Bearer-токен.
        api_response = self.client.post(
            "/api/v1/learners",
            json={"name": "Третьеклашка", "avatar": "🦊", "grade": 3},
            headers={"X-Device-Id": "youtube-test-device"},
        )
        self.assertEqual(api_response.status_code, 201)
        self.token = api_response.get_json()["token"]

    def _csrf(self) -> str:
        html = self.client.get("/").get_data(as_text=True)
        marker = 'name="csrf-token" content="'
        start = html.find(marker) + len(marker)
        return html[start : html.find('"', start)]

    def test_web_page_and_json_endpoint_show_cached_video(self):
        execute(
            """INSERT INTO topic_videos
                   (topic_slug, video_id, title, channel, duration, source)
               VALUES ('fractions', 'web00000001', 'Дроби 5 класс', 'Школа', 600, 'manual')"""
        )
        page = self.client.get("/topic/fractions")
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn("Видео по теме", html)
        self.assertIn("youtube-nocookie.com/embed/web00000001", html)

        response = self.client.get("/topic/fractions/videos")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["videos"][0]["video_id"], "web00000001")

    def test_api_endpoint_returns_videos_and_csp_allows_youtube(self):
        execute(
            """INSERT INTO topic_videos
                   (topic_slug, video_id, title, channel, duration, source)
               VALUES ('fractions', 'api00000001', 'Дроби 5 класс', 'Школа', 600, 'manual')"""
        )
        response = self.client.get(
            "/api/v1/topics/fractions/videos",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["youtube_enabled"])
        self.assertEqual(payload["videos"][0]["video_id"], "api00000001")

        health = self.client.get("/healthz")
        csp = health.headers["Content-Security-Policy"]
        self.assertIn("frame-src", csp)
        self.assertIn("https://www.youtube-nocookie.com", csp)

    def test_disabled_youtube_hides_block(self):
        youtube_service.save_settings(
            {"enabled": False, "api_key": "test-youtube-key", "ai_ranking": False},
            keep_key=True,
        )
        page = self.client.get("/topic/fractions").get_data(as_text=True)
        self.assertNotIn("Видео по теме", page)


if __name__ == "__main__":
    unittest.main()
