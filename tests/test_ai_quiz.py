"""Вопросы ИИ по теме: разбор ответа модели, проверка ответов и кэш."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("APP_ENV", "testing")
os.environ["DATABASE_PATH"] = os.path.join(
    tempfile.gettempdir(), "edu_math_ai_quiz_test.db"
)
os.environ["SECRET_KEY"] = "test-secret"

from content.answer import check_answer  # noqa: E402
from database import init_db, reset_database  # noqa: E402
from services import ai_quiz, reading_quiz, text_quality  # noqa: E402

RUSSIAN_TEXT = (
    "Земля — наш общий дом. На планете живут люди разных стран и народов. "
    "У каждого народа есть свой язык, обычаи и культура. Люди берегут природу "
    "и помогают друг другу. На карте можно увидеть материки и океаны."
)

MOJIBAKE = (
    "ɁȿɆɅə  ²  ɇȺɒ  ɈȻɓɂɃ  ȾɈɆ ɇɚɡɨɜɢɬɟ ɧɚɫɟɥɺɧɧɵɣ ɩɭɧɤɬ ɢ ɫɬɪɚɧɭ   "
    "ɝɞɟ ɜɵ ɠɢ  ɜɺ   ɬɟ  ɉɨɱɟɦɭ ɠɢɬɟɥɟɣ ɪɚɡɧɵɯ ɫɬɪɚɧ ɡɨɜɭɬ ɡɟɦɥɹɧɚɦɢ"
)

GOOD_JSON = """```json
[
  {"question": "Что общего у народов Земли?",
   "options": ["Общий дом — планета Земля", "Один язык", "Одна страна", "Один обычай"],
   "answer": "Общий дом — планета Земля",
   "explanation": "Люди живут на одной планете и берегут её."},
  {"question": "Что есть у каждого народа?",
   "options": ["Свой язык и обычаи", "Одна валюта", "Один президент", "Одна школа"],
   "answer": "Свой язык и обычаи",
   "explanation": "У каждого народа свои язык, обычаи и культура."}
]
```"""


def topic(**overrides):
    base = {
        "slug": "world-earth",
        "title": "Земля — наш общий дом",
        "subject_slug": "world",
        "subject_name": "Человек и мир",
        "subject_id": 1,
        "grade": 3,
        "description": "Страны и народы, общий дом человечества.",
        "content_json": None,
    }
    base.update(overrides)
    return base


class TestTextQuality(unittest.TestCase):

    def test_russian_text_is_readable(self):
        self.assertTrue(text_quality.readable(RUSSIAN_TEXT, "cyr"))

    def test_mojibake_is_not_readable(self):
        self.assertFalse(text_quality.readable(MOJIBAKE, "cyr"))

    def test_english_text_is_not_readable_as_russian(self):
        self.assertFalse(text_quality.readable(
            "People live in different countries and speak different languages.",
            "cyr",
        ))


class TestValidation(unittest.TestCase):

    def test_answer_must_be_one_of_options(self):
        items = ai_quiz.validate([
            {"question": "Какой ответ верный?",
             "options": ["Один", "Два", "Три", "Четыре"],
             "answer": "Пять",
             "explanation": "Так."}
        ])
        self.assertEqual(items, [])

    def test_meta_questions_are_rejected(self):
        items = ai_quiz.validate([
            {"question": "На какой странице пособия эта тема?",
             "options": ["1", "2", "3", "4"],
             "answer": "2",
             "explanation": "В пособии."},
            {"question": "К какому предмету относится тема?",
             "options": ["Математика", "Русский язык", "Человек и мир", "ИЗО"],
             "answer": "Человек и мир",
             "explanation": "Это предмет."},
        ])
        self.assertEqual(items, [])

    def test_duplicate_options_are_rejected(self):
        items = ai_quiz.validate([
            {"question": "Сколько будет два плюс два?",
             "options": ["4", "4", "5", "6"],
             "answer": "4",
             "explanation": "Счёт."}
        ])
        self.assertEqual(items, [])

    def test_valid_item_is_normalized(self):
        items = ai_quiz.validate([
            {"question": "Что есть у каждого народа?",
             "options": ["Язык и обычаи", "Одна валюта", "Один президент", "Одна школа"],
             "answer": "язык и обычаи",
             "explanation": "У народа свои язык и обычаи."}
        ])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["answer"], "Язык и обычаи")


class TestQuestions(unittest.TestCase):

    def setUp(self):
        init_db()
        reset_database()
        self.patches = [
            mock.patch.object(ai_quiz.ai_service, "is_enabled", return_value=True),
            mock.patch.object(ai_quiz.ai_service, "log_request", return_value=None),
            mock.patch.object(
                ai_quiz.ai_service, "get_settings", return_value={"model": "test"}
            ),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()

    def test_questions_have_choices_and_check_correctly(self):
        with mock.patch.object(
            ai_quiz.ai_service, "chat", return_value=(GOOD_JSON, None)
        ):
            tasks = ai_quiz.questions(topic(), 2)
        self.assertEqual(len(tasks), 2)
        for item in tasks:
            self.assertEqual(item["answer_type"], "choice")
            self.assertEqual(len(item["choices"]), 4)
            self.assertIn(item["answer"], item["choices"])
            self.assertTrue(check_answer(item["answer"], item)[0])
            wrong = next(c for c in item["choices"] if c != item["answer"])
            self.assertFalse(check_answer(wrong, item)[0])

    def test_questions_are_cached_per_topic(self):
        with mock.patch.object(
            ai_quiz.ai_service, "chat", return_value=(GOOD_JSON, None)
        ) as chat:
            ai_quiz.questions(topic(), 2)
            ai_quiz.questions(topic(), 2)
        self.assertEqual(chat.call_count, 1)

    def test_disabled_ai_returns_nothing(self):
        with mock.patch.object(ai_quiz.ai_service, "is_enabled", return_value=False):
            self.assertEqual(ai_quiz.questions(topic(), 4), [])

    def test_broken_model_answer_is_ignored(self):
        with mock.patch.object(
            ai_quiz.ai_service, "chat", return_value=("не JSON", None)
        ):
            self.assertEqual(ai_quiz.questions(topic(), 4), [])


class TestReadingQuizUsesAi(unittest.TestCase):

    def setUp(self):
        init_db()
        reset_database()

    def test_build_questions_prefers_ai_and_drops_page_questions(self):
        cached = json.dumps([[8, RUSSIAN_TEXT]], ensure_ascii=False)
        with mock.patch.object(
            ai_quiz.ai_service, "is_enabled", return_value=True
        ), mock.patch.object(
            ai_quiz.ai_service, "chat", return_value=(GOOD_JSON, None)
        ), mock.patch.object(
            ai_quiz.ai_service, "log_request", return_value=None
        ), mock.patch.object(
            ai_quiz.ai_service, "get_settings", return_value={"model": "test"}
        ):
            questions = reading_quiz.build_questions(
                topic(content_json=cached), 2
            )
        self.assertEqual(len(questions), 2)
        for item in questions:
            self.assertNotIn("страниц", item["question"].lower())
            self.assertNotIn("предмету", item["question"].lower())
            self.assertIn("choices", item)

    def test_offline_fallback_has_no_meta_questions(self):
        from database import execute

        for slug, title in (("world-two", "Страны мира"), ("world-three", "Народы мира")):
            execute(
                """INSERT INTO topics (slug, title, grade, subject_id, description)
                   VALUES (?, ?, 3, 1, ?)""",
                (slug, title, f"Описание темы «{title}» для проверки."),
            )
        with mock.patch.object(
            ai_quiz.ai_service, "is_enabled", return_value=False
        ):
            questions = reading_quiz.build_questions(topic(), 4)
        self.assertTrue(questions)
        for item in questions:
            self.assertNotIn("страниц", item["question"].lower())
            self.assertNotIn("предмету", item["question"].lower())


if __name__ == "__main__":
    unittest.main()
