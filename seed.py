"""Наполнение базы данными учебной программы (идемпотентно).

Запуск:  python seed.py  [--reset]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from content.curriculum import TOPICS
from database import execute, init_db, query_all, query_one

# Пароль администратора, если он не задан через переменную окружения ADMIN_PASSWORD.
DEFAULT_ADMIN_PASSWORD = "math2025"

# Предметы платформы. Ключ — стабильный код для адресов и импорта.
DEFAULT_SUBJECTS: list[tuple[str, str, str, str, str]] = [
    ("math", "Математика", "📐", "indigo",
     "Числа, действия, величины, геометрия и задачи."),
    ("english", "Английский язык", "📘", "sky",
     "Аудирование, говорение, чтение и письмо по учебнику."),
    ("russian_lang", "Русский язык", "📕", "rose",
     "Звуки и буквы, состав слова, части речи, орфография."),
    ("russian_lit", "Русская литература", "📚", "violet",
     "Чтение и разбор художественных произведений."),
    ("belarusian_lang", "Белорусский язык", "📗", "emerald",
     "Беларуская мова: гукі, словы, сказ, арфаграфія."),
    ("belarusian_lit", "Белорусская литература", "📖", "teal",
     "Беларуская літаратура: творы, героі, выразнае чытанне."),
    ("world", "Человек и мир", "🌍", "amber",
     "Прырода, чалавек і грамадства, здароўе і бяспека."),
    ("literature", "Литературное чтение", "📜", "rose",
     "Чтение и работа с текстом."),
]


def ensure_subject(slug: str, name: str, icon: str = "📘", color: str = "sky",
                   description: str = "", order_index: int | None = None) -> int:
    """Найти предмет по коду или названию, иначе создать (без дублей)."""
    from services import orgs

    row = orgs.get_subject_by_slug(slug) or query_one(
        "SELECT * FROM subjects WHERE lower(name) = lower(?)", (name,)
    )
    if row:
        if order_index is not None and not row["order_index"]:
            execute("UPDATE subjects SET order_index = ? WHERE id = ?", (order_index, row["id"]))
        return row["id"]
    subject_id = orgs.create_subject(slug, name, icon, color, description)
    if order_index is not None:
        execute("UPDATE subjects SET order_index = ? WHERE id = ?", (order_index, subject_id))
    return subject_id


def sync_content() -> int:
    """Привести таблицы topics/methods к актуальной программе."""
    init_db()
    math_id = ensure_subject(*DEFAULT_SUBJECTS[0])
    count = 0
    for order_index, topic in enumerate(TOPICS):
        execute(
            """INSERT INTO topics
               (slug, title, grade, subject_id, source, kind, icon, color,
                part, page_start, page_end, description, min_level, order_index, created_at)
               VALUES (?, ?, ?, ?, 'curriculum', 'practice', ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(slug) DO UPDATE SET
                   title = excluded.title, grade = excluded.grade,
                   subject_id = COALESCE(topics.subject_id, excluded.subject_id),
                   icon = excluded.icon, color = excluded.color, part = excluded.part,
                   page_start = excluded.page_start, page_end = excluded.page_end,
                   description = excluded.description, min_level = excluded.min_level,
                   order_index = excluded.order_index""",
            (
                topic["slug"], topic["title"], topic["grade"], math_id,
                topic["icon"], topic["color"], topic["part"], topic["page_start"],
                topic["page_end"], topic["description"], topic["min_level"], order_index,
            ),
        )
        count += 1
        for method_index, method in enumerate(topic["methods"]):
            execute(
                """INSERT INTO methods
                   (topic_slug, slug, name, widget, explanation, steps_json, example_key, order_index)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(topic_slug, slug) DO UPDATE SET
                       name = excluded.name, widget = excluded.widget,
                       explanation = excluded.explanation, steps_json = excluded.steps_json,
                       example_key = excluded.example_key, order_index = excluded.order_index""",
                (
                    topic["slug"], method["slug"], method["name"], method.get("widget", "none"),
                    method.get("explanation", ""), json.dumps(method.get("steps", []), ensure_ascii=False),
                    method.get("example", ""), method_index,
                ),
            )
    return count


def verify() -> None:
    topics = query_all("SELECT slug, title, grade FROM topics ORDER BY grade, order_index")
    methods = query_all("SELECT topic_slug, COUNT(*) AS n FROM methods GROUP BY topic_slug")
    print(f"Тем в базе: {len(topics)}")
    for t in topics:
        count = next((m["n"] for m in methods if m["topic_slug"] == t["slug"]), 0)
        print(f"  [{t['grade']} класс] {t['title']} — способов объяснения: {count}")


def seed_base_entities() -> str:
    """Базовые справочники (предметы) и учётная запись администратора.

    Возвращает пароль созданного администратора (пустую строку, если он уже был).
    """
    for index, (slug, name, icon, color, description) in enumerate(DEFAULT_SUBJECTS):
        ensure_subject(slug, name, icon, color, description, order_index=index)
    return ensure_admin()


def ensure_admin() -> str:
    """Создать администратора, если его ещё нет. Вернуть пароль (если создан)."""
    from database import query_one
    from services import auth

    row = query_one("SELECT id FROM users WHERE role = ?", (auth.ROLE_ADMIN,))
    if row:
        return ""
    login = os.environ.get("ADMIN_LOGIN", "admin")
    password = os.environ.get("ADMIN_PASSWORD") or DEFAULT_ADMIN_PASSWORD
    auth.create_user(login, password, auth.ROLE_ADMIN, "Администратор", "платформы",
                     email=os.environ.get("ADMIN_EMAIL") or None, avatar="🛠")
    return password


def main() -> int:
    parser = argparse.ArgumentParser(description="Наполнение БД учебной программой")
    parser.add_argument("--reset", action="store_true", help="полностью очистить базу")
    args = parser.parse_args()

    if args.reset:
        from database import reset_database

        reset_database()
        print("База очищена.")

    seed_base_entities()
    count = sync_content()
    print(f"Загружено тем: {count}")
    from services import topics as topics_service

    filled = topics_service.sync_course_topics()
    if filled:
        print(f"Тем добавлено в курсы: {filled}")
    verify()
    return 0


if __name__ == "__main__":
    sys.exit(main())
