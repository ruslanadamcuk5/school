"""Конфигурация приложения (production-ready, настройка через переменные окружения)."""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    """Базовая конфигурация."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    DATABASE_PATH = os.environ.get(
        "DATABASE_PATH", str(BASE_DIR / "data" / "math_tutor.db")
    )

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("COOKIE_SECURE", False)
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=365)

    # Загрузка учебников (PDF). Лимит задаётся в мегабайтах и общий для всего запроса.
    MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 60)
    # небольшой запас на поля multipart-формы поверх самого файла
    MAX_CONTENT_LENGTH = (MAX_UPLOAD_MB + 2) * 1024 * 1024

    JSON_AS_ASCII = False
    TEMPLATES_AUTO_RELOAD = False
    SEND_FILE_MAX_AGE_DEFAULT = 60 * 60 * 24 * 7  # учебник кэшируется неделями

    # Игровые параметры
    TASKS_PER_ROUND = _int("TASKS_PER_ROUND", 8)
    BOSS_TASKS = _int("BOSS_TASKS", 3)
    MAX_HINTS = 3
    XP_PER_CORRECT = 10
    XP_PER_BOSS = 50
    COINS_PER_CORRECT = 2
    COIN_COST_HINT = 3
    DAILY_TASKS = _int("DAILY_TASKS", 3)

    # Безопасность
    PIN_MAX_ATTEMPTS = 5
    PIN_LOCK_SECONDS = 300

    # ИИ (облачные модели). По умолчанию выключено — приложение работает офлайн.
    AI_TIMEOUT = _int("AI_TIMEOUT", 45)
    AI_MAX_PER_HOUR = _int("AI_MAX_PER_HOUR", 60)

    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    # Доверять X-Forwarded-* от reverse-proxy (Alwaysdata, nginx, Caddy).
    TRUST_PROXY = _bool("TRUST_PROXY", False)


class DevelopmentConfig(Config):
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True
    # стабильный ключ, чтобы сессия не слетала при перезапуске сервера
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-edu-math-local")


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    # Шаблоны перечитываются при изменении файла. Иначе uWSGI с lazy-apps
    # держит старую версию страницы в воркере до перезапуска сайта.
    TEMPLATES_AUTO_RELOAD = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    SECRET_KEY = "testing-secret"
    DATABASE_PATH = str(BASE_DIR / "data" / "test_math_tutor.db")


def get_config(name: str | None = None) -> type[Config]:
    name = name or os.environ.get("APP_ENV", "production")
    return {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "testing": TestingConfig,
    }.get(name.lower(), ProductionConfig)
