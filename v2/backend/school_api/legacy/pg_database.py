"""PostgreSQL implementation of the legacy ``database`` module.

The v2 backend keeps the proven domain layer (services/*) and exposes the same
``/api/v1`` contract used by the Android app, while all data lives in
PostgreSQL.  This module is installed as ``sys.modules["database"]`` before the
legacy package is imported, so every service talks to PostgreSQL without a
single line changed in the domain code.

Only a small, well understood SQLite compatibility layer is needed:

* ``?`` placeholders become ``%s``;
* ``datetime('now', '-5 minutes')`` is provided by a PL/pgSQL function;
* ``INSERT OR IGNORE`` becomes ``ON CONFLICT DO NOTHING``;
* ``INSERT OR REPLACE`` becomes a targeted ``ON CONFLICT ... DO UPDATE``;
* ``IFNULL`` becomes ``COALESCE`` and ``LIKE`` becomes ``ILIKE``;
* ``BEGIN IMMEDIATE`` becomes ``BEGIN``;
* boolean parameters are stored as integers, because the legacy schema uses
  integer flags.
"""
from __future__ import annotations

import os
import re
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

BASE_DIR = Path(__file__).resolve().parents[4]
SCHEMA_PATH = BASE_DIR / "v2" / "backend" / "sql" / "pg_schema.sql"

_local = threading.local()

# Tables whose SQLite ``INSERT OR REPLACE`` has a known conflict target.
_REPLACE_TARGETS = {
    "learner_accounts": ("(learner_id)", "user_id = EXCLUDED.user_id"),
    "course_topics": (
        "(course_id, topic_slug)",
        "order_index = EXCLUDED.order_index, enabled = EXCLUDED.enabled",
    ),
    "textbook_topics": (
        "(textbook_id, topic_slug)",
        "page = EXCLUDED.page, page_end = EXCLUDED.page_end",
    ),
}


def dsn() -> str:
    """PostgreSQL connection string (``DATABASE_URL``)."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Example: "
            "postgresql://user:password@host:5432/school"
        )
    return url


def _escape_percent(sql: str) -> str:
    """Double literal percent signs, keeping psycopg placeholders intact."""
    sql = re.sub(
        r"%\(([A-Za-z_]\w*)\)s",
        lambda m: "\x00N" + m.group(1) + "\x00",
        sql,
    )
    marker = "\x00PLACEHOLDER\x00"
    sql = sql.replace("%s", marker).replace("%", "%%").replace(marker, "%s")
    return re.sub(r"\x00N([A-Za-z_]\w*)\x00", r"%(\1)s", sql)


def _outside_quotes(sql: str, transform) -> str:
    """Apply ``transform`` to SQL outside single/double quoted literals."""
    out: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(sql):
        ch = sql[i]
        if quote:
            out.append(ch)
            if ch == quote:
                # SQL doubles the quote character inside a literal.
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    out.append(sql[i + 1])
                    i += 1
                else:
                    quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            i += 1
            continue
        out.append(ch)
        i += 1
    return transform("".join(out))


def _replace_placeholders(sql: str) -> str:
    def transform(text: str) -> str:
        text = text.replace("?", "%s")
        # Named parameters (``:me``) are used by a few services.  PostgreSQL
        # spelling is ``%(me)s``.  ``::type`` casts are left alone.
        text = re.sub(
            r"(?<!:):([A-Za-z_]\w*)", r"%(\1)s", text
        )
        return text

    return _outside_quotes(sql, transform)


def _replace_keywords(sql: str) -> str:
    def transform(text: str) -> str:
        text = re.sub(r"\bIFNULL\s*\(", "COALESCE(", text, flags=re.IGNORECASE)
        text = re.sub(r"\bLIKE\b", "ILIKE", text, flags=re.IGNORECASE)
        text = re.sub(
            r"\bBEGIN\s+IMMEDIATE\b", "BEGIN", text, flags=re.IGNORECASE
        )
        return text

    return _outside_quotes(sql, transform)


def translate(sql: str) -> str:
    """Translate one SQLite statement to PostgreSQL."""
    text = sql.strip()
    if not text:
        return text

    replace_info = None
    match = re.match(
        r"INSERT\s+OR\s+REPLACE\s+INTO\s+([a-zA-Z_][\w]*)", text, re.IGNORECASE
    )
    if match:
        table = match.group(1).lower()
        replace_info = _REPLACE_TARGETS.get(table)
        text = re.sub(
            r"INSERT\s+OR\s+REPLACE\s+INTO", "INSERT INTO", text, count=1,
            flags=re.IGNORECASE,
        )

    ignore = bool(re.match(r"INSERT\s+OR\s+IGNORE\s+INTO", text, re.IGNORECASE))
    if ignore:
        text = re.sub(
            r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", text, count=1,
            flags=re.IGNORECASE,
        )

    text = _replace_keywords(_replace_placeholders(text))

    upper = text.upper()
    if (ignore or replace_info is not None) and " ON CONFLICT" not in upper:
        if replace_info is not None:
            target, update = replace_info
            suffix = f" ON CONFLICT {target} DO UPDATE SET {update}"
        else:
            suffix = " ON CONFLICT DO NOTHING"
        stripped = text.rstrip()
        if stripped.endswith(";"):
            text = stripped[:-1] + suffix + ";"
        else:
            text = stripped + suffix

    # psycopg treats ``%`` as the start of a placeholder when parameters are
    # supplied, so literal percent signs must be doubled.  The conversion above
    # already produced ``%s`` markers; protect them while escaping the rest.
    return _escape_percent(text)


def _adapt(value: Any) -> Any:
    """Make Python values acceptable for the legacy integer/text columns."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return type(value)(_adapt(item) for item in value)
    return value


def _adapt_params(params) -> Any:
    if isinstance(params, Mapping):
        return {key: _adapt(value) for key, value in params.items()}
    return tuple(_adapt(item) for item in (params or ()))


class _Cursor:
    """Thin cursor wrapper that exposes the sqlite3 API used by services."""

    def __init__(self, cursor, lastrowid: int = 0) -> None:
        self._cursor = cursor
        self.lastrowid = lastrowid

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)

    def close(self) -> None:
        self._cursor.close()


class Connection:
    """sqlite3.Connection-compatible facade over a psycopg connection."""

    def __init__(self, raw: psycopg.Connection) -> None:
        self.raw = raw
        self._total_changes = 0

    @property
    def total_changes(self) -> int:
        """sqlite3 compatibility: number of rows changed on this connection."""
        return self._total_changes

    def execute(self, sql: str, params: Sequence[Any] = ()) -> _Cursor:
        query = translate(sql)
        adapted = _adapt_params(params)
        lastrowid = 0
        is_insert = query.lstrip()[:6].upper() == "INSERT"
        if is_insert and "RETURNING" not in query.upper():
            # The legacy ``execute()`` returns sqlite3's lastrowid. PostgreSQL
            # has no such concept, so ask for the inserted row. ``RETURNING *``
            # also works for tables with a composite primary key.
            stripped = query.rstrip()
            if stripped.endswith(";"):
                stripped = stripped[:-1]
            query = stripped + " RETURNING *"
        cursor = self.raw.execute(query, adapted)
        if is_insert:
            try:
                row = cursor.fetchone()
            except psycopg.ProgrammingError:
                row = None
            if row:
                lastrowid = int(row.get("id") or 0)
        if cursor.rowcount and cursor.rowcount > 0:
            self._total_changes += cursor.rowcount
        return _Cursor(cursor, lastrowid)

    def executemany(self, sql: str, seq: Iterable[Sequence[Any]]) -> None:
        query = translate(sql)
        with self.raw.cursor() as cursor:
            cursor.executemany(query, [_adapt_params(row) for row in seq])
            if cursor.rowcount and cursor.rowcount > 0:
                self._total_changes += cursor.rowcount

    def executescript(self, script: str) -> None:
        with self.raw.cursor() as cursor:
            cursor.execute(script)

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()

    def close(self) -> None:
        self.raw.close()
        if getattr(_local, "conn", None) is self:
            _local.conn = None

    def __getattr__(self, item: str):
        return getattr(self.raw, item)


def connect(path: str | None = None) -> Connection:
    """Return the current thread's connection (reopened when needed)."""
    current = getattr(_local, "conn", None)
    if current is not None and not current.raw.closed:
        return current
    raw = psycopg.connect(dsn(), autocommit=True, row_factory=dict_row)
    current = Connection(raw)
    _local.conn = current
    return current


def query_all(sql: str, params: Sequence[Any] = ()) -> list[dict]:
    conn = connect()
    return conn.execute(sql, params).fetchall()


def query_one(sql: str, params: Sequence[Any] = ()) -> dict | None:
    conn = connect()
    return conn.execute(sql, params).fetchone()


def execute(sql: str, params: Sequence[Any] = ()) -> int:
    conn = connect()
    return conn.execute(sql, params).lastrowid or 0


def execute_many(sql: str, seq: Iterable[Sequence[Any]]) -> None:
    conn = connect()
    conn.executemany(sql, seq)


def init_db(path: str | None = None) -> None:
    """Create the PostgreSQL schema idempotently."""
    script = SCHEMA_PATH.read_text(encoding="utf-8")
    with psycopg.connect(dsn(), autocommit=True) as raw:
        with raw.cursor() as cursor:
            cursor.execute(script)
    # Reset cached thread connection after a schema change.
    current = getattr(_local, "conn", None)
    if current is not None:
        try:
            current.close()
        except Exception:
            pass
        _local.conn = None


def db_path() -> str:
    """Kept for compatibility with tooling that introspects the module."""
    return os.environ.get("DATABASE_URL", "")


def upload_dir() -> str:
    """Directory for uploaded files (PDF textbooks)."""
    path = os.environ.get("UPLOAD_DIR") or str(BASE_DIR / "data" / "uploads")
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
    """Delete every row while keeping the schema (used by tests/demo data)."""
    with psycopg.connect(dsn(), autocommit=True) as raw:
        with raw.cursor() as cursor:
            cursor.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
            tables = [row["tablename"] for row in cursor.fetchall()]
            if tables:
                joined = ", ".join(f'"{name}"' for name in tables)
                cursor.execute(f"TRUNCATE {joined} RESTART IDENTITY CASCADE")


def migrate(path: str | None = None) -> None:
    """Migrations are part of pg_schema.sql; kept as a no-op."""
    return None
