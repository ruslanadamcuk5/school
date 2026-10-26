"""Регистрация blueprints."""
from __future__ import annotations

from .admin import bp as admin_bp
from .ai import bp as ai_bp
from .api_v1 import bp as api_v1_bp
from .app_release import bp as app_release_bp
from .auth import bp as auth_bp
from .library import bp as library_bp
from .main import bp as main_bp
from .parent import bp as parent_bp
from .play import bp as play_bp
from .student import bp as student_bp
from .teacher import bp as teacher_bp

BLUEPRINTS = (
    main_bp,
    app_release_bp,
    auth_bp,
    library_bp,
    ai_bp,
    api_v1_bp,
    play_bp,
    teacher_bp,
    student_bp,
    parent_bp,
    admin_bp,
)

__all__ = ["BLUEPRINTS"]
