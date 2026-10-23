"""Продакшн-точка входа WSGI.

Подходит для gunicorn/uwsgi/waitress и для хостингов, которые ищут в
WSGI-файле переменную ``application`` (Alwaysdata, PythonAnywhere и т. п.)::

    gunicorn -w 4 'wsgi:application'
    gunicorn -w 4 'wsgi:app'

Импорт модуля создаёт приложение, применяет миграции и наполняет базу
базовыми данными (идемпотентно), поэтому отдельный шаг «seed» не нужен.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import app  # noqa: E402

# uwsgi по умолчанию ищет именно `application`
application = app

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 5000)),
        debug=False,
    )
