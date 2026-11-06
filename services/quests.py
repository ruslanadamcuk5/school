"""3D-квесты по темам учебных пособий.

Эпизод — это одна практическая тема курса (например, «Умножение и деление»),
разложенная на пять станций. Задания собираются офлайн из уже проверенных
генераторов ``content.generators``; правильные ответы хранятся только на
сервере и никогда не попадают в браузер до проверки.

Сценарий универсален: один 3D-плеер на фронтенде проигрывает любой эпизод,
поэтому новая тема (и новая загруженная книга) не требует отдельной игры.
"""
from __future__ import annotations

import hashlib
import json
import random
import secrets
import time
from typing import Any

from content.answer import check_answer, expected_display
from content.curriculum import topic_by_slug as curriculum_topic
from content.generators import generators_for_topic, get_generator, shuffle_options
from database import execute, query_all, query_one
from services import progress as progress_service

QUEST_LENGTH = 5
MINUTES_PER_QUEST = 10

# Пять станций одного эпизода. ``theme`` выбирает 3D-декорацию на клиенте.
STATIONS: tuple[dict[str, Any], ...] = (
    {
        "key": "gate",
        "title": "Ворота знаний",
        "theme": "gate",
        "icon": "🚪",
        "color": "#8b5cf6",
        "prompt": "Разомнись перед дорогой",
    },
    {
        "key": "bridge",
        "title": "Мост чисел",
        "theme": "bridge",
        "icon": "🌉",
        "color": "#22d3ee",
        "prompt": "Перейди через реку",
    },
    {
        "key": "forest",
        "title": "Лес загадок",
        "theme": "forest",
        "icon": "🌲",
        "color": "#34d399",
        "prompt": "Найди тропинку",
    },
    {
        "key": "tower",
        "title": "Башня задач",
        "theme": "tower",
        "icon": "🗼",
        "color": "#fbbf24",
        "prompt": "Поднимись на вершину",
    },
    {
        "key": "crystal",
        "title": "Кристалл ответов",
        "theme": "crystal",
        "icon": "💎",
        "color": "#f472b6",
        "prompt": "Зажги кристалл",
    },
)

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS quest_runs (
        run_key     TEXT PRIMARY KEY,
        learner_id  INTEGER NOT NULL,
        quest_slug  TEXT NOT NULL,
        topic_slug  TEXT NOT NULL,
        tasks_json  TEXT NOT NULL DEFAULT '[]',
        state_json  TEXT NOT NULL DEFAULT '{}',
        status      TEXT NOT NULL DEFAULT 'active',
        correct     INTEGER NOT NULL DEFAULT 0,
        total       INTEGER NOT NULL DEFAULT 5,
        xp          INTEGER NOT NULL DEFAULT 0,
        coins       INTEGER NOT NULL DEFAULT 0,
        started_at  TEXT NOT NULL DEFAULT (datetime('now')),
        finished_at TEXT
    )""",
    """CREATE INDEX IF NOT EXISTS idx_quest_runs_learner
       ON quest_runs(learner_id, status)""",
    """CREATE TABLE IF NOT EXISTS quest_progress (
        learner_id  INTEGER NOT NULL,
        quest_slug  TEXT NOT NULL,
        topic_slug  TEXT NOT NULL,
        attempts    INTEGER NOT NULL DEFAULT 0,
        completed   INTEGER NOT NULL DEFAULT 0,
        best_correct INTEGER NOT NULL DEFAULT 0,
        best_stars  INTEGER NOT NULL DEFAULT 0,
        best_xp     INTEGER NOT NULL DEFAULT 0,
        best_time_ms INTEGER NOT NULL DEFAULT 0,
        updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (learner_id, quest_slug)
    )""",
)


_MIGRATED = False


def ensure_tables() -> None:
    """Создать таблицы в существующей базе (SQLite и PostgreSQL)."""
    for statement in _SCHEMA:
        execute(statement)
    global _MIGRATED
    if not _MIGRATED:
        _MIGRATED = True
        # Ранняя версия таблицы использовала integer-подобный ``id``; в
        # PostgreSQL совместимый слой принимает его за AUTOINCREMENT.
        try:
            execute("ALTER TABLE quest_runs RENAME COLUMN id TO run_key")
        except Exception:  # noqa: BLE001 - колонка уже переименована
            pass


# ------------------------------------------------------------------ топики
def _subject_row(subject_id: int | None) -> dict | None:
    if subject_id:
        row = query_one("SELECT * FROM subjects WHERE id = ?", (subject_id,))
        return dict(row) if row else None
    return None


def _math_subject() -> dict | None:
    row = query_one("SELECT * FROM subjects WHERE slug = 'math'")
    if row:
        return dict(row)
    row = query_one("SELECT * FROM subjects ORDER BY id LIMIT 1")
    return dict(row) if row else None


def _db_topic(slug: str, grade: int, subject_id: int) -> dict | None:
    row = query_one(
        """SELECT * FROM topics
            WHERE slug = ? AND grade = ? AND subject_id = ?""",
        (slug, grade, subject_id),
    )
    if not row:
        return None
    data = dict(row)
    methods: list[dict] = []
    try:
        raw = json.loads(data.get("content_json") or "{}")
        # Для тем-чтения content_json — список страниц [(номер, текст)],
        # а способы объяснения есть только у практических тем.
        methods = raw.get("methods") or [] if isinstance(raw, dict) else []
    except (TypeError, ValueError):
        methods = []
    subject = query_one(
        "SELECT name, slug FROM subjects WHERE id = ?", (data.get("subject_id"),)
    )
    return {
        "slug": data["slug"],
        "title": data["title"],
        "description": data.get("description") or "",
        "icon": data.get("icon") or "⭐",
        "color": data.get("color") or "violet",
        "grade": int(data["grade"]),
        "part": int(data.get("part") or 1),
        "page_start": int(data.get("page_start") or 1),
        "page_end": int(data.get("page_end") or data.get("page_start") or 1),
        "subject_id": data.get("subject_id"),
        "subject_name": (subject["name"] if subject else ""),
        "subject_slug": (subject["slug"] if subject else ""),
        "kind": data.get("kind") or "reading",
        "source": data.get("source") or "manual",
        "content_json": data.get("content_json"),
        "generators": generators_for_topic(data["slug"]),
        "methods": methods,
    }


def topic_can_quest(topic: dict | Any) -> bool:
    """Может ли по теме собраться квест.

    Для 1–4 классов подходит любая загруженная тема: задания собираются из
    текста пособия, вопросов ИИ или офлайн-фолбэка. Для старших классов —
    только темы с проверенными генераторами.
    """
    try:
        grade = int(topic["grade"])
    except (KeyError, TypeError, ValueError, IndexError):
        return False
    if 1 <= grade <= 4:
        return True
    return bool(generators_for_topic(str(topic["slug"])))


def _topics_for(grade: int, subject_id: int) -> list[dict]:
    """Все темы предмета, по которым можно провести квест."""
    subject = _subject_row(subject_id)
    is_math = bool(subject and subject.get("slug") == "math")
    topics: list[dict] = []
    seen: set[str] = set()

    if is_math:
        from content.curriculum import topics_for_grade

        for topic in topics_for_grade(grade):
            keys = [k for k in topic["generators"] if get_generator(k)]
            if keys:
                topics.append({**topic, "generators": keys})
                seen.add(topic["slug"])

    # Темы из загруженных пособий: для 1–4 классов — любые, для остальных —
    # только те, где уже есть генераторы заданий.
    rows = query_all(
        """SELECT slug FROM topics
            WHERE grade = ? AND subject_id = ?
            ORDER BY page_start, id""",
        (grade, subject_id),
    )
    for row in rows:
        if row["slug"] in seen:
            continue
        topic = _db_topic(row["slug"], grade, subject_id)
        if topic and topic_can_quest(topic):
            topics.append(topic)
            seen.add(row["slug"])
    return topics


def _visible_slugs(learner: dict, subject_id: int, grade: int) -> set[str]:
    user_id = learner.get("user_id")
    if not user_id:
        return set()
    try:
        from services import orgs

        return set(orgs.course_topic_slugs_for_student(user_id, subject_id, grade))
    except Exception:  # noqa: BLE001 - видимость не должна ломать квесты
        return set()


def _books(grade: int, subject_id: int) -> list[dict]:
    try:
        from services import textbooks

        rows = textbooks.textbooks_for_grade(grade, subject_id)
    except Exception:  # noqa: BLE001
        rows = []
    books = []
    for index, row in enumerate(rows):
        book = dict(row)
        books.append(
            {
                "id": book["id"],
                "title": book["title"],
                "author": book.get("author") or "",
                "pages": book.get("pages") or 0,
                "part": index + 1,
            }
        )
    return books


def _book_for(topic: dict, books: list[dict]) -> dict | None:
    if not books:
        return None
    part = int(topic.get("part") or 1)
    if 1 <= part <= len(books):
        return books[part - 1]
    return books[0]


def _progress_map(learner_id: int) -> dict[str, dict]:
    ensure_tables()
    rows = query_all(
        "SELECT * FROM quest_progress WHERE learner_id = ?", (learner_id,)
    )
    return {row["quest_slug"]: dict(row) for row in rows}


def _active_run(learner_id: int, quest_slug: str) -> str | None:
    row = query_one(
        """SELECT run_key FROM quest_runs
            WHERE learner_id = ? AND quest_slug = ? AND status = 'active'
            ORDER BY started_at DESC, run_key DESC LIMIT 1""",
        (learner_id, quest_slug),
    )
    return row["run_key"] if row else None


def _episode(topic: dict, books: list[dict], progress: dict | None,
             active_run: str | None) -> dict[str, Any]:
    topic_slug = topic["slug"]
    best = progress or {}
    return {
        "slug": topic_slug,
        "title": topic["title"],
        "description": topic.get("description") or "",
        "icon": topic.get("icon") or "⭐",
        "color": topic.get("color") or "violet",
        "grade": topic["grade"],
        "part": topic.get("part") or 1,
        "page_start": topic.get("page_start") or 1,
        "page_end": topic.get("page_end") or topic.get("page_start") or 1,
        "minutes": MINUTES_PER_QUEST,
        "stations": [dict(station) for station in STATIONS],
        "book": _book_for(topic, books),
        "completed": bool(best.get("completed")),
        "stars": int(best.get("best_stars") or 0),
        "best_correct": int(best.get("best_correct") or 0),
        "attempts": int(best.get("attempts") or 0),
        "best_xp": int(best.get("best_xp") or 0),
        "active_run_id": active_run,
    }


# ------------------------------------------------------------------ каталог
def list_quests(learner: dict, subject_id: int | None = None) -> dict[str, Any]:
    ensure_tables()
    learner = dict(learner)
    grade = int(learner.get("grade") or 3)
    subject = _subject_row(subject_id) if subject_id else _math_subject()
    if subject is None:
        return {"quests": [], "books": [], "book": None, "grade": grade,
                "subject": None, "completed": 0, "total": 0}

    subject_id = int(subject["id"])
    topics = _topics_for(grade, subject_id)

    books = _books(grade, subject_id)
    progress = _progress_map(int(learner["id"]))
    quests = []
    for topic in topics:
        active = _active_run(int(learner["id"]), topic["slug"])
        quests.append(_episode(topic, books, progress.get(topic["slug"]), active))

    return {
        "quests": quests,
        "books": books,
        "book": books[0] if books else None,
        "subject": {
            "id": subject_id,
            "name": subject.get("name") or "Математика",
            "slug": subject.get("slug") or "math",
            "icon": subject.get("icon") or "🔢",
        },
        "grade": grade,
        "completed": sum(1 for quest in quests if quest["completed"]),
        "total": len(quests),
    }


def _find_topic(learner: dict, slug: str) -> tuple[dict, int, list[dict]]:
    learner = dict(learner)
    grade = int(learner.get("grade") or 3)
    subject = _math_subject()
    if subject is None:
        raise QuestError(404, "not_found", "Предметы ещё не настроены")
    subject_id = int(subject["id"])

    topic = curriculum_topic(slug) if subject.get("slug") == "math" else None
    if topic and int(topic["grade"]) != grade:
        topic = None
    if topic is None:
        row = query_one(
            "SELECT * FROM topics WHERE slug = ? AND grade = ?", (slug, grade)
        )
        if row:
            subject_id = int(row["subject_id"] or subject_id)
            topic = _db_topic(slug, grade, subject_id)
    if topic is None:
        raise QuestError(404, "not_found", "Квест не найден")
    keys = [key for key in topic.get("generators", []) if get_generator(key)]
    topic = {**topic, "generators": keys}
    if not keys and not topic_can_quest(topic):
        raise QuestError(404, "not_found", "Для этой темы ещё нет заданий квеста")
    # Квест открыт для любой темы своего класса: темы загруженных пособий
    # видны ученику, даже если курс ещё не включил их в программу.
    return topic, subject_id, _books(grade, subject_id)


class QuestError(Exception):
    """Ошибка квеста с HTTP-статусом и машинным кодом."""

    def __init__(self, status: int, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.status = status
        self.code = code
        self.message = message or code


def quest_detail(learner: dict, slug: str) -> dict[str, Any]:
    ensure_tables()
    learner = dict(learner)
    topic, _, books = _find_topic(learner, slug)
    progress = _progress_map(int(learner["id"])).get(slug)
    active = _active_run(int(learner["id"]), slug)
    return _episode(topic, books, progress, active)


# ------------------------------------------------------------------ задания
def _fallback_reading_tasks(
    topic: dict,
    seed: str,
    needed: int,
    used_questions: set[str],
) -> list[dict[str, Any]]:
    """Простые офлайн-вопросы, если текста и ИИ-вопросов совсем нет.

    Они не заменяют предметные задания, но позволяют открыть квест по любой
    загруженной теме (например, по скану без текстового слоя) и не показывают
    ребёнку ошибку «квест не сформирован».
    """
    from content.generators.base import task as make_task

    if needed <= 0:
        return []
    rng = random.Random(f"{seed}:fallback")
    subject_id = topic.get("subject_id")
    grade = int(topic.get("grade") or 3)
    slug = topic.get("slug") or ""
    rows = query_all(
        """SELECT title, description FROM topics
            WHERE subject_id = ? AND grade = ? AND slug <> ?
            ORDER BY id""",
        (subject_id, grade, slug),
    )
    titles = [str(row["title"]) for row in rows if str(row["title"] or "").strip()]
    descriptions = [
        str(row["description"]) for row in rows
        if len(str(row["description"] or "").strip()) >= 20
    ]
    subject_name = str(topic.get("subject_name") or "").strip()
    subject_rows = query_all(
        """SELECT name FROM subjects
            WHERE COALESCE(name, '') <> '' AND name <> ?
            ORDER BY name""",
        (subject_name,),
    )
    subjects = [str(row["name"]) for row in subject_rows]

    candidates: list[dict[str, Any]] = []
    title = str(topic.get("title") or "").strip()
    title_prompts = (
        "Как называется тема урока?",
        "Выбери название темы, которую сейчас изучаем.",
        "Какая тема открыта перед тобой?",
    )
    if title and len(titles) >= 3:
        for prompt in title_prompts:
            choices = shuffle_options(
                [title, *rng.sample(titles, min(3, len(titles)))]
            )
            candidates.append(make_task(
                prompt,
                title,
                answer_type="choice",
                choices=choices,
                solution=f"Это тема «{title}».",
                difficulty=1,
            ))

    description = str(topic.get("description") or "").strip()
    if len(description) >= 20 and len(descriptions) >= 3:
        choices = shuffle_options(
            [description[:180], *[item[:180] for item in rng.sample(descriptions, 3)]]
        )
        candidates.append(make_task(
            f"Какое описание подходит теме «{title}»?",
            description[:180],
            answer_type="choice",
            choices=choices,
            solution=f"Это описание темы «{title}».",
            difficulty=1,
        ))

    if subject_name and len(subjects) >= 3 and title:
        choices = shuffle_options(
            [subject_name, *rng.sample(subjects, min(3, len(subjects)))]
        )
        candidates.append(make_task(
            f"К какому предмету относится тема «{title}»?",
            subject_name,
            answer_type="choice",
            choices=choices,
            solution=f"Тема «{title}» относится к предмету «{subject_name}».",
            difficulty=1,
        ))
        candidates.append(make_task(
            f"Какой школьный предмет изучает тему «{title}»?",
            subject_name,
            answer_type="choice",
            choices=shuffle_options(list(choices)),
            solution=f"Это тема по предмету «{subject_name}».",
            difficulty=1,
        ))

    if title and 1 <= grade <= 4:
        grades = sorted({
            str(grade),
            *[str(item) for item in rng.sample([1, 2, 3, 4], 3)],
        })
        candidates.append(make_task(
            f"В каком классе проходят тему «{title}»?",
            str(grade),
            answer_type="choice",
            choices=shuffle_options(grades),
            solution=f"Тема «{title}» из программы {grade} класса.",
            difficulty=1,
        ))

    rng.shuffle(candidates)
    tasks: list[dict[str, Any]] = []

    def add(base: dict[str, Any], *, repeat: bool) -> None:
        question = str(base.get("question") or "")
        key = question.casefold()
        if repeat:
            # Вопрос повторяется, но с другим порядком вариантов: так
            # задание остаётся решаемым и не выглядит точной копией.
            base["choices"] = shuffle_options(list(base.get("choices") or []))
        else:
            if key in used_questions:
                return
            used_questions.add(key)
        tasks.append({
            **base,
            "generator": "reading_fallback",
            "method": None,
        })

    for base in candidates:
        if len(tasks) >= needed:
            break
        add(dict(base), repeat=False)

    # Если разных вопросов меньше, чем нужно станций, повторяем их.
    index = 0
    while candidates and len(tasks) < needed:
        add(dict(candidates[index % len(candidates)]), repeat=True)
        index += 1
    return tasks


def _reading_tasks(
    topic: dict, seed: str, user_id: int | None = None
) -> list[dict[str, Any]]:
    """Задания по тексту темы: ИИ-вопросы, cloze и офлайн-фолбэк."""
    from services import reading_quiz, topics as topics_service

    rng = random.Random(seed)
    row = topics_service.get_topic(topic["slug"])
    pool: list[dict[str, Any]] = []
    if row is not None:
        try:
            # Берём с запасом: из большого пула каждый запуск выбирает свои
            # пять вопросов, поэтому прохождение не повторяется.
            # allow_ai=False — запуск квеста не должен ждать модель: берём
            # только сохранённый кэш, cloze и офлайн-фолбэк.
            pool = reading_quiz.build_questions(
                row, QUEST_LENGTH * 4, user_id=user_id, allow_ai=False
            )
        except Exception:  # noqa: BLE001 - квест не должен падать из-за PDF/ИИ
            pool = []

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in pool:
        question = str(item.get("question") or "").strip()
        if not question:
            continue
        key = question.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    rng.shuffle(unique)

    tasks: list[dict[str, Any]] = []
    for item in unique[:QUEST_LENGTH]:
        tasks.append({
            **item,
            "generator": item.get("generator") or "reading",
            "method": None,
        })

    if len(tasks) < QUEST_LENGTH:
        tasks.extend(_fallback_reading_tasks(
            topic,
            seed,
            QUEST_LENGTH - len(tasks),
            {str(task.get("question") or "").casefold() for task in tasks},
        ))
    return tasks[:QUEST_LENGTH]


def _build_tasks(
    topic: dict, seed: str, user_id: int | None = None
) -> list[dict[str, Any]]:
    """Собрать пять разных заданий по теме.

    Если у темы есть проверенные генераторы (математика), задания берутся из
    них. Иначе — из текста загруженного пособия, ИИ-вопросов и офлайн-фолбэка.
    """
    keys = [key for key in topic.get("generators", []) if get_generator(key)]
    if not keys:
        return _reading_tasks(topic, seed, user_id)

    rng = random.Random(seed)
    rng.shuffle(keys)
    methods = [method["slug"] for method in topic.get("methods", [])]
    tasks: list[dict[str, Any]] = []
    used_questions: set[str] = set()

    for index in range(QUEST_LENGTH):
        generator_key = keys[index % len(keys)]
        generator = get_generator(generator_key)
        if generator is None:
            continue
        task: dict[str, Any] | None = None
        # До шести попыток, чтобы в одном эпизоде не было одинаковых вопросов.
        for _ in range(6):
            candidate = generator(rng.randint(1, 3))
            question = str(candidate.get("question") or "")
            if question and question not in used_questions:
                task = candidate
                break
        if task is None:
            task = generator(rng.randint(1, 3))
        used_questions.add(str(task.get("question") or ""))
        tasks.append(
            {
                **task,
                "generator": generator_key,
                "method": methods[index % len(methods)] if methods else None,
                "station": index,
            }
        )
    return tasks


def _public_task(task: dict, index: int) -> dict[str, Any]:
    station = STATIONS[index]
    return {
        "index": index,
        "station": dict(station),
        "question": task.get("question") or "",
        "answer_type": task.get("answer_type") or "number",
        "choices": task.get("choices") or [],
        "widget": task.get("widget"),
        "difficulty": task.get("difficulty") or 1,
        "hint": (task.get("hints") or [None])[0],
    }


def _new_state() -> dict[str, Any]:
    return {
        "stations": [
            {"done": False, "correct": False, "attempts": 0} for _ in STATIONS
        ],
        "correct": 0,
        "xp": 0,
        "coins": 0,
        "started_ms": int(time.time() * 1000),
    }


def _run_payload(row: dict, topic: dict, tasks: list[dict],
                 state: dict) -> dict[str, Any]:
    total = len(tasks)
    return {
        "run_id": row["run_key"],
        "status": row.get("status") or "active",
        "quest": {
            "slug": topic["slug"],
            "title": topic["title"],
            "icon": topic.get("icon") or "⭐",
            "grade": topic["grade"],
            "page_start": topic.get("page_start") or 1,
            "page_end": topic.get("page_end") or topic.get("page_start") or 1,
            "minutes": MINUTES_PER_QUEST,
        },
        "tasks": [_public_task(task, index) for index, task in enumerate(tasks)],
        "stations": [
            {**dict(station), **state["stations"][index]}
            for index, station in enumerate(STATIONS[:total])
        ],
        "total": total,
        "correct": int(state.get("correct") or 0),
        "xp": int(state.get("xp") or 0),
        "coins": int(state.get("coins") or 0),
        "finished": all(item.get("done") for item in state["stations"][:total]),
    }


def _load_run(learner_id: int, run_id: str) -> dict:
    row = query_one(
        "SELECT * FROM quest_runs WHERE run_key = ? AND learner_id = ?",
        (run_id, learner_id),
    )
    if not row:
        raise QuestError(404, "run_not_found", "Квест не найден. Начните заново.")
    return dict(row)


def _parse(row: dict) -> tuple[list[dict], dict]:
    try:
        tasks = json.loads(row.get("tasks_json") or "[]")
        state = json.loads(row.get("state_json") or "{}")
    except (TypeError, ValueError) as exc:
        raise QuestError(500, "broken_run", "Не удалось прочитать квест") from exc
    state.setdefault("stations", _new_state()["stations"])
    state.setdefault("correct", 0)
    state.setdefault("xp", 0)
    state.setdefault("coins", 0)
    state.setdefault("started_ms", int(time.time() * 1000))
    return tasks, state


def _save(row: dict, state: dict) -> None:
    execute(
        """UPDATE quest_runs
              SET state_json = ?, correct = ?, xp = ?, coins = ?
            WHERE run_key = ?""",
        (
            json.dumps(state, ensure_ascii=False),
            int(state.get("correct") or 0),
            int(state.get("xp") or 0),
            int(state.get("coins") or 0),
            row["run_key"],
        ),
    )


def start_run(learner: dict, slug: str) -> dict[str, Any]:
    ensure_tables()
    learner = dict(learner)
    topic, _, books = _find_topic(learner, slug)
    learner_id = int(learner["id"])

    # Незаконченные попытки этой темы закрываем: активной остаётся последняя.
    execute(
        """UPDATE quest_runs SET status = 'abandoned', finished_at = datetime('now')
            WHERE learner_id = ? AND quest_slug = ? AND status = 'active'""",
        (learner_id, slug),
    )

    seed = f"{slug}:{learner_id}:{secrets.token_hex(8)}"
    tasks = _build_tasks(
        topic, seed, int(learner["user_id"]) if learner.get("user_id") else None
    )
    if len(tasks) < QUEST_LENGTH:
        raise QuestError(500, "no_tasks", "Не удалось собрать задания квеста")

    state = _new_state()
    run_id = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:20]
    execute(
        """INSERT INTO quest_runs
           (run_key, learner_id, quest_slug, topic_slug, tasks_json, state_json, total)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            learner_id,
            slug,
            slug,
            json.dumps(tasks, ensure_ascii=False),
            json.dumps(state, ensure_ascii=False),
            len(tasks),
        ),
    )
    row = _load_run(learner_id, run_id)
    payload = _run_payload(row, topic, tasks, state)
    payload["quest"]["book"] = _book_for(topic, books)
    return payload


def get_run(learner: dict, run_id: str) -> dict[str, Any]:
    ensure_tables()
    learner = dict(learner)
    row = _load_run(int(learner["id"]), run_id)
    if row.get("status") == "abandoned":
        raise QuestError(409, "run_abandoned", "Эта попытка закрыта. Начните квест заново.")
    topic, _, books = _find_topic(learner, row["quest_slug"])
    tasks, state = _parse(row)
    payload = _run_payload(row, topic, tasks, state)
    payload["quest"]["book"] = _book_for(topic, books)
    if row.get("status") == "completed":
        payload["result"] = _result_payload(row, tasks, state)
    return payload


def check_station(learner: dict, run_id: str, station: int,
                  answer: Any) -> dict[str, Any]:
    ensure_tables()
    learner = dict(learner)
    learner_id = int(learner["id"])
    row = _load_run(learner_id, run_id)
    if row.get("status") != "active":
        raise QuestError(409, "run_finished", "Этот квест уже завершён")

    tasks, state = _parse(row)
    if not isinstance(station, int) or not 0 <= station < len(tasks):
        raise QuestError(400, "bad_station", "Неизвестная станция")

    status = state["stations"][station]
    if status.get("done"):
        raise QuestError(409, "already_answered", "Эта станция уже пройдена")

    task = tasks[station]
    correct, expected = check_answer(answer, task)
    status["attempts"] = int(status.get("attempts") or 0) + 1
    gain_xp = gain_coins = 0
    hint = None

    if correct:
        status["done"] = True
        status["correct"] = True
        state["correct"] = int(state.get("correct") or 0) + 1
        gain_xp, gain_coins = progress_service.reward_amounts(learner_id, "practice")
        state["xp"] = int(state.get("xp") or 0) + gain_xp
        state["coins"] = int(state.get("coins") or 0) + gain_coins
        progress_service.record_attempt(
            learner_id,
            row["topic_slug"],
            task.get("method"),
            task.get("generator"),
            True,
            str(answer),
            expected,
            0,
            0,
            mode="quest",
        )
    else:
        if status["attempts"] >= 2:
            status["done"] = True
            status["correct"] = False
            progress_service.record_attempt(
                learner_id,
                row["topic_slug"],
                task.get("method"),
                task.get("generator"),
                False,
                str(answer),
                expected,
                0,
                0,
                mode="quest",
            )
        else:
            hints = task.get("hints") or []
            hint = hints[0] if hints else None

    _save(row, state)
    all_done = all(item.get("done") for item in state["stations"][:len(tasks)])

    return {
        "correct": correct,
        "station": station,
        "done": bool(status.get("done")),
        "correct_total": int(state.get("correct") or 0),
        "answered_total": sum(1 for item in state["stations"][:len(tasks)] if item.get("done")),
        "attempts": int(status["attempts"]),
        "attempts_left": max(0, 2 - int(status["attempts"])),
        "expected": expected_display(task) if status.get("done") and not correct else None,
        "hint": hint,
        "xp": gain_xp,
        "coins": gain_coins,
        "total": len(tasks),
        "all_done": all_done,
    }


def _result_payload(row: dict, tasks: list[dict], state: dict) -> dict[str, Any]:
    total = len(tasks)
    correct = int(state.get("correct") or 0)
    stars = progress_service.stars_for(correct, total)
    return {
        "correct": correct,
        "total": total,
        "stars": stars,
        "xp": int(state.get("xp") or 0),
        "coins": int(state.get("coins") or 0),
        "bonus_xp": int(state.get("bonus_xp") or 0),
        "bonus_coins": int(state.get("bonus_coins") or 0),
        "elapsed_ms": max(0, int(time.time() * 1000) - int(state.get("started_ms") or 0)),
    }


def finish_run(learner: dict, run_id: str) -> dict[str, Any]:
    ensure_tables()
    learner = dict(learner)
    learner_id = int(learner["id"])
    row = _load_run(learner_id, run_id)
    tasks, state = _parse(row)
    topic, _, _ = _find_topic(learner, row["quest_slug"])

    if row.get("status") == "completed":
        result = _result_payload(row, tasks, state)
        result["already_completed"] = True
        result["quest"] = {
            "slug": topic["slug"],
            "title": topic["title"],
            "icon": topic.get("icon") or "⭐",
        }
        return result

    total = len(tasks)
    if not all(item.get("done") for item in state["stations"][:total]):
        raise QuestError(409, "not_finished", "Сначала пройдите все станции")

    correct = int(state.get("correct") or 0)
    stars = progress_service.apply_round_result(learner_id, topic["slug"], correct, total)

    previous_row = query_one(
        "SELECT * FROM quest_progress WHERE learner_id = ? AND quest_slug = ?",
        (learner_id, topic["slug"]),
    )
    previous = dict(previous_row) if previous_row else None
    first_time = not previous or not int(previous.get("completed") or 0)

    bonus_xp = (20 + 5 * correct) if first_time else 0
    bonus_coins = (10 + 2 * correct) if first_time else 0
    state["bonus_xp"] = bonus_xp
    state["bonus_coins"] = bonus_coins

    if bonus_xp or bonus_coins:
        execute(
            "UPDATE learners SET xp = xp + ?, coins = coins + ? WHERE id = ?",
            (bonus_xp, bonus_coins, learner_id),
        )
        progress_service.touch_day(learner_id)

    result = _result_payload(row, tasks, state)
    best_stars = max(stars, int(previous.get("best_stars") or 0) if previous else 0)
    best_correct = max(correct, int(previous.get("best_correct") or 0) if previous else 0)
    best_xp = max(int(result["xp"]) + bonus_xp,
                  int(previous.get("best_xp") or 0) if previous else 0)
    elapsed = int(result["elapsed_ms"])
    best_time = int(previous.get("best_time_ms") or 0) if previous else 0
    if best_time <= 0 or (correct >= best_correct and elapsed < best_time):
        best_time = elapsed

    if previous:
        execute(
            """UPDATE quest_progress
                  SET attempts = attempts + 1, completed = 1, best_correct = ?,
                      best_stars = ?, best_xp = ?, best_time_ms = ?,
                      updated_at = datetime('now')
                WHERE learner_id = ? AND quest_slug = ?""",
            (best_correct, best_stars, best_xp, best_time,
             learner_id, topic["slug"]),
        )
    else:
        execute(
            """INSERT INTO quest_progress
               (learner_id, quest_slug, topic_slug, attempts, completed,
                best_correct, best_stars, best_xp, best_time_ms)
               VALUES (?, ?, ?, 1, 1, ?, ?, ?, ?)""",
            (learner_id, topic["slug"], topic["slug"], best_correct,
             best_stars, best_xp, best_time),
        )

    execute(
        """UPDATE quest_runs
              SET status = 'completed', finished_at = datetime('now'),
                  xp = ?, coins = ?
            WHERE run_key = ?""",
        (int(state.get("xp") or 0) + bonus_xp,
         int(state.get("coins") or 0) + bonus_coins, run_id),
    )

    result.update(
        {
            "already_completed": False,
            "first_time": first_time,
            "stars": best_stars,
            "quest": {
                "slug": topic["slug"],
                "title": topic["title"],
                "icon": topic.get("icon") or "⭐",
            },
        }
    )
    return result
