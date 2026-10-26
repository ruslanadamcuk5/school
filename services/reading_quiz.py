"""Задания для тем-чтения: вопросы ИИ по теме и cloze по тексту пособия.

Основной источник вопросов — модель ИИ: она составляет проверочные вопросы
по выбранной теме (название, предмет, класс, описание и читаемый текст
пособия). Если ИИ не настроен, остаются офлайн-задания: пропущенное слово
по тексту страниц. Вопросы «на какой странице» и «к какому предмету»
больше не задаются — они проверяли оформление пособия, а не знания.
"""
from __future__ import annotations

import json
import random
import re
from functools import lru_cache
from typing import Any

from content.answer import normalize_text
from content.generators.base import shuffle_options, task
from database import execute, query_all
from services import ai_quiz, pdf_text, text_quality, textbooks

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


def _description_question(topic: Any) -> dict[str, Any] | None:
    """Запасной вопрос, если ИИ недоступен и текста пособия нет.

    Сопоставление описания и темы — единственное, что можно составить
    полностью офлайн, не выдумывая фактов.
    """
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
    if not others:
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


def _excerpt(pages: list[tuple[int | None, str]], limit: int = 6000) -> str:
    """Фрагмент читаемого текста пособия для модели ИИ."""
    parts: list[str] = []
    total = 0
    for _, text in pages:
        text = re.sub(r"\s+", " ", text or "").strip()
        if not text:
            continue
        parts.append(text)
        total += len(text)
        if total >= limit:
            break
    return "\n".join(parts)[:limit]


def build_questions(
    topic: Any, count: int = 5, *, user_id: int | None = None
) -> list[dict[str, Any]]:
    """Сгенерировать до `count` заданий по теме.

    Сначала — вопросы по теме от ИИ (если он настроен), затем — пропущенные
    слова по читаемому тексту пособия. Битый текст сканов не используется.
    """
    if not topic or count <= 0:
        return []
    subject_slug = topic["subject_slug"] if "subject_slug" in topic.keys() else ""
    script = "lat" if subject_slug in {"english", "angl"} else "cyr"
    pages = topic_pages(topic)
    readable_pages = [
        (page, text) for page, text in pages
        if text_quality.readable(text, script)
    ]

    pool: list[dict[str, Any]] = []
    pool.extend(ai_quiz.questions(
        topic,
        count,
        text=_excerpt(readable_pages),
        script=script,
        user_id=user_id,
    ))
    if len(pool) < count and readable_pages:
        pool.extend(
            _cloze_questions(readable_pages, (count - len(pool)) * 2, script)
        )
    if not pool:
        fallback = _description_question(topic)
        if fallback:
            pool.append(fallback)

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in pool:
        key = normalize_text(item["question"])
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
