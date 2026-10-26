# Деплой на Alwaysdata (бесплатный тариф)

В результате приложение будет доступно по адресу:

```
https://<ваш-логин>.alwaysdata.net
```

Бесплатный тариф Alwaysdata (2026): **1 ГБ SSD**, **256 МБ RAM**, сайт на
`*.alwaysdata.net`, Python WSGI, SQLite, веб-консоль. Постоянный диск — значит
база и загруженные PDF не пропадают при перезапуске.

> ИИ-функции на бесплатном тарифе работают: внешний интернет не ограничен
> белым списком (в отличие от PythonAnywhere Beginner). Но ИИ по умолчанию
> выключен — включается в `/admin/ai`.

---

## 0. Что подготовить

1. Аккаунт Alwaysdata (регистрация бесплатная):
   <https://www.alwaysdata.com/en/register/?p=2012>
   При регистрации выберите поддомен — он станет адресом приложения.
2. Архив с кодом. Соберите его на своём компьютере:

   ```powershell
   cd C:\Users\adamrv\Documents\edu-math
   python tools/make_deploy_zip.py
   # → dist\edu-math-deploy.zip
   ```

   Если нужно перенести уже существующую базу и загруженные книги:

   ```powershell
   python tools/make_deploy_zip.py --with-data
   ```

   > `--with-data` кладёт в архив `data/math_tutor.db` и `data/uploads/`.
   > Без флага на сервере будет чистая база: темы математики создадутся
   > автоматически из программы, а пособия вы загрузите заново.

---

## 1. Загрузить код

### Вариант A — файловый менеджер (проще)

1. Панель Alwaysdata → **Files** (или **Advanced → File manager**).
2. В домашнем каталоге создайте папку `edu-math`.
3. Загрузите `edu-math-deploy.zip` и распакуйте в `~/edu-math`
   (в файловом менеджере есть «Extract»).
   В итоге должен получиться путь `~/edu-math/app.py`.

### Вариант B — SFTP (удобно для архива с данными)

Если архив большой (`--with-data`, ~140 МБ), файловый менеджер может не подойти.
Подключитесь любым SFTP-клиентом (WinSCP, FileZilla) к
`<логин>@ssh-<логин>.alwaysdata.net` (порт 22, пароль — от панели) и загрузите
`edu-math-deploy.zip` в `/home/<логин>/`, затем распакуйте в консоли:

```bash
cd ~
unzip -o edu-math-deploy.zip -d edu-math
```

### Вариант C — консоль

Панель → **Advanced → Consoles** → новый **Bash**-консоль:

```bash
cd ~
# если код в git-репозитории:
git clone https://github.com/<вы>/<репозиторий>.git edu-math
# либо распакуйте загруженный архив:
unzip edu-math-deploy.zip -d edu-math
```

---

## 2. Виртуальное окружение и зависимости

В том же Bash-консоли:

```bash
cd ~/edu-math
python3.12 -m venv ~/.virtualenvs/edu-math
source ~/.virtualenvs/edu-math/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Проверка, что всё импортируется:

```bash
python -c "import flask, pypdf, fitz; print('ok')"
```

> Если `python3.12` не найден, посмотрите доступные версии: `ls /usr/bin/python3*`
> и используйте, например, `python3.13`. Нужен Python **3.10+**.

---

## 3. Настройки (`.env`)

Секреты не должны попадать в архив, поэтому создайте файл на сервере.

```bash
cd ~/edu-math
cp .env.example deploy/alwaysdata/.env
nano deploy/alwaysdata/.env
```

Минимум, что стоит заполнить:

```ini
APP_ENV=production
SECRET_KEY=<длинная случайная строка>
ADMIN_LOGIN=admin
ADMIN_PASSWORD=<пароль администратора>
TRUST_PROXY=1
COOKIE_SECURE=1
```

Сгенерировать `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

> Если `SECRET_KEY` оставить пустым, WSGI-файл сам создаст постоянный ключ
> в `data/.secret_key`. Но задать явно — надёжнее.
>
> `ADMIN_PASSWORD` действует только при **первом** создании администратора.
> Если база уже есть, пароль меняется в приложении: «Профиль».

---

## 4. Создать сайт в панели

Панель → **Web → Sites → Add a site**:

| Поле | Значение |
|---|---|
| Type | **Python WSGI** |
| Addresses | `<ваш-логин>.alwaysdata.net` (уже принадлежит вам) |
| Working directory | `/home/<логин>/edu-math` |
| Python version | `3.12` (или другая доступная ≥ 3.10) |
| Virtualenv | `/home/<логин>/.virtualenvs/edu-math` |
| WSGI file | `/home/<логин>/edu-math/deploy/alwaysdata/wsgi.py` |

Сохраните сайт. Панель сама перезапустит процесс.

> Если для сайта есть раздел **Environment**, ничего добавлять не нужно:
> `deploy/alwaysdata/wsgi.py` читает `.env` и выставляет переменные сам.

### Статика (необязательно, но быстрее)

В настройках сайта → **Static files** добавьте:

| URL | Каталог |
|---|---|
| `/static/` | `/home/<логин>/edu-math/static` |

Flask и сам отдаёт статику, поэтому без этого всё тоже работает.

---

## 5. Первый запуск и проверка

1. Откройте `https://<логин>.alwaysdata.net/healthz` — должно вернуться:

   ```json
   {"db": true, "status": "ok", "time": "..."}
   ```

2. Откройте главную: `https://<логин>.alwaysdata.net/`
3. Войдите как `admin` с паролем из `ADMIN_PASSWORD`
   (или посмотрите случайный пароль в **Web → Sites → Logs**).
4. Сразу смените пароль: **Профиль**.
5. Загрузите учебные пособия: **Админ → Пособия (PDF)**.

### Если 502 / 500

Смотрите лог сайта: **Web → Sites → <сайт> → Logs** (или
`~/admin.log` / `~/.logs/`). Типичные причины:

| Симптом | Причина | Решение |
|---|---|---|
| `ModuleNotFoundError: flask` | зависимости не в том virtualenv | активируйте venv и `pip install -r requirements.txt` |
| `SECRET_KEY ...` / сессии слетают | ключ не задан | задайте `SECRET_KEY` или дайте WSGI создать `data/.secret_key` |
| 502 сразу после создания сайта | неверный путь WSGI-файла | проверьте `/home/<логин>/edu-math/deploy/alwaysdata/wsgi.py` |
| `Permission denied` на `data/` | нет прав | `chmod -R u+rwX ~/edu-math/data` |
| Ошибка импорта `fitz` | не установился PyMuPDF | `pip install PyMuPDF` |

Проверка прямо на сервере:

```bash
cd ~/edu-math
source ~/.virtualenvs/edu-math/bin/activate
python tools/prod_check.py
```

---

## 6. Обновление приложения

```bash
cd ~/edu-math
git pull            # или загрузите новый архив и распакуйте поверх
source ~/.virtualenvs/edu-math/bin/activate
pip install -r requirements.txt
```

Затем в панели: **Web → Sites → <сайт> → Restart**.
Миграции базы применяются автоматически при старте.

### Обновление Android APK

APK и метаданные лежат в `~/edu-math/data/releases/`:

```text
uchus-debug.apk
version.json
```

После сборки новой версии скопируйте оба файла на сервер (SFTP или `scp`),
увеличьте `version_code` в `version.json` и перезапустите сайт. Главная страница
сразу покажет новую версию, а установленные приложения при запуске предложат
обновление. Сам код Flask перезапускается кнопкой **Restart** в панели.

---

## 7. Резервная копия

База и файлы лежат на постоянном диске:

```
~/edu-math/data/math_tutor.db
~/edu-math/data/uploads/
~/edu-math/data/.secret_key
```

Скачайте их через файловый менеджер. Для SQLite полезно сначала сделать
согласованную копию:

```bash
cd ~/edu-math
sqlite3 data/math_tutor.db ".backup data/backup_$(date +%F).db"
```

---

## 8. Ограничения бесплатного тарифа

| Ресурс | Лимит | Что это значит |
|---|---|---|
| Диск | 1 ГБ | хватит на БД и несколько десятков PDF (лимит одного файла — 60 МБ) |
| RAM | 256 МБ | приложение небольшое, но PyMuPDF при разборе PDF требует памяти: загружайте книги по одной |
| Сайтов | 1 | хватает |
| SSH | нет | используйте веб-консоль Bash |
| Резервные копии | 3 дня | делайте свои копии перед обновлениями |

Если приложение начнёт не влезать в 256 МБ — переходите на тариф Plus
(1 ГБ RAM), код менять не нужно.

---

## 9. Что дальше

После деплоя адрес `https://<логин>.alwaysdata.net` — это **базовый URL**
для Android-приложения. Он вводится один раз на экране входа (или
собирается в приложение как значение по умолчанию).
