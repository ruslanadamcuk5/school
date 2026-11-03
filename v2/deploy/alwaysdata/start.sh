#!/bin/bash
# Запуск v2 (FastAPI + SPA) как «User program» на AlwaysData.
# Программа обязана слушать IPv6-адрес из $IP (обычно ::) и порт из $PORT.
# Локально: HOST=127.0.0.1 PORT=8000 v2/deploy/alwaysdata/start.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="${SCHOOL_APP_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}"
cd "$APP_ROOT"

# Отдельное окружение, чтобы не менять зависимости живого Flask-сайта.
VENV="${SCHOOL_VENV:-$HOME/.virtualenvs/school-v2}"
[ -d "$VENV" ] || VENV="$HOME/.virtualenvs/edu-math"
# shellcheck disable=SC1091
source "$VENV/bin/activate"

ENV_FILE="${SCHOOL_ENV_FILE:-$APP_ROOT/.env.v2}"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

export PYTHONPATH="$APP_ROOT/v2/backend:$APP_ROOT"
export PYTHONUNBUFFERED=1

exec uvicorn school_api.main:app \
  --host "${HOST:-${IP:-::}}" \
  --port "${PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips='*' \
  --workers "${WEB_CONCURRENCY:-1}"
