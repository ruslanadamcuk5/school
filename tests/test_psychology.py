"""Тесты раздела «Школьная психология»."""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault(
    "DATABASE_PATH",
    os.path.join(tempfile.gettempdir(), "edu_math_psychology_test.db"),
)
os.environ.setdefault("SECRET_KEY", "test-secret")

from services import psychology as psych  # noqa: E402
from services import psychology_catalog as catalog  # noqa: E402


class TestCatalog(unittest.TestCase):
    def test_every_band_has_full_set(self):
        for band in catalog.BANDS:
            tests = catalog.tests_for_grade(band["grades"][0])
            self.assertEqual(len(tests), 4, band["key"])
            self.assertEqual(
                {test["category"] for test in tests},
                {"abilities", "activities", "problems", "development"},
            )

    def test_questions_and_scales_are_valid(self):
        answered = 0
        for test in catalog.TESTS:
            self.assertTrue(test["questions"], test["slug"])
            for key in test["scales"]:
                self.assertIn(key, catalog.SCALES, test["slug"])
            for question in test["questions"]:
                self.assertEqual(len(question["options"]), 4, question["text"])
                for option in question["options"]:
                    self.assertTrue(option["scores"])
                    for key, value in option["scores"].items():
                        self.assertIn(key, test["scales"])
                        self.assertGreaterEqual(value, 0)
                        self.assertLessEqual(value, 3)
                answered += 1
        self.assertGreater(answered, 80)

    def test_sources_and_disclaimer(self):
        self.assertIn("Республики Беларусь", catalog.SOURCE_NOTE)
        self.assertTrue(catalog.DISCLAIMER)


class TestEvaluation(unittest.TestCase):
    def _answers(self, test, choice):
        return {str(index): choice for index in range(len(test["questions"]))}

    def test_high_and_low_results(self):
        for test in catalog.TESTS:
            high = psych.evaluate(test, self._answers(test, 3), 5)
            self.assertTrue(high["headline"])
            self.assertEqual(len(high["scales"]), len(test["scales"]))
            self.assertTrue(high["recommendations"])
            for scale in high["scales"]:
                self.assertGreaterEqual(scale["percent"], 0)
                self.assertLessEqual(scale["percent"], 100)
            low = psych.evaluate(test, self._answers(test, 0), 5)
            self.assertTrue(low["summary"])

    def test_problem_test_marks_attention(self):
        test = catalog.get_test("middle-problems")
        result = psych.evaluate(test, {str(i): 3 for i in range(8)}, 7)
        self.assertTrue(
            any(item["kind"] == "attention" for item in result["recommendations"])
        )

    def test_leader_recommendation(self):
        test = catalog.get_test("middle-development")
        result = psych.evaluate(test, {str(i): 3 for i in range(8)}, 7)
        titles = [item["title"] for item in result["recommendations"]]
        self.assertIn("Обратите внимание: ваш ребёнок — лидер", titles)

    def test_missing_answer_rejected(self):
        test = catalog.get_test("primary-abilities")
        with self.assertRaises(ValueError):
            psych.evaluate(test, {"0": 1}, 3)


class TestPsychologyApi(unittest.TestCase):
    def setUp(self):
        from app import create_app

        self.app = create_app("testing")
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.suffix = str(int(time.time() * 1000))[-8:]

    def _student(self, grade=6):
        from services import api_tokens, auth, learners

        login = f"psy_stu_{self.suffix}"
        user_id = auth.create_user(login, "math2025", "student", first_name="Петя")
        learner_id = learners.ensure_learner_for_user(auth.get_user(user_id))
        learners.update_learner(learner_id, grade=grade)
        token = api_tokens.create(user_id=user_id, label="psy-test")
        return user_id, learner_id, {"Authorization": f"Bearer {token}"}

    def _family_learner(self, grade=2):
        from services import api_tokens, learners

        learner_id = learners.create_learner(f"Семья {self.suffix}", "🦊", grade)
        token = api_tokens.create(learner_id=learner_id, label="psy-family")
        return learner_id, {"Authorization": f"Bearer {token}"}

    def _parent(self, child_user_id):
        from services import api_tokens, auth

        login = f"psy_par_{self.suffix}"
        user_id = auth.create_user(login, "math2025", "parent", first_name="Мама")
        auth.link_parent_child(user_id, child_user_id)
        token = api_tokens.create(user_id=user_id, label="psy-parent")
        return user_id, {"Authorization": f"Bearer {token}"}

    def _pass_test(self, headers, index=0):
        listing = self.client.get("/api/v1/psychology/tests", headers=headers).get_json()
        test = listing["tests"][index]
        detail = self.client.get(
            f"/api/v1/psychology/tests/{test['slug']}", headers=headers
        ).get_json()
        answers = {str(question["id"]): 3 for question in detail["questions"]}
        response = self.client.post(
            f"/api/v1/psychology/tests/{test['slug']}",
            headers=headers,
            json={"answers": answers},
        )
        return test, detail, response

    def test_student_flow(self):
        _, _, headers = self._student(6)
        listing = self.client.get("/api/v1/psychology/tests", headers=headers)
        self.assertEqual(listing.status_code, 200)
        data = listing.get_json()
        self.assertEqual(data["grade"], 6)
        self.assertEqual(data["band"]["key"], "middle")
        self.assertEqual(len(data["tests"]), 4)

        test, detail, response = self._pass_test(headers)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        result = response.get_json()["result"]
        self.assertTrue(result["headline"])
        self.assertEqual(result["test_slug"], test["slug"])
        self.assertTrue(result["scales"])
        self.assertEqual(result["audience"], "student")
        self.assertNotIn("parent", result["recommendations"][0])

        detail_result = self.client.get(
            f"/api/v1/psychology/results/{result['id']}", headers=headers
        )
        self.assertEqual(detail_result.status_code, 200)
        self.assertEqual(detail_result.get_json()["result"]["id"], result["id"])

        again = self.client.get("/api/v1/psychology/tests", headers=headers).get_json()
        completed = [item for item in again["tests"] if item["slug"] == test["slug"]][0]
        self.assertTrue(completed["completed"])
        self.assertEqual(completed["attempts"], 1)
        self.assertTrue(again["history"])

    def test_family_learner_can_pass(self):
        _, headers = self._family_learner(2)
        listing = self.client.get("/api/v1/psychology/tests", headers=headers).get_json()
        self.assertEqual(listing["band"]["key"], "primary")
        _, _, response = self._pass_test(headers)
        self.assertEqual(response.status_code, 200)

    def test_parent_sees_results_and_notifications(self):
        child_id, _, headers = self._student(7)
        parent_id, parent_headers = self._parent(child_id)
        _, _, response = self._pass_test(headers)
        result_id = response.get_json()["result"]["id"]

        overview = self.client.get(
            "/api/v1/psychology/parent/overview", headers=parent_headers
        )
        self.assertEqual(overview.status_code, 200)
        children = overview.get_json()["children"]
        self.assertEqual(len(children), 1)
        child = children[0]
        self.assertTrue(child["results"])
        self.assertTrue(child["recommendations"])
        self.assertGreaterEqual(child["stats"]["tests"], 1)

        detail = self.client.get(
            f"/api/v1/psychology/parent/results/{result_id}", headers=parent_headers
        )
        self.assertEqual(detail.status_code, 200)
        payload = detail.get_json()["result"]
        self.assertEqual(payload["audience"], "parent")
        self.assertEqual(payload["learner"]["id"], children[0]["learner"]["id"])

        notes = self.client.get("/api/v1/notifications", headers=parent_headers).get_json()
        kinds = {item["kind"] for item in notes["notifications"]}
        self.assertIn("psych_result", kinds)
        self.assertIn("psych_recommendation", kinds)
        self.assertGreaterEqual(notes["unread"], 2)

    def test_other_parent_cannot_read_result(self):
        _, _, headers = self._student(8)
        _, _, response = self._pass_test(headers)
        result_id = response.get_json()["result"]["id"]

        from services import api_tokens, auth

        login = f"psy_other_{self.suffix}"
        other_id = auth.create_user(login, "math2025", "parent", first_name="Другой")
        token = api_tokens.create(user_id=other_id, label="other")
        detail = self.client.get(
            f"/api/v1/psychology/parent/results/{result_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(detail.status_code, 404)

    def test_wrong_grade_rejected(self):
        _, _, headers = self._student(3)
        response = self.client.get(
            "/api/v1/psychology/tests/senior-problems", headers=headers
        )
        self.assertEqual(response.status_code, 403)

    def test_status_endpoint(self):
        response = self.client.get("/api/v1/psychology/status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["enabled"])
        self.assertEqual(len(data["bands"]), 3)
        self.assertEqual(len(data["categories"]), 4)


if __name__ == "__main__":
    unittest.main()
