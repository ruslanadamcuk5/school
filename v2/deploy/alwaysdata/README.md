# Деплой v2 на AlwaysData

Сайт `virusadk.alwaysdata.net` сейчас работает на Flask через **uWSGI (WSGI)**.
FastAPI требует **ASGI**, поэтому v2 запускается отдельным процессом uvicorn,
а панель AlwaysData проксирует на него HTTP. Текущий сайт при этом не
останавливается: переключение делается после проверки.

Нужны права в панели AlwaysData (аккаунт `virusadk`). По SSH всё, кроме
создания базы и сайта, можно сделать скриптами ниже.

---

## 1. PostgreSQL

1. Панель → **Databases** → **PostgreSQL** → **Add a database**.
2. Имя: например `virusadk_school`. Панель покажет хост, порт, имя базы,
   пользователя и пароль.
3. Проверка с сервера:

```bash
psql 'postgresql://virusadk:ПАРОЛЬ@postgresql-virusadk.alwaysdata.net:5432/virusadk_school' -c 'select version()'
```

## 2. Код и зависимости

Код уже в репозитории (`main`, каталог `v2/`). На сервере:

```bash
cd ~/edu-math
# код v2 копируется тем же способом, что и текущий сайт (zip/scp/rsync)

source ~/.virtualenvs/edu-math/bin/activate
pip install -r v2/backend/requirements.txt

# SPA собирается на сервере (node и npm на AlwaysData есть)
cd v2/frontend
npm ci
npm run build
cd ~/edu-math
```

## 3. Переменные окружения

```bash
cp v2/deploy/alwaysdata/env.example .env.v2
chmod 600 .env.v2
# отредактируйте DATABASE_URL, SECRET_KEY, ADMIN_PASSWORD
```

## 4. Схема и перенос данных

```bash
cd ~/edu-math
source .env.v2

psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f v2/backend/sql/pg_schema.sql

# резервные копии перед переносом
tar czf ~/uploads-backup-$(date +%F-%H%M).tgz data/uploads

python v2/backend/sql/migrate_sqlite.py \
  --sqlite data/math_tutor.db \
  --dry-run          # посмотреть план

python v2/backend/sql/migrate_sqlite.py --sqlite data/math_tutor.db
```

Скрипт идемпотентен и в конце сверяет количество строк в SQLite и PostgreSQL.
Файлы из `data/uploads` остаются на месте — переносить их не нужно.

## 5. Сайт в панели

1. Панель → **Sites** → **Add a site**.
2. Тип: **User program** (в русской панели — «Пользовательская программа»).
3. Команда:

```
/home/virusadk/edu-math/v2/deploy/alwaysdata/start.sh
```

4. Домен: сначала тестовый поддомен (например `v2.virusadk.alwaysdata.net`),
   чтобы проверить, не трогая основной сайт.

Скрипт сам читает `.env.v2`, поднимает uvicorn на порту из `PORT` и отдаёт
и `/api/v1` (Android), и `/api/v2`, и SPA.

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
