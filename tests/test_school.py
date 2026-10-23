"""Тесты мультиарендного режима: регистрация, роли, классы, работы, админка."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DB = os.path.join(tempfile.gettempdir(), "edu_math_school_test.db")
os.environ["APP_ENV"] = "testing"
os.environ["DATABASE_PATH"] = _TMP_DB
os.environ["SECRET_KEY"] = "school-test-secret"

for suffix in ("", "-wal", "-shm"):
    if os.path.exists(_TMP_DB + suffix):
        os.remove(_TMP_DB + suffix)

from content.curriculum import TOPICS  # noqa: E402
from database import query_one  # noqa: E402
from services import assignments as assignments_service  # noqa: E402
from services import auth, orgs  # noqa: E402
from services import textbooks as textbooks_service  # noqa: E402
from services import topics as topics_service  # noqa: E402


def make_client():
    from app import create_app

    app = create_app("testing")
    app.config["TESTING"] = True
    return app.test_client()


def fresh_db():
    """Удалить тестовую БД, чтобы каждый тест стартовал с чистого состояния."""
    for suffix in ("", "-wal", "-shm"):
        path = _TMP_DB + suffix
        if os.path.exists(path):
            os.remove(path)


def csrf(client, path="/"):
    html = client.get(path).get_data(as_text=True)
    marker = 'name="csrf-token" content="'
    index = html.find(marker)
    start = index + len(marker)
    return html[start:html.find('"', start)]


class TestAuthRoles(unittest.TestCase):
    def setUp(self):
        fresh_db()
        self.client = make_client()

    def test_password_hashing(self):
        hashed = auth.hash_password("Пароль123")
        self.assertNotIn("Пароль123", hashed)
        self.assertTrue(auth.verify_password("Пароль123", hashed))
        self.assertFalse(auth.verify_password("другой", hashed))

    def test_registration_requires_unique_login(self):
        token = csrf(self.client, "/register")
        response = self.client.post("/register", data={
            "role": "student", "login": "ivan", "password": "pass1234",
            "password2": "pass1234", "first_name": "Иван",
            "csrf_token": token,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(auth.login_taken("ivan"))
        self.assertFalse(auth.login_taken("ivan2"))

    def test_login_logout(self):
        token = csrf(self.client, "/register")
        self.client.post("/register", data={
            "role": "teacher", "login": "teacher1", "password": "pass1234",
            "password2": "pass1234", "first_name": "Учитель",
            "csrf_token": token,
        })
        self.client.get("/logout")
        token = csrf(self.client, "/login")
        response = self.client.post("/login", data={
            "login": "teacher1", "password": "pass1234", "csrf_token": token,
        })
        self.assertEqual(response.status_code, 302)
        response = self.client.get("/teacher/")
        self.assertEqual(response.status_code, 200)
        self.client.get("/logout")
        response = self.client.get("/teacher/")
        self.assertEqual(response.status_code, 302)

    def test_admin_role_cannot_be_self_registered(self):
        token = csrf(self.client, "/register")
        response = self.client.post("/register", data={
            "role": "admin", "login": "hacker", "password": "pass1234",
            "password2": "pass1234", "first_name": "Кто-то", "csrf_token": token,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(auth.login_taken("hacker"))

    def test_wrong_password(self):
        token = csrf(self.client, "/register")
        self.client.post("/register", data={
            "role": "student", "login": "petya", "password": "pass1234",
            "password2": "pass1234", "first_name": "Петя", "csrf_token": token,
        })
        self.client.get("/logout")
        token = csrf(self.client, "/login")
        response = self.client.post("/login", data={
            "login": "petya", "password": "неверный", "csrf_token": token,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("Неверный логин или пароль", response.get_data(as_text=True))


class TestOrganization(unittest.TestCase):
    def setUp(self):
        fresh_db()
        self.client = make_client()
        self.token = csrf(self.client, "/register")
        # администратор создаётся только системой (seed) — не через регистрацию
        self.admin_login = "boss"
        self.admin_password = "pass1234"
        self.admin_id = auth.create_user(
            self.admin_login, self.admin_password, auth.ROLE_ADMIN, "Главный", "платформы"
        )

    def _as_admin(self):
        self.client.get("/logout")
        token = csrf(self.client, "/login")
        self.client.post("/login", data={
            "login": self.admin_login, "password": self.admin_password, "csrf_token": token,
        })
        return token

    def test_city_school_class_chain(self):
        city_id = orgs.create_city("Минск")
        school_id = orgs.create_school(city_id, "Гимназия №1")
        class_id = orgs.create_class(school_id, 3, "А")
        self.assertEqual(orgs.get_class(class_id)["school_id"], school_id)
        self.assertEqual(orgs.get_school(school_id)["city_id"], city_id)
        self.assertEqual(orgs.class_title(orgs.get_class(class_id)), "3 «А»")

    def test_student_teacher_binding(self):
        city_id = orgs.create_city("Минск")
        school_id = orgs.create_school(city_id, "Школа №5")
        teacher_id = auth.create_user("uchitel", "pass1234", auth.ROLE_TEACHER, "Иван", "Петров")
        class_id = orgs.create_class(school_id, 3, "Б", teacher_id)
        student_id = auth.create_user("uchenok", "pass1234", auth.ROLE_STUDENT, "Маша", "Иванова")
        orgs.add_student_to_class(class_id, student_id)

        # учитель класса подтягивается автоматически
        teacher = orgs.teacher_of_class(class_id)
        self.assertEqual(teacher["id"], teacher_id)
        classes = orgs.classes_of_student(student_id)
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0]["teacher_id"], teacher_id)
        self.assertEqual(len(orgs.students_of_class(class_id)), 1)

    def test_course_topics_configuration(self):
        subject = orgs.get_subject_by_slug("math")
        course_id = orgs.create_course(subject["id"], "Математика 3", 3, teacher_id=self.admin_id)
        slugs = [t["slug"] for t in TOPICS if t["grade"] == 3][:3]
        orgs.set_course_topics(course_id, slugs)
        rows = orgs.course_topics(course_id, enabled_only=True)
        self.assertEqual(len(rows), 3)
        orgs.toggle_course_topic(course_id, slugs[0], False)
        rows = orgs.course_topics(course_id, enabled_only=True)
        self.assertEqual(len(rows), 2)

    def test_parent_child_link_by_code(self):
        student_id = auth.create_user("kid", "pass1234", auth.ROLE_STUDENT, "Дима", "Круглов")
        child = auth.get_user(student_id)
        self.assertTrue(child["child_code"])
        parent_id = auth.create_user("mama", "pass1234", auth.ROLE_PARENT, "Мария", "Круглова")
        found = auth.find_child_by_code(child["child_code"])
        self.assertIsNotNone(found)
        self.assertTrue(auth.link_parent_child(parent_id, student_id))
        self.assertEqual(len(auth.children_of(parent_id)), 1)

    def test_admin_pages_available(self):
        self._as_admin()
        for path in ("/admin/", "/admin/users", "/admin/cities", "/admin/schools",
                     "/admin/classes", "/admin/subjects", "/admin/courses",
                     "/admin/textbooks", "/admin/audit"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)

    def test_oversized_upload_returns_friendly_413(self):
        token = self._as_admin()
        app = self.client.application
        original_limit = app.config["MAX_CONTENT_LENGTH"]
        app.config["MAX_CONTENT_LENGTH"] = 2048
        try:
            response = self.client.post(
                "/admin/textbooks",
                data={
                    "action": "upload",
                    "title": "Огромный учебник",
                    "subject_id": "1",
                    "csrf_token": token,
                    "file": (BytesIO(b"%PDF-1.4\n" + b"0" * 8192), "big.pdf"),
                },
                content_type="multipart/form-data",
            )
        finally:
            app.config["MAX_CONTENT_LENGTH"] = original_limit
        self.assertEqual(response.status_code, 413)
        html = response.get_data(as_text=True)
        self.assertIn("Файл слишком большой", html)
        self.assertIn("МБ", html)

    def test_admin_can_create_entities_via_ui(self):
        token = self._as_admin()
        response = self.client.post("/admin/cities", data={
            "action": "add", "name": "Гомель", "csrf_token": token,
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(any(c["name"] == "Гомель" for c in orgs.list_cities()))

    def test_teacher_cannot_open_admin(self):
        token = csrf(self.client, "/register")
        self.client.post("/register", data={
            "role": "teacher", "login": "teach2", "password": "pass1234",
            "password2": "pass1234", "first_name": "Учитель", "csrf_token": token,
        })
        response = self.client.get("/admin/users")
        self.assertEqual(response.status_code, 403)


class TestAssignments(unittest.TestCase):
    def setUp(self):
        fresh_db()
        self.client = make_client()
        self.token = csrf(self.client, "/register")
        self.admin_id = auth.create_user(
            "boss2", "pass1234", auth.ROLE_ADMIN, "Главный", "платформы"
        )
        city_id = orgs.create_city("Минск")
        school_id = orgs.create_school(city_id, "Школа")
        self.class_id = orgs.create_class(school_id, 3, "А", self.admin_id)
        self.student_id = auth.create_user("s1", "pass1234", auth.ROLE_STUDENT, "Ученик")
        orgs.add_student_to_class(self.class_id, self.student_id)

    def test_assignment_lifecycle(self):
        topics = [t["slug"] for t in TOPICS if t["grade"] == 3][:2]
        assignment_id = assignments_service.create_assignment(
            "Контрольная №1", kind="контрольная", class_id=self.class_id,
            teacher_id=self.admin_id, topic_slugs=topics, questions_count=4,
        )
        assignment = assignments_service.get_assignment(assignment_id)
        self.assertEqual(assignments_service.assignment_topics(assignment), topics)

        tasks = assignments_service.build_tasks(topics, 4)
        self.assertEqual(len(tasks), 4)
        for task in tasks:
            self.assertIn("question", task)
            self.assertIn("answer", task)

        # ученик решает
        given = [task["answer"] for task in tasks]
        score, details = assignments_service.check_assignment_answers(tasks, given)
        self.assertEqual(score, 4)
        assignments_service.save_result(assignment_id, self.student_id, score, 4, details)

        results = assignments_service.results_with_students(assignment_id)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["percent"], 100)
        self.assertEqual(results[0]["grade"], 10)

        # публикация
        assignments_service.publish_assignment(assignment_id)
        self.assertEqual(
            assignments_service.get_assignment(assignment_id)["status"], "опубликована"
        )
        visible = assignments_service.list_assignments(student_id=self.student_id, status="опубликована")
        self.assertEqual(len(visible), 1)

    def test_grade_scale(self):
        self.assertEqual(assignments_service.grade_for_percent(100), 10)
        self.assertEqual(assignments_service.grade_for_percent(85), 9)
        self.assertEqual(assignments_service.grade_for_percent(55), 6)
        self.assertEqual(assignments_service.grade_for_percent(5), 1)


class TestSubjectAssignments(unittest.TestCase):
    """Работы и тесты по темам всех предметов."""

    def setUp(self):
        fresh_db()
        self.client = make_client()
        self.token = csrf(self.client, "/register")
        self.admin_id = auth.create_user(
            "boss_works", "pass1234", auth.ROLE_ADMIN, "Главный", "платформы"
        )
        city_id = orgs.create_city("Минск")
        school_id = orgs.create_school(city_id, "Школа")
        self.teacher_id = auth.create_user(
            "teacher_eng", "pass1234", auth.ROLE_TEACHER, "Ольга", "Языкова"
        )
        self.class_id = orgs.create_class(school_id, 3, "А", self.teacher_id)
        self.student_id = auth.create_user(
            "student_eng", "pass1234", auth.ROLE_STUDENT, "Ваня", "Ветров"
        )
        orgs.add_student_to_class(self.class_id, self.student_id)
        self.parent_id = auth.create_user(
            "parent_eng", "pass1234", auth.ROLE_PARENT, "Мария", "Ветрова"
        )
        auth.link_parent_child(self.parent_id, self.student_id)

        self.english = orgs.get_subject_by_slug("english") or orgs.get_subject_by_slug("angl")
        self.topic_slug = topics_service.create_topic(
            self.english["id"], 3, "UNIT 1. About me",
            description="Знакомство, приветствия и английские буквы.",
        )
        self.topic_slug2 = topics_service.create_topic(
            self.english["id"], 3, "UNIT 2. My family",
            description="Семья, родственники и рассказ о себе.",
        )
        self.course_id = orgs.create_course(
            self.english["id"], "Английский, 3 класс", 3, teacher_id=self.teacher_id
        )
        orgs.set_course_topics(self.course_id, [self.topic_slug, self.topic_slug2])

    def _login(self, login_name):
        self.client.get("/logout")
        token = csrf(self.client, "/login")
        response = self.client.post("/login", data={
            "login": login_name, "password": "pass1234", "csrf_token": token,
        })
        self.assertEqual(response.status_code, 302)

    def test_teacher_work_form_lists_non_math_courses(self):
        self._login("teacher_eng")
        page = self.client.get("/teacher/works/new")
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn("Английский, 3 класс", html)
        self.assertIn("UNIT 1. About me", html)

        token = csrf(self.client, "/teacher/works/new")
        response = self.client.post("/teacher/works/new", data={
            "title": "Домашняя по английскому",
            "kind": "домашняя",
            "class_id": str(self.class_id),
            "course_id": str(self.course_id),
            "subject_id": str(self.english["id"]),
            "topic_slugs": [self.topic_slug, self.topic_slug2],
            "questions_count": "4",
            "csrf_token": token,
        })
        self.assertEqual(response.status_code, 302)
        works = assignments_service.list_assignments(teacher_id=self.teacher_id)
        self.assertEqual(len(works), 1)
        tasks = assignments_service.assignment_tasks(works[0])
        self.assertTrue(tasks)
        self.assertTrue(all(task["generator"] == "reading" for task in tasks))
        self.assertEqual(works[0]["subject_id"], self.english["id"])

    def test_parent_sends_work_to_child_and_child_completes_it(self):
        self._login("parent_eng")
        page = self.client.get("/parent/assignments")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Ваня", page.get_data(as_text=True))

        token = csrf(self.client, "/parent/assignments")
        response = self.client.post("/parent/assignments", data={
            "child_ids": [str(self.student_id)],
            "title": "Читаем UNIT 1",
            "kind": "домашняя",
            "subject_id": str(self.english["id"]),
            "topic_slugs": [self.topic_slug],
            "questions_count": "3",
            "csrf_token": token,
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Читаем UNIT 1", response.get_data(as_text=True))

        works = assignments_service.list_assignments(teacher_id=self.parent_id)
        self.assertEqual(len(works), 1)
        assignment = works[0]
        self.assertEqual(assignment["student_id"], self.student_id)
        self.assertEqual(assignment["status"], "опубликована")
        tasks = assignments_service.assignment_tasks(assignment)

        self._login("student_eng")
        page = self.client.get("/student/works")
        self.assertIn("Читаем UNIT 1", page.get_data(as_text=True))
        page = self.client.get(f"/student/works/{assignment['id']}")
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        # у каждого задания своя группа радиокнопок, иначе браузер
        # отправляет только один выбранный вариант на всю работу
        self.assertIn('name="answer_0"', html)
        if len(tasks) > 1:
            self.assertIn('name="answer_1"', html)

        token = csrf(self.client, f"/student/works/{assignment['id']}")
        response = self.client.post(
            f"/student/works/{assignment['id']}/submit",
            data={
                **{f"answer_{index}": task["answer"]
                   for index, task in enumerate(tasks)},
                "csrf_token": token,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        result = assignments_service.get_result(assignment["id"], self.student_id)
        self.assertIsNotNone(result)
        self.assertEqual(result["score"], result["max_score"])

    def test_reading_topic_quiz_awards_progress(self):
        self._login("student_eng")
        page = self.client.get(f"/topic/{self.topic_slug}/quiz")
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn("Проверить ответы", html)
        self.assertIn('name="answer_0"', html)
        with self.client.session_transaction() as sess:
            items = list(sess["reading_quiz"]["items"])
        token = csrf(self.client, f"/topic/{self.topic_slug}")
        response = self.client.post(
            f"/topic/{self.topic_slug}/quiz",
            data={
                **{f"answer_{index}": item["answer"]
                   for index, item in enumerate(items)},
                "csrf_token": token,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Результат теста", response.get_data(as_text=True))
        learner = query_one(
            "SELECT * FROM learners WHERE user_id = ?", (self.student_id,)
        )
        self.assertGreater(learner["xp"], 0)
        progress = query_one(
            "SELECT * FROM topic_progress WHERE learner_id = ? AND topic_slug = ?",
            (learner["id"], self.topic_slug),
        )
        self.assertGreaterEqual(progress["stars"], 1)


class TestStudentFlow(unittest.TestCase):
    def setUp(self):
        fresh_db()
        self.client = make_client()
        self.token = csrf(self.client, "/register")
        admin_id = auth.create_user(
            "boss3", "pass1234", auth.ROLE_ADMIN, "Главный", "платформы"
        )
        city_id = orgs.create_city("Минск")
        school_id = orgs.create_school(city_id, "Школа")
        class_id = orgs.create_class(school_id, 4, "В", admin_id)
        student_id = auth.create_user("st4", "pass1234", auth.ROLE_STUDENT, "Ваня", "Ветров")
        orgs.add_student_to_class(class_id, student_id)
        self.class_id = class_id
        self.student_id = student_id

    def test_student_dashboard_and_works(self):
        self.client.get("/logout")
        token = csrf(self.client, "/login")
        self.client.post("/login", data={"login": "st4", "password": "pass1234", "csrf_token": token})

        response = self.client.get("/student/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Мой кабинет", response.get_data(as_text=True))

        response = self.client.get("/student/works")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/student/textbooks")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/student/schedule")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/student/badges")
        self.assertEqual(response.status_code, 200)

    def test_student_profile_created_for_account(self):
        self.client.get("/logout")
        token = csrf(self.client, "/login")
        self.client.post("/login", data={"login": "st4", "password": "pass1234", "csrf_token": token})
        from database import query_one

        row = query_one(
            """SELECT l.* FROM learner_accounts la JOIN learners l ON l.id = la.learner_id
                WHERE la.user_id = ?""",
            (self.student_id,),
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["grade"], 4)

    def test_student_cannot_open_teacher_area(self):
        self.client.get("/logout")
        token = csrf(self.client, "/login")
        self.client.post("/login", data={"login": "st4", "password": "pass1234", "csrf_token": token})
        self.assertEqual(self.client.get("/teacher/").status_code, 403)


class TestSubjectTopics(unittest.TestCase):
    """Темы языков/литературы: импорт, карта предмета, чтение по пособию."""

    def setUp(self):
        fresh_db()
        self.client = make_client()
        self.token = csrf(self.client, "/register")
        self.admin_id = auth.create_user(
            "boss_subjects", "pass1234", auth.ROLE_ADMIN, "Главный", "платформы"
        )
        city_id = orgs.create_city("Минск")
        school_id = orgs.create_school(city_id, "Школа")
        self.class_id = orgs.create_class(school_id, 3, "А", self.admin_id)
        self.student_id = auth.create_user(
            "student_subjects", "pass1234", auth.ROLE_STUDENT, "Ученик"
        )
        orgs.add_student_to_class(self.class_id, self.student_id)
        self.english = orgs.get_subject_by_slug("english") or orgs.get_subject_by_slug("angl")
        self.assertIsNotNone(self.english)
        self.topic_slug = topics_service.create_topic(
            self.english["id"], 3, "UNIT 1. About me",
            description="Знакомство, приветствия, английские буквы.",
        )

    def _login(self, login_name):
        self.client.get("/logout")
        token = csrf(self.client, "/login")
        response = self.client.post("/login", data={
            "login": login_name, "password": "pass1234", "csrf_token": token,
        })
        self.assertEqual(response.status_code, 302)

    def _as_admin(self):
        self._login("boss_subjects")

    def test_topic_visible_in_subject_map_and_reading_flow(self):
        self._login("student_subjects")
        response = self.client.get(f"/map?subject={self.english['slug']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("UNIT 1. About me", response.get_data(as_text=True))

        page = self.client.get(f"/topic/{self.topic_slug}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Я изучил тему", page.get_data(as_text=True))

        learner = query_one(
            "SELECT * FROM learners WHERE user_id = ?", (self.student_id,)
        )
        xp_before = learner["xp"]
        token = csrf(self.client, f"/topic/{self.topic_slug}")
        response = self.client.post(
            f"/topic/{self.topic_slug}/complete",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        after = query_one("SELECT * FROM learners WHERE user_id = ?", (self.student_id,))
        self.assertGreater(after["xp"], xp_before)

        # повторная отметка не начисляет опыт
        token = csrf(self.client, f"/topic/{self.topic_slug}")
        self.client.post(
            f"/topic/{self.topic_slug}/complete",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        again = query_one("SELECT * FROM learners WHERE user_id = ?", (self.student_id,))
        self.assertEqual(again["xp"], after["xp"])
        progress = query_one(
            "SELECT * FROM topic_progress WHERE learner_id = ? AND topic_slug = ?",
            (learner["id"], self.topic_slug),
        )
        self.assertEqual(progress["stars"], 1)

    def test_admin_course_topics_scoped_to_subject(self):
        self._as_admin()
        course_id = orgs.create_course(
            self.english["id"], "Английский, 3 класс", 3, teacher_id=self.admin_id
        )
        orgs.set_course_topics(course_id, [self.topic_slug])
        response = self.client.get(f"/admin/courses/{course_id}/topics")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("UNIT 1. About me", html)
        self.assertNotIn("Числа до 1000", html)

        response = self.client.get(f"/admin/subjects/{self.english['id']}/topics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("UNIT 1. About me", response.get_data(as_text=True))

    def test_delete_subject_removes_topics_and_methods(self):
        math = orgs.get_subject_by_slug("math")
        self.assertIsNotNone(math)
        orgs.delete_subject(math["id"])
        self.assertIsNone(orgs.get_subject(math["id"]))
        self.assertEqual(
            query_one("SELECT COUNT(*) AS n FROM topics WHERE subject_id = ?", (math["id"],))["n"],
            0,
        )
        self.assertEqual(
            query_one("SELECT COUNT(*) AS n FROM methods")["n"], 0
        )

    def test_textbook_page_scoped_and_manual_topic_import(self):
        self._as_admin()
        book_id = textbooks_service.create_textbook(
            self.english["id"], 3, "Английский, 3 класс", "fake.pdf", pages=10
        )
        page = self.client.get(f"/admin/textbooks/{book_id}")
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn("UNIT 1. About me", html)
        self.assertIn("Сформировать темы из PDF", html)
        self.assertNotIn("Числа до 1000", html)

        token = csrf(self.client, f"/admin/textbooks/{book_id}")
        response = self.client.post(f"/admin/textbooks/{book_id}", data={
            "action": "manual_topics",
            "manual_topics": "Unit A — 2\nUnit B — 5",
            "csrf_token": token,
        })
        self.assertEqual(response.status_code, 302)
        links = {row["title"]: row for row in textbooks_service.topics_for_textbook(book_id)}
        self.assertIn("Unit A", links)
        self.assertEqual(links["Unit A"]["page"], 2)
        self.assertEqual(links["Unit A"]["page_end"], 4)
        self.assertEqual(links["Unit B"]["page"], 5)

        # смена класса у пособия убирает привязки к темам другого класса
        textbooks_service.update_textbook(book_id, grade=4)
        self.assertEqual(textbooks_service.topics_for_textbook(book_id), [])


class TestPdfTopicParser(unittest.TestCase):
    def test_parse_contents_text(self):
        from services.pdf_topics import parse_contents_text, parse_manual_topics

        text = (
            "3 Contents\n"
            "UNIT 1. About me.  . . . . . . . . . . . . . . . . . . .  4\n"
            "UNIT 2. My family.  . . . . . . . . . . . . . . . . . .  29\n"
            "Vocabulary  . . . . . . . . . . . . . . . . . . . . . . .  134"
        )
        entries = parse_contents_text(text)
        self.assertEqual(entries[:2], [("UNIT 1. About me", 4), ("UNIT 2. My family", 29)])
        self.assertEqual(entries[-1], ("Vocabulary", 134))

        ellipsis = parse_contents_text("Введение … 3\nПовторение …… 10")
        self.assertEqual(ellipsis, [("Введение", 3), ("Повторение", 10)])
        spaced = parse_contents_text("Звуки и буквы        5\nСостав слова        18")
        self.assertEqual(spaced, [("Звуки и буквы", 5), ("Состав слова", 18)])

        manual = parse_manual_topics("Введение — 3\nПовторение | 10\nИтоги 20")
        self.assertEqual(manual, [("Введение", 3), ("Повторение", 10), ("Итоги", 20)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
