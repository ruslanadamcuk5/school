"""Установить пароль администратора (для демо и восстановления доступа)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import query_one  # noqa: E402
from services import auth  # noqa: E402

login = sys.argv[1] if len(sys.argv) > 1 else "admin"
password = sys.argv[2] if len(sys.argv) > 2 else "math2025"

row = query_one("SELECT id FROM users WHERE role = 'admin'")
if row:
    auth.update_user(row["id"], login=login)
    auth.set_password(row["id"], password)
    print(f"Пароль администратора обновлён: {login} / {password}")
else:
    auth.create_user(login, password, auth.ROLE_ADMIN, "Главный", "платформы")
    print(f"Создан администратор: {login} / {password}")
