-- ============================================================
--  Схема базы данных «Учусь · 3–4 класс» (SQLite)
-- ============================================================

CREATE TABLE IF NOT EXISTS learners (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    avatar       TEXT    NOT NULL DEFAULT '🦊',
    grade        INTEGER NOT NULL DEFAULT 3,
    pin_hash     TEXT,
    coins        INTEGER NOT NULL DEFAULT 0,
    xp           INTEGER NOT NULL DEFAULT 0,
    streak_days  INTEGER NOT NULL DEFAULT 0,
    last_day     TEXT,
    sound_on     INTEGER NOT NULL DEFAULT 1,
    voice_on     INTEGER NOT NULL DEFAULT 1,
    daily_limit  INTEGER NOT NULL DEFAULT 0,
    device_id    TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS topics (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    slug         TEXT    NOT NULL UNIQUE,
    title        TEXT    NOT NULL,
    grade        INTEGER NOT NULL,
    subject_id   INTEGER,
    textbook_id  INTEGER,
    source       TEXT    NOT NULL DEFAULT 'manual',   -- curriculum | pdf | manual
    kind         TEXT    NOT NULL DEFAULT 'reading',  -- practice | reading
    icon         TEXT    NOT NULL DEFAULT '⭐',
    color        TEXT    NOT NULL DEFAULT 'sky',
    part         INTEGER NOT NULL DEFAULT 1,
    page_start   INTEGER NOT NULL DEFAULT 1,
    page_end     INTEGER NOT NULL DEFAULT 1,
    description  TEXT    NOT NULL DEFAULT '',
    content_json TEXT,
    min_level    INTEGER NOT NULL DEFAULT 1,
    order_index  INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS methods (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_slug   TEXT    NOT NULL,
    slug         TEXT    NOT NULL,
    name         TEXT    NOT NULL,
    widget       TEXT    NOT NULL DEFAULT 'none',
    explanation  TEXT    NOT NULL DEFAULT '',
    steps_json   TEXT    NOT NULL DEFAULT '[]',
    example_key  TEXT,
    order_index  INTEGER NOT NULL DEFAULT 0,
    UNIQUE (topic_slug, slug),
    FOREIGN KEY (topic_slug) REFERENCES topics(slug)
);

CREATE TABLE IF NOT EXISTS attempts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id   INTEGER NOT NULL,
    topic_slug   TEXT    NOT NULL,
    method_slug  TEXT,
    generator    TEXT,
    correct      INTEGER NOT NULL DEFAULT 0,
    given_answer TEXT,
    expected     TEXT,
    time_ms      INTEGER NOT NULL DEFAULT 0,
    hints_used   INTEGER NOT NULL DEFAULT 0,
    mode         TEXT    NOT NULL DEFAULT 'practice',
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_attempts_learner ON attempts(learner_id, created_at);
CREATE INDEX IF NOT EXISTS idx_attempts_topic ON attempts(learner_id, topic_slug);

CREATE TABLE IF NOT EXISTS topic_progress (
    learner_id   INTEGER NOT NULL,
    topic_slug   TEXT    NOT NULL,
    stars        INTEGER NOT NULL DEFAULT 0,
    best_streak  INTEGER NOT NULL DEFAULT 0,
    best_accuracy REAL   NOT NULL DEFAULT 0,
    attempts     INTEGER NOT NULL DEFAULT 0,
    correct      INTEGER NOT NULL DEFAULT 0,
    boss_cleared INTEGER NOT NULL DEFAULT 0,
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (learner_id, topic_slug)
);

CREATE TABLE IF NOT EXISTS method_progress (
    learner_id   INTEGER NOT NULL,
    topic_slug   TEXT    NOT NULL,
    method_slug  TEXT    NOT NULL,
    seen         INTEGER NOT NULL DEFAULT 0,
    attempts     INTEGER NOT NULL DEFAULT 0,
    correct      INTEGER NOT NULL DEFAULT 0,
    mastered     INTEGER NOT NULL DEFAULT 0,
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (learner_id, topic_slug, method_slug)
);

CREATE TABLE IF NOT EXISTS badges (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id   INTEGER NOT NULL,
    badge_key    TEXT    NOT NULL,
    earned_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (learner_id, badge_key)
);

CREATE TABLE IF NOT EXISTS daily_answers (
    learner_id   INTEGER NOT NULL,
    day          TEXT    NOT NULL,
    generator    TEXT    NOT NULL,
    correct      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (learner_id, day, generator)
);

CREATE TABLE IF NOT EXISTS play_sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id   INTEGER NOT NULL,
    topic_slug   TEXT    NOT NULL,
    mode         TEXT    NOT NULL DEFAULT 'practice',
    started_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    ended_at     TEXT,
    task_count   INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    xp_gained    INTEGER NOT NULL DEFAULT 0,
    round_state  TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_learner ON play_sessions(learner_id, started_at);

CREATE TABLE IF NOT EXISTS app_meta (
    key          TEXT PRIMARY KEY,
    value        TEXT
);

-- ============================================================
--  МНОГОПОЛЬЗОВАТЕЛЬСКАЯ ЧАСТЬ: организации, аккаунты, курсы
-- ============================================================

-- Аккаунты пользователей: admin | teacher | student | parent
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    login         TEXT    NOT NULL UNIQUE,
    email         TEXT,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'student',
    first_name    TEXT    NOT NULL DEFAULT '',
    last_name     TEXT    NOT NULL DEFAULT '',
    avatar        TEXT    NOT NULL DEFAULT '🦊',
    phone         TEXT,
    city_id       INTEGER,
    school_id     INTEGER,
    child_code    TEXT,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    last_login    TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_school ON users(school_id);

-- Привязка аккаунта ученика к профилю прогресса
CREATE TABLE IF NOT EXISTS learner_accounts (
    learner_id    INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL UNIQUE,
    linked_at     TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Географическая структура: город → школа → класс
CREATE TABLE IF NOT EXISTS cities (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    region        TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS schools (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    city_id       INTEGER NOT NULL,
    name          TEXT NOT NULL,
    short_name    TEXT,
    address       TEXT,
    director      TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (city_id, name),
    FOREIGN KEY (city_id) REFERENCES cities(id)
);

CREATE INDEX IF NOT EXISTS idx_schools_city ON schools(city_id);

-- Учебный класс (3 «А», 4 «Б» и т.д.) с ведущим учителем
CREATE TABLE IF NOT EXISTS school_classes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    school_id     INTEGER NOT NULL,
    grade         INTEGER NOT NULL,
    letter        TEXT NOT NULL DEFAULT '',
    title         TEXT,
    teacher_id    INTEGER,
    year          TEXT NOT NULL DEFAULT '2025/2026',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (school_id, grade, letter, year),
    FOREIGN KEY (school_id) REFERENCES schools(id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_classes_school ON school_classes(school_id);
CREATE INDEX IF NOT EXISTS idx_classes_teacher ON school_classes(teacher_id);

-- Ученики в классах (у ученика может быть несколько классов/параллелей)
CREATE TABLE IF NOT EXISTS class_students (
    class_id      INTEGER NOT NULL,
    student_id    INTEGER NOT NULL,
    joined_at     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (class_id, student_id),
    FOREIGN KEY (class_id) REFERENCES school_classes(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_class_students_student ON class_students(student_id);

-- Связь родителя с детьми
CREATE TABLE IF NOT EXISTS parent_children (
    parent_id     INTEGER NOT NULL,
    child_id      INTEGER NOT NULL,
    relation      TEXT NOT NULL DEFAULT 'родитель',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (parent_id, child_id),
    FOREIGN KEY (parent_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (child_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Предметы
CREATE TABLE IF NOT EXISTS subjects (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    slug          TEXT NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    icon          TEXT NOT NULL DEFAULT '📘',
    color         TEXT NOT NULL DEFAULT 'sky',
    description   TEXT,
    is_active     INTEGER NOT NULL DEFAULT 1,
    order_index   INTEGER NOT NULL DEFAULT 0
);

-- Курс предмета (программа для класса/параллели)
CREATE TABLE IF NOT EXISTS courses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id    INTEGER NOT NULL,
    title         TEXT NOT NULL,
    description   TEXT,
    grade         INTEGER NOT NULL DEFAULT 3,
    teacher_id    INTEGER,
    school_id     INTEGER,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_courses_teacher ON courses(teacher_id);
CREATE INDEX IF NOT EXISTS idx_courses_subject ON courses(subject_id);

-- Темы, включённые в курс (учитель настраивает состав и порядок)
CREATE TABLE IF NOT EXISTS course_topics (
    course_id     INTEGER NOT NULL,
    topic_slug    TEXT NOT NULL,
    order_index   INTEGER NOT NULL DEFAULT 0,
    enabled       INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (course_id, topic_slug),
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);

-- Классы, подключённые к курсу
CREATE TABLE IF NOT EXISTS course_classes (
    course_id     INTEGER NOT NULL,
    class_id      INTEGER NOT NULL,
    PRIMARY KEY (course_id, class_id),
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (class_id) REFERENCES school_classes(id) ON DELETE CASCADE
);

-- Учебные пособия (PDF), загруженные администратором
CREATE TABLE IF NOT EXISTS textbooks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id    INTEGER NOT NULL,
    grade         INTEGER NOT NULL,
    title         TEXT NOT NULL,
    author        TEXT,
    publisher     TEXT,
    year          TEXT,
    filename      TEXT NOT NULL,
    original_name TEXT,
    size_bytes    INTEGER NOT NULL DEFAULT 0,
    pages         INTEGER NOT NULL DEFAULT 0,
    description   TEXT,
    uploaded_by   INTEGER,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_textbooks_grade ON textbooks(subject_id, grade);

-- Привязка пособия к теме и странице
CREATE TABLE IF NOT EXISTS textbook_topics (
    textbook_id   INTEGER NOT NULL,
    topic_slug    TEXT NOT NULL,
    page          INTEGER NOT NULL DEFAULT 1,
    page_end      INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (textbook_id, topic_slug),
    FOREIGN KEY (textbook_id) REFERENCES textbooks(id) ON DELETE CASCADE
);

-- Проверочные и контрольные работы
CREATE TABLE IF NOT EXISTS assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'проверочная',
    description     TEXT,
    course_id       INTEGER,
    subject_id      INTEGER,
    class_id        INTEGER,
    teacher_id      INTEGER,
    student_id      INTEGER,
    topic_slugs     TEXT NOT NULL DEFAULT '[]',
    questions_json  TEXT NOT NULL DEFAULT '[]',
    questions_count INTEGER NOT NULL DEFAULT 10,
    time_limit      INTEGER NOT NULL DEFAULT 0,
    due_date        TEXT,
    status          TEXT NOT NULL DEFAULT 'черновик',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    published_at    TEXT,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL,
    FOREIGN KEY (class_id) REFERENCES school_classes(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_assignments_class ON assignments(class_id, status);
CREATE INDEX IF NOT EXISTS idx_assignments_teacher ON assignments(teacher_id);

-- Выполненные работы
CREATE TABLE IF NOT EXISTS assignment_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id   INTEGER NOT NULL,
    student_id      INTEGER NOT NULL,
    score           INTEGER NOT NULL DEFAULT 0,
    max_score       INTEGER NOT NULL DEFAULT 0,
    answers         TEXT NOT NULL DEFAULT '[]',
    duration_sec    INTEGER NOT NULL DEFAULT 0,
    started_at      TEXT,
    completed_at    TEXT,
    UNIQUE (assignment_id, student_id),
    FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Расписание уроков класса
CREATE TABLE IF NOT EXISTS schedules (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id      INTEGER NOT NULL,
    subject_id    INTEGER,
    teacher_id    INTEGER,
    weekday       INTEGER NOT NULL DEFAULT 1,
    lesson_no     INTEGER NOT NULL DEFAULT 1,
    time_start    TEXT,
    time_end      TEXT,
    topic_slug    TEXT,
    note          TEXT,
    FOREIGN KEY (class_id) REFERENCES school_classes(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_schedules_class ON schedules(class_id, weekday);

-- Журнал действий администратора
CREATE TABLE IF NOT EXISTS audit_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER,
    action        TEXT NOT NULL,
    entity        TEXT,
    entity_id     TEXT,
    details       TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);

-- ============================================================
--  БИБЛИОТЕКА: книги учителя и доступ учеников
-- ============================================================

-- Книга, которую учитель загрузил в библиотеку школы.
-- Файл (PDF) хранится в textbooks; темы берутся из оглавления книги.
CREATE TABLE IF NOT EXISTS library_books (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id      INTEGER NOT NULL,
    textbook_id   INTEGER NOT NULL,
    subject_id    INTEGER,
    grade         INTEGER,
    title         TEXT NOT NULL,
    author        TEXT,
    description   TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (textbook_id) REFERENCES textbooks(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id)
);

CREATE INDEX IF NOT EXISTS idx_library_books_owner ON library_books(owner_id);
CREATE INDEX IF NOT EXISTS idx_library_books_textbook ON library_books(textbook_id);
CREATE INDEX IF NOT EXISTS idx_library_books_subject ON library_books(subject_id, grade);

-- Классы, которым доступна книга: их ученики видят её в своей библиотеке.
CREATE TABLE IF NOT EXISTS library_book_classes (
    book_id    INTEGER NOT NULL,
    class_id   INTEGER NOT NULL,
    added_at   TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (book_id, class_id),
    FOREIGN KEY (book_id) REFERENCES library_books(id) ON DELETE CASCADE,
    FOREIGN KEY (class_id) REFERENCES school_classes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_library_book_classes_class ON library_book_classes(class_id);

-- Рекомендация учителя: конкретная тема книги (или книга целиком)
-- классу либо отдельному ученику.
CREATE TABLE IF NOT EXISTS library_recommendations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id    INTEGER NOT NULL,
    book_id       INTEGER NOT NULL,
    topic_slug    TEXT,
    target_kind   TEXT NOT NULL DEFAULT 'student',  -- student | class
    student_id    INTEGER,
    class_id      INTEGER,
    note          TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES library_books(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (class_id) REFERENCES school_classes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lib_rec_student ON library_recommendations(student_id);
CREATE INDEX IF NOT EXISTS idx_lib_rec_class ON library_recommendations(class_id);
CREATE INDEX IF NOT EXISTS idx_lib_rec_teacher ON library_recommendations(teacher_id);
CREATE INDEX IF NOT EXISTS idx_lib_rec_book ON library_recommendations(book_id);

-- Отметка «прочитано» — своя для каждого ученика,
-- даже если рекомендация выдана целому классу.
CREATE TABLE IF NOT EXISTS library_recommendation_done (
    rec_id      INTEGER NOT NULL,
    student_id  INTEGER NOT NULL,
    done_at     TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (rec_id, student_id),
    FOREIGN KEY (rec_id) REFERENCES library_recommendations(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================================
--  ИИ: настройки облачной модели, кэш объяснений и журнал запросов
-- ============================================================

-- Единственная строка с настройками подключения к облачной модели.
-- Пока enabled = 0 или нет ключа, все функции ИИ скрыты и приложение
-- работает полностью офлайн.
CREATE TABLE IF NOT EXISTS ai_settings (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    enabled      INTEGER NOT NULL DEFAULT 0,
    provider     TEXT    NOT NULL DEFAULT 'openrouter',
    base_url     TEXT    NOT NULL DEFAULT 'https://openrouter.ai/api/v1',
    api_key      TEXT,
    model        TEXT    NOT NULL DEFAULT 'openai/gpt-4o-mini',
    temperature  REAL    NOT NULL DEFAULT 0.3,
    max_tokens   INTEGER NOT NULL DEFAULT 900,
    system_note  TEXT,
    updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO ai_settings (id) VALUES (1);

-- Готовые объяснения тем: генерируются один раз и показываются сразу,
-- поэтому страницы остаются быстрыми, а объяснения доступны и без сети.
CREATE TABLE IF NOT EXISTS ai_explanations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_slug  TEXT    NOT NULL UNIQUE,
    grade       INTEGER,
    model       TEXT,
    content     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ai_explanations_slug ON ai_explanations(topic_slug);

-- Вопросы по теме, составленные ИИ. Кэш на тему: один запрос на всех учеников.
CREATE TABLE IF NOT EXISTS ai_quizzes (
    topic_slug  TEXT    PRIMARY KEY,
    grade       INTEGER,
    model       TEXT,
    payload     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Журнал обращений к ИИ: помогает администратору видеть ошибки и активность.
CREATE TABLE IF NOT EXISTS ai_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    kind        TEXT    NOT NULL,
    model       TEXT,
    ok          INTEGER NOT NULL DEFAULT 0,
    detail      TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ai_requests_created ON ai_requests(created_at);

-- ============================================================
--  Мобильный API: долгоживущие токены (Bearer) вместо cookie-сессий
-- ============================================================

-- В базе хранится только SHA-256 от токена: утечка базы не даёт войти.
CREATE TABLE IF NOT EXISTS api_tokens (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash   TEXT    NOT NULL UNIQUE,
    kind         TEXT    NOT NULL DEFAULT 'user',   -- user | learner
    user_id      INTEGER,
    learner_id   INTEGER,
    label        TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    last_used_at TEXT,
    expires_at   TEXT,
    revoked      INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (learner_id) REFERENCES learners(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_api_tokens_learner ON api_tokens(learner_id);


