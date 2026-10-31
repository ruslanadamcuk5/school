"""Математика: репетитор — точка входа приложения.

Запуск для разработки:  python run.py
Продакшн:               gunicorn -w 4 'app:create_app()'  (см. wsgi.py)
"""
from __future__ import annotations

import logging
import os
import secrets
import sys
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request, session, url_for

from config import get_config
from database import init_db, query_one
from routes import BLUEPRINTS

log = logging.getLogger("edu-math")


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(get_config(config_name))
    # ключ из окружения всегда актуален (класс конфигурации мог импортироваться раньше)
    env_secret = os.environ.get("SECRET_KEY")
    if env_secret:
        app.config["SECRET_KEY"] = env_secret

    _configure_logging(app)
    _ensure_secret_key(app)
    _configure_proxy(app)

    with app.app_context():
        init_db()
        from seed import seed_base_entities, sync_content, sync_starter_topics

        admin_password = seed_base_entities()
        sync_content()
        sync_starter_topics()
        from services import topics as topics_service

        topics_service.sync_course_topics()
        from routes.parent import ensure_parent_pin

        pin = ensure_parent_pin()
        if pin:
            log.warning("=" * 62)
            log.warning("  PIN-код родительской зоны: %s", pin)
            log.warning("  (сохраните его — он понадобится для входа в раздел родителя)")
            log.warning("=" * 62)
        if admin_password:
            log.warning("=" * 62)
            log.warning("  Создан администратор: логин admin, пароль %s", admin_password)
            log.warning("  (смените пароль в разделе «Профиль»)")
            log.warning("=" * 62)

    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

    _register_filters(app)
    _register_context(app)
    _register_globals(app)
    _register_security(app)
    _register_errors(app)

    @app.route("/favicon.ico")
    def favicon():
        return app.send_static_file("img/favicon.svg")

    @app.route("/healthz")
    def healthz():
        try:
            query_one("SELECT 1 AS ok")
            db_ok = True
        except Exception:  # pragma: no cover
            db_ok = False
        return jsonify({"status": "ok" if db_ok else "degraded", "db": db_ok,
                        "time": datetime.now(timezone.utc).isoformat()}), (200 if db_ok else 503)

    @app.after_request
    def _no_store(resp):
        path = request.path
        if path.startswith("/static/") and not app.debug:
            resp.headers["Cache-Control"] = "public, max-age=604800"
        elif path.startswith("/api/v1/books/") and path.endswith(".png"):
            # Страницы PDF неизменны: разрешаем дисковый кэш мобильному клиенту.
            resp.headers["Cache-Control"] = "private, max-age=86400"
        else:
            resp.headers["Cache-Control"] = "no-store, must-revalidate"
        return resp

    return app


def _configure_logging(app: Flask) -> None:
    level = getattr(logging, str(app.config.get("LOG_LEVEL", "INFO")).upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    app.logger.setLevel(level)


def _ensure_secret_key(app: Flask) -> None:
    """Гарантировать непустой SECRET_KEY.

    Пустая переменная окружения (частая ошибка в ``.env``) раньше приводила
    к ``RuntimeError`` при первом обращении к сессии. Теперь ключ создаётся
    один раз и сохраняется в ``data/.secret_key``, чтобы сессии переживали
    перезапуск приложения.
    """
    env_key = (os.environ.get("SECRET_KEY") or "").strip()
    if env_key:
        app.config["SECRET_KEY"] = env_key
        return

    current = (app.config.get("SECRET_KEY") or "").strip()
    if current and current != "change-me-in-production":
        app.config["SECRET_KEY"] = current
        return

    from pathlib import Path

    path = Path(app.root_path) / "data" / ".secret_key"
    try:
        if path.exists():
            stored = path.read_text(encoding="utf-8").strip()
            if stored:
                app.config["SECRET_KEY"] = stored
                return
        path.parent.mkdir(parents=True, exist_ok=True)
        generated = secrets.token_urlsafe(48)
        path.write_text(generated, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:  # pragma: no cover - экзотические файловые системы
            pass
        app.config["SECRET_KEY"] = generated
        app.logger.warning(
            "SECRET_KEY не задан — создан постоянный ключ %s. "
            "Для продакшена лучше задать переменную окружения.",
            path,
        )
    except OSError:  # pragma: no cover
        app.config["SECRET_KEY"] = secrets.token_urlsafe(48)
        app.logger.warning(
            "SECRET_KEY не задан — сгенерирован временный ключ. "
            "Задайте переменную окружения SECRET_KEY для продакшена."
        )


def _configure_proxy(app: Flask) -> None:
    """Доверять заголовкам X-Forwarded-* от reverse-proxy (HTTPS на хостинге)."""
    if not app.config.get("TRUST_PROXY"):
        return
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)


def _register_filters(app: Flask) -> None:
    import json

    @app.template_filter("fromjson")
    def _fromjson(value: str):
        try:
            return json.loads(value or "[]")
        except (ValueError, TypeError):
            return []

    @app.template_filter("filesize")
    def _filesize(value: int) -> str:
        size = float(value or 0)
        for unit in ("Б", "КБ", "МБ", "ГБ"):
            if size < 1024:
                return f"{size:.0f} {unit}" if unit == "Б" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} ТБ"


def _user_grade_for_theme(user, learner) -> int | None:
    """Определяет класс пользователя для выбора темы оформления."""
    from services import auth as _auth, orgs as _orgs_service

    if user and user["role"] == _auth.ROLE_STUDENT:
        try:
            classes = _orgs_service.classes_of_student(int(user["id"]))
            if classes:
                return int(classes[0]["grade"])
        except Exception:  # pragma: no cover
            pass
    if learner is not None:
        try:
            grade = learner["grade"]
        except (KeyError, TypeError, IndexError):
            grade = None
        return int(grade) if grade else None
    return None


def _theme_mode(user, learner) -> str:
    """Игровая тема — только 1–4 классы, у остальных строгий учебный дизайн."""
    from services import auth as _auth

    if user and user["role"] in (_auth.ROLE_ADMIN, _auth.ROLE_TEACHER, _auth.ROLE_PARENT):
        return "adult"
    grade = _user_grade_for_theme(user, learner)
    if grade is None or grade <= 4:
        return "playful"
    return "strict"


def _register_globals(app: Flask) -> None:
    @app.template_global()
    def endpoint_exists(name: str) -> bool:
        """Есть ли в приложении такой endpoint.

        Нужен, чтобы старый (не перезапущенный) процесс не ронял все страницы
        с BuildError на новом маршруте: ссылка просто не показывается.
        """
        from flask import current_app

        try:
            return any(rule.endpoint == name for rule in current_app.url_map.iter_rules())
        except Exception:  # pragma: no cover
            return False

    @app.template_global()
    def safe_url(endpoint: str, fallback: str = "/") -> str:
        """Ссылка на endpoint; если его нет — запасной адрес."""
        from flask import current_app, url_for

        try:
            if endpoint_exists(endpoint):
                return url_for(endpoint)
        except Exception:  # pragma: no cover
            pass
        return fallback


def _register_context(app: Flask) -> None:
    from services import learners as learners_service
    from services import progress as progress_service

    @app.context_processor
    def inject_globals():
        from content.curriculum import TOPICS
        from content.generators import REGISTRY
        from services import auth, learners as learners_service
        from services import progress as progress_service
        from services import topics as topics_service
        from services import google_auth as google_auth_service

        learner = None
        stats = None
        user = None
        try:
            user = auth.current_user()
            learner = learners_service.current_learner()
            if learner is not None:
                stats = progress_service.learner_stats(learner["id"])
        except Exception:  # pragma: no cover
            learner, stats = None, None
        try:
            titles = topics_service.topic_titles()
        except Exception:  # pragma: no cover - БД может быть ещё не готова
            titles = {}
        for topic in TOPICS:
            titles.setdefault(topic["slug"], topic["title"])
        theme = _theme_mode(user, learner)
        notifications_unread = 0
        try:
            from services import notifications as notifications_service

            if user is not None:
                notifications_unread = notifications_service.unread_count(int(user["id"]))
            elif learner is not None:
                notifications_unread = notifications_service.unread_count_for_learner(
                    int(learner["id"])
                )
        except Exception:  # pragma: no cover - уведомления не должны ломать страницы
            notifications_unread = 0
        ai_enabled, ai_available, ai_status = False, False, None
        try:
            from services import ai as ai_service

            ai_status = ai_service.status()
            ai_enabled = bool(ai_status["enabled"])
            ai_available = ai_enabled and bool(user or learner)
        except Exception:  # pragma: no cover - ИИ не должен ломать страницы
            ai_enabled, ai_available, ai_status = False, False, None
        decor = {"frame": "", "title": "", "theme": "", "pet": None}
        if learner is not None:
            try:
                from services import shop as shop_service

                decor = shop_service.decorations(int(learner["id"]))
            except Exception:  # pragma: no cover - магазин не должен ломать страницы
                decor = {"frame": "", "title": "", "theme": "", "pet": None}
        return {
            "current_learner": learner,
            "learner_stats": stats,
            "learner_decor": decor,
            "shop_theme": decor.get("theme") or "",
            "current_user": user,
            "user_role": user["role"] if user else None,
            "theme_mode": theme,
            "is_playful": theme == "playful",
            "is_strict": theme == "strict",
            "is_adult": theme == "adult",
            "user_grade": _user_grade_for_theme(user, learner),
            "csrf_token": _csrf_token,
            "ai_enabled": ai_enabled,
            "ai_available": ai_available,
            "ai_status": ai_status,
            "google_auth_enabled": google_auth_service.is_configured(),
            "app_name": "Школьник",
            "app_full_name": "Общеобразовательная платформа обучения",
            "notifications_unread": notifications_unread,
            "today": datetime.now().strftime("%d.%m.%Y"),
            "topic_titles": titles,
            "topics_count": len(TOPICS),
            "methods_count": sum(len(t["methods"]) for t in TOPICS),
            "generators_count": len(REGISTRY),
            "topic_colors": {
                "indigo": "#6366f1", "sky": "#0ea5e9", "violet": "#8b5cf6",
                "emerald": "#10b981", "amber": "#f59e0b", "rose": "#f43f5e",
                "cyan": "#06b6d4", "orange": "#f97316", "teal": "#14b8a6",
                "blue": "#3b82f6", "fuchsia": "#d946ef", "lime": "#84cc16",
            },
        }

    def _csrf_token() -> str:
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(24)
            session["_csrf_token"] = token
        return token


def _register_security(app: Flask) -> None:
    @app.before_request
    def _ensure_csrf_token():
        if not session.get("_csrf_token"):
            session["_csrf_token"] = secrets.token_urlsafe(24)

    @app.before_request
    def _sync_due_notifications():
        """Ленивая проверка сроков: уведомления и без планировщика.

        sync_due() сам ограничивает частоту (раз в 5 минут на процесс),
        поэтому на каждом запросе это только чтение из памяти.
        """
        if not session.get("user_id"):
            return None
        try:
            from services import notifications as notifications_service

            notifications_service.sync_due()
        except Exception:  # pragma: no cover - уведомления не должны ломать страницы
            pass
        return None

    @app.before_request
    def _csrf_protect():
        # Мобильный API аутентифицируется Bearer-токеном в заголовке, а не
        # cookie, поэтому CSRF ему не нужен и не должен блокировать запросы.
        if request.path.startswith("/api/v1/"):
            return None
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            token = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
            expected = session.get("_csrf_token")
            if not expected or token != expected:
                if request.path.startswith("/api/"):
                    return jsonify({"ok": False, "error": "csrf"}), 403
                from flask import abort

                abort(400)

    @app.after_request
    def _security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        try:
            from services import map_settings as map_settings_service

            tile_origins = " ".join(map_settings_service.csp_origins())
        except Exception:  # pragma: no cover - настройки карты не должны ломать ответ
            tile_origins = "https://tile.openstreetmap.org"
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: https://i.ytimg.com "
            + "https://img.youtube.com " + tile_origins + "; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; font-src 'self' data:; connect-src 'self'; "
            "frame-src 'self' https://www.youtube.com https://www.youtube-nocookie.com; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'self'",
        )
        return resp


def _register_errors(app: Flask) -> None:
    @app.errorhandler(403)
    def _forbidden(error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "forbidden"}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def _not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "not_found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(400)
    def _bad_request(error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "bad_request"}), 400
        return render_template("errors/400.html"), 400

    @app.errorhandler(405)
    def _method_not_allowed(error):
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "method_not_allowed"}), 405
        return render_template("errors/404.html"), 405

    @app.errorhandler(413)
    def _too_large(error):
        # Приходит из Flask/Werkzeug, когда тело запроса больше MAX_CONTENT_LENGTH.
        limit_mb = app.config.get("MAX_UPLOAD_MB", 60)
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "too_large", "limit_mb": limit_mb}), 413
        back_url = url_for("main.map_page")
        referrer = request.referrer or ""
        if referrer.startswith(request.host_url):
            back_url = referrer
        return render_template(
            "errors/413.html", limit_mb=limit_mb, back_url=back_url
        ), 413

    @app.errorhandler(500)
    def _server_error(error):  # pragma: no cover
        app.logger.exception("Внутренняя ошибка: %s", error)
        if request.path.startswith("/api/"):
            return jsonify({"ok": False, "error": "server_error"}), 500
        return render_template("errors/500.html"), 500


app = create_app()

if __name__ == "__main__":
    import socket
    import sys

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    development = os.environ.get("APP_ENV", "development") == "development"

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        busy = probe.connect_ex((host, port)) == 0
    # В дочернем процессе автоперезагрузки порт держит родитель.
    if busy and not os.environ.get("WERKZEUG_RUN_MAIN"):
        print(
            f"\n  ⚠ Порт {port} уже занят другим экземпляром приложения."
            "\n    Остановите его или задайте другой PORT — иначе запросы"
            "\n    будут попадать на устаревшую версию кода.\n"
        )
        sys.exit(1)

    app.run(host=host, port=port, debug=development, use_reloader=development)
