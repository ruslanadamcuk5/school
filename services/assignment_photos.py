"""Фотографии письменных ответов к работам.

Файлы лежат вне статики: доступ к ним выдаёт только Flask-маршрут после
проверки, что пользователь имеет отношение к работе. Имена генерируются
случайно, исходное имя файла не используется.
"""
from __future__ import annotations

import os
import uuid

from database import upload_dir

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
MAX_BYTES = 8 * 1024 * 1024
MAX_FILES = 6


def photos_root() -> str:
    path = os.path.join(upload_dir(), "assignment_answers")
    os.makedirs(path, exist_ok=True)
    return path


def save_photos(files, assignment_id: int, student_id: int) -> list[str]:
    """Сохранить фотографии ответов и вернуть относительные пути.

    Некорректные файлы пропускаются, но если не удалось сохранить ни одного
    файла, выбрасывается ValueError с понятным текстом.
    """
    saved: list[str] = []
    target_dir = os.path.join(photos_root(), str(assignment_id), str(student_id))
    os.makedirs(target_dir, exist_ok=True)
    for storage in list(files or [])[:MAX_FILES]:
        filename = (getattr(storage, "filename", "") or "").strip()
        if not filename:
            continue
        extension = os.path.splitext(filename)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            continue
        data = storage.read(MAX_BYTES + 1)
        if not data or len(data) > MAX_BYTES:
            continue
        new_name = f"{uuid.uuid4().hex}{extension}"
        with open(os.path.join(target_dir, new_name), "wb") as handle:
            handle.write(data)
        saved.append(f"{assignment_id}/{student_id}/{new_name}")
    if files and not saved:
        raise ValueError(
            "Не удалось сохранить фото. Загрузите JPG/PNG/WebP размером до 8 МБ."
        )
    return saved


def absolute_path(relative_path: str) -> str | None:
    """Безопасно превратить относительный путь в абсолютный."""
    if not relative_path:
        return None
    root = os.path.realpath(photos_root())
    target = os.path.realpath(os.path.join(root, relative_path))
    if not target.startswith(root + os.sep):
        return None
    return target if os.path.isfile(target) else None


def delete_photos(relative_paths: list[str]) -> None:
    for relative in relative_paths or []:
        path = absolute_path(relative)
        if path:
            try:
                os.remove(path)
            except OSError:
                pass
