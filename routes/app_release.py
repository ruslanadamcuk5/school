"""Скачивание Android-приложения и публичная проверка обновлений."""
from __future__ import annotations

from flask import Blueprint, abort, jsonify, send_file, url_for

from services import release as release_service

bp = Blueprint("app_release", __name__)


@bp.get("/download/android")
def download():
    """Отдать актуальный APK. Ссылка постоянная, содержимое обновляется."""
    item = release_service.info()
    path = release_service.file_path(item)
    if item is None or path is None:
        abort(404)
    return send_file(
        path,
        mimetype="application/vnd.android.package-archive",
        as_attachment=True,
        download_name=item["download_name"],
        conditional=True,
        max_age=0,
    )


@bp.get("/api/v1/app/version")
def version():
    """Публичные метаданные для автообновления Android-приложения."""
    item = release_service.info()
    if item is None:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "app_not_published",
                    "message": "Приложение пока не опубликовано на сервере.",
                }
            ),
            404,
        )
    return jsonify(
        {
            "ok": True,
            "version_code": item["version_code"],
            "version_name": item["version_name"],
            # Параметр версии делает ссылку уникальной: браузер не пытается
            # докачать старый частично загруженный файл по тому же адресу.
            "download_url": url_for(
                "app_release.download", _external=True, v=item["version_code"]
            ),
            "size": item["size"],
            "sha256": item["sha256"],
            "notes": item["notes"],
            "published_at": item["published_at"],
        }
    )
