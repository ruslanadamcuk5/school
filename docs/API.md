# JSON API v1

REST-интерфейс для Android-приложения и внешних клиентов. Тот же код и та же база
данных, что и у веб-версии: изменения сразу видны на сайте и в приложении.

* Базовый адрес: `https://<логин>.alwaysdata.net/api/v1`
* Формат: JSON (`Content-Type: application/json`)
* Кодировка: UTF-8
* Все ответы содержат `ok: true` или `ok: false`.

Код находится в `routes/api_v1/` (Flask Blueprint с `url_prefix="/api/v1"`).

---

## Аутентификация

Три способа входа, все возвращают **непрозрачный Bearer-токен** (не JWT). Токен
хранится в БД в виде SHA-256-хэша, его можно отозвать, срок жизни — 180 дней.

### Аккаунт (учитель, ученик, родитель, администратор)

```http
POST /api/v1/auth/login
{"login": "petrova", "password": "math2025"}
```

Ответ:

```json
{
  "ok": true,
  "token": "…",
  "user": {"id": 2, "login": "petrova", "role": "teacher", "first_name": "…", "…": "…"},
  "learner": null,
  "theme": "adult"
}
```

У ученика дополнительно приходит `learner` — профиль прогресса (`id`, `name`, `grade`,
`xp`, `coins`, `streak_days`, `has_pin`).

### Вход через Google (Android)

Приложение получает Google ID token через Credential Manager и отправляет его
на сервер вместе с nonce:

```http
POST /api/v1/auth/google
{"id_token": "eyJhbGciOi…", "nonce": "случайная-строка-не-короче-16-символов"}
```

Сервер проверяет токен через `oauth2.googleapis.com/tokeninfo`: подпись, `aud`
(должен совпадать с Web Client ID), `iss`, `exp`, `email_verified` и `nonce`.
Для существующего аккаунта ответ такой же, как у `/auth/login`: `token`,
`user`, `learner`, `theme`. Если почта однозначно совпадает с существующим
аккаунтом без привязанного Google, он привязывается автоматически.

Новому пользователю аккаунт сразу не создаётся — сервер возвращает выбор роли:

```json
{
  "ok": true,
  "needs_signup": true,
  "signup_token": "…",
  "email": "ivan@example.com",
  "first_name": "Иван",
  "last_name": "Петров",
  "picture": "https://…",
  "suggested_login": "ivan"
}
```

`signup_token` подписан секретным ключом сервера и действует 15 минут.
Регистрация завершается запросом:

```http
POST /api/v1/auth/google/finish
{"signup_token": "…", "role": "student", "login": "ivan",
 "first_name": "Иван", "last_name": "Петров"}
```

* `role` — `student`, `teacher` или `parent`; администратором через Google стать нельзя;
* `first_name` и `last_name` необязательны — берутся из Google, если не переданы;
* `child_code` — только для родителя, необязателен; при совпадении ребёнок
  сразу привязывается;
* `avatar` — эмодзи, по умолчанию `🦊`.

Ответ — обычная сессия с `token`, как после `/auth/login`.

Ошибки: `google_disabled` (503 — ключи Google не настроены на сервере),
`bad_request` / `bad_nonce` / `bad_role` / `bad_name` / `bad_login` /
`signup_expired` (400), `google_token_invalid` (401), `inactive` (403),
`login_taken` (409), `too_many_attempts` (429).

### Семейный профиль без аккаунта

Семейные профили привязаны к устройству. Клиент генерирует UUID и передаёт его в
заголовке `X-Device-Id` при **каждом** запросе. Список профилей устройства:

```http
GET /api/v1/learners
X-Device-Id: 3f2c…
```

```json
{"ok": true, "learners": [{"id": 5, "name": "Миша", "avatar": "🦊", "grade": 3, "has_pin": true}]}
```

Вход в профиль:

```http
POST /api/v1/learners/5/login
X-Device-Id: 3f2c…
{"pin": "1234"}
```

Если у профиля задан PIN, поле `pin` обязательно (иначе `401 pin_required`,
при неверном PIN — `403 bad_pin`). Возвращается `token` и `learner`.

Создание профиля (не более 8 на устройство):

```http
POST /api/v1/learners
X-Device-Id: 3f2c…
{"name": "Миша", "avatar": "🦊", "grade": 3, "pin": "1234"}
```

Смена профиля в рамках того же семейного токена:

```http
POST /api/v1/learners/switch
{"learner_id": 6}
```

### Заголовки

```http
Authorization: Bearer <token>
X-Device-Id: <uuid>          # только для семейных профилей
```

`GET /auth/me` возвращает текущую сессию, `POST /auth/logout` отзывает токен.

### Ошибки

```json
{"ok": false, "error": "forbidden", "message": "Нет доступа"}
```

| HTTP | `error` | Когда |
|---|---|---|
| 400 | `bad_parameter`, `bad_grade`, … | неверные данные |
| 401 | `unauthorized`, `bad_credentials`, `pin_required` | нет/просрочен токен, неверный пароль |
| 403 | `forbidden`, `bad_pin`, `inactive` | нет прав, неверный PIN, аккаунт выключен |
| 404 | `not_found` | объект не найден или чужой |
| 409 | `conflict`, `delete_failed` | дубликат, нельзя удалить |
| 429 | `rate_limited` | слишком много запросов к ИИ |

CSRF для `/api/v1/*` не применяется: токен передаётся заголовком, а не cookie.
Ответы API отдаются с `Cache-Control: no-store`.

---

## Роли

| Роль | Что доступно |
|---|---|
| `admin` | всё: пользователи, организации, темы, пособия, ИИ, журнал |
| `teacher` | свои классы (`school_classes.teacher_id`), ученики, работы, библиотека, расписание |
| `student` | карта тем, тренировки, тесты, работы, библиотека, расписание |
| `parent` | привязанные дети, их прогресс, задания, библиотека ребёнка |
| семейный профиль | карта тем, тренировки, тесты, чтение пособий своего класса |

Администратор всегда имеет доступ к чтению пособий. Учитель открывает пособия своих
классов. Ученик с аккаунтом — пособия класса, в котором состоит.

---

## Метаданные и каталог

| Метод | Путь | Описание |
|---|---|---|
| GET | `/health` | проверка БД, версия API |
| GET | `/app/version` | публичные метаданные APK и ссылка на скачивание |
| GET | `/meta` | приложение, классы 1–11, предметы, статус ИИ |
| GET | `/topics?grade=&subject_id=&search=` | каталог тем (метаданные, без прогресса) |

`/app/version` не требует токена. Если релиз не опубликован — `404` с
`{"ok": false, "error": "app_not_published"}`. Ответ для опубликованного APK:

```json
{
  "ok": true,
  "version_code": 4,
  "version_name": "1.3",
  "download_url": "https://<логин>.alwaysdata.net/download/android",
  "size": 19648212,
  "sha256": "8cb34aa230832dacaa2c20f635ff59b888ad37506a72573f525e414b13298297",
  "notes": "Что нового",
  "published_at": "2026-10-26T12:00:00+00:00"
}
```

Android-приложение сравнивает `version_code` со своим `BuildConfig.VERSION_CODE`
и предлагает обновление, если серверная версия больше.

`/meta`:

```json
{
  "ok": true,
  "app": {"name": "Учусь", "version": "1.0"},
  "grades": [1, 2, 3, …],
  "subjects": [{"id": 1, "slug": "math", "name": "Математика", "icon": "🔢"}],
  "ai": {"enabled": false, "provider": null, "provider_name": null, "model": null}
}
```

`/topics` — единственный способ выбрать тему для учителя/родителя/администратора,
у которых нет собственного прогресса ученика. Возвращает `topics` и `subjects`.

---

## Ученик: карта, темы, чтение

| Метод | Путь | Описание |
|---|---|---|
| GET | `/map?grade=&subject=` | карта тем, ежедневные задания, статистика |
| GET | `/topics/{slug}` | тема, способы решения, пособия, соседние темы |
| GET | `/topics/{slug}/text` | текст страниц пособия для чтения |
| GET | `/topics/{slug}/quiz` | тест по теме (вопросы без ответов) |
| POST | `/topics/{slug}/quiz` | `{"quiz_id": 1, "answers": ["…"]}` |
| POST | `/topics/{slug}/read` | отметить тему прочитанной |

Тест по теме-чтению (например, «Человек и мир») составляет ИИ: 8 вопросов с
вариантами ответов и пояснениями. Готовая подборка кэшируется в `ai_quizzes`,
поэтому повторный тест открывается мгновенно. Если ИИ выключен, вопросы
строятся по описанию темы офлайн. Вопросы «на какой странице» и «к какому
предмету» не задаются. Ответы проверяются по выбранному варианту
(регистр и лишние пробелы не важны).

`/topics/{slug}/text` возвращает `topic.books` — список
`{"id": <textbook_id>, "title": "…", "page": 12, "page_end": 15}`. По `id` и
`page` клиент открывает `GET /books/{id}/page/{page}.png` — так работает кнопка
«Открыть страницы учебника» в Android-приложении. Текст страниц кэшируется
клиентом для чтения без сети.

`/map` для ученика берёт класс из его профиля. Ответ:

```json
{
  "ok": true,
  "grade": 3,
  "subject": {"id": 1, "slug": "math", "name": "Математика", "icon": "🔢"},
  "subjects": [ … ],
  "topics": [{"slug": "add.within20", "title": "…", "icon": "➕", "stars": 2, "accuracy": 84, "…": "…"}],
  "daily": [{"generator": "add.within20", "topic": "…", "label": "…", "done": false}],
  "daily_done": false,
  "stats": {"level": 4, "xp": 320, "coins": 40, "stars": 12, "accuracy": 81, "streak_days": 3}
}
```

Темы бывают двух видов: `kind = "practice"` (генераторы и 63 способа решения) и
`kind = "reading"` (текст пособия, тест по тексту). Для тем-чтения вопросы теста
хранятся **на сервере**; правильные ответы никогда не уходят клиенту.

---

## Тренировка и игра

| Метод | Путь | Описание |
|---|---|---|
| POST | `/play/start` | `{"topic_slug": "…", "mode": "practice|boss", "method": "…"}` |
| GET | `/play/{round_id}` | текущее задание раунда |
| POST | `/play/{round_id}/answer` | `{"answer": "42"}` |
| POST | `/play/{round_id}/hint` | подсказка (ограниченное число) |
| POST | `/play/{round_id}/switch-method` | объяснить другим способом |
| GET | `/play/{round_id}/result` | итог раунда, звёзды, значки, разбор |

Состояние раунда (`round_state`) хранится в БД: счёт, комбо, номер задания,
использованные подсказки. Повторный `GET /result` идемпотентен — прогресс не
начисляется дважды.

### Ежедневное задание

```http
GET  /api/v1/daily
POST /api/v1/daily/start   {"generator": "add.within20"}
```

`/daily` возвращает список генераторов на сегодня и признак выполнения.
`/daily/start` возвращает тот же контракт, что `/play/start`.

---

## Работы (задания)

### Ученик

| Метод | Путь | Описание |
|---|---|---|
| GET | `/assignments` | опубликованные работы ученика |
| GET | `/assignments/{id}` | вопросы без ответов, результат, если сдано |
| POST | `/assignments/{id}/submit` | `{"answers": ["…"], "duration_sec": 420}` |
| POST | `/assignments/{id}/retry` | разрешить повторную попытку |
| GET | `/assignments/{id}/result` | результат и разбор |

Ответ на сдачу:

```json
{
  "ok": true,
  "score": 8,
  "max_score": 10,
  "result": {"score": 8, "max_score": 10, "percent": 80, "grade": 4, "completed_at": "…"},
  "details": [{"question": "…", "given": "5", "expected": "6", "correct": false, "solution": "…"}]
}
```

### Учитель

| Метод | Путь | Описание |
|---|---|---|
| GET | `/teacher/assignments` | работы, созданные учителем |
| POST | `/teacher/assignments` | создать и опубликовать |
| PATCH | `/teacher/assignments/{id}` | изменить |
| POST | `/teacher/assignments/{id}/publish` | опубликовать черновик |
| POST | `/teacher/assignments/{id}/close` | закрыть |
| DELETE | `/teacher/assignments/{id}` | удалить |
| GET | `/teacher/assignments/{id}/results` | результаты класса |

Создание:

```json
{
  "title": "Проверочная по сложению",
  "kind": "проверочная",
  "class_id": 3,
  "topic_slugs": ["add.within20", "add.within100"],
  "questions_count": 10,
  "time_limit": 0,
  "due_date": "2026-11-01",
  "status": "опубликована"
}
```

Статусы: `черновик`, `опубликована`, `закрыта`. `results` содержит строки
`{student, result, percent, grade}`; у ученика без попытки `result = null`.

### Родитель

| Метод | Путь | Описание |
|---|---|---|
| GET | `/parent/assignments` | задания, созданные родителем |
| POST | `/parent/assignments` | то же тело, но `child_ids: [user_id]` |

Темы проверяются по классу ребёнка; создавать работы можно только для привязанных
детей.

---

## Библиотека и пособия

| Метод | Путь | Кто | Описание |
|---|---|---|---|
| GET | `/library` | ученик; семейный профиль | книги классов, рекомендации, статистика. Семейному профилю возвращаются пособия своего класса (только чтение) |
| GET | `/library/books/{id}` | ученик | книга, темы, рекомендации |
| POST | `/library/recommendations/{id}/done` | ученик | отметить рекомендацию прочитанной |
| GET | `/parent/library?child_id=` | родитель | библиотека ребёнка (`child_id` — **id пользователя**) |
| GET | `/teacher/library?search=&grade=&subject_id=` | учитель, админ | книги учителя, классы, ученики, предметы |
| POST | `/teacher/library` | учитель, админ | добавить книгу (`textbook_id`, `class_ids`, …) |
| PATCH | `/teacher/library/{id}` | учитель | изменить доступ (`class_ids`) |
| DELETE | `/teacher/library/{id}` | учитель | убрать книгу |
| POST | `/teacher/library/{id}/recommend` | учитель | рекомендация классам/ученикам |
| GET | `/teacher/library/recommendations` | учитель | выданные рекомендации |
| DELETE | `/teacher/library/recommendations/{id}` | учитель | отозвать |
| GET | `/teacher/textbooks?subject_id=&grade=&search=` | учитель | доступные PDF-пособия |
| POST | `/teacher/textbooks` | учитель | загрузка PDF (`multipart/form-data`) |
| GET | `/books/{id}` | все роли | пособие + привязка тем к страницам |
| GET | `/books/{id}/page/{n}.png` | все роли | страница PDF как PNG (кэшируется) |

Рекомендация:

```json
{"topic_slug": "add.within20", "class_ids": [3], "student_ids": [], "note": "Повторить перед тестом"}
```

Загрузка пособия (`multipart/form-data`): `file` (PDF), `subject_id`, `grade`,
`title`, `author`, `description`. Ответ:

```json
{"ok": true, "textbook_id": 12, "book_id": 30, "pages": 128, "topics_linked": 14, "topics_created": 0, "visible_to_classes": [3]}
```

Страницы рендерятся `PyMuPDF` в PNG и кэшируются в `data/page_cache/`.

---

## Кабинет учителя

| Метод | Путь | Описание |
|---|---|---|
| GET | `/teacher/dashboard` | сводка, классы (до 6), последние работы, ученики (до 12) |
| GET | `/teacher/classes` | классы учителя |
| GET | `/teacher/classes/{id}` | класс, ученики, работы, расписание |
| GET | `/teacher/students` | все ученики классов учителя |
| GET | `/teacher/students/{id}` | карточка ученика (id — **id пользователя**) |
| GET | `/teacher/schedule?class_id=` | расписание класса |
| POST | `/teacher/schedule` | добавить/заменить урок |
| DELETE | `/teacher/schedule/{id}` | удалить урок |
| GET | `/schedule` | расписание ученика (его класса) |

Урок:

```json
{"class_id": 3, "weekday": 0, "lesson_no": 1, "subject_id": 1, "time_start": "08:30", "time_end": "09:15", "note": "Сложение", "topic_slug": "add.within20"}
```

`weekday`: 0 — понедельник … 6 — воскресенье. Ответы `GET` и `POST` одинаковы:
`{"ok": true, "class_id": 3, "weekdays": ["Пн", …, "Вс"], "schedule": [...]}`.

---

## Кабинет родителя

| Метод | Путь | Описание |
|---|---|---|
| GET | `/parent/dashboard` | дети, суммарная статистика |
| GET | `/parent/children` | дети с классами и прогрессом |
| GET | `/parent/children/{learner_id}` | подробная карточка ребёнка |
| PATCH | `/parent/children/{learner_id}` | `name`, `avatar`, `grade`, `sound_on`, `voice_on`, `daily_limit` |
| POST | `/parent/children/{learner_id}/reset` | `{"confirm": "yes"}` — сброс прогресса |
| POST | `/parent/link` | `{"code": "ABC123"}` — привязать ребёнка по коду |
| GET | `/parent/children/{learner_id}/export` | CSV с прогрессом |

Важно: в путях `/parent/children/{id}` используется **id ученика** (`learners.id`),
а `child_id` в `/parent/library` — **id пользователя** (`users.id`). В объекте ребёнка
есть оба: `learner.id` и `user.id`.

---

## Администрирование

| Метод | Путь | Описание |
|---|---|---|
| GET | `/admin/stats` | счётчики, роли, ИИ, последние пользователи и действия |
| GET | `/admin/users?role=&search=` | список пользователей и роли |
| POST | `/admin/users` | создать пользователя |
| PATCH | `/admin/users/{id}` | изменить (`login`, `role`, `is_active`, `avatar`) |
| POST | `/admin/users/{id}/password` | `{"password": "…"}` |
| DELETE | `/admin/users/{id}` | удалить |
| GET | `/admin/orgs` | города, школы, классы, предметы, учителя |
| POST | `/admin/cities` | `{"name": "…", "region": "…"}` |
| POST | `/admin/schools` | `{"city_id": 1, "name": "…", "address": "…", "director": "…"}` |
| PATCH | `/admin/schools/{id}` | изменить школу |
| DELETE | `/admin/schools/{id}` | удалить школу |
| POST | `/admin/classes` | `{"school_id": 1, "grade": 3, "letter": "А", "teacher_id": 2}` |
| PATCH | `/admin/classes/{id}` | изменить класс |
| DELETE | `/admin/classes/{id}` | удалить класс |
| POST | `/admin/classes/{id}/students` | `{"student_id": 5}` / `{"student_id": 5, "remove": true}` |
| GET | `/admin/topics?subject_id=&grade=&search=` | темы |
| POST | `/admin/topics` | создать тему |
| PATCH | `/admin/topics/{slug}` | изменить `title`, `icon`, `description`, `order_index`, `page_start`, `page_end` |
| DELETE | `/admin/topics/{slug}` | удалить |
| GET | `/admin/textbooks?subject_id=&grade=&search=` | пособия |
| DELETE | `/admin/textbooks/{id}` | удалить пособие |
| GET | `/admin/ai` | настройки, провайдеры, статистика |
| PUT | `/admin/ai` | сохранить настройки |
| POST | `/admin/ai/test` | проверить связь: `{"ok": true, "message": "…"}` |
| GET | `/admin/audit?limit=200` | журнал действий |

Создание пользователя:

```json
{
  "login": "ivanov",
  "password": "…",
  "role": "student",
  "first_name": "Иван",
  "last_name": "Иванов",
  "email": "…",
  "city_id": 1,
  "school_id": 1,
  "class_id": 3
}
```

Для роли `student` автоматически создаётся профиль ученика; `class_id` сразу
добавляет его в класс.

---

## ИИ (необязательно)

| Метод | Путь | Описание |
|---|---|---|
| GET | `/ai/status` | включён ли ИИ, провайдер и модель |
| GET | `/ai/explain/{slug}` | готовое объяснение темы из кэша |
| POST | `/ai/explain/{slug}/refresh` | сгенерировать объяснение заново |
| POST | `/ai/assistant` | `{"question": "…", "page": "…"}` |

`/ai/status`:

```json
{"ok": true, "ai": {"enabled": true, "provider": "openrouter", "provider_name": "OpenRouter", "model": "…"}}
```

Если ИИ не настроен, все разделы скрываются: `/ai/status` возвращает
`enabled: false`, а остальные маршруты отвечают `404 ai_disabled`/`404`. Приложение
обязано скрывать кнопки ИИ при `enabled != true`.

Настройки (`PUT /admin/ai`):

```json
{
  "enabled": true,
  "provider": "openrouter",
  "base_url": "https://openrouter.ai/api/v1",
  "api_key": "sk-…",
  "keep_key": false,
  "model": "openai/gpt-4o-mini",
  "temperature": 0.3,
  "max_tokens": 900,
  "system_note": "Отвечай кратко и по-русски"
}
```

`keep_key: true` сохраняет ранее записанный ключ, если `api_key` не передан.
Ключ хранится на сервере; клиент получает только `has_key: true/false`.

---

## Дополнительные эндпоинты (версия 1.7)

Часть маршрутов появилась позже основного описания; они перечислены здесь.

### Работы: фото, результат, повтор

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/assignments/{id}/submit-photo` | сдать работу фотографиями (`multipart/form-data`, поле `photos`, до 6 файлов) |
| GET | `/assignments/{id}/result` | результат проверки, включая оценку ИИ и комментарий |
| POST | `/assignments/{id}/retry` | начать попытку заново, если работа это разрешает |

Сдача фото принимает только реальные JPEG/PNG/WebP/HEIC (проверка по сигнатуре
файла). Ответ содержит `submission_type: "photo"` и список сохранённых файлов.

### Уведомления

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/notifications` | список уведомлений, `unread` — счётчик непрочитанных |
| POST | `/notifications/{id}/read` | отметить одно прочитанным |
| POST | `/notifications/read-all` | отметить все прочитанными |

### Библиотека учителя

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/teacher/library` | книги учителя и статистика выдачи |
| POST | `/teacher/library` | добавить книгу в библиотеку класса |
| PATCH | `/teacher/library/{id}` | изменить книгу (классы, описание) |
| DELETE | `/teacher/library/{id}` | убрать книгу |
| POST | `/teacher/library/{id}/recommend` | рекомендовать книгу ученику или классу |
| GET | `/teacher/library/recommendations` | список рекомендаций |
| DELETE | `/teacher/library/recommendations/{id}` | отозвать рекомендацию |
| GET | `/teacher/textbooks` | доступные PDF-пособия |
| POST | `/teacher/textbooks` | загрузить пособие (PDF) |
| GET | `/teacher/recommend/topics` | темы, доступные для рекомендации |
| POST | `/teacher/recommend` | рекомендовать тему |

### Кабинет учителя и расписание

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/teacher/dashboard` | сводка: классы, работы, ученики |
| GET | `/teacher/classes` | классы учителя |
| GET | `/teacher/classes/{id}` | класс и его ученики |
| GET | `/teacher/students` | ученики учителя |
| GET | `/teacher/students/{id}` | карточка ученика |
| GET | `/schedule` | расписание ученика или родителя |
| GET | `/teacher/schedule` | расписание учителя |
| POST | `/teacher/schedule` | добавить урок |
| DELETE | `/teacher/schedule/{id}` | удалить урок |

### e-padruchnik (версия 1.8)

Поиск и импорт учебных пособий с национального портала `e-padruchnik.adu.by`.
Доступно учителям и администраторам.

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/padruchnik/search?q=…&grade=3&page=0` | поиск пособий; `items` — карточки, `has_next` — есть ли следующая страница |
| GET | `/padruchnik/subjects` | предметы для выбора при импорте |
| POST | `/padruchnik/import` | скачать PDF, создать пособие и разобрать темы |
| POST | `/padruchnik/upload` | загрузить PDF вручную (multipart), если сервер не может скачать его сам |

Поиск работает по локальному снимку каталога портала
(`services/padruchnik_catalog.json`), поэтому отвечает мгновенно и не зависит
от доступности `e-padruchnik.adu.by` с сервера. В ответе есть `source`
(`catalog` или `e-padruchnik.adu.by`), `total` и `generated_at`; у каждой
карточки — `pdf_url` с прямой ссылкой на PDF и `language`.

Тело импорта: `{"book_id": 1217, "subject_id": 1, "grade": 3, "class_ids": [4, 5]}`.
Учитель обязан передать хотя бы один свой класс: импортированное пособие сразу
открывается этим классам в библиотеке. Администратор может импортировать без
классов. Ответ: `textbook_id`, `book_id` (книга библиотеки), `pages`, `linked`
(сколько тем найдено в оглавлении), `created`.

Импорт синхронный и может занимать до минуты (скачивание PDF до 80 МБ).
Портал не имеет официального API, поэтому возможны ошибки `import_failed` —
текст причины возвращается в `message`.

Если сервер не может скачать PDF (например, портал блокирует его IP), ответ
`import_failed` содержит `can_upload: true`, а в `message` — прямую ссылку.
Приложение в этом случае предлагает выбрать файл на устройстве и отправляет
его в `POST /padruchnik/upload`:

`multipart/form-data`: `file` (PDF), `book_id`, `subject_id`, `grade`,
`class_ids` (повторяющееся поле или строка `4,5`). Ответ — тот же, что у
`/padruchnik/import` (`201`).

### Семейные профили

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/learners/switch` | переключить активный профиль, сохранив токен устройства |

Повторные неудачные попытки входа и ввода PIN ограничиваются на сервере:
после 5 ошибок API отвечает `429` с кодом `too_many_attempts` и полем
`message`, где указано время ожидания.

---

## Ограничения и особенности

* Идентификаторы: прогресс, звёзды, попытки — это `learners.id`; работы, классы,
  рекомендации и оценки — `users.id`. В одном ответе могут встречаться оба.
* Ответы на тесты по тексту и на работы никогда не отправляются до сдачи.
* `GET /books/{id}` принимает **id пособия** (`textbooks.id`), а
  `GET /library/books/{id}` — **id книги библиотеки** (`library_books.id`).
* PDF-страницы и сами PDF доступны только тем, кому доступна книга.
* Все изменения из API сразу видны в веб-версии: отдельной синхронизации нет.
