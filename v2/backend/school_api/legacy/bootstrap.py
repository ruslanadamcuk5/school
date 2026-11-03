"""Bootstrap the legacy Flask application on top of PostgreSQL.

The existing project contains ~13k lines of domain logic and 163 JSON API
endpoints.  Rewriting all of that at once would be reckless.  Instead the v2
gateway installs a PostgreSQL ``database`` module and mounts the unchanged
``/api/v1`` application behind FastAPI.  Android clients keep working, the SPA
gets the same data, and the domain layer can be migrated to native FastAPI
routers incrementally.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from threading import Lock

PROJECT_ROOT = Path(__file__).resolve().parents[4]

_lock = Lock()
_flask_app = None


def _install_postgres() -> None:
    """Install the PostgreSQL database module before any legacy import."""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from school_api.legacy import pg_database

    sys.modules["database"] = pg_database

    # The domain layer catches sqlite3.Error to degrade gracefully.  Map it to
    # psycopg's exception hierarchy so those guards keep working.
    import sqlite3

    import psycopg

    sqlite3.Error = psycopg.Error  # type: ignore[attr-defined]
    sqlite3.IntegrityError = psycopg.errors.IntegrityError  # type: ignore[attr-defined]
    sqlite3.OperationalError = psycopg.OperationalError  # type: ignore[attr-defined]
    sqlite3.ProgrammingError = psycopg.ProgrammingError  # type: ignore[attr-defined]

    os.environ.setdefault("APP_ENV", "production")
    os.environ.setdefault("DATABASE_PATH", str(PROJECT_ROOT / "data" / "math_tutor.db"))


def get_flask_app():
    """Create (once) and return the legacy WSGI application."""
    global _flask_app
    if _flask_app is not None:
        return _flask_app
    with _lock:
        if _flask_app is not None:
            return _flask_app
        _install_postgres()
        from app import create_app as create_flask_app

        _flask_app = create_flask_app()
        return _flask_app
