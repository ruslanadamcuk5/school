"""Демо-данные для знакомства с школьным режимом.

Запуск:  python tools/demo_data.py
Создаёт город → школу → классы → учителя, учеников, родителя, курсы,
расписание и опубликованную проверочную работу.

Учётные записи (пароль у всех — math2025):
  администратор — boss        учитель — petrova      ученики — ivanov, masha, sidorov, koval, molot
  родитель — mama_ivanova
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import assignments as assignments_service  # noqa: E402
from services import auth, orgs  # noqa: E402
from database import query_one  # noqa: E402

PASSWORD = "math2025"


def main() -> int:
    if query_one("SELECT id FROM users WHERE role = 'teacher'"):
        print("Демо-данные уже созданы. Очистите базу (python seed.py --reset) и повторите.")
        return 0

    city_id = orgs.create_city("Минск", "Минская область")
    school_id = orgs.create_school(city_id, "Гимназия №1", "ул. Ленина, 5", "Иванова А.П.")

    teacher_id = auth.create_user("petrova", PASSWORD, auth.ROLE_TEACHER, "Анна", "Петрова",
                                  email="petrova@school1.by", school_id=school_id, city_id=city_id)
    class_3a = orgs.create_class(school_id, 3, "А", teacher_id, title="3 «А»")
    class_3b = orgs.create_class(school_id, 3, "Б", teacher_id, title="3 «Б»")
    class_4a = orgs.create_class(school_id, 4, "А", teacher_id, title="4 «А»")

    students = []
    for login, first, last, class_id in [
        ("ivanov", "Иван", "Иванов", class_3a),
        ("masha", "Мария", "Петрова", class_3a),
        ("sidorov", "Никита", "Сидоров", class_3a),
        ("koval", "Аня", "Коваль", class_3b),
        ("molot", "Тимур", "Молот", class_4a),
    ]:
        student_id = auth.create_user(login, PASSWORD, auth.ROLE_STUDENT, first, last,
                                      school_id=school_id, city_id=city_id)
        orgs.add_student_to_class(class_id, student_id)
        students.append(student_id)

    parent_id = auth.create_user("mama_ivanova", PASSWORD, auth.ROLE_PARENT, "Ольга", "Иванова",
                                 school_id=school_id, city_id=city_id)
    child = auth.get_user(students[0])
    auth.link_parent_child(parent_id, child["id"], "мама")

    subject = orgs.get_subject_by_slug("math")
    course_3 = orgs.create_course(subject["id"], "Математика, 3 класс", 3,
                                  description="Программа 3 класса по учебнику Муравьёвой и Урбан.",
                                  teacher_id=teacher_id, school_id=school_id)
    orgs.set_course_topics(course_3, ["numbers_1000", "add_sub_1000", "mult_div_table",
                                      "remainder", "expressions", "equations", "units",
                                      "word_problems"])
    orgs.set_course_classes(course_3, [class_3a, class_3b])

    course_4 = orgs.create_course(subject["id"], "Математика, 4 класс", 4,
                                  teacher_id=teacher_id, school_id=school_id)
    orgs.set_course_topics(course_4, ["mult_div_column", "divisibility", "fractions_ops",
                                      "motion", "area_units", "time_calc"])
    orgs.set_course_classes(course_4, [class_4a])

    orgs.save_schedule_item(class_3a, 1, 1, subject["id"], teacher_id, "09:00", "09:45",
                            "numbers_1000", "Числа до 1000")
    orgs.save_schedule_item(class_3a, 2, 2, subject["id"], teacher_id, "09:50", "10:35",
                            "mult_div_table", "Таблица умножения")
    orgs.save_schedule_item(class_3b, 1, 1, subject["id"], teacher_id, "08:30", "09:15",
                            "add_sub_1000", "Сложение в столбик")

    assignments_service.create_assignment(
        "Проверочная работа: числа до 1000", kind="проверочная",
        description="Без калькулятора, на 15 минут.",
        course_id=course_3, subject_id=subject["id"], class_id=class_3a,
        teacher_id=teacher_id, topic_slugs=["numbers_1000", "add_sub_1000"],
        questions_count=6, time_limit=15, due_date="2030-10-30", status="опубликована",
    )
    assignments_service.create_assignment(
        "Контрольная работа №1", kind="контрольная",
        course_id=course_3, subject_id=subject["id"], class_id=class_3b,
        teacher_id=teacher_id, topic_slugs=["mult_div_table", "remainder", "expressions"],
        questions_count=8, status="черновик",
    )

    # демо-администратор с известным паролем
    admin = query_one("SELECT id FROM users WHERE role = 'admin'")
    if admin:
        auth.update_user(admin["id"], login="admin")
        auth.set_password(admin["id"], PASSWORD)
        admin_login = "admin"
    else:
        auth.create_user("admin", PASSWORD, auth.ROLE_ADMIN, "Главный", "платформы")
        admin_login = "admin"

    print("Готово:")
    print("  город: Минск, школа: Гимназия №1, классы: 3«А», 3«Б», 4«А»")
    print(f"  администратор: {admin_login} / {PASSWORD}")
    print(f"  учитель: petrova / {PASSWORD}")
    print(f"  ученики: ivanov, masha, sidorov, koval, molot / {PASSWORD}")
    print(f"  родитель: mama_ivanova / {PASSWORD} (код ребёнка: {child['child_code']})")
    print(f"  курсы: «Математика, 3 класс» и «Математика, 4 класс»")
    return 0


if __name__ == "__main__":
    sys.exit(main())
