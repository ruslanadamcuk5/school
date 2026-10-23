"""Локальный запуск для разработки:  python run.py"""
from __future__ import annotations

import os
import socket
import sys

from app import create_app

app = create_app(os.environ.get("APP_ENV", "development"))


def port_busy(host: str, port: int) -> bool:
    """Занят ли порт другим процессом."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    development = os.environ.get("APP_ENV", "development") == "development"

    # Проверяем порт только в родительском процессе: при автоперезагрузке
    # сокет держит именно он, а дочерний процесс перезапускается по файлам.
    if not os.environ.get("WERKZEUG_RUN_MAIN") and port_busy(host, port):
        print(f"\n  ⚠ Порт {port} уже занят другим экземпляром приложения.")
        print("    Остановите его или задайте другой PORT (например, PORT=5001).")
        print("    Иначе запросы будут попадать на устаревшую версию кода.\n")
        sys.exit(1)

    print(f"\n  📚 Учусь · 3–4 класс: http://{host}:{port}\n")
    # В разработке включаем автоперезагрузку: изменения в коде применяются
    # сразу, без ручного перезапуска сервера.
    app.run(host=host, port=port, debug=development, use_reloader=development)
