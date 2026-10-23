"""Задания для тем-чтения: cloze по тексту пособия и вопросы по теме.

Генерация полностью офлайн. Если у PDF есть текстовый слой, задания
составляются по предложениям из указанных страниц. Для сканов остаются
вопросы по теме, предмету и страницам пособия.
"""
from __future__ import annotations

import json
import random
import re
from functools import lru_cache
from typing import Any

from content.generators.base import shuffle_options, task
from database import execute, query_all
from services import pdf_text, textbooks

_STOPWORDS = {
    "это", "этот", "эта", "эти", "как", "что", "чтобы", "когда", "тогда",
    "где", "здесь", "там", "его", "её", "их", "они", "она", "оно", "мы", "вы",
    "для", "из", "или", "но", "не", "на", "по", "с", "со", "к", "ко", "у",
    "в", "во", "за", "от", "до", "при", "про", "над", "под", "без", "через",
    "the", "and", "that", "this", "with", "from", "have", "has", "are", "was",
    "were", "you", "your", "they", "their", "there", "what", "when", "where",
    "which", "will", "would", "can", "could", "should", "about", "into",
    "і", "ў", "на", "па", "з", "у", "што", "як", "гэта", "яны", "яна", "яно",
}

_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁёІіЎў'’-]{4,}")
_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁёІіЎў'’-]+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")
_BOILERPLATE = re.compile(
    r"правообладатель|национальный институт образования|вышэйшая школа|"
    r"isbn|удк|ббк|все права|©|https?://|www\.",
    re.IGNORECASE,
)
_EDITORIAL_WORDS = {
    "правообладатель", "национальный", "институт", "образования",
    "вышэйшая", "isbn", "удк", "ббк",
}


@lru_cache(maxsize=512)
def _pdf_page_text(path: str, page: int) -> str:
    """Текст одной страницы PDF (нумерация в файле, с единицы)."""
    try:
        return pdf_text.page_text(path, int(page))
    except Exception:  # noqa: BLE001 - повреждённый PDF не должен ронять создание работы
        return ""


def topic_pages(topic: Any, max_chars: int = 20000) -> list[tuple[int | None, str]]:
    """Страницы пособия для темы: [(номер страницы, текст), …].

    Номер страницы совпадает с тем, что открывается по ссылке из темы,
    поэтому подсказка «открой страницу N» всегда ведёт к нужному месту.
    """
    cached = topic["content_json"] if "content_json" in topic.keys() else None
    if cached:
        try:
            data = json.loads(cached)
            if isinstance(data, list) and data:
                return [
                    (int(item[0]) if item[0] else None, str(item[1]))
                    for item in data
                    if isinstance(item, (list, tuple)) and len(item) == 2
                ]
        except (ValueError, TypeError, IndexError):
            pass
    pages: list[tuple[int | None, str]] = []
    total = 0
    try:
        books = textbooks.textbooks_for_topic(
            topic["slug"],
            subject_id=topic["subject_id"],
            grade=topic["grade"],
        )
    except Exception:  # noqa: BLE001
        books = []
    for book in books[:3]:
        path = textbooks.file_path(book)
        start = int(book["page"] or 1)
        end = min(int(book["page_end"] or start), start + 9)
        for page in range(start, end + 1):
            text = _pdf_page_text(path, page)
            if not text:
                continue
            pages.append((page, text))
            total += len(text)
            if total >= max_chars:
                break
        if total >= max_chars:
            break
    if not pages:
        description = str(topic["description"] or "").strip()
        if description:
            pages.append((None, description))
    elif any(page is not None for page, _ in pages):
        # кэшируем извлечённый текст, чтобы тест открывался мгновенно
        execute(
            "UPDATE topics SET content_json = ? WHERE slug = ?",
            (
                json.dumps([[page, text] for page, text in pages], ensure_ascii=False),
                topic["slug"],
            ),
        )
    return pages


def _script(word: str) -> str:
    if re.search(r"[А-Яа-яЁёІіЎў]", word):
        return "cyr"
    if re.search(r"[A-Za-z]", word):
        return "lat"
    return ""


def _sentences(text: str, script: str = "") -> list[str]:
    text = re.sub(r"\s+", " ", text or "")
    result = []
    for sentence in _SENTENCE_SPLIT.split(text):
        sentence = sentence.strip(" \t\n\r—–-")
        if not (35 <= len(sentence) <= 300):
            continue
        if _BOILERPLATE.search(sentence):
            continue
        if sentence.count("(") != sentence.count(")"):
            continue
        tokens = _TOKEN_RE.findall(sentence)
        if len(tokens) < 6:
            continue
        # отсекаем перечни имён, заголовки и обрывки без строчных слов
        if sum(1 for token in tokens if token[:1].islower()) < 2:
            continue
        if len(re.findall(r"\d", sentence)) > 8:
            continue
        if script:
            cyr = sum(1 for token in tokens if _script(token) == "cyr")
            lat = sum(1 for token in tokens if _script(token) == "lat")
            if script == "lat" and (lat < 4 or lat < cyr):
                continue
            if script == "cyr" and (cyr < 4 or cyr < lat):
                continue
        result.append(sentence)
    return result


def _words(text: str) -> list[str]:
    return [word for word in _WORD_RE.findall(text or "")
            if word.casefold() not in _STOPWORDS
            and word.casefold() not in _EDITORIAL_WORDS
            and len(word) <= 16]


def _cloze_questions(
    pages: list[tuple[int | None, str]], limit: int, script: str = ""
) -> list[dict[str, Any]]:
    sentences = [
        (page, sentence)
        for page, text in pages
        for sentence in _sentences(text, script)
    ]
    if not sentences:
        return []
    random.shuffle(sentences)
    available_words = list(dict.fromkeys(
        _words("\n".join(text for _, text in pages))
    ))
    asked: set[str] = set()
    questions: list[dict[str, Any]] = []
    for page, sentence in sentences:
        if len(questions) >= limit:
            break
        candidates = [
            word for word in _words(sentence)
            if word.casefold() not in asked and 4 <= len(word) <= 15
        ]
        if not candidates:
            continue
        answer = ""
        chosen: list[str] = []
        for candidate in sorted(candidates, key=len, reverse=True):
            distractors = [
                word for word in available_words
                if word.casefold() != candidate.casefold()
                and word.casefold() not in candidate.casefold()
                and candidate.casefold() not in word.casefold()
                and _script(word) == _script(candidate)
                and abs(len(word) - len(candidate)) <= 5
            ]
            distractors = list(dict.fromkeys(distractors))
            if len(distractors) >= 3:
                answer = candidate
                chosen = random.sample(distractors, 3)
                break
        if not answer:
            continue
        asked.add(answer.casefold())
        shown = re.sub(
            rf"(?<!\w){re.escape(answer)}(?!\w)", "_____", sentence, count=1
        )
        if len(shown) > 260:
            position = shown.find("_____")
            left = max(0, position - 110)
            shown = ("…" if left else "") + shown[left:position + 120] + "…"
        where = f" (с. {page})" if page else ""
        questions.append(task(
            f"Прочитай в пособии{where} и выбери пропущенное слово: «{shown}»",
            answer,
            answer_type="choice",
            choices=shuffle_options([answer, *chosen]),
            solution=f"В тексте пособия: «{sentence}»",
            hints=[f"Открой пособие на странице {page}" if page else "Открой тему в пособии"],
            difficulty=1,
        ))
    return questions


def _subject_question(topic: Any) -> dict[str, Any] | None:
    rows = query_all("SELECT name FROM subjects WHERE is_active = 1 ORDER BY order_index, id")
    names = [row["name"] for row in rows]
    correct = topic["subject_name"] if "subject_name" in topic.keys() else ""
    if not correct or correct not in names or len(names) < 2:
        return None
    distractors = [name for name in names if name != correct]
    chosen = random.sample(distractors, min(3, len(distractors)))
    return task(
        f"К какому предмету относится тема «{topic['title']}»?",
        correct,
        answer_type="choice",
        choices=shuffle_options([correct, *chosen]),
        solution=f"Тема «{topic['title']}» — предмет «{correct}».",
        difficulty=1,
    )


def _description_question(topic: Any) -> dict[str, Any] | None:
    description = str(topic["description"] or "").strip()
    if len(description) < 20:
        return None
    rows = query_all(
        """SELECT title FROM topics
            WHERE subject_id = ? AND grade = ? AND slug <> ?
              AND COALESCE(description, '') <> ''""",
        (topic["subject_id"], topic["grade"], topic["slug"]),
    )
    others = [row["title"] for row in rows]
    if len(others) < 2:
        return None
    chosen = random.sample(others, min(3, len(others)))
    return task(
        f"Какая тема изучает: «{description[:180]}»?",
        topic["title"],
        answer_type="choice",
        choices=shuffle_options([topic["title"], *chosen]),
        solution=f"Это тема «{topic['title']}».",
        difficulty=1,
    )


def _page_question(topic: Any, books: list[Any]) -> dict[str, Any] | None:
    if not books:
        return None
    book = books[0]
    page = int(book["page"] or 1)
    total = int(book["pages"] or 2000)
    values = {page}
    attempts = 0
    while len(values) < 4 and attempts < 40:
        attempts += 1
        candidate = max(1, min(total, page + random.choice([-8, -5, -3, 3, 5, 8, 12])))
        values.add(candidate)
    if len(values) < 2:
        return None
    choices = [str(value) for value in sorted(values)]
    return task(
        f"На какой странице пособия «{book['title']}» начинается тема "
        f"«{topic['title']}»?",
        str(page),
        answer_type="choice",
        choices=choices,
        solution=f"Тема начинается на странице {page}.",
        hints=["Открой оглавление или карточку темы"],
        difficulty=1,
    )


def build_questions(topic: Any, count: int = 5) -> list[dict[str, Any]]:
    """Сгенерировать до `count` заданий по теме-чтению."""
    if not topic or count <= 0:
        return []
    books: list[Any] = []
    try:
        books = textbooks.textbooks_for_topic(
            topic["slug"],
            subject_id=topic["subject_id"],
            grade=topic["grade"],
        )
    except Exception:  # noqa: BLE001
        pass
    subject_slug = topic["subject_slug"] if "subject_slug" in topic.keys() else ""
    script = "lat" if subject_slug in {"english", "angl"} else "cyr"
    pool: list[dict[str, Any]] = []
    pool.extend(_cloze_questions(topic_pages(topic), count * 2, script))
    for extra in (
        _description_question(topic),
        _page_question(topic, books),
        _subject_question(topic),
    ):
        if extra:
            pool.append(extra)
    random.shuffle(pool)
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in pool:
        key = item["question"]
        if key in seen:
            continue
        seen.add(key)
        item["generator"] = "reading"
        item["topic_slug"] = topic["slug"]
        item["points"] = 1
        result.append(item)
        if len(result) >= count:
            break
    return result
