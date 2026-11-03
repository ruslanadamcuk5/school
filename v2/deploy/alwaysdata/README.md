# Деплой v2 на AlwaysData

Сайт `virusadk.alwaysdata.net` сейчас работает на Flask через **uWSGI (WSGI)**.
FastAPI требует **ASGI**, поэтому v2 запускается отдельным процессом uvicorn,
а панель AlwaysData проксирует на него HTTP. Текущий сайт при этом не
останавливается: переключение делается после проверки.

Нужны права в панели AlwaysData (аккаунт `virusadk`). По SSH всё, кроме
создания базы и сайта, можно сделать скриптами ниже.

## Быстрый путь через API

Если в панели создан ключ (**Settings → API**), базу и сайт можно создать
одной командой:

```bash
export ALWAYSDATA_TOKEN='...'
export ALWAYSDATA_ACCOUNT='virusadk'
python3 v2/deploy/alwaysdata/provision.py           # только план
python3 v2/deploy/alwaysdata/provision.py --apply   # создать
```

Скрипт создаёт пользователя PostgreSQL, базу `virusadk_school` и сайт
`v2.virusadk.alwaysdata.net`, а строку подключения сохраняет в
`/tmp/opencode/alwaysdata_secrets.json` (права 600). Дальше — шаги 2–4.

---

## 1. PostgreSQL

1. Панель → **Databases** → **PostgreSQL** → **Add a database**.
2. Имя: например `virusadk_school`. Панель покажет хост, порт, имя базы,
   пользователя и пароль.
3. Проверка с сервера:

```bash
psql 'postgresql://virusadk_school:ПАРОЛЬ@postgresql-virusadk.alwaysdata.net:5432/virusadk_school' -c 'select version()'
```

## 2. Код и зависимости

v2 разворачивается в отдельный каталог `~/edu-math-v2`, чтобы не менять файлы
живого Flask-сайта. Данные (`data/`) подключаются симлинком:

```bash
cd ~/edu-math-v2
ln -sfn ~/edu-math/data data      # SQLite, uploads и всё остальное — общие
```

Зависимости — в отдельном окружении:

```bash
python3 -m venv ~/.virtualenvs/school-v2
~/.virtualenvs/school-v2/bin/pip install -r ~/edu-math-v2/v2/backend/requirements.txt
```

SPA собирается на сервере (node и npm на AlwaysData есть):

```bash
cd ~/edu-math-v2/v2/frontend
npm ci
npm run build
```

## 3. Переменные окружения

```bash
cd ~/edu-math-v2
cp v2/deploy/alwaysdata/env.example .env.v2
chmod 600 .env.v2
# отредактируйте DATABASE_URL, SECRET_KEY, ADMIN_PASSWORD
```

## 4. Схема и перенос данных

```bash
cd ~/edu-math-v2
source .env.v2

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f v2/backend/sql/pg_schema.sql

# резервная копия SQLite на момент переноса (файл может быть занят сайтом)
python3 - <<'PY'
import sqlite3
src = sqlite3.connect('data/math_tutor.db')
dst = sqlite3.connect('/tmp/school-migrate.db')
with dst:
    src.backup(dst)
PY

python v2/backend/sql/migrate_sqlite.py \
  --sqlite /tmp/school-migrate.db \
  --dry-run          # посмотреть план

python v2/backend/sql/migrate_sqlite.py --sqlite /tmp/school-migrate.db
```

Скрипт идемпотентен и в конце сверяет количество строк в SQLite и PostgreSQL.
Файлы из `data/uploads` остаются на месте — переносить их не нужно.

## 5. Сайт в панели

1. Панель → **Sites** → **Add a site**.
2. Тип: **User program** (в русской панели — «Пользовательская программа»).
3. Команда:

```
/home/virusadk/edu-math-v2/v2/deploy/alwaysdata/start.sh
```

4. Рабочий каталог: `edu-math-v2`.
5. Домен: сначала тестовый поддомен (например `v2.virusadk.alwaysdata.net`),
   чтобы проверить, не трогая основной сайт.

Скрипт сам читает `.env.v2`, поднимает uvicorn на IPv6-адресе из `$IP` и порту
из `$PORT` и отдаёт и `/api/v1` (Android), и `/api/v2`, и SPA.

## 6. Проверка перед переключением

```bash
curl -s https://v2.virusadk.alwaysdata.net/api/v2/health
curl -s https://v2.virusadk.alwaysdata.net/api/v1/app/version
curl -s -o /dev/null -w '%{http_code}\n' https://v2.virusadk.alwaysdata.net/
```

Проверить по ролям: ученик, родитель, учитель, админ. Отдельно — загрузку
PDF, видео YouTube, удалённую помощь и звуковой вызов из Android-приложения.

## 7. Переключение и откат

1. В панели у основного сайта сменить тип/команду на v2 **или** переключить
   домен на новый сайт.
2. Откат: вернуть прежний тип сайта (WSGI, `deploy/alwaysdata/wsgi.py`).
   SQLite-база и `data/uploads` не удаляются, поэтому откат мгновенный.

## Если «User program» недоступен

Тогда FastAPI размещается на отдельном ASGI-хосте (VPS/Render/Railway), а на
AlwaysData остаётся текущий Flask-сайт. SPA и Android обращаются к новому
хосту. Вариант с Docker — в `v2/README.md`.
