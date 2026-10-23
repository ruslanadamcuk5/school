"""Облачный ИИ: настройки подключения, объяснения тем и помощник по приложению.

Все обращения к модели выполняются **на сервере** по OpenAI-совместимому
протоколу (`POST {base_url}/chat/completions`) — браузер не ходит во внешние
сервисы. По умолчанию ИИ **выключен**: пока администратор не включит его и не
укажет ключ, приложение работает как раньше и не делает сетевых запросов.
"""
from __future__ import annotations

import html
import json
import re
import sqlite3
import urllib.error
import urllib.request
from typing import Any, Iterable

from config import Config
from database import execute, query_all, query_one

USER_AGENT = "edu-math-ai/1.0 (school educational app)"
MAX_QUESTION_CHARS = 2000
MAX_HISTORY_ITEMS = 6

# ------------------------------------------------------------------ провайдеры
# Все провайдеры ниже совместимы с OpenAI Chat Completions — меняются только
# адрес и названия моделей. По умолчанию выбран OpenRouter: один ключ даёт
# доступ к десяткам моделей разных компаний.
PROVIDERS: tuple[dict[str, Any], ...] = (
    {
        "id": "openrouter",
        "name": "OpenRouter (рекомендуется)",
        "base_url": "https://openrouter.ai/api/v1",
        "keys_url": "https://openrouter.ai/keys",
        "models": (
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "anthropic/claude-3.5-sonnet",
            "google/gemini-2.0-flash-001",
            "meta-llama/llama-3.3-70b-instruct",
            "deepseek/deepseek-chat",
        ),
        "note": "Один ключ — модели OpenAI, Anthropic, Google, Meta, DeepSeek и других.",
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "keys_url": "https://platform.openai.com/api-keys",
        "models": ("gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"),
        "note": "Ключ на platform.openai.com.",
    },
    {
        "id": "groq",
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "keys_url": "https://console.groq.com/keys",
        "models": ("llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"),
        "note": "Очень быстрые ответы, щедрый бесплатный лимит.",
    },
    {
        "id": "mistral",
        "name": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "keys_url": "https://console.mistral.ai/api-keys",
        "models": ("mistral-small-latest", "mistral-large-latest", "open-mistral-nemo"),
        "note": "Европейский провайдер, есть бесплатный тариф.",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "keys_url": "https://platform.deepseek.com/api_keys",
        "models": ("deepseek-chat", "deepseek-reasoner"),
        "note": "Недорогие модели с хорошим русским языком.",
    },
    {
        "id": "gemini",
        "name": "Google Gemini (OpenAI-совместимый)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "keys_url": "https://aistudio.google.com/app/apikey",
        "models": ("gemini-2.0-flash", "gemini-1.5-flash"),
        "note": "Ключ из Google AI Studio.",
    },
    {
        "id": "ollama",
        "name": "Ollama (локально на сервере)",
        "base_url": "http://localhost:11434/v1",
        "keys_url": "https://ollama.com",
        "models": ("llama3.1", "qwen2.5"),
        "note": "Полностью локально: интернет и ключ не нужны.",
    },
    {
        "id": "custom",
        "name": "Другая OpenAI-совместимая",
        "base_url": "",
        "keys_url": "",
        "models": (),
        "note": "Укажите адрес и модель вручную.",
    },
)

_PROVIDER_MAP = {item["id"]: item for item in PROVIDERS}

DEFAULT_PROVIDER = "openrouter"


def provider_defaults(provider_id: str) -> dict[str, Any]:
    return _PROVIDER_MAP.get(provider_id, _PROVIDER_MAP[DEFAULT_PROVIDER])


def provider_name(provider_id: str) -> str:
    return provider_defaults(provider_id)["name"]


# ------------------------------------------------------------------ настройки
def default_settings() -> dict[str, Any]:
    provider = provider_defaults(DEFAULT_PROVIDER)
    return {
        "enabled": 0,
        "provider": DEFAULT_PROVIDER,
        "base_url": provider["base_url"],
        "api_key": "",
        "model": provider["models"][0] if provider["models"] else "",
        "temperature": 0.3,
        "max_tokens": 900,
        "system_note": "",
    }


def get_settings() -> dict[str, Any]:
    """Текущие настройки ИИ (создаёт строку по умолчанию при необходимости)."""
    try:
        row = query_one("SELECT * FROM ai_settings WHERE id = 1")
    except sqlite3.Error:
        row = None
    if row is None:
        execute("INSERT OR IGNORE INTO ai_settings (id) VALUES (1)")
        row = query_one("SELECT * FROM ai_settings WHERE id = 1")
    if row is None:  # pragma: no cover - на всякий случай
        return default_settings()
    return dict(row)


def save_settings(data: dict[str, Any], *, keep_key: bool = False) -> dict[str, Any]:
    """Сохранить настройки. Пустой ключ (keep_key=False) очищает его."""
    current = get_settings()
    provider = str(data.get("provider") or current["provider"] or DEFAULT_PROVIDER)
    if provider not in _PROVIDER_MAP:
        provider = DEFAULT_PROVIDER
    base_url = (data.get("base_url") or "").strip()
    if not base_url:
        base_url = provider_defaults(provider)["base_url"]
    model = (data.get("model") or "").strip() or current["model"]

    if keep_key:
        api_key = current["api_key"] or ""
    else:
        api_key = (data.get("api_key") or "").strip()

    try:
        temperature = float(data.get("temperature", current["temperature"]))
    except (TypeError, ValueError):
        temperature = float(current["temperature"])
    temperature = min(1.5, max(0.0, temperature))

    try:
        max_tokens = int(data.get("max_tokens", current["max_tokens"]))
    except (TypeError, ValueError):
        max_tokens = int(current["max_tokens"])
    max_tokens = min(4000, max(100, max_tokens))

    execute(
        """UPDATE ai_settings
              SET enabled = ?, provider = ?, base_url = ?, api_key = ?,
                  model = ?, temperature = ?, max_tokens = ?, system_note = ?,
                  updated_at = datetime('now')
            WHERE id = 1""",
        (
            1 if data.get("enabled") else 0,
            provider,
            base_url,
            api_key or None,
            model,
            temperature,
            max_tokens,
            (data.get("system_note") or "").strip()[:2000] or None,
        ),
    )
    return get_settings()


def is_enabled() -> bool:
    """Готов ли ИИ к работе: включён, есть ключ, адрес и модель."""
    try:
        settings = get_settings()
    except sqlite3.Error:  # pragma: no cover - БД недоступна
        return False
    return bool(
        settings.get("enabled")
        and (settings.get("api_key") or "").strip()
        and (settings.get("base_url") or "").strip()
        and (settings.get("model") or "").strip()
    )


def status() -> dict[str, Any]:
    """Краткое состояние ИИ для шаблонов (без раскрытия ключа)."""
    try:
        settings = get_settings()
    except sqlite3.Error:  # pragma: no cover
        settings = default_settings()
    return {
        "enabled": is_enabled(),
        "provider": settings.get("provider") or DEFAULT_PROVIDER,
        "provider_name": provider_name(settings.get("provider") or DEFAULT_PROVIDER),
        "model": settings.get("model") or "",
        "base_url": settings.get("base_url") or "",
        "has_key": bool((settings.get("api_key") or "").strip()),
    }


# ------------------------------------------------------------------ запрос к модели
def _app_referer() -> str:
    try:
        from flask import request

        return request.host_url.rstrip("/")
    except Exception:  # pragma: no cover - вне контекста запроса
        return ""


def chat(
    messages: Iterable[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: int | None = None,
) -> tuple[str, str | None]:
    """Отправить сообщения модели. Возвращает (текст, ошибка)."""
    settings = get_settings()
    if not is_enabled():
        return "", "Модель ИИ не настроена"
    base_url = (settings["base_url"] or "").strip().rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": settings["model"],
        "messages": list(messages),
        "temperature": settings["temperature"] if temperature is None else temperature,
        "max_tokens": settings["max_tokens"] if max_tokens is None else max_tokens,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings['api_key']}",
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if settings.get("provider") == "openrouter":
        headers["HTTP-Referer"] = _app_referer() or "http://localhost"
        # Значение HTTP-заголовка должно быть в latin-1, поэтому только ASCII.
        headers["X-Title"] = "Uchus (edu-math)"

    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(
            request, timeout=timeout or Config.AI_TIMEOUT
        ) as response:
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "replace")[:500]
        except Exception:  # pragma: no cover
            detail = ""
        return "", f"HTTP {exc.code}: {detail or exc.reason}"
    except urllib.error.URLError as exc:
        return "", f"нет связи с сервисом ({exc.reason})"
    except (TimeoutError, OSError) as exc:
        return "", f"сервис не ответил: {exc}"
    except Exception as exc:  # pragma: no cover - неожиданная ошибка сети/кодировки
        return "", f"ошибка запроса к сервису: {exc}"

    try:
        data = json.loads(body)
    except ValueError:
        return "", "некорректный ответ сервиса"

    if isinstance(data, dict) and data.get("error"):
        error = data["error"]
        message = error.get("message") if isinstance(error, dict) else str(error)
        return "", f"ошибка сервиса: {message}"

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return "", "модель вернула пустой ответ"
    text = (content or "").strip()
    if not text:
        return "", "модель вернула пустой ответ"
    return text, None


def test_connection() -> tuple[bool, str]:
    """Проверить связь с моделью коротким запросом."""
    text, error = chat(
        [
            {"role": "system", "content": "Отвечай очень кратко."},
            {"role": "user", "content": "Ответь одним словом: работает?"},
        ],
        temperature=0.0,
        max_tokens=32,
        timeout=Config.AI_TIMEOUT,
    )
    if error:
        return False, error
    return True, text[:200]


def log_request(user_id: int | None, kind: str, ok: bool, detail: str = "") -> None:
    try:
        settings = get_settings()
        execute(
            """INSERT INTO ai_requests (user_id, kind, model, ok, detail)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, kind, settings.get("model"), 1 if ok else 0, (detail or "")[:400]),
        )
    except sqlite3.Error:  # pragma: no cover - журнал не должен ломать запрос
        pass


# ------------------------------------------------------------------ объяснение темы
_EXPLAIN_SYSTEM = (
    "Ты — опытный школьный учитель из Беларуси. Объясняешь темы программы "
    "простым и дружелюбным языком, без воды и без приветствий. Пиши по-русски. "
    "Оформляй ответ заголовками `##`, списками через «- » и выделяй главное "
    "**жирным**. Обязательно приводи примеры и разбирай их по шагам."
)

_EXPLAIN_TEMPLATE = """Тема: {title}
Предмет: {subject}
Класс: {grade}
Кратко из учебника: {description}{pages}{extra}

Объясни тему ученику {grade} класса в таком порядке:
## Что это простыми словами
## Главное правило
## Разбор на примерах
(2–3 примера, каждый — по шагам)
## Частые ошибки
## Как запомнить
## Проверь себя
(3 вопроса с ответами)
Держись темы, не добавляй лишних разделов."""


def _topic_prompt(info: dict[str, Any]) -> str:
    pages = ""
    if info.get("page_start"):
        pages = f"\nСтраницы пособия: {info['page_start']}"
        if info.get("page_end") and info["page_end"] != info["page_start"]:
            pages += f"–{info['page_end']}"
    return _EXPLAIN_TEMPLATE.format(
        title=info.get("title") or info.get("slug"),
        subject=info.get("subject") or "школьный предмет",
        grade=info.get("grade") or "",
        description=info.get("description") or "нет описания",
        pages=pages,
        extra=f"\nДополнительно: {info['extra']}" if info.get("extra") else "",
    )


def cached_explanation(slug: str) -> dict[str, Any] | None:
    try:
        row = query_one("SELECT * FROM ai_explanations WHERE topic_slug = ?", (slug,))
    except sqlite3.Error:  # pragma: no cover
        return None
    return dict(row) if row else None


def _save_explanation(slug: str, grade: Any, model: str, content: str) -> None:
    execute(
        """INSERT INTO ai_explanations (topic_slug, grade, model, content)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(topic_slug) DO UPDATE SET
               content = excluded.content,
               model = excluded.model,
               grade = excluded.grade,
               created_at = datetime('now')""",
        (slug, grade, model, content),
    )


def explain_topic(
    info: dict[str, Any], *, force: bool = False, user_id: int | None = None
) -> tuple[str, str | None]:
    """Объяснение темы с кэшированием. Возвращает (текст, ошибка)."""
    slug = info["slug"]
    if not force:
        cached = cached_explanation(slug)
        if cached and cached.get("content"):
            return cached["content"], None

    settings = get_settings()
    extra_note = (settings.get("system_note") or "").strip()
    system = _EXPLAIN_SYSTEM + (f"\nДополнительно: {extra_note}" if extra_note else "")
    text, error = chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": _topic_prompt(info)},
        ],
        temperature=0.4,
        max_tokens=max(600, int(settings.get("max_tokens") or 900)),
    )
    if error:
        log_request(user_id, "explain", False, f"{slug}: {error}")
        return "", error
    _save_explanation(slug, info.get("grade"), settings.get("model") or "", text)
    log_request(user_id, "explain", True, f"{slug}: {len(text)} символов")
    return text, None


# ------------------------------------------------------------------ помощник
_GUIDE_COMMON = """Приложение «Учусь» — школьная платформа (1–11 классы): обучение по темам,
тренировки с объяснениями, тесты, работы и библиотека.

Как учиться (ученик):
- «🗺 Карта тем» — все темы класса. Открой тему и нажми «▶ Тренироваться».
- Кнопка «Объяснить иначе» показывает тему другим способом, если непонятно.
- «📝 Тест по теме» — проверка знаний, «🐉 Испытание-босс» — сложное задание.
- Опыт, монеты и звёзды растут за верные ответы (в 1–4 классах игра, в 5–11 — строгий режим).
- Тексты и задания по предметам читаются на странице темы: там же кнопка пособия (PDF).

Разделы ученика:
- «📝 Мои работы» — задания учителя и родителя с результатами.
- «📖 Учебники» — загруженные пособия по классу и предметам.
- «📚 Библиотека» — книги класса и рекомендации учителя; отметка «прочитано».
- «🗓 Расписание», «🏅 Значки», «🤖 ИИ» — объяснение темы и помощник.

Разделы учителя:
- «👦 Ученики» — классы и успеваемость, добавление ученика по логину.
- «📚 Курсы» — включение тем и их порядок.
- «📝 Работы» — создание проверочных, контрольных, срезов по любым предметам.
- «📖 Пособия» — загруженные PDF своего класса.
- «📚 Библиотека» — загрузка книг, доступ классам и рекомендации тем.
- «🤖 ИИ» (у администратора) — подключение облачной модели.

Разделы родителя:
- «👨‍👩‍👧 Мои дети» — статистика ребёнка, значки, экспорт CSV.
- Назначение заданий ребёнку по любому предмету с проверкой результатов.
- «📚 Библиотека» — книги и рекомендации ребёнка.

Помощь по ИИ:
- «🤖 Объяснить с ИИ» есть на странице каждой темы: подробное объяснение с примерами.
- Кнопка «🤖 Помощник» внизу справа отвечает на вопросы о приложении."""


def _assistant_system(role: str, name: str, page: str) -> str:
    role_ru = {
        "admin": "администратор",
        "teacher": "учитель",
        "student": "ученик",
        "parent": "родитель",
    }.get(role or "", "гость")
    return (
        "Ты — встроенный помощник школьной платформы «Учусь». Помогаешь "
        "пользоваться приложением: подсказываешь, где что находится и как "
        "выполнить действие. Отвечай кратко (до 6 предложений), дружелюбно, "
        "по-русски, простыми словами. Опирайся только на список возможностей "
        "ниже и не придумывай функций, которых нет. Если вопрос не о приложении "
        "или об учёбе, вежливо верни разговор к работе с «Учусь».\n\n"
        f"Пользователь: {role_ru} {name or ''}. Текущая страница: {page or '—'}.\n\n"
        f"Возможности приложения:\n{_GUIDE_COMMON}"
    )


def assistant_reply(
    question: str,
    *,
    role: str = "",
    name: str = "",
    page: str = "",
    history: list[dict[str, str]] | None = None,
    user_id: int | None = None,
) -> tuple[str, str | None]:
    question = (question or "").strip()[:MAX_QUESTION_CHARS]
    if not question:
        return "", "Пустой вопрос"
    messages = [{"role": "system", "content": _assistant_system(role, name, page)}]
    for item in (history or [])[-MAX_HISTORY_ITEMS:]:
        if not isinstance(item, dict):
            continue
        item_role = item.get("role")
        content = str(item.get("content") or "").strip()
        if item_role in ("user", "assistant") and content:
            messages.append({"role": item_role, "content": content[:1500]})
    messages.append({"role": "user", "content": question})

    text, error = chat(messages, temperature=0.3, max_tokens=700)
    if error:
        log_request(user_id, "assistant", False, error)
        return "", error
    log_request(user_id, "assistant", True, f"{len(text)} символов")
    return text, None


# ------------------------------------------------------------------ статистика + разметка
def clear_explanations() -> int:
    row = query_one("SELECT COUNT(*) AS c FROM ai_explanations")
    execute("DELETE FROM ai_explanations")
    return int(row["c"]) if row else 0


def stats() -> dict[str, Any]:
    total = query_one("SELECT COUNT(*) AS c FROM ai_requests")["c"]
    ok = query_one("SELECT COUNT(*) AS c FROM ai_requests WHERE ok = 1")["c"]
    explanations = query_one("SELECT COUNT(*) AS c FROM ai_explanations")["c"]
    last_error = query_one(
        """SELECT detail, created_at FROM ai_requests
            WHERE ok = 0 AND detail IS NOT NULL AND detail <> ''
            ORDER BY id DESC LIMIT 1"""
    )
    recent = query_all(
        """SELECT kind, ok, detail, created_at FROM ai_requests
            ORDER BY id DESC LIMIT 10"""
    )
    return {
        "total": total,
        "ok": ok,
        "failed": total - ok,
        "explanations": explanations,
        "last_error": dict(last_error) if last_error else None,
        "recent": [dict(row) for row in recent],
    }


def render_ai_text(text: str) -> str:
    """Безопасно превратить ответ модели в HTML (мини-markdown)."""
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    paragraph: list[str] = []
    list_mode: str | None = None

    def flush_paragraph() -> None:
        if paragraph:
            out.append("<p>" + " ".join(paragraph) + "</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_mode
        if list_mode:
            out.append(f"</{list_mode}>")
            list_mode = None

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            close_list()
            continue
        safe = html.escape(stripped)
        safe = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe)
        safe = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", safe)
        safe = re.sub(r"`([^`]+)`", r"<code>\1</code>", safe)

        heading = re.match(r"^(#{1,4})\s*(.+)$", safe)
        if heading:
            flush_paragraph()
            close_list()
            level = min(5, max(3, len(heading.group(1)) + 1))  # h3..h5
            out.append(f"<h{level}>{heading.group(2)}</h{level}>")
            continue

        bullet = re.match(r"^[-*•]\s+(.+)$", safe)
        if bullet:
            flush_paragraph()
            if list_mode != "ul":
                close_list()
                out.append("<ul>")
                list_mode = "ul"
            out.append(f"<li>{bullet.group(1)}</li>")
            continue

        numbered = re.match(r"^\d+[.)]\s+(.+)$", safe)
        if numbered:
            flush_paragraph()
            if list_mode != "ol":
                close_list()
                out.append("<ol>")
                list_mode = "ol"
            out.append(f"<li>{numbered.group(1)}</li>")
            continue

        close_list()
        paragraph.append(safe)

    flush_paragraph()
    close_list()
    return "\n".join(out) or "<p class='muted'>Модель вернула пустой ответ.</p>"
