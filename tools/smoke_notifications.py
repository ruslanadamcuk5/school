"""Интеграционная проверка: задания, авторы, уведомления, расписание."""
from __future__ import annotations

import os
import sys
import tempfile

DB = os.path.join(tempfile.gettempdir(), "school_smoke.db")
for suffix in ("", "-wal", "-shm"):
    if os.path.exists(DB + suffix):
        os.remove(DB + suffix)

os.environ["DATABASE_PATH"] = DB
os.environ["SECRET_KEY"] = "smoke-secret"
os.environ["APP_ENV"] = "production"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import wsgi  # noqa: E402  (инициализирует схему и базовые данные)
from database import execute  # noqa: E402
from services import assignments, auth, notifications, orgs  # noqa: E402

failures: list[str] = []


def check(name: str, condition: bool, extra: str = "") -> None:
    print(("OK   " if condition else "FAIL ") + name + (" " + extra if extra else ""))
    if not condition:
        failures.append(name)


teacher_id = auth.create_user("smoke_teacher", "pass1234", auth.ROLE_TEACHER, "Иван", "Петров")
parent_id = auth.create_user("smoke_parent", "pass1234", auth.ROLE_PARENT, "Мария", "Петрова")
student_id = auth.create_user("smoke_student", "pass1234", auth.ROLE_STUDENT, "Петя", "Петров", avatar="🦊")
other_student_id = auth.create_user("smoke_student2", "pass1234", auth.ROLE_STUDENT, "Аня", "Петрова")

city_id = orgs.create_city("Минск")
school_id = orgs.create_school(city_id, "Школа №1")
class_id = orgs.create_class(school_id, 5, "А", teacher_id)
orgs.add_student_to_class(class_id, student_id)
orgs.add_student_to_class(class_id, other_student_id)
execute("INSERT INTO parent_children (parent_id, child_id) VALUES (?, ?)", (parent_id, student_id))

# 1. Задание учителя: ученик и родитель получают уведомление «от учителя».
teacher_task = assignments.create_assignment(
    title="Дроби", class_id=class_id, teacher_id=teacher_id,
    topic_slugs=[], questions_count=1, status="опубликована",
    tasks=[{"question": "1+1", "answer": "2", "points": 1}],
)
notifications.notify_published(teacher_task)
student_notes = notifications.list_for_user(student_id)
parent_notes = notifications.list_for_user(parent_id)
check("ученик получает уведомление о новом задании", len(student_notes) == 1)
check("родитель получает уведомление о новом задании", len(parent_notes) == 1)
check("в уведомлении указан автор-учитель", "от учителя" in (student_notes[0]["body"] if student_notes else ""))

# 2. Автор задания отображается как «родителя».
parent_task = assignments.create_assignment(
    title="Повторение", student_id=student_id, teacher_id=parent_id,
    topic_slugs=[], questions_count=1, status="опубликована",
    tasks=[{"question": "2+2", "answer": "4", "points": 1}],
)
row = assignments.get_assignment(parent_task)
check("задание родителя помечено автором parent", row is not None and row["author_role"] == "parent")
notifications.notify_published(parent_task)
student_notes = notifications.list_for_user(student_id)
check("ученик видит задание от родителя", any("от родителя" in n["body"] for n in student_notes))

# 3. Выполнение: автор и родитель получают уведомление.
assignments.save_result(
    teacher_task, student_id, 1, 1,
    [{"question": "1+1", "given": "2", "answer": "2", "correct": True, "solution": ""}],
)
teacher_notes = notifications.list_for_user(teacher_id)
check("учитель получает уведомление о выполнении", any(n["kind"] == notifications.KIND_DONE for n in teacher_notes))
parent_notes = notifications.list_for_user(parent_id)
check("родитель получает уведомление о выполнении", any(n["kind"] == notifications.KIND_DONE for n in parent_notes))

# 4. Просроченное задание: уведомления ученику, родителю и учителю.
missed_task = assignments.create_assignment(
    title="Просроченная работа", class_id=class_id, teacher_id=teacher_id,
    topic_slugs=[], questions_count=1, status="опубликована",
    due_date="2020-01-01",
    tasks=[{"question": "3+3", "answer": "6", "points": 1}],
)
notifications.notify_published(missed_task)
created = notifications.sync_missed(missed_task)
check("sync_missed создаёт уведомления", created >= 1, f"created={created}")
student_notes = notifications.list_for_user(student_id)
check("ученик получает уведомление о пропуске", any(n["kind"] == notifications.KIND_MISSED for n in student_notes))
parent_notes = notifications.list_for_user(parent_id)
check("родитель получает уведомление о пропуске", any(n["kind"] == notifications.KIND_MISSED for n in parent_notes))
# повторный вызов не должен плодить дубли
before = len(notifications.list_for_user(student_id, 200))
notifications.sync_missed(missed_task)
after = len(notifications.list_for_user(student_id, 200))
check("повторный sync_missed не дублирует уведомления", before == after)

# 5. Расписание учителя применяется к ученику класса.
orgs.save_schedule_item(class_id, weekday=1, lesson_no=1, teacher_id=teacher_id,
                        time_start="08:30", time_end="09:15", note="Математика")
schedule = orgs.schedule_for_student(student_id)
check("ученик видит расписание своего класса", len(schedule) == 1)
check("в расписании указан урок и время", schedule and schedule[0]["lesson_no"] == 1 and schedule[0]["time_start"] == "08:30")
other_schedule = orgs.schedule_for_student(other_student_id)
check("расписание применяется ко всем ученикам класса", len(other_schedule) == 1)

# 6. Отметка «прочитано».
if student_notes:
    notifications.mark_read(student_id, int(student_notes[0]["id"]))
    check("отметка о прочтении работает", notifications.unread_count(student_id) < len(student_notes))

print()
if failures:
    print("FAILED:", ", ".join(failures))
    sys.exit(1)
print("ALL CHECKS PASSED")
