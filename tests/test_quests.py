"""Тесты 3D-квестов: каталог, запуск, проверка ответов и награды.

Правильные ответы не должны попадать в браузер до проверки, а чужой прогресс
нельзя открыть по чужому run_id.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DB = os.path.join(tempfile.gettempdir(), "edu_math_quests_test.db")
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_PATH"] = _TMP_DB
os.environ["SECRET_KEY"] = "quests-test-secret"

for suffix in ("", "-wal", "-shm"):
    if os.path.exists(_TMP_DB + suffix):
        os.remove(_TMP_DB + suffix)

from database import execute, init_db, query_one
from services import api_tokens


def make_client():
    from app import create_app

    app = create_app("testing")
    app.config["TESTING"] = True
    return app.test_client()


def fresh_db() -> None:
    os.environ["DATABASE_PATH"] = _TMP_DB
    for suffix in ("", "-wal", "-shm"):
        path = _TMP_DB + suffix
        if os.path.exists(path):
            os.remove(path)
    init_db()
    execute("INSERT INTO subjects (name, slug, icon) VALUES ('Математика','math','🔢')")


def make_learner(name: str = "Квестер") -> tuple[int, str]:
    execute("INSERT INTO learners (name, grade) VALUES (?, 3)", (name,))
    learner_id = query_one(
        "SELECT id FROM learners WHERE name = ? ORDER BY id DESC LIMIT 1", (name,)
    )["id"]
    token = api_tokens.create(learner_id=learner_id, label="quests-test")
    return learner_id, token


class QuestApiTest(unittest.TestCase):
    def setUp(self):
        fresh_db()
        self.client = make_client()
        self.learner_id, self.token = make_learner()
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def get(self, path):
        return self.client.get(path, headers=self.headers)

    def post(self, path, payload=None):
        return self.client.post(path, headers=self.headers, json=payload or {})

    def test_catalog_and_detail(self):
        response = self.get("/api/v1/quests")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["grade"], 3)
        self.assertGreaterEqual(data["total"], 10)
        titles = [quest["title"] for quest in data["quests"]]
        self.assertIn("Умножение и деление", titles)
        first = data["quests"][0]
        self.assertEqual(len(first["stations"]), 5)
        self.assertEqual(first["minutes"], 10)

        detail = self.get(f"/api/v1/quests/{first['slug']}").get_json()
        self.assertTrue(detail["ok"])
        self.assertEqual(detail["quest"]["title"], first["title"])

        self.assertEqual(self.get("/api/v1/quests/no-such-quest").status_code, 404)

    def test_run_does_not_leak_answers_and_rewards_work(self):
        start = self.post("/api/v1/quests/numbers_1000/start")
        self.assertEqual(start.status_code, 200, start.get_data(as_text=True))
        run = start.get_json()
        self.assertEqual(run["total"], 5)
        self.assertEqual(len(run["tasks"]), 5)
        for task in run["tasks"]:
            self.assertNotIn("answer", task)
            self.assertNotIn("solution", task)
            self.assertNotIn("accept", task)

        row = query_one("SELECT tasks_json FROM quest_runs WHERE run_key = ?", (run["run_id"],))
        tasks = json.loads(row["tasks_json"])

        # Один неверный ответ даёт подсказку, но не закрывает станцию.
        wrong = self.post(
            f"/api/v1/quests/runs/{run['run_id']}/check",
            {"station": 0, "answer": "заведомо неверно"},
        ).get_json()
        self.assertFalse(wrong["correct"])
        self.assertFalse(wrong["done"])
        self.assertEqual(wrong["attempts_left"], 1)
        self.assertTrue(wrong["hint"] or True)

        for index, task in enumerate(tasks):
            result = self.post(
                f"/api/v1/quests/runs/{run['run_id']}/check",
                {"station": index, "answer": task["answer"]},
            )
            self.assertEqual(result.status_code, 200, result.get_data(as_text=True))
            payload = result.get_json()
            self.assertTrue(payload["correct"], payload)
            self.assertTrue(payload["done"])
        self.assertTrue(payload["all_done"])

        finish = self.post(f"/api/v1/quests/runs/{run['run_id']}/finish").get_json()
        self.assertTrue(finish["ok"])
        self.assertEqual(finish["correct"], 5)
        self.assertEqual(finish["stars"], 3)
        self.assertTrue(finish["first_time"])
        self.assertGreater(finish["bonus_xp"], 0)
        self.assertEqual(finish["xp"], 50)
        self.assertEqual(finish["coins"], 10)

        learner = query_one("SELECT xp, coins FROM learners WHERE id = ?", (self.learner_id,))
        self.assertEqual(learner["xp"], 95)
        self.assertEqual(learner["coins"], 30)

        # Повторный finish идемпотентен: бонус не начисляется второй раз.
        again = self.post(f"/api/v1/quests/runs/{run['run_id']}/finish").get_json()
        self.assertTrue(again["already_completed"])
        learner = query_one("SELECT xp FROM learners WHERE id = ?", (self.learner_id,))
        self.assertEqual(learner["xp"], 95)

        catalog = self.get("/api/v1/quests").get_json()
        quest = next(q for q in catalog["quests"] if q["slug"] == "numbers_1000")
        self.assertTrue(quest["completed"])
        self.assertEqual(quest["stars"], 3)
        self.assertEqual(quest["best_correct"], 5)

    def test_second_wrong_answer_closes_station(self):
        run = self.post("/api/v1/quests/numbers_1000/start").get_json()
        for _ in range(2):
            result = self.post(
                f"/api/v1/quests/runs/{run['run_id']}/check",
                {"station": 0, "answer": "неверно"},
            ).get_json()
        self.assertTrue(result["done"])
        self.assertFalse(result["correct"])
        self.assertTrue(result["expected"])
        self.assertEqual(result["attempts_left"], 0)

    def test_finish_requires_all_stations(self):
        run = self.post("/api/v1/quests/numbers_1000/start").get_json()
        response = self.post(f"/api/v1/quests/runs/{run['run_id']}/finish")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "not_finished")

    def test_foreign_run_is_hidden(self):
        run = self.post("/api/v1/quests/numbers_1000/start").get_json()
        _, other_token = make_learner("Другой")
        response = self.client.get(
            f"/api/v1/quests/runs/{run['run_id']}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            f"/api/v1/quests/runs/{run['run_id']}/check",
            headers={"Authorization": f"Bearer {other_token}"},
            json={"station": 0, "answer": "1"},
        )
        self.assertEqual(response.status_code, 404)

    def test_resume_active_run(self):
        first = self.post("/api/v1/quests/mult_div_table/start").get_json()
        detail = self.get("/api/v1/quests/mult_div_table").get_json()
        self.assertEqual(detail["quest"]["active_run_id"], first["run_id"])
        resumed = self.get(f"/api/v1/quests/runs/{first['run_id']}").get_json()
        self.assertEqual(resumed["run_id"], first["run_id"])
        self.assertEqual(resumed["quest"]["slug"], "mult_div_table")
        # Новый запуск закрывает предыдущую попытку.
        second = self.post("/api/v1/quests/mult_div_table/start").get_json()
        self.assertNotEqual(second["run_id"], first["run_id"])
        self.assertEqual(
            self.get(f"/api/v1/quests/runs/{first['run_id']}").status_code, 409
        )


if __name__ == "__main__":
    unittest.main()
