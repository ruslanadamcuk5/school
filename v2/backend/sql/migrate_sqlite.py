#!/usr/bin/env python3
"""Перенос данных из SQLite в PostgreSQL для платформы «Школьник».

Скрипт читает рабочую SQLite-базу (ту, с которой работал Flask) и копирует
все таблицы в PostgreSQL. Он идемпотентен: повторный запуск не создаёт
дубликатов благодаря ``ON CONFLICT DO NOTHING``. Схему PostgreSQL создавать
не нужно — её готовит сам backend при первом запуске (или ``pg_schema.sql``).

Примеры
-------
    # посмотреть, что будет скопировано
    DATABASE_URL=postgresql://user@host/db \
        python v2/backend/sql/migrate_sqlite.py --sqlite data/math_tutor.db --dry-run

    # перенести данные в чистую базу
    DATABASE_URL=postgresql://user@host/db \
        python v2/backend/sql/migrate_sqlite.py --sqlite data/math_tutor.db

    # заменить данные в уже заполненной базе (осторожно!)
    DATABASE_URL=postgresql://user@host/db \
        python v2/backend/sql/migrate_sqlite.py --truncate --yes

Файлы, загруженные пользователями (PDF учебников, обложки), лежат отдельно в
``uploads/`` (или ``UPLOAD_DIR``) и переносятся обычным ``rsync``/``scp``.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - подсказка при запуске без зависимостей
    sys.exit("Нужен psycopg: pip install 'psycopg[binary]'")


BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_SQLITE = BASE_DIR / "data" / "math_tutor.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SQLite → PostgreSQL перенос данных")
    parser.add_argument(
        "--sqlite",
        default=os.environ.get("DATABASE_PATH", str(DEFAULT_SQLITE)),
        help="путь к SQLite-базе (по умолчанию DATABASE_PATH или data/math_tutor.db)",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="строка подключения PostgreSQL (по умолчанию DATABASE_URL)",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="очистить таблицы PostgreSQL перед копированием",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="подтвердить опасное действие (нужно вместе с --truncate)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="только показать план, ничего не записывать",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=250,
        help="сколько строк вставлять за один запрос (по умолчанию 250)",
    )
    parser.add_argument(
        "--only",
        default="",
        help="копировать только эти таблицы (через запятую)",
    )
    return parser.parse_args()


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows]


def sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({quote(table)})")]


def pg_tables(conn: psycopg.Connection) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name"""
        )
        return [row["table_name"] for row in cur.fetchall()]


def pg_columns(conn: psycopg.Connection, table: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position""",
            (table,),
        )
        return [row["column_name"] for row in cur.fetchall()]


def pg_dependencies(conn: psycopg.Connection) -> dict[str, set[str]]:
    """Для каждой таблицы — таблицы, которые должны быть скопированы раньше."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT conrelid::regclass::text AS child,
                      confrelid::regclass::text AS parent
                 FROM pg_constraint
                WHERE contype = 'f' AND connamespace = 'public'::regnamespace"""
        )
        deps: dict[str, set[str]] = {}
        for row in cur.fetchall():
            child = row["child"].split(".")[-1].strip('"')
            parent = row["parent"].split(".")[-1].strip('"')
            if child != parent:
                deps.setdefault(child, set()).add(parent)
        return deps


def sort_tables(tables: list[str], deps: dict[str, set[str]]) -> list[str]:
    """Топологическая сортировка: родители раньше детей."""
    pending = {table: {parent for parent in deps.get(table, set()) if parent in tables} for table in tables}
    ordered: list[str] = []
    while pending:
        ready = sorted(table for table, parents in pending.items() if not parents)
        if not ready:
            # Цикл (например, взаимные ссылки) — добавляем остаток как есть.
            ordered.extend(sorted(pending))
            break
        for table in ready:
            ordered.append(table)
            pending.pop(table)
        for parents in pending.values():
            parents.difference_update(ready)
    return ordered


def truncate(conn: psycopg.Connection, tables: list[str]) -> None:
    if not tables:
        return
    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE " + ", ".join(quote(table) for table in tables)
            + " RESTART IDENTITY CASCADE"
        )
    conn.commit()


def set_sequences(conn: psycopg.Connection, tables: list[str]) -> None:
    id_tables = {table for table in tables if "id" in pg_columns(conn, table)}
    with conn.cursor() as cur:
        for table in tables:
            if table not in id_tables:
                continue
            cur.execute(
                "SELECT pg_get_serial_sequence(%s, 'id') AS seq",
                (f"public.{table}",),
            )
            row = cur.fetchone()
            seq = row["seq"] if row else None
            if not seq:
                continue
            cur.execute(f"SELECT COALESCE(MAX(id), 0) AS max_id FROM {quote(table)}")
            max_id = int(cur.fetchone()["max_id"] or 0)
            # setval(..., false) — следующий id будет max_id + 1.
            cur.execute("SELECT setval(%s, %s, false)", (seq, max(max_id, 0) + 1))
    conn.commit()


def copy_table(
    source: sqlite3.Connection,
    target: psycopg.Connection,
    table: str,
    columns: list[str],
    *,
    batch: int,
    dry_run: bool,
) -> tuple[int, int]:
    """Копирует одну таблицу. Возвращает (вставлено, пропущено дубликатов)."""
    if not columns:
        return (0, 0)
    select_sql = (
        f"SELECT {', '.join(quote(col) for col in columns)} FROM {quote(table)}"
    )
    rows = source.execute(select_sql).fetchall()
    if dry_run or not rows:
        return (len(rows), 0)

    placeholders = ", ".join(["%s"] * len(columns))
    column_list = ", ".join(quote(col) for col in columns)
    insert_sql = (
        f"INSERT INTO {quote(table)} ({column_list}) VALUES ({placeholders}) "
        "ON CONFLICT DO NOTHING"
    )

    inserted = 0
    with target.cursor() as cur:
        for start in range(0, len(rows), batch):
            chunk = rows[start : start + batch]
            values = [tuple(row) for row in chunk]
            cur.executemany(insert_sql, values)
            inserted += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    target.commit()
    return (inserted, len(rows) - inserted)


def verify_counts(
    source: sqlite3.Connection,
    target: psycopg.Connection,
    tables: list[str],
) -> list[tuple[str, int, int]]:
    """Сверяет количество строк. Возвращает расхождения (таблица, SQLite, PG)."""
    mismatches: list[tuple[str, int, int]] = []
    for table in tables:
        sqlite_count = int(source.execute(f"SELECT COUNT(*) FROM {quote(table)}").fetchone()[0])
        with target.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS c FROM {quote(table)}")
            pg_count = int(cur.fetchone()["c"])
        if sqlite_count != pg_count:
            mismatches.append((table, sqlite_count, pg_count))
    return mismatches


def main() -> int:
    args = parse_args()
    sqlite_path = Path(args.sqlite).expanduser()
    if not sqlite_path.exists():
        sys.exit(f"SQLite-база не найдена: {sqlite_path}")
    if not args.database_url.strip():
        sys.exit("Укажите DATABASE_URL или --database-url")
    if args.truncate and not args.yes and not args.dry_run:
        sys.exit("Очистка таблиц требует подтверждения: добавьте --yes")
    if args.batch < 1:
        sys.exit("--batch должен быть положительным")

    source = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    target = psycopg.connect(args.database_url, row_factory=dict_row)

    try:
        tables = pg_tables(target)
        existing = set(sqlite_tables(source))
        deps = pg_dependencies(target)
        ordered = sort_tables(tables, deps)
        only = {name.strip() for name in args.only.split(",") if name.strip()}
        if only:
            ordered = [table for table in ordered if table in only]

        to_copy = [table for table in ordered if table in existing]
        missing = [table for table in ordered if table not in existing]
        unknown = sorted(existing - set(tables))

        print(f"SQLite:      {sqlite_path}")
        print(f"PostgreSQL:  {args.database_url.split('@')[-1]}")
        print(f"Таблиц к копированию: {len(to_copy)}")
        if missing:
            print(f"Нет в SQLite (пропущены): {', '.join(missing)}")
        if unknown:
            print(f"Нет в PostgreSQL (пропущены): {', '.join(unknown)}")

        if args.truncate:
            print("Очистка таблиц PostgreSQL…")
            if not args.dry_run:
                truncate(target, to_copy)

        total_rows = 0
        total_dupes = 0
        failed: list[tuple[str, str]] = []
        for table in to_copy:
            src_cols = sqlite_columns(source, table)
            dst_cols = set(pg_columns(target, table))
            columns = [col for col in src_cols if col in dst_cols]
            dropped = [col for col in src_cols if col not in dst_cols]
            if dropped:
                print(f"  ! {table}: пропущены колонки без пары в PostgreSQL: {', '.join(dropped)}")
            try:
                inserted, dupes = copy_table(
                    source, target, table, columns,
                    batch=args.batch, dry_run=args.dry_run,
                )
            except Exception as exc:  # noqa: BLE001 — показываем и продолжаем
                target.rollback()
                failed.append((table, str(exc).strip().splitlines()[0]))
                print(f"  ✗ {table}: {failed[-1][1]}")
                continue
            total_rows += inserted
            total_dupes += dupes
            suffix = " (план)" if args.dry_run else ""
            print(f"  ✓ {table}: {inserted}{suffix}" + (f", пропущено дубликатов {dupes}" if dupes else ""))

        if not args.dry_run:
            set_sequences(target, to_copy)
            mismatches = verify_counts(source, target, to_copy)
            if mismatches:
                print()
                print("Расхождения количества строк (SQLite / PostgreSQL):")
                for table, sqlite_count, pg_count in mismatches:
                    print(f"  ! {table}: {sqlite_count} / {pg_count}")
            else:
                print("Проверка количества строк: всё совпадает.")

        print()
        if args.dry_run:
            print(f"План: {total_rows} строк в {len(to_copy)} таблицах. Ничего не записано.")
        else:
            print(f"Готово: вставлено {total_rows} строк, пропущено дубликатов {total_dupes}.")
            print("Последовательности id выставлены по максимальным значениям.")
        if failed:
            print(f"Не удалось скопировать {len(failed)} таблиц(ы):")
            for table, error in failed:
                print(f"  - {table}: {error}")
            return 1
        return 0
    finally:
        source.close()
        target.close()


if __name__ == "__main__":
    raise SystemExit(main())
