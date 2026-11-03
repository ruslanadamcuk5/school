"""Convert the legacy SQLite schema to PostgreSQL.

Run from the repository root:

    python v2/backend/sql/convert_schema.py

The legacy application stores timestamps as UTC text.  We keep that contract
(services compare strings), but provide a PostgreSQL ``datetime()`` function
with the same semantics as SQLite's.  This lets the existing domain layer run
unchanged while the data lives in PostgreSQL.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "schema.sql"
LEGACY_DATABASE = ROOT / "database.py"
TARGET = Path(__file__).with_name("pg_schema.sql")

HEADER = """-- ============================================================
--  PostgreSQL schema for the v2 application.
--  Generated from schema.sql by convert_schema.py.
--  Do not edit by hand: change schema.sql and regenerate.
-- ============================================================

-- SQLite-compatible UTC timestamp helper.  The legacy domain layer stores and
-- compares timestamps as strings in the format YYYY-MM-DD HH:MM:SS.
CREATE OR REPLACE FUNCTION datetime(ts text, modifier text DEFAULT NULL)
RETURNS text
LANGUAGE plpgsql
AS $$
BEGIN
    IF ts = 'now' THEN
        IF modifier IS NULL THEN
            RETURN to_char((now() AT TIME ZONE 'utc'), 'YYYY-MM-DD HH24:MI:SS');
        END IF;
        RETURN to_char(
            (now() AT TIME ZONE 'utc') + modifier::interval,
            'YYYY-MM-DD HH24:MI:SS'
        );
    END IF;
    IF modifier IS NULL THEN
        RETURN ts;
    END IF;
    RETURN to_char(ts::timestamp + modifier::interval, 'YYYY-MM-DD HH24:MI:SS');
END;
$$;

"""


def convert(sql: str) -> str:
    out = sql
    out = out.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    out = out.replace("DEFAULT (datetime('now'))", "DEFAULT datetime('now')")
    out = out.replace("INSERT OR IGNORE INTO", "INSERT INTO")
    # In schema seed rows there is no conflict target: use DO NOTHING.
    out = re.sub(
        r"(INSERT INTO\s+\w+\s*\([^;]+?\)\s*VALUES\s*\([^;]+?\))\s*;",
        r"\1 ON CONFLICT DO NOTHING;",
        out,
        flags=re.IGNORECASE,
    )
    return out


def migration_sql() -> str:
    """Columns added to old databases by ``database.migrate()``.

    ``schema.sql`` only contains the initial schema; the live application adds
    a number of columns at startup.  The PostgreSQL schema needs them too, but
    expressed as idempotent ``ADD COLUMN IF NOT EXISTS`` statements.
    """
    tree = ast.parse(LEGACY_DATABASE.read_text(encoding="utf-8"))
    columns: list[tuple[str, str, str]] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
            value = node.value
        else:
            continue
        if "MIGRATIONS" not in targets:
            continue
        columns = ast.literal_eval(value)
        break
    lines = ["", "-- Columns added by legacy database.migrate()."]
    for table, column, definition in columns:
        lines.append(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition};"
        )
    lines += [
        "",
        "-- Indexes and cleanups from database.migrate().",
        "CREATE INDEX IF NOT EXISTS idx_learners_family ON learners(family_key);",
        "CREATE INDEX IF NOT EXISTS idx_learners_device ON learners(device_id);",
        "CREATE INDEX IF NOT EXISTS idx_topics_subject "
        "ON topics(subject_id, grade, order_index);",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub "
        "ON users(google_sub) WHERE google_sub IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_textbook_topics_slug "
        "ON textbook_topics(topic_slug);",
        "CREATE INDEX IF NOT EXISTS idx_assignments_student "
        "ON assignments(student_id, status);",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_dedup "
        "ON app_notifications(dedup_key) WHERE dedup_key <> '';",
        "CREATE INDEX IF NOT EXISTS idx_notifications_user "
        "ON app_notifications(user_id, is_read, created_at);",
        "DROP TABLE IF EXISTS library_covers;",
        "DROP TABLE IF EXISTS user_books;",
        "DROP TABLE IF EXISTS book_recommendations;",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    converted = convert(source)
    TARGET.write_text(
        HEADER + "\n" + converted + "\n" + migration_sql(), encoding="utf-8"
    )
    print(f"wrote {TARGET} ({len(converted)} bytes)")


if __name__ == "__main__":
    main()
