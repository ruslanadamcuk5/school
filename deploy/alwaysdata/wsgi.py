"""WSGI-файл для Alwaysdata (Sites → Python WSGI).

Что делает файл:
* подхватывает ``deploy/alwaysdata/.env`` (если он есть);
* создаёт постоянный ``SECRET_KEY`` в ``data/.secret_key`` (если переменная
  окружения не задана) — иначе сессии слетали бы при каждом перезапуске;
* кладёт базу и загруженные PDF в ``data/`` внутри проекта;
* включает доверие заголовкам reverse-proxy (HTTPS на Alwaysdata).

Подключение в панели Alwaysdata:

    Тип сайта:        Python WSGI
    Working directory: /home/<логин>/edu-math
    Python version:    3.12
    Virtualenv:        /home/<логин>/.virtualenvs/edu-math
    WSGI file:         /home/<логин>/edu-math/deploy/alwaysdata/wsgi.py

Подробная инструкция — deploy/alwaysdata/README.md
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]  # deploy/alwaysdata/wsgi.py -> корень проекта
DATA = ROOT / "data"

ENV_FILE = ROOT / "deploy" / "alwaysdata" / ".env"


def _load_env(path: Path) -> None:
    """Минимальный парсер файла KEY=VALUE (без внешних зависимостей)."""
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


_load_env(ENV_FILE)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA.mkdir(parents=True, exist_ok=True)


def _persistent_secret() -> str:
    """SECRET_KEY: из окружения, из data/.secret_key или новый постоянный."""
    env_secret = (os.environ.get("SECRET_KEY") or "").strip()
    if env_secret and env_secret != "change-me-in-production":
        return env_secret
    path = DATA / ".secret_key"
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    except OSError:
        pass
    value = secrets.token_urlsafe(48)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except OSError:
        pass
    return value


os.environ.setdefault("APP_ENV", "production")
os.environ.setdefault("DATABASE_PATH", str(DATA / "math_tutor.db"))
os.environ.setdefault("UPLOAD_DIR", str(DATA / "uploads"))
os.environ.setdefault("TRUST_PROXY", "1")
os.environ.setdefault("COOKIE_SECURE", "1")
os.environ["SECRET_KEY"] = _persistent_secret()

from app import app  # noqa: E402

application = app
