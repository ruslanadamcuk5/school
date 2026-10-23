"""Проверка готовности приложения к продакшну.

Запуск (перед деплоем или после)::

    python tools/prod_check.py

Проверяет окружение, базу, каталог загрузок и ключевые страницы.
Возвращает код 1, если что-то критично не так.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    ok = bool(ok)
    _results.append((name, ok, detail))
    mark = "OK  " if ok else "FAIL"
    line = f"[{mark}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    return ok


def warn(name: str, detail: str) -> None:
    _results.append((name, True, detail))
    print(f"[WARN] {name} — {detail}")


def main() -> int:
    os.environ.setdefault("APP_ENV", "production")

    print("=" * 68)
    print("  Проверка готовности: Учусь")
    print("=" * 68)
    print(f"  Python:   {sys.version.split()[0]}")
    print(f"  APP_ENV:  {os.environ.get('APP_ENV')}")
    print(f"  Каталог:  {ROOT}")
    print("-" * 68)

    check("Python 3.10+", sys.version_info >= (3, 10), sys.version.split()[0])

    secret = (os.environ.get("SECRET_KEY") or "").strip()
    if not secret:
        warn("SECRET_KEY", "не задан — на Alwaysdata создастся data/.secret_key")
    elif secret == "change-me-in-production":
        check("SECRET_KEY изменён", False, "значение по умолчанию недопустимо")
    else:
        check("SECRET_KEY задан", len(secret) >= 24, f"{len(secret)} символов")

    try:
        from app import app
    except Exception as exc:  # pragma: no cover - сюда попадаем при битой конфигурации
        check("Импорт приложения", False, f"{type(exc).__name__}: {exc}")
        return _summary()

    check("Приложение создано", True)

    from database import db_path

    path = Path(db_path())
    check("Каталог БД существует", path.parent.is_dir(), str(path.parent))
    check("Файл БД создан", path.is_file(), str(path))
    try:
        conn = sqlite3.connect(path)
        try:
            tables = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
            ).fetchone()[0]
        finally:
            conn.close()
        check("Схема БД", tables > 10, f"таблиц: {tables}")
    except sqlite3.Error as exc:
        check("Схема БД", False, str(exc))

    upload = Path(os.environ.get("UPLOAD_DIR") or (ROOT / "data" / "uploads"))
    try:
        upload.mkdir(parents=True, exist_ok=True)
        probe = upload / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        check("Каталог загрузок доступен для записи", True, str(upload))
    except OSError as exc:
        check("Каталог загрузок доступен для записи", False, f"{upload}: {exc}")

    app.config["TESTING"] = True
    client = app.test_client()
    for url, expected in (
        ("/healthz", 200),
        ("/login", 200),
        ("/", 200),
    ):
        try:
            response = client.get(url)
            check(f"GET {url}", response.status_code == expected, f"HTTP {response.status_code}")
        except Exception as exc:  # pragma: no cover
            check(f"GET {url}", False, f"{type(exc).__name__}: {exc}")

    try:
        payload = client.get("/healthz").get_json() or {}
        check("База отвечает через /healthz", bool(payload.get("db")), str(payload.get("status")))
    except Exception as exc:  # pragma: no cover
        check("База отвечает через /healthz", False, str(exc))

    return _summary()


def _summary() -> int:
    failed = [item for item in _results if not item[1]]
    print("-" * 68)
    if failed:
        print(f"  ПРОВЕРКА НЕ ПРОЙДЕНА: ошибок {len(failed)}")
        for name, _, detail in failed:
            print(f"    - {name}: {detail}")
        return 1
    print("  ВСЁ ГОТОВО ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
