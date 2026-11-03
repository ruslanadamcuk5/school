# Школьник 2.0 — FastAPI + React + PostgreSQL

Второе поколение платформы «Школьник»: тот же функционал, новая архитектура и
современный интерфейс. Android-приложение продолжает работать без обновления —
для него сохранён весь контракт `/api/v1`.

## Что внутри

| Слой | Технологии | Где лежит |
| --- | --- | --- |
| API-шлюз | FastAPI, Uvicorn, a2wsgi | `v2/backend/school_api` |
| Доменная логика | проверенные `services/*`, Flask-роуты `/api/v1` | корень проекта |
| База данных | PostgreSQL 14+ (адаптер `pg_database.py`) | `v2/backend/sql` |
| Сайт | React 19, Vite 6, Tailwind CSS 4, Lucide | `v2/frontend` |
| Android | без изменений, `/api/v1` | `android/` |

Ключевая идея: **не переписывать 13 000 строк рабочей логики**. FastAPI
становится ASGI-шлюзом, а проверенный слой `services/*` работает поверх
PostgreSQL через совместимый модуль `database`. Поэтому новая и старая части
видят одни и те же данные, а исправление в домене действует везде.

```
Android ─┐
         ├─► /api/v1  (legacy Flask через a2wsgi) ─┐
Сайт ────┼─► /api/v2  (нативные FastAPI роуты) ───┼─► services/* ─► PostgreSQL
         └─► /        (React SPA из dist)         ─┘
```

## Быстрый старт (локально)

Нужны Python 3.12+, Node.js 20+ и PostgreSQL 14+.

```bash
# 1. База данных
createdb school_v2

# 2. Backend
python3 -m venv .venv
.venv/bin/pip install -r v2/backend/requirements.txt
export DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/school_v2'
export SECRET_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
export ADMIN_PASSWORD='math2025'          # пароль первого администратора
.venv/bin/uvicorn school_api.main:app --host 127.0.0.1 --port 8000 --reload
# PYTHONPATH=v2/backend:. нужен, если пакет не установлен
```

При первом запуске backend сам создаёт схему PostgreSQL из
`v2/backend/sql/pg_schema.sql` и стартовые данные (город, школа, классы,
администратор). Если база уже наполнена — ничего не перезаписывается.

```bash
# 3. Frontend (разработка)
cd v2/frontend
npm install
npm run dev        # http://localhost:5173, проксирует /api на :8000
```

```bash
# 4. Production-сборка сайта
cd v2/frontend
npm ci
npm run build      # результат в v2/frontend/dist
```

После сборки FastAPI раздаёт SPA с `/`, включая клиентские маршруты
(`/app/admin/users` и т. п.). Перезапускать backend после сборки не нужно.

## Переменные окружения

| Переменная | Назначение |
| --- | --- |
| `DATABASE_URL` | строка подключения PostgreSQL, **обязательна** |
| `SECRET_KEY` | подпись cookie и токенов, задайте длинную случайную строку |
| `ADMIN_PASSWORD` | пароль администратора при первичном наполнении |
| `UPLOAD_DIR` | папка загруженных PDF и фотографий (по умолчанию `data/uploads`) |
| `HOST`, `PORT` | адрес Uvicorn (по умолчанию `0.0.0.0:8000`) |
| `RELOAD` | `1` включает autoreload в разработке |
| `APP_ENV` | `development` или `production` |
| `TRUST_PROXY` | `1`, если приложение стоит за nginx/Alwaysdata |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | вход через Google (необязательно) |
| `APP_VERSION` | версия в `/api/v2/health`, по умолчанию `2.0.0` |

## Перенос данных из SQLite

Скрипт копирует все таблицы, сохраняет `id` и выставляет последовательности.
Он идемпотентен: повторный запуск не создаёт дубликатов.

```bash
# 1. Сначала дайте backend один раз создать схему (или примените pg_schema.sql)
psql "$DATABASE_URL" -f v2/backend/sql/pg_schema.sql

# 2. Посмотрите план
DATABASE_URL="$DATABASE_URL" \
  python v2/backend/sql/migrate_sqlite.py --sqlite data/math_tutor.db --dry-run

# 3. Перенесите данные
DATABASE_URL="$DATABASE_URL" \
  python v2/backend/sql/migrate_sqlite.py --sqlite data/math_tutor.db

# 4. Проверьте количество строк и последовательности — скрипт сделает это сам
```

Полезные флаги:

* `--truncate --yes` — очистить таблицы перед копированием (для повторного
  переноса «с нуля»);
* `--only users,learners,topics` — скопировать только выбранные таблицы;
* `--batch 500` — размер пакета вставки.

Файлы (`data/uploads`, PDF учебников, обложки) переносятся отдельно:

```bash
rsync -av data/uploads/ user@server:/path/to/app/data/uploads/
```

## Проверка после запуска

```bash
curl -s http://127.0.0.1:8000/api/v2/health
curl -s http://127.0.0.1:8000/api/v1/health
curl -s http://127.0.0.1:8000/api/v2/public/landing | head -c 300

# вход и запрос от имени ученика
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v2/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"login":"masha","password":"math2025"}' | python3 -c 'import json,sys;print(json.load(sys.stdin)["token"])')
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/v1/topics | head -c 300
```

Документация API: `http://127.0.0.1:8000/api/v2/docs`.

## Развёртывание

### Вариант A. Свой сервер / VPS (рекомендуется)

```bash
git clone <repo> /srv/school && cd /srv/school
python3 -m venv .venv
.venv/bin/pip install -r v2/backend/requirements.txt
cd v2/frontend && npm ci && npm run build && cd ../..

export DATABASE_URL='postgresql://school:…@127.0.0.1:5432/school'
export SECRET_KEY='…'
export APP_ENV=production
export TRUST_PROXY=1
export PYTHONPATH=v2/backend:.

.venv/bin/uvicorn school_api.main:app \
  --host 127.0.0.1 --port 8000 --workers 2
```

Снаружи — nginx/Caddy с TLS:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    client_max_body_size 50m;   # загрузка PDF
}
```

### Вариант B. AlwaysData

У AlwaysData сайты на Python исторически запускаются через **uWSGI (WSGI)**,
а FastAPI требует **ASGI**. Проверьте в панели тип сайта: если доступен
«Python ASGI», укажите команду:

```
uvicorn school_api.main:app --host 127.0.0.1 --port $PORT
```

Если ASGI-типа нет, есть два безопасных пути:

1. **Отдельный ASGI-хост** (VPS, Render, Railway, Fly.io) для FastAPI, а на
   AlwaysData оставить статику/редирект. Сайт и Android ходят на новый хост.
2. **Сохранить текущий Flask-сайт** на AlwaysData без изменений, а v2
   разворачивать рядом и переключить домен после проверки. Так production не
   останавливается ни на минуту.

Перед переключением обязательно:

```bash
# на AlwaysData
pg_dump …                       # резервная копия текущей базы
tar czf uploads-backup.tgz data/uploads
```

и только затем переносите данные скриптом `migrate_sqlite.py`.

### Docker (альтернатива)

```bash
docker run -d --name school-pg \
  -e POSTGRES_PASSWORD=secret -e POSTGRES_DB=school \
  -v school_pg:/var/lib/postgresql/data postgres:16

docker build -f v2/Dockerfile -t school-v2 .
docker run -d --name school -p 8000:8000 \
  -e DATABASE_URL='postgresql://postgres:secret@school-pg:5432/school' \
  -e SECRET_KEY='…' -v school_uploads:/app/data/uploads school-v2
```

## Структура репозитория

```
v2/
  backend/
    school_api/
      main.py           # FastAPI + монтирование legacy и SPA
      api/v2.py         # нативные эндпоинты /api/v2
      legacy/           # bootstrap Flask и PostgreSQL-адаптер database
    sql/
      pg_schema.sql     # схема PostgreSQL
      convert_schema.py # schema.sql + миграции → pg_schema.sql
      migrate_sqlite.py # перенос данных SQLite → PostgreSQL
    requirements.txt
  frontend/
    src/
      pages/            # страницы по ролям и админка
      components/       # Shell, UI-примитивы
      lib/              # api-клиент, хуки, форматирование
    dist/               # production-сборка (после npm run build)
```

## Что важно помнить

* **Не меняйте `schema.sql` без пересборки** `pg_schema.sql`:
  `python v2/backend/sql/convert_schema.py`.
* **Android не трогаем.** Контракт `/api/v1` и версия APK остаются прежними.
* **Секреты не коммитим.** `SECRET_KEY`, ключи YouTube/ИИ и `DATABASE_URL`
  живут только в окружении.
* **Резервные копии.** `pg_dump` ежедневно + копия `data/uploads`.
* **Два процесса не нужны.** FastAPI сам отдаёт и API, и сайт; отдельный
  nginx — только для TLS и проксирования.
