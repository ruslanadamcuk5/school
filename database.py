"""Слой доступа к базе данных (SQLite) и служебные функции."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Sequence

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"

_row_factory = sqlite3.Row


def db_path() -> str:
    """Путь к файлу БД (учитывает DATABASE_PATH из окружения)."""
    return os.environ.get(
        "DATABASE_PATH", str(BASE_DIR / "data" / "math_tutor.db")
    )


def connect(path: str | None = None) -> sqlite3.Connection:
    """Открыть соединение с БД."""
    target = path or db_path()
    if target != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    conn = sqlite3.connect(target, timeout=15, isolation_level=None)
    conn.row_factory = _row_factory
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def query_all(sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    conn = connect()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def query_one(sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
    conn = connect()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def execute(sql: str, params: Sequence[Any] = ()) -> int:
    """Выполнить запись, вернуть lastrowid."""
    conn = connect()
    try:
        cur = conn.execute(sql, params)
        return cur.lastrowid or 0
    finally:
        conn.close()


def execute_many(sql: str, seq: Iterable[Sequence[Any]]) -> None:
    conn = connect()
    try:
        conn.executemany(sql, seq)
    finally:
        conn.close()


def init_db(path: str | None = None) -> None:
    """Создать схему (идемпотентно) и применить миграции."""
    conn = connect(path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    finally:
        conn.close()
    migrate(path)


# Колонки, которые добавляются в существующие таблицы при обновлении
MIGRATIONS: list[tuple[str, str, str]] = [
    ("learners", "user_id", "INTEGER"),
    ("learners", "class_id", "INTEGER"),
    # семейные профили, созданные в мобильном приложении: привязка к устройству
    ("learners", "device_id", "TEXT"),
    # семейные профили веб-интерфейса: изоляция по ключу семьи
    ("learners", "family_key", "TEXT"),
    # опыт, потраченный в магазине: уровень считается по сумме xp + xp_spent,
    # поэтому покупки не «понижают» ребёнка в уровне
    ("learners", "xp_spent", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "child_code", "TEXT"),
    ("users", "is_active", "INTEGER NOT NULL DEFAULT 1"),
    # вход через Google: sub из OpenID Connect
    ("users", "google_sub", "TEXT"),
    ("assignments", "questions_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("assignments", "student_id", "INTEGER"),
    ("assignments", "author_role", "TEXT"),
    # типы заданий: тест, чтение темы, диктант, творческое/иное задание
    ("assignments", "task_type", "TEXT NOT NULL DEFAULT 'test'"),
    ("assignments", "reference_text", "TEXT"),
    ("assignments", "audio_text", "TEXT"),
    ("assignments", "allow_photo", "INTEGER NOT NULL DEFAULT 1"),
    ("assignments", "allow_text", "INTEGER NOT NULL DEFAULT 1"),
    # ответы фотографией и проверка ИИ
    ("assignment_results", "submission_type", "TEXT NOT NULL DEFAULT 'inline'"),
    ("assignment_results", "photos", "TEXT NOT NULL DEFAULT '[]'"),
    ("assignment_results", "ai_status", "TEXT NOT NULL DEFAULT 'not_requested'"),
    ("assignment_results", "ai_feedback", "TEXT"),
    ("assignment_results", "ai_model", "TEXT"),
    ("assignment_results", "ai_score", "INTEGER"),
    # темы теперь привязаны к предмету и могут приходить из содержания пособия
    ("topics", "subject_id", "INTEGER"),
    ("topics", "textbook_id", "INTEGER"),
    ("topics", "source", "TEXT NOT NULL DEFAULT 'curriculum'"),
    ("topics", "kind", "TEXT NOT NULL DEFAULT 'practice'"),
    ("topics", "created_at", "TEXT"),
    ("topics", "content_json", "TEXT"),
    ("textbook_topics", "page_end", "INTEGER NOT NULL DEFAULT 1"),
    # библиотека: назначение рекомендации (класс или ученик)
    ("library_recommendations", "target_kind", "TEXT NOT NULL DEFAULT 'student'"),
    ("library_recommendations", "class_id", "INTEGER"),
    # геолокация: передача больше не требует согласия ребёнка, а родитель
    # может прислать команду включения геолокации на устройстве.
    ("location_sharing", "force_requested_at", "TEXT"),
    ("location_sharing", "force_requested_by", "INTEGER"),
    ("location_sharing", "force_ack_at", "TEXT"),
]


_NOTIFICATIONS_TABLE = """
CREATE TABLE {name} (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    -- NULL — уведомление семейному профилю без аккаунта (learner_id).
    user_id         INTEGER,
    kind            TEXT    NOT NULL,
    title           TEXT    NOT NULL,
    body            TEXT    NOT NULL,
    assignment_id   INTEGER NOT NULL DEFAULT 0,
    student_id      INTEGER NOT NULL DEFAULT 0,
    learner_id      INTEGER NOT NULL DEFAULT 0,
    class_id        INTEGER NOT NULL DEFAULT 0,
    sender_id       INTEGER NOT NULL DEFAULT 0,
    link            TEXT    NOT NULL DEFAULT '',
    dedup_key       TEXT    NOT NULL DEFAULT '',
    is_read         INTEGER NOT NULL DEFAULT 0,
    read_at         TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)
"""


def _migrate_notifications(conn: sqlite3.Connection) -> None:
    """Пересобрать app_notifications под новые поля (dedup_key, read_at, ...).

    Старая таблица имела UNIQUE(user_id, kind, assignment_id, student_id),
    из-за чего второе произвольное сообщение тому же человеку отбрасывалось.
    SQLite не умеет удалять ограничение — пересоздаём таблицу с сохранением
    данных. Старые уведомления получают dedup_key, чтобы не задвоиться.
    """
    rows = conn.execute("PRAGMA table_info(app_notifications)").fetchall()
    if not rows:
        return
    names = {row[1]: row for row in rows}
    user_not_null = bool(names["user_id"][3]) if "user_id" in names else False
    if "dedup_key" in names and "learner_id" not in names:
        conn.execute(
            "ALTER TABLE app_notifications "
            "ADD COLUMN learner_id INTEGER NOT NULL DEFAULT 0"
        )
        names.add("learner_id")
    if "dedup_key" not in names:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(_NOTIFICATIONS_TABLE.format(name="app_notifications_new"))
            conn.execute(
                """INSERT INTO app_notifications_new
                       (id, user_id, kind, title, body, assignment_id, student_id,
                        learner_id, class_id, sender_id, link, dedup_key, is_read,
                        read_at, created_at)
                   SELECT id, user_id, kind, title, body, assignment_id, student_id,
                          0, 0, 0, '',
                          'legacy:' || user_id || ':' || kind || ':'
                            || assignment_id || ':' || student_id || ':'
                            || coalesce(created_at, ''),
                          is_read, NULL, created_at
                     FROM app_notifications"""
            )
            conn.execute("DROP TABLE app_notifications")
            conn.execute("ALTER TABLE app_notifications_new RENAME TO app_notifications")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        names = {row[1]: row for row in conn.execute("PRAGMA table_info(app_notifications)")}
        user_not_null = bool(names["user_id"][3]) if "user_id" in names else False
    if user_not_null:
        # Раньше user_id был NOT NULL, и уведомление семейному профилю
        # (user_id=0) нарушало внешний ключ. Пересобираем без NOT NULL.
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(_NOTIFICATIONS_TABLE.format(name="app_notifications_new"))
            conn.execute(
                """INSERT INTO app_notifications_new
                       (id, user_id, kind, title, body, assignment_id, student_id,
                        learner_id, class_id, sender_id, link, dedup_key, is_read,
                        read_at, created_at)
                   SELECT id, CASE WHEN user_id = 0 THEN NULL ELSE user_id END,
                          kind, title, body, assignment_id, student_id,
                          learner_id, class_id, sender_id, link, dedup_key, is_read,
                          read_at, created_at
                     FROM app_notifications"""
            )
            conn.execute("DROP TABLE app_notifications")
            conn.execute("ALTER TABLE app_notifications_new RENAME TO app_notifications")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_dedup "
        "ON app_notifications(dedup_key) WHERE dedup_key <> ''"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_notifications_user "
        "ON app_notifications(user_id, is_read, created_at)"
    )


def migrate(path: str | None = None) -> None:
    """Добавить недостающие колонки и заполнить новые поля (безопасно для старых БД)."""
    conn = connect(path)
    try:
        _migrate_notifications(conn)
        for table, column, definition in MIGRATIONS:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            if not rows:
                continue
            names = {row[1] for row in rows}
            if column not in names:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        # Передача геолокации теперь всегда включена: старые записи с
        # enabled=0 обновляем, чтобы прежние сборки приложения не остановили
        # службу после обновления сервера.
        try:
            conn.execute("UPDATE location_sharing SET enabled = 1 WHERE enabled = 0")
        except sqlite3.OperationalError:
            pass
        _backfill_topic_subjects(conn)
        # Старым заданиям проставляем автора по роли создателя (учитель/родитель).
        try:
            conn.execute(
                """UPDATE assignments
                      SET author_role = (SELECT role FROM users
                                          WHERE users.id = assignments.teacher_id)
                    WHERE author_role IS NULL AND teacher_id IS NOT NULL"""
            )
        except sqlite3.OperationalError:
            pass
        # Индексы по колонкам, которые появляются миграциями выше. Раньше они
        # были в schema.sql и падали на старой базе: CREATE INDEX выполнялся до
        # ALTER TABLE, из-за чего обновление сайта ломалось.
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_learners_family ON learners(family_key)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_learners_device ON learners(device_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_topics_subject "
            "ON topics(subject_id, grade, order_index)"
        )
        # Один Google-аккаунт — не больше одной учётной записи.
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub "
            "ON users(google_sub) WHERE google_sub IS NOT NULL"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_textbook_topics_slug "
            "ON textbook_topics(topic_slug)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_assignments_student "
            "ON assignments(student_id, status)"
        )
        # Устаревшая «глобальная библиотека» (онлайн-каталог и личные полки
        # найденных книг) больше не используется — библиотека теперь у учителя.
        for table in ("library_covers", "user_books", "book_recommendations"):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
    finally:
        conn.close()


def _backfill_topic_subjects(conn: sqlite3.Connection) -> None:
    """Проставить предмет/тип старым темам и убрать перекрёстные привязки пособий."""
    try:
        subject = conn.execute(
            "SELECT id FROM subjects WHERE slug = 'math' OR name = 'Математика' "
            "ORDER BY CASE WHEN slug = 'math' THEN 0 ELSE 1 END LIMIT 1"
        ).fetchone()
        if subject:
            from content.curriculum import TOPICS

            slugs = [topic["slug"] for topic in TOPICS]
            marks = ", ".join("?" for _ in slugs)
            conn.execute(
                f"UPDATE topics SET subject_id = ? WHERE slug IN ({marks}) "
                "AND (subject_id IS NULL OR subject_id = 0)",
                (subject[0], *slugs),
            )
        conn.execute(
            "UPDATE topics SET source = 'curriculum', kind = 'practice' "
            "WHERE source IS NULL OR source = ''"
        )
        conn.execute("UPDATE topics SET created_at = datetime('now') WHERE created_at IS NULL")
        conn.execute("UPDATE textbook_topics SET page_end = page WHERE page_end < page")
        # Раньше любое пособие привязывалось ко всем темам класса — в том числе
        # математическим. Удаляем связи, где предмет пособия и темы не совпадают.
        conn.execute(
            """DELETE FROM textbook_topics
                WHERE rowid IN (
                    SELECT tt.rowid FROM textbook_topics tt
                      JOIN textbooks b ON b.id = tt.textbook_id
                      JOIN topics t ON t.slug = tt.topic_slug
                     WHERE t.subject_id IS NOT NULL
                       AND (b.subject_id <> t.subject_id OR b.grade <> t.grade)
                )"""
        )
    except sqlite3.Error:
        # при первом создании БД таблиц может ещё не быть — это нормально
        pass


def upload_dir() -> str:
    """Каталог для загруженных файлов (пособия в PDF)."""
    path = os.environ.get("UPLOAD_DIR") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "uploads"
    )
    os.makedirs(path, exist_ok=True)
    return path


def get_meta(key: str, default: str | None = None) -> str | None:
    row = query_one("SELECT value FROM app_meta WHERE key = ?", (key,))
    return row["value"] if row else default


def set_meta(key: str, value: str) -> None:
    execute(
        "INSERT INTO app_meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def reset_database(path: str | None = None) -> None:
    """Полностью очистить БД (родительская зона)."""
    conn = connect(path)
    try:
        tables = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        for table in tables:
            conn.execute(f"DELETE FROM {table}")
    finally:
        conn.close()
