#!/usr/bin/env python3
"""Подготовка v2 на AlwaysData через API.

Создаёт пользователя PostgreSQL, базу и сайт типа «User program».
По умолчанию только показывает план (dry-run), ничего не меняя.

    export ALWAYSDATA_TOKEN='...'      # Settings → API в панели
    export ALWAYSDATA_ACCOUNT='virusadk'
    python3 v2/deploy/alwaysdata/provision.py            # план
    python3 v2/deploy/alwaysdata/provision.py --apply    # создать

Секреты (пароль базы) сохраняются в /tmp/opencode/alwaysdata_secrets.json
с правами 600 и в git не попадают.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.alwaysdata.com/v1"
SECRETS = Path("/tmp/opencode/alwaysdata_secrets.json")


def request(method: str, path: str, payload: dict | None = None) -> dict | list:
    token = os.environ.get("ALWAYSDATA_TOKEN", "").strip()
    account = os.environ.get("ALWAYSDATA_ACCOUNT", "").strip()
    if not token or not account:
        sys.exit("Нужны ALWAYSDATA_TOKEN и ALWAYSDATA_ACCOUNT")
    auth = base64.b64encode(f"{token} account={account}:".encode()).decode()
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode() or "{}"
            return json.loads(body)
    except urllib.error.HTTPError as error:
        body = error.read().decode()
        sys.exit(f"{method} {path} → HTTP {error.code}: {body[:600]}")


def find(items: list[dict], **fields) -> dict | None:
    for item in items:
        if all(item.get(key) == value for key, value in fields.items()):
            return item
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="выполнить изменения")
    parser.add_argument("--database", default="virusadk_school")
    parser.add_argument("--site-name", default="v2")
    parser.add_argument("--address", default="v2.virusadk.alwaysdata.net")
    parser.add_argument(
        "--command",
        default="/home/virusadk/edu-math-v2/v2/deploy/alwaysdata/start.sh",
    )
    parser.add_argument("--working-directory", default="edu-math-v2")
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="сменить пароль существующего пользователя PostgreSQL",
    )
    args = parser.parse_args()

    account = request("GET", "/account/")
    account_name = account.get("name") or os.environ["ALWAYSDATA_ACCOUNT"]
    print(f"аккаунт: {account_name} (id={account.get('id')})")

    users = request("GET", "/database/user/") or []
    databases = request("GET", "/database/") or []
    sites = request("GET", "/site/") or []

    pg_user = find(users, type="POSTGRESQL", name=args.database)
    pg_db = find(databases, name=args.database)
    site = find(sites, name=args.site_name) or next(
        (s for s in sites if args.address in (s.get("addresses") or [])), None
    )

    print(f"пользователь PostgreSQL: {'есть' if pg_user else 'нет'}")
    print(f"база {args.database}: {'есть' if pg_db else 'нет'}")
    print(f"сайт {args.site_name}: {'есть' if site else 'нет'}")

    if not args.apply:
        print("\nЭто план. Запустите с --apply, чтобы создать недостающее.")
        return

    password = None
    if pg_user is None:
        password = secrets.token_urlsafe(24)
        pg_user = request(
            "POST",
            "/database/user/",
            {
                "name": args.database,
                "password": password,
                "type": "POSTGRESQL",
            },
        )
        print(f"+ пользователь PostgreSQL создан: {pg_user.get('name')}")
    elif args.reset_password or not pg_user.get("password"):
        password = secrets.token_urlsafe(24)
        pg_user = request(
            "PATCH",
            f"/database/user/{pg_user['id']}/",
            {"password": password},
        )
        print("~ пароль пользователя PostgreSQL обновлён")
    else:
        password = pg_user.get("password")

    if pg_db is None:
        pg_db = request(
            "POST",
            "/database/",
            {"name": args.database, "type": "POSTGRESQL"},
        )
        print(f"+ база создана: {pg_db.get('name')}")

    # Пользователю нужно право FULL на базу.
    permissions = dict(pg_user.get("permissions") or {})
    if permissions.get(args.database) != "FULL":
        pg_user = request(
            "PATCH",
            f"/database/user/{pg_user['id']}/",
            {"permissions": {**permissions, args.database: "FULL"}},
        )
        print(f"~ право FULL на {args.database} выдано")

    if site is None:
        site = request(
            "POST",
            "/site/",
            {
                "name": args.site_name,
                "type": "user_program",
                "command": args.command,
                "working_directory": args.working_directory,
                "addresses": [args.address],
                "ssl_force": True,
                "max_idle_time": 1800,
            },
        )
        print(f"+ сайт создан: {site.get('name')} → {args.address}")
    else:
        print(f"= сайт уже существует: id={site.get('id')}")

    host = f"postgresql-{account_name}.alwaysdata.net"
    url = f"postgresql://{args.database}:{password}@{host}:5432/{args.database}"
    SECRETS.write_text(
        json.dumps(
            {
                "account": account_name,
                "database": args.database,
                "user": args.database,
                "password": password,
                "host": host,
                "url": url,
                "site": site.get("id"),
                "address": args.address,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    SECRETS.chmod(0o600)
    print(f"\nDATABASE_URL сохранён в {SECRETS}")
    print(f"https://{args.address}/api/v2/health")


if __name__ == "__main__":
    main()
