"""Вход и регистрация через Google (OAuth 2.0 / OpenID Connect).

Схема простая и не требует сторонних библиотек:

1. Пользователь нажимает «Войти через Google».
2. ``authorize_url()`` уводит его на accounts.google.com с одноразовым ``state``.
3. Google возвращает код на ``/auth/google/callback``.
4. ``exchange_code()`` меняет код на access token, ``fetch_userinfo()`` читает
   профиль с openidconnect.googleapis.com.

Подпись id_token не проверяем: профиль запрашивается у Google напрямую по
access token, полученному по HTTPS, поэтому подделка ответа невозможна.
"""
from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from flask import current_app, url_for

AUTHORIZE_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPE = "openid email profile"


class GoogleAuthError(RuntimeError):
    """Google не подтвердил вход: сеть, отозванный код или неверный ответ."""


# Кэш файла с секретами: читаем заново только при изменении mtime.
_file_cache: dict[str, Any] = {"path": "", "mtime": -1.0, "value": ("", "")}


def _file_credentials() -> tuple[str, str]:
    """Client ID/secret из data/google_oauth.json (если нет в окружении)."""
    path = os.environ.get("GOOGLE_CREDENTIALS_FILE") or str(
        Path(current_app.root_path) / "data" / "google_oauth.json"
    )
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        _file_cache.update({"path": path, "mtime": -1.0, "value": ("", "")})
        return "", ""
    if _file_cache["path"] == path and _file_cache["mtime"] == mtime:
        return _file_cache["value"]
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        value = ("", "")
    else:
        value = (
            str(data.get("client_id") or "").strip(),
            str(data.get("client_secret") or "").strip(),
        )
    _file_cache.update({"path": path, "mtime": mtime, "value": value})
    return value


def credentials() -> tuple[str, str]:
    """Пара client_id/client_secret: сначала окружение, затем файл."""
    cfg = current_app.config
    client_id = (cfg.get("GOOGLE_CLIENT_ID") or "").strip()
    secret = (cfg.get("GOOGLE_CLIENT_SECRET") or "").strip()
    if client_id and secret:
        return client_id, secret
    return _file_credentials()


def is_configured() -> bool:
    client_id, secret = credentials()
    return bool(client_id and secret)


def redirect_uri() -> str:
    configured = (current_app.config.get("GOOGLE_REDIRECT_URI") or "").strip()
    if configured:
        return configured
    return url_for("auth.google_callback", _external=True)


def new_state() -> str:
    return secrets.token_urlsafe(32)


def authorize_url(state: str, redirect: str | None = None) -> str:
    client_id, _ = credentials()
    params = {
        "client_id": client_id,
        "redirect_uri": redirect or redirect_uri(),
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
        "access_type": "online",
        # Пользователь может выбрать другой аккаунт, а не входить молча.
        "prompt": "select_account",
    }
    return f"{AUTHORIZE_ENDPOINT}?{urllib.parse.urlencode(params)}"


def _request_json(request: urllib.request.Request) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(
            request, timeout=int(current_app.config.get("GOOGLE_TIMEOUT", 15))
        ) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:  # pragma: no cover - сеть
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        raise GoogleAuthError(f"Google ответил {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise GoogleAuthError(f"Нет связи с Google: {exc}") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise GoogleAuthError("Google вернул не JSON") from exc
    if not isinstance(data, dict):
        raise GoogleAuthError("Неожиданный ответ Google")
    return data


def exchange_code(code: str, redirect: str | None = None) -> dict[str, Any]:
    """Обменять код авторизации на токены."""
    client_id, client_secret = credentials()
    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect or redirect_uri(),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    data = _request_json(request)
    if not data.get("access_token"):
        raise GoogleAuthError("В ответе Google нет access_token")
    return data


def fetch_userinfo(access_token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        USERINFO_ENDPOINT,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )
    return _request_json(request)


def profile_from_userinfo(info: dict[str, Any]) -> dict[str, Any]:
    """Проверить и нормализовать профиль Google."""
    sub = str(info.get("sub") or "").strip()
    if not sub:
        raise GoogleAuthError("Google не вернул идентификатор аккаунта")
    email = str(info.get("email") or "").strip().lower()
    verified = info.get("email_verified")
    if isinstance(verified, str):
        verified = verified.strip().lower() == "true"
    if email and not verified:
        # Неподтверждённую почту нельзя использовать для входа.
        email = ""
    if not email:
        raise GoogleAuthError("Google не подтвердил адрес почты")
    return {
        "sub": sub,
        "email": email,
        "first_name": str(info.get("given_name") or "").strip()[:40],
        "last_name": str(info.get("family_name") or "").strip()[:40],
        "picture": str(info.get("picture") or "").strip(),
    }
