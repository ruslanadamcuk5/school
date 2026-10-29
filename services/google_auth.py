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

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from flask import current_app, redirect, url_for
from itsdangerous import BadData, URLSafeTimedSerializer

AUTHORIZE_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"
TOKENINFO_ENDPOINT = "https://oauth2.googleapis.com/tokeninfo"
SCOPE = "openid email profile"
# Сколько живёт подписанный токен регистрации из Android-приложения.
SIGNUP_MAX_AGE = 900
# Возврат в приложение после входа через браузер (Custom Tabs).
ANDROID_CALLBACK = "uchus://auth"
# Одноразовый код входа в приложении живёт пять минут.
LOGIN_CODE_MAX_AGE = 300


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


def verify_id_token(id_token: str, nonce: str | None = None) -> dict[str, Any]:
    """Проверить ID token из Android (Credential Manager).

    Google сам проверяет подпись в ``tokeninfo``, а мы — аудиторию, издателя,
    срок действия и ``nonce``. Так токен, выпущенный для другого приложения,
    не даст войти в наш аккаунт.
    """
    token = (id_token or "").strip()
    if not token or len(token) > 8000:
        raise GoogleAuthError("Пустой или слишком длинный ID-токен")
    client_id, _ = credentials()
    if not client_id:
        raise GoogleAuthError("Вход через Google не настроен")
    query = urllib.parse.urlencode({"id_token": token})
    request = urllib.request.Request(
        f"{TOKENINFO_ENDPOINT}?{query}", headers={"Accept": "application/json"}
    )
    info = _request_json(request)

    if str(info.get("aud") or "") != client_id:
        raise GoogleAuthError("ID-токен выдан другому приложению")
    issuer = str(info.get("iss") or "")
    if issuer not in ("accounts.google.com", "https://accounts.google.com"):
        raise GoogleAuthError("Неверный издатель ID-токена")
    try:
        expires = int(info.get("exp") or 0)
    except (TypeError, ValueError):
        expires = 0
    if expires <= int(time.time()) - 30:
        raise GoogleAuthError("ID-токен истёк")
    token_nonce = str(info.get("nonce") or "")
    if nonce:
        # Android присылает «сырой» nonce, а Google получает его SHA-256
        # (так делают Firebase и Supabase). Принимаем оба варианта, чтобы
        # вход не зависел от того, хеширует Google значение или нет.
        expected = {str(nonce)}
        if len(str(nonce)) <= 256:
            expected.add(hashlib.sha256(str(nonce).encode("utf-8")).hexdigest())
        if not any(hmac.compare_digest(token_nonce, value) for value in expected):
            raise GoogleAuthError("Неверный nonce")
    elif token_nonce:
        # Токен выпущен с nonce, а клиент его не прислал: возможно повторение.
        raise GoogleAuthError("Не передан nonce")
    return profile_from_userinfo(info)


def _signup_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="google-signup"
    )


def make_signup_token(profile: dict[str, Any]) -> str:
    """Короткоживущий подписанный токен для завершения регистрации в приложении."""
    return _signup_serializer().dumps(profile)


def read_signup_token(token: str) -> dict[str, Any]:
    try:
        data = _signup_serializer().loads(token or "", max_age=SIGNUP_MAX_AGE)
    except BadData as exc:
        raise GoogleAuthError("Регистрация истекла, войдите через Google ещё раз") from exc
    if not isinstance(data, dict) or not data.get("sub") or not data.get("email"):
        raise GoogleAuthError("Некорректный токен регистрации")
    return data


def challenge_for(verifier: str) -> str:
    """S256-challenge для PKCE: base64url(SHA-256(verifier)) без «=»."""
    digest = hashlib.sha256((verifier or "").encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _login_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="google-login-code"
    )


def make_login_code(user_id: int, challenge: str) -> str:
    """Короткоживущий код возврата в приложение после входа в браузере.

    Код бесполезен без ``verifier``: приложение присылает его на обмен,
    а сервер сверяет хеш с ``challenge`` из начала входа. Так перехват
    ссылки ``uchus://auth`` другим приложением не даёт войти.
    """
    return _login_serializer().dumps(
        {
            "user_id": int(user_id),
            "challenge": str(challenge),
            "nonce": secrets.token_urlsafe(8),
        }
    )


def read_login_code(token: str) -> dict[str, Any]:
    try:
        data = _login_serializer().loads(token or "", max_age=LOGIN_CODE_MAX_AGE)
    except BadData as exc:
        raise GoogleAuthError("Ссылка входа истекла, войдите через Google ещё раз") from exc
    if not isinstance(data, dict):
        raise GoogleAuthError("Некорректный код входа")
    try:
        user_id = int(data.get("user_id") or 0)
    except (TypeError, ValueError):
        user_id = 0
    challenge = str(data.get("challenge") or "")
    if user_id <= 0 or not challenge:
        raise GoogleAuthError("Некорректный код входа")
    return {"user_id": user_id, "challenge": challenge}


def android_redirect(code: str | None = None, error: str | None = None):
    """Вернуть браузер в приложение по схеме ``uchus://auth``."""
    params: dict[str, str] = {}
    if code:
        params["code"] = code
    if error:
        params["error"] = error
    query = urllib.parse.urlencode(params)
    return redirect(f"{ANDROID_CALLBACK}?{query}" if query else ANDROID_CALLBACK)



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
