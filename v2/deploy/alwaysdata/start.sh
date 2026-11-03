#!/bin/bash
# Запуск v2 (FastAPI + SPA) как «User program» на AlwaysData.
# Панель передаёт порт в переменной PORT; локально по умолчанию 8000.
set -euo pipefail

cd "$HOME/edu-math"
# shellcheck disable=SC1091
source "$HOME/.virtualenvs/edu-math/bin/activate"

ENV_FILE="${SCHOOL_ENV_FILE:-$HOME/edu-math/.env.v2}"
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

export PYTHONPATH="$HOME/edu-math/v2/backend:$HOME/edu-math"
export PYTHONUNBUFFERED=1

exec uvicorn school_api.main:app \
  --host 127.0.0.1 \
  --port "${PORT:-8000}" \
  --proxy-headers \
  --forwarded-allow-ips='*' \
  --workers "${WEB_CONCURRENCY:-1}"
