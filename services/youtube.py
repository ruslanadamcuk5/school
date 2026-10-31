"""YouTube: автоматический подбор обучающих видео к темам.

Интеграция работает через официальный **YouTube Data API v3**. Ключ
администратора хранится только в базе на сервере и никогда не попадает в
браузер или мобильное приложение.

Алгоритм:
1. Для темы строится поисковый запрос (по названию, предмету и классу).
2. ``search.list`` находит ролики, ``videos.list`` проверяет, что они
   публичные, доступны для встраивания и не заблокированы в регионе.
3. Подключённый ИИ (если он включён) уточняет запрос и выбирает самые
   подходящие ролики **только из реальной выдачи**. Выдуманные идентификаторы
   отбрасываются. Без ИИ работает прозрачная эвристика по названию, каналу,
   длительности и ключевым словам.
4. Результат кэшируется в базе, поэтому YouTube не опрашивается на каждый
   просмотр. Ручные ссылки администратора всегда показываются первыми и не
   удаляются при обновлении кэша.
"""
from __future__ import annotations

import html
import json
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from config import Config
from database import execute, query_all, query_one

USER_AGENT = "edu-math-youtube/1.0 (school educational app)"
API_ROOT = "https://www.googleapis.com/youtube/v3"
EMBED_ROOT = "https://www.youtube-nocookie.com/embed"
WATCH_ROOT = "https://www.youtube.com/watch"

DEFAULT_MAX_PER_TOPIC = 3
DEFAULT_CACHE_DAYS = 14
MAX_WARM_TOPICS = 5
MAX_MANUAL_PER_TOPIC = 10
ERROR_RETRY_MINUTES = 60
EMPTY_RETRY_DAYS = 3

DEFAULT_SETTINGS: dict[str, Any] = {
    "enabled": 0,
    "api_key": "",
    "region_code": "BY",
    "relevance_language": "ru",
    "max_per_topic": DEFAULT_MAX_PER_TOPIC,
    "min_duration": 60,
    "max_duration": 3600,
    "cache_days": DEFAULT_CACHE_DAYS,
    "ai_ranking": 1,
}

_STOP_WORDS = {
    "и", "в", "во", "на", "по", "с", "со", "для", "к", "ко", "из", "от",
    "до", "за", "о", "об", "the", "a", "an", "of", "to", "in", "for",
    "тема", "темы", "урок", "уроки", "класс", "класса", "школьный",
}

_NEGATIVE_WORDS = (
    "shorts", "#shorts", "прикол", "смешн", "мем", "играем", "летсплей",
    "let's play", "minecraft", "роблокс", "roblox", "челлендж", "влог",
    "реклама", "трейлер", "фильм", "сериал", "песня", "клип", "тикток",
    "tiktok", "обзор товаров", "распаковка", "ставка", "казино",
)

_POSITIVE_WORDS = (
    "объясн", "разбор", "правило", "как решать", "как найти", "изучаем",
    "просто о", "понятно", "школа", "урок", "учимся", "решаем",
)

_EDU_CHANNELS = (
    "инфоурок", "интернетурок", "interneturok", "foxford", "фоксфорд",
    "skyeng", "скулково", "умскул", "lecta", "лекта", "просвещение",
    "знайка", "академия", "education", "школа", "учитель", "репетитор",
)


# ------------------------------------------------------------------ настройки
def _defaults() -> dict[str, Any]:
    return dict(DEFAULT_SETTINGS)


def get_settings() -> dict[str, Any]:
    """Текущие настройки YouTube (строка создаётся при первом обращении)."""
    try:
        row = query_one("SELECT * FROM youtube_settings WHERE id = 1")
    except sqlite3.Error:
        row = None
    if row is None:
        try:
            execute("INSERT OR IGNORE INTO youtube_settings (id) VALUES (1)")
            row = query_one("SELECT * FROM youtube_settings WHERE id = 1")
        except sqlite3.Error:  # pragma: no cover - база ещё не готова
            return _defaults()
    return dict(row) if row else _defaults()


def save_settings(data: dict[str, Any], *, keep_key: bool = False) -> dict[str, Any]:
    """Сохранить настройки. Пустой ключ при keep_key=False удаляет его."""
    current = get_settings()

    region = str(data.get("region_code") or current.get("region_code") or "BY").strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", region):
        region = "BY"
    language = str(
        data.get("relevance_language") or current.get("relevance_language") or "ru"
    ).strip().lower()
    if not re.fullmatch(r"[a-z]{2}(?:-[a-z]{2})?", language):
        language = "ru"

    def _int(name: str, fallback: int, low: int, high: int) -> int:
        try:
            value = int(data.get(name, fallback))
        except (TypeError, ValueError):
            value = fallback
        return max(low, min(high, value))

    max_per_topic = _int("max_per_topic", int(current.get("max_per_topic") or 3), 1, 6)
    min_duration = _int("min_duration", int(current.get("min_duration") or 60), 30, 600)
    max_duration = _int("max_duration", int(current.get("max_duration") or 3600), 120, 7200)
    if max_duration <= min_duration:
        max_duration = max(min_duration + 120, 600)
    cache_days = _int("cache_days", int(current.get("cache_days") or 14), 1, 90)

    if keep_key:
        api_key = current.get("api_key") or ""
    else:
        api_key = (data.get("api_key") or "").strip()

    enabled = 1 if data.get("enabled") else 0
    ai_ranking = 1 if data.get("ai_ranking") else 0

    execute(
        """UPDATE youtube_settings
              SET enabled = ?, api_key = ?, region_code = ?,
                  relevance_language = ?, max_per_topic = ?, min_duration = ?,
                  max_duration = ?, cache_days = ?, ai_ranking = ?,
                  updated_at = datetime('now')
            WHERE id = 1""",
        (
            enabled, api_key or None, region, language, max_per_topic,
            min_duration, max_duration, cache_days, ai_ranking,
        ),
    )
    return get_settings()


def is_enabled() -> bool:
    """Готов ли YouTube к работе: включён и есть ключ API."""
    try:
        settings = get_settings()
    except sqlite3.Error:  # pragma: no cover
        return False
    return bool(
        settings.get("enabled")
        and (settings.get("api_key") or "").strip()
        and (settings.get("region_code") or "").strip()
    )


def status() -> dict[str, Any]:
    """Состояние интеграции без раскрытия ключа."""
    settings = get_settings()
    return {
        "enabled": is_enabled(),
        "configured": bool((settings.get("api_key") or "").strip()),
        "has_key": bool((settings.get("api_key") or "").strip()),
        "region_code": settings.get("region_code") or "BY",
        "relevance_language": settings.get("relevance_language") or "ru",
        "max_per_topic": int(settings.get("max_per_topic") or 3),
        "min_duration": int(settings.get("min_duration") or 60),
        "max_duration": int(settings.get("max_duration") or 3600),
        "cache_days": int(settings.get("cache_days") or 14),
        "ai_ranking": bool(settings.get("ai_ranking")),
        "updated_at": settings.get("updated_at"),
    }


def clear_cache() -> dict[str, int]:
    """Удалить автоматически подобранные видео и отметки кэша.

    Ручные ссылки администратора остаются: они не зависят от YouTube API.
    """
    videos = query_one(
        "SELECT COUNT(*) AS c FROM topic_videos WHERE source = 'auto'"
    )
    caches = query_one("SELECT COUNT(*) AS c FROM topic_video_cache")
    execute("DELETE FROM topic_videos WHERE source = 'auto'")
    execute("DELETE FROM topic_video_cache")
    return {
        "videos": int(videos["c"]) if videos else 0,
        "topics": int(caches["c"]) if caches else 0,
    }


# ------------------------------------------------------------------ утилиты
def parse_video_id(value: str) -> str:
    """Достать 11-символьный идентификатор из ссылки или строки."""
    raw = html.unescape((value or "").strip())
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", raw):
        return raw
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    try:
        parsed = urllib.parse.urlparse(raw)
    except ValueError:
        return ""
    host = (parsed.netloc or "").lower()
    host = host[4:] if host.startswith("www.") else host
    if host not in {
        "youtube.com", "m.youtube.com", "music.youtube.com",
        "youtu.be", "youtube-nocookie.com",
    }:
        return ""
    candidate = ""
    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
    elif parsed.path in ("/watch", "/watch/"):
        candidate = (urllib.parse.parse_qs(parsed.query).get("v") or [""])[0]
    else:
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in ("embed", "shorts", "live", "v"):
            candidate = parts[1]
    candidate = (candidate or "").strip()
    return candidate if re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate) else ""


def parse_duration(value: str) -> int:
    """ISO‑8601 ``PT1H2M3S`` → секунды."""
    match = re.fullmatch(
        r"P(?:\d+D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", (value or "").strip()
    )
    if not match:
        return 0
    hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def format_duration(seconds: int) -> str:
    seconds = max(0, int(seconds or 0))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def embed_url(video_id: str) -> str:
    return f"{EMBED_ROOT}/{video_id}?rel=0&modestbranding=1&playsinline=1"


def watch_url(video_id: str) -> str:
    return f"{WATCH_ROOT}?v={video_id}"


def _future(days: int = 0, minutes: int = 0) -> str:
    moment = datetime.now(timezone.utc) + timedelta(days=days, minutes=minutes)
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def _tokens(text: str) -> list[str]:
    return [
        token for token in re.findall(r"[a-zа-яё0-9]+", (text or "").lower())
        if len(token) >= 2 and token not in _STOP_WORDS
    ]


def _topic_tokens(info: dict[str, Any]) -> list[str]:
    tokens = _tokens(info.get("title") or "")
    # Для коротких названий («Дроби») одного слова мало: добавляем предмет.
    if len(tokens) < 2:
        tokens += [t for t in _tokens(info.get("subject") or "") if t not in tokens]
    return tokens[:8]


# ------------------------------------------------------------------ YouTube API
def _api(
    endpoint: str,
    params: dict[str, Any],
    *,
    settings: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    settings = settings or get_settings()
    key = (settings.get("api_key") or "").strip()
    if not key:
        return None, "Ключ YouTube API не задан"
    query = {k: v for k, v in params.items() if v not in (None, "")}
    query["key"] = key
    url = f"{API_ROOT}/{endpoint}?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        method="GET",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=getattr(Config, "YOUTUBE_TIMEOUT", 15)
        ) as response:
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8", "replace"))
        except Exception:  # pragma: no cover - некорректный ответ
            payload = {}
        reason = ""
        message = ""
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            message = str(error.get("message") or "")
            errors = error.get("errors")
            if isinstance(errors, list) and errors:
                reason = str((errors[0] or {}).get("reason") or "")
        hint = f" ({reason})" if reason else ""
        return None, f"YouTube API {exc.code}{hint}: {message or exc.reason}"
    except urllib.error.URLError as exc:
        return None, f"Нет связи с YouTube API: {exc.reason}"
    except (TimeoutError, OSError) as exc:
        return None, f"YouTube API не ответил: {exc}"
    except Exception as exc:  # pragma: no cover - неожиданная ошибка
        return None, f"Ошибка запроса к YouTube API: {exc}"

    try:
        data = json.loads(body)
    except ValueError:
        return None, "YouTube API вернул некорректный ответ"
    if not isinstance(data, dict):
        return None, "YouTube API вернул неожиданный ответ"
    if data.get("error"):
        error = data["error"]
        message = error.get("message") if isinstance(error, dict) else str(error)
        return None, f"YouTube API: {message}"
    return data, None


def test_connection() -> tuple[bool, str]:
    """Проверить ключ дешёвым запросом (1 unit, без поиска)."""
    if not is_enabled():
        return False, "Сначала включите YouTube и сохраните ключ API."
    data, error = _api("i18nLanguages", {"part": "snippet", "hl": "ru"})
    if error:
        return False, error
    languages = len((data or {}).get("items") or [])
    return True, f"YouTube API отвечает (языков в ответе: {languages})."


def _region_blocked(video: dict[str, Any], region: str) -> bool:
    details = video.get("contentDetails") or {}
    restriction = details.get("regionRestriction") or {}
    blocked = {str(item).upper() for item in (restriction.get("blocked") or [])}
    allowed = {str(item).upper() for item in (restriction.get("allowed") or [])}
    if region.upper() in blocked:
        return True
    if allowed and region.upper() not in allowed:
        return True
    return False


def _thumbnail(snippet: dict[str, Any]) -> str:
    thumbs = snippet.get("thumbnails") or {}
    for key in ("maxres", "standard", "high", "medium", "default"):
        item = thumbs.get(key)
        if isinstance(item, dict) and item.get("url"):
            return str(item["url"])
    return ""


def _normalize_video(item: dict[str, Any]) -> dict[str, Any]:
    snippet = item.get("snippet") or {}
    status = item.get("status") or {}
    details = item.get("contentDetails") or {}
    return {
        "video_id": str(item.get("id") or ""),
        "title": html.unescape(str(snippet.get("title") or "")).strip(),
        "channel": html.unescape(str(snippet.get("channelTitle") or "")).strip(),
        "description": html.unescape(str(snippet.get("description") or "")).strip(),
        "thumbnail": _thumbnail(snippet),
        "duration": parse_duration(str(details.get("duration") or "")),
        "embeddable": bool(status.get("embeddable")),
        "privacy": str(status.get("privacyStatus") or ""),
        "published_at": str(snippet.get("publishedAt") or ""),
        "region_blocked": False,
    }


def _fetch_details(
    video_ids: Iterable[str], *, settings: dict[str, Any] | None = None
) -> tuple[list[dict[str, Any]], str | None]:
    ids = list(dict.fromkeys(video_id for video_id in video_ids if video_id))[:50]
    if not ids:
        return [], None
    data, error = _api(
        "videos",
        {
            "part": "snippet,contentDetails,status",
            "id": ",".join(ids),
            "maxResults": len(ids),
        },
        settings=settings,
    )
    if error:
        return [], error
    result = []
    for item in (data or {}).get("items") or []:
        if isinstance(item, dict):
            result.append(_normalize_video(item))
    return result, None


def _search(
    query: str, *, settings: dict[str, Any] | None = None
) -> tuple[list[str], str | None]:
    settings = settings or get_settings()
    data, error = _api(
        "search",
        {
            "part": "snippet",
            "type": "video",
            "q": query,
            "maxResults": 10,
            "order": "relevance",
            "relevanceLanguage": settings.get("relevance_language") or "ru",
            "regionCode": settings.get("region_code") or "BY",
            "safeSearch": "strict",
            "videoDuration": "medium",
            "videoEmbeddable": "true",
            "videoSyndicated": "true",
        },
        settings=settings,
    )
    if error:
        return [], error
    ids = []
    for item in (data or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        identifier = item.get("id") or {}
        video_id = identifier.get("videoId") if isinstance(identifier, dict) else None
        if video_id:
            ids.append(str(video_id))
    return list(dict.fromkeys(ids)), None


# ------------------------------------------------------------------ ИИ
def _ai_available(settings: dict[str, Any]) -> bool:
    if not settings.get("ai_ranking"):
        return False
    try:
        from services import ai as ai_service

        return ai_service.is_enabled()
    except Exception:  # pragma: no cover - ИИ не должен ломать подбор
        return False


def _extract_json(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _ai_queries(info: dict[str, Any]) -> list[str]:
    """Попросить ИИ короткие поисковые запросы на русском."""
    try:
        from services import ai as ai_service

        prompt = (
            "Ты помогаешь подобрать обучающие видео на YouTube для школьной темы.\n"
            f"Тема: {info.get('title') or info.get('slug')}\n"
            f"Предмет: {info.get('subject') or 'школьный предмет'}\n"
            f"Класс: {info.get('grade') or ''}\n"
            f"Кратко: {info.get('description') or 'нет описания'}\n\n"
            "Придумай 1–2 коротких поисковых запроса на русском языке, по которым "
            "YouTube найдёт именно объяснение этой темы для этого класса. "
            "Запросы должны быть без кавычек, без названий каналов, без ссылок и "
            "без лишних предметов. Верни ТОЛЬКО JSON:\n"
            '{"queries": ["обыкновенные дроби 5 класс объяснение"]}'
        )
        text, error = ai_service.chat(
            [
                {"role": "system", "content": "Отвечай только валидным JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=220,
            timeout=getattr(Config, "YOUTUBE_AI_TIMEOUT", 25),
        )
        if error:
            return []
        data = _extract_json(text)
        queries = data.get("queries") if data else None
        if not isinstance(queries, list):
            return []
        result = []
        for query in queries[:2]:
            query = str(query or "").strip().strip('"«»')
            query = re.sub(r"https?://\S+", "", query).strip()
            query = re.sub(r"\s+", " ", query)
            if 3 <= len(query) <= 90 and query not in result:
                result.append(query)
        return result
    except Exception:  # pragma: no cover - ИИ не должен ломать подбор
        return []


def _ai_rank(
    info: dict[str, Any],
    candidates: list[dict[str, Any]],
    limit: int,
) -> list[str]:
    """Выбрать ролики из кандидатов. Возвращает только реальные video_id."""
    if not candidates:
        return []
    try:
        from services import ai as ai_service

        lines = []
        for index, video in enumerate(candidates, start=1):
            description = re.sub(r"\s+", " ", video.get("description") or "")[:220]
            lines.append(
                f"[{index}] id={video['video_id']} | {video.get('title') or ''} | "
                f"канал: {video.get('channel') or '—'} | "
                f"{format_duration(video.get('duration') or 0)} | {description}"
            )
        prompt = (
            "Ты — методист школьной платформы. Выбери из списка видео, которые "
            "действительно объясняют указанную тему, и ничего лишнего.\n"
            f"Тема: {info.get('title') or info.get('slug')}\n"
            f"Предмет: {info.get('subject') or 'школьный предмет'}\n"
            f"Класс: {info.get('grade') or ''}\n"
            f"Описание темы: {info.get('description') or 'нет описания'}\n\n"
            f"Кандидаты:\n" + "\n".join(lines) + "\n\n"
            f"Выбери не больше {limit} самых подходящих роликов. Отдавай "
            "предпочтение понятным урокам и разборам на русском языке, без "
            "развлечений, рекламы, shorts, песен, обзоров игр и роликов для "
            "другого класса. Нельзя придумывать идентификаторы: используй "
            "только id из списка выше.\n"
            'Верни ТОЛЬКО JSON: {"video_ids": ["id1", "id2"]}'
        )
        text, error = ai_service.chat(
            [
                {"role": "system", "content": "Отвечай только валидным JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=300,
            timeout=getattr(Config, "YOUTUBE_AI_TIMEOUT", 25),
        )
        if error:
            return []
        data = _extract_json(text)
        chosen = data.get("video_ids") if data else None
        if not isinstance(chosen, list):
            return []
        allowed = {video["video_id"] for video in candidates}
        result = []
        for video_id in chosen:
            video_id = str(video_id or "").strip()
            if video_id in allowed and video_id not in result:
                result.append(video_id)
        return result[:limit]
    except Exception:  # pragma: no cover - ИИ не должен ломать подбор
        return []


# ------------------------------------------------------------------ ранжирование
def _topic_info(slug: str) -> dict[str, Any] | None:
    try:
        row = query_one(
            """SELECT t.*, s.name AS subject_name, s.slug AS subject_slug
                 FROM topics t LEFT JOIN subjects s ON s.id = t.subject_id
                WHERE t.slug = ?""",
            (slug,),
        )
    except sqlite3.Error:  # pragma: no cover
        row = None
    if row is not None:
        data = dict(row)
        return {
            "slug": data.get("slug") or slug,
            "title": data.get("title") or slug,
            "grade": data.get("grade"),
            "subject": data.get("subject_name") or "",
            "subject_slug": data.get("subject_slug") or "",
            "description": data.get("description") or "",
        }
    try:
        from content.curriculum import topic_by_slug

        curriculum = topic_by_slug(slug)
    except Exception:  # pragma: no cover
        curriculum = None
    if curriculum:
        return {
            "slug": curriculum["slug"],
            "title": curriculum.get("title") or slug,
            "grade": curriculum.get("grade"),
            "subject": "Математика",
            "subject_slug": "math",
            "description": curriculum.get("description") or "",
        }
    return None


def _queries_for(info: dict[str, Any], settings: dict[str, Any]) -> list[str]:
    title = (info.get("title") or "").strip()
    subject = (info.get("subject") or "").strip()
    grade = info.get("grade") or ""
    queries: list[str] = []
    if _ai_available(settings):
        queries.extend(_ai_queries(info))
    base = " ".join(part for part in (title, subject, f"{grade} класс") if part)
    queries.append(f"{base} объяснение".strip())
    if subject and subject.lower() not in title.lower():
        queries.append(f"{title} {grade} класс {subject} урок".strip())
    else:
        queries.append(f"{title} {grade} класс урок разбор".strip())
    result = []
    for query in queries:
        query = re.sub(r"\s+", " ", str(query or "")).strip()
        if query and query not in result:
            result.append(query[:100])
    return result[:2]


def _score_candidate(
    video: dict[str, Any], info: dict[str, Any], settings: dict[str, Any]
) -> float:
    title = (video.get("title") or "").lower()
    channel = (video.get("channel") or "").lower()
    description = (video.get("description") or "").lower()
    title_tokens = set(_tokens(title))
    description_tokens = set(_tokens(description))
    topic_tokens = _topic_tokens(info)
    if not topic_tokens:
        return 0.0

    score = 0.0
    matched = 0
    for token in topic_tokens:
        if token in title_tokens:
            score += 1.6
            matched += 1
        elif token in description_tokens:
            score += 0.35
        elif len(token) >= 4 and any(
            item.startswith(token[: max(4, len(token) - 2)]) for item in title_tokens
        ):
            score += 0.8
            matched += 1

    phrase = " ".join(topic_tokens)
    if phrase and phrase in title:
        score += 3.0

    subject_tokens = _tokens(info.get("subject") or "")
    if subject_tokens and all(token in title_tokens for token in subject_tokens[:2]):
        score += 1.0
    grade = str(info.get("grade") or "")
    if grade and re.search(rf"\b{re.escape(grade)}\s*класс", title):
        score += 1.2
    for other in re.findall(r"\b(\d{1,2})\s*класс", title):
        if grade and other != grade:
            score -= 2.5
            break

    positive_hits = sum(1 for word in _POSITIVE_WORDS if word in title)
    score += min(1.8, positive_hits * 0.6)
    if any(word in channel for word in _EDU_CHANNELS):
        score += 0.8
    duration = int(video.get("duration") or 0)
    if 180 <= duration <= 1200:
        score += 0.5
    elif duration and duration < 90:
        score -= 2.0
    elif duration > 2400:
        score -= 1.0

    for word in _NEGATIVE_WORDS:
        if word in title or word in channel:
            score -= 3.0
            break

    needed = min(2, len(topic_tokens))
    if matched < needed and phrase not in title:
        score -= 2.0
    return score


def _filter_candidates(
    videos: list[dict[str, Any]], settings: dict[str, Any], info: dict[str, Any]
) -> list[dict[str, Any]]:
    region = str(settings.get("region_code") or "BY").upper()
    min_duration = int(settings.get("min_duration") or 60)
    max_duration = int(settings.get("max_duration") or 3600)
    result = []
    for video in videos:
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video.get("video_id") or ""):
            continue
        if video.get("privacy") != "public":
            continue
        if not video.get("embeddable"):
            continue
        if _region_blocked(video, region):
            continue
        duration = int(video.get("duration") or 0)
        if duration and (duration < min_duration or duration > max_duration):
            continue
        video["score"] = round(_score_candidate(video, info, settings), 2)
        result.append(video)
    return result


def _heuristic_choice(
    videos: list[dict[str, Any]], info: dict[str, Any], limit: int
) -> list[dict[str, Any]]:
    threshold = 2.0 if len(_topic_tokens(info)) >= 2 else 1.2
    ranked = sorted(
        (video for video in videos if video.get("score", 0) >= threshold),
        key=lambda video: (video.get("score", 0), video.get("duration", 0)),
        reverse=True,
    )
    return ranked[:limit]


def _select_videos(
    videos: list[dict[str, Any]],
    info: dict[str, Any],
    settings: dict[str, Any],
    *,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    limit = int(settings.get("max_per_topic") or DEFAULT_MAX_PER_TOPIC)
    heuristic = _heuristic_choice(videos, info, max(limit * 2, limit))
    if not _ai_available(settings):
        return heuristic[:limit]

    # ИИ видит только проверенных кандидатов; его выбор важнее эвристики.
    candidates = sorted(videos, key=lambda video: video.get("score", 0), reverse=True)[:20]
    chosen_ids = _ai_rank(info, candidates, limit)
    by_id = {video["video_id"]: video for video in candidates}
    chosen = [by_id[video_id] for video_id in chosen_ids if video_id in by_id]
    try:
        from services import ai as ai_service

        ai_service.log_request(
            user_id, "youtube", True,
            f"{info.get('slug')}: ИИ выбрал {len(chosen)} из {len(candidates)}",
        )
    except Exception:  # pragma: no cover
        pass
    if not chosen:
        return heuristic[:limit]
    for video in heuristic:
        if len(chosen) >= limit:
            break
        if video["video_id"] not in chosen_ids:
            chosen.append(video)
    return chosen[:limit]


# ------------------------------------------------------------------ кэш и БД
def _insert_video(
    slug: str,
    video: dict[str, Any],
    *,
    source: str,
    position: int,
    query: str,
) -> None:
    execute(
        """INSERT INTO topic_videos
               (topic_slug, video_id, title, channel, description, thumbnail,
                duration, source, position, query, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(topic_slug, video_id) DO UPDATE SET
               title = excluded.title,
               channel = excluded.channel,
               description = excluded.description,
               thumbnail = excluded.thumbnail,
               duration = excluded.duration,
               position = CASE WHEN topic_videos.source = 'manual'
                               THEN topic_videos.position ELSE excluded.position END,
               query = CASE WHEN topic_videos.source = 'manual'
                            THEN topic_videos.query ELSE excluded.query END,
               updated_at = datetime('now')""",
        (
            slug, video["video_id"], video.get("title") or "",
            video.get("channel") or "", (video.get("description") or "")[:600],
            video.get("thumbnail") or "", int(video.get("duration") or 0),
            source, position, query[:200],
        ),
    )


def _save_cache(
    slug: str,
    *,
    query: str,
    status: str,
    found: int,
    selected: int,
    error: str = "",
    expires_at: str,
) -> None:
    execute(
        """INSERT INTO topic_video_cache
               (topic_slug, query, status, error, found, selected,
                checked_at, expires_at)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)
           ON CONFLICT(topic_slug) DO UPDATE SET
               query = excluded.query, status = excluded.status,
               error = excluded.error, found = excluded.found,
               selected = excluded.selected, checked_at = datetime('now'),
               expires_at = excluded.expires_at""",
        (slug, query[:200], status, (error or "")[:500], found, selected, expires_at),
    )


def _store_auto(
    slug: str, videos: list[dict[str, Any]], query: str
) -> None:
    # Старые автоматические ролики заменяем, но заблокированные администратором
    # оставляем, чтобы они не вернулись при следующем обновлении.
    execute(
        "DELETE FROM topic_videos WHERE topic_slug = ? AND source = 'auto' AND blocked = 0",
        (slug,),
    )
    for position, video in enumerate(videos):
        _insert_video(slug, video, source="auto", position=position, query=query)


def refresh_topic_videos(
    slug_or_info: str | dict[str, Any],
    *,
    user_id: int | None = None,
    settings: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """Найти/обновить видео темы. Возвращает (видео из БД, ошибка)."""
    settings = settings or get_settings()
    info = (
        slug_or_info
        if isinstance(slug_or_info, dict)
        else _topic_info(str(slug_or_info))
    )
    if not info:
        return [], "Тема не найдена"
    slug = info["slug"]
    if not is_enabled():
        return cached_videos(slug), "YouTube не настроен"

    queries = _queries_for(info, settings)
    if not queries:
        return cached_videos(slug), "Не удалось построить поисковый запрос"

    gathered: list[dict[str, Any]] = []
    found_count = 0
    search_error = ""
    used_query = ""
    for query in queries:
        used_query = used_query or query
        ids, error = _search(query, settings=settings)
        if error:
            search_error = error
            break
        found_count += len(ids)
        details, details_error = _fetch_details(ids, settings=settings)
        if details_error:
            search_error = details_error
            break
        gathered.extend(details)
        filtered = _filter_candidates(gathered, settings, info)
        relevant = _heuristic_choice(
            filtered, info, int(settings.get("max_per_topic") or 3)
        )
        if len(relevant) >= int(settings.get("max_per_topic") or 3):
            break

    if search_error:
        execute(
            """INSERT INTO topic_video_cache
                   (topic_slug, query, status, error, found, selected,
                    checked_at, expires_at)
               VALUES (?, ?, 'error', ?, ?, 0, datetime('now'), ?)
               ON CONFLICT(topic_slug) DO UPDATE SET
                   query = excluded.query, status = 'error',
                   error = excluded.error, found = excluded.found,
                   checked_at = datetime('now'), expires_at = excluded.expires_at""",
            (slug, used_query[:200], search_error[:500], found_count,
             _future(minutes=ERROR_RETRY_MINUTES)),
        )
        return cached_videos(slug), search_error

    # Убираем дубли, оставляя первое вхождение (первый запрос приоритетнее).
    unique: dict[str, dict[str, Any]] = {}
    for video in gathered:
        unique.setdefault(video["video_id"], video)
    filtered = _filter_candidates(list(unique.values()), settings, info)

    chosen = _select_videos(filtered, info, settings, user_id=user_id)
    _store_auto(slug, chosen, used_query)
    if chosen:
        _save_cache(
            slug, query=used_query, status="ok", found=len(filtered),
            selected=len(chosen),
            expires_at=_future(days=int(settings.get("cache_days") or 14)),
        )
    else:
        _save_cache(
            slug, query=used_query, status="empty", found=len(filtered),
            selected=0, expires_at=_future(days=EMPTY_RETRY_DAYS),
        )
    return cached_videos(slug), None


def _cache_row(slug: str) -> dict[str, Any] | None:
    try:
        row = query_one(
            """SELECT *, CASE WHEN expires_at IS NOT NULL
                              AND expires_at > datetime('now')
                         THEN 1 ELSE 0 END AS fresh
                 FROM topic_video_cache WHERE topic_slug = ?""",
            (slug,),
        )
    except sqlite3.Error:  # pragma: no cover
        return None
    return dict(row) if row else None


def _video_payload(row: Any) -> dict[str, Any]:
    data = dict(row)
    video_id = data.get("video_id") or ""
    return {
        "id": data.get("id"),
        "video_id": video_id,
        "title": data.get("title") or "",
        "channel": data.get("channel") or "",
        "description": data.get("description") or "",
        "thumbnail": data.get("thumbnail") or "",
        "duration_seconds": int(data.get("duration") or 0),
        "duration_label": format_duration(int(data.get("duration") or 0)),
        "source": data.get("source") or "auto",
        "embed_url": embed_url(video_id) if video_id else "",
        "watch_url": watch_url(video_id) if video_id else "",
    }


def cached_videos(slug: str, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Видео из базы без обращения к YouTube. Ручные — всегда первыми."""
    try:
        rows = query_all(
            """SELECT * FROM topic_videos
                WHERE topic_slug = ? AND blocked = 0
                ORDER BY CASE source WHEN 'manual' THEN 0 ELSE 1 END,
                         position, id""",
            (slug,),
        )
    except sqlite3.Error:  # pragma: no cover
        return []
    payload = [_video_payload(row) for row in rows]
    if limit is None:
        return payload
    limit = max(1, int(limit))
    manual = [item for item in payload if item["source"] == "manual"]
    auto = [item for item in payload if item["source"] != "manual"]
    if len(manual) >= limit:
        return manual
    return manual + auto[: limit - len(manual)]


def page_payload(slug: str) -> dict[str, Any]:
    """Данные для первоначальной отрисовки страницы (без сети)."""
    settings = get_settings()
    limit = int(settings.get("max_per_topic") or DEFAULT_MAX_PER_TOPIC)
    cache = _cache_row(slug)
    return {
        "youtube_enabled": is_enabled(),
        "youtube_videos": cached_videos(slug, limit=limit),
        "youtube_stale": not bool(cache and cache.get("fresh")),
        "youtube_cache": cache,
        "youtube_max": limit,
    }


def videos_for_topic(
    slug: str,
    *,
    allow_fetch: bool = True,
    refresh: bool = False,
    user_id: int | None = None,
) -> dict[str, Any]:
    """Полный ответ для веб-страницы и мобильного API."""
    info = _topic_info(slug)
    if not info:
        return {
            "ok": False,
            "error": "Тема не найдена",
            "youtube_enabled": False,
            "videos": [],
        }
    settings = get_settings()
    limit = int(settings.get("max_per_topic") or DEFAULT_MAX_PER_TOPIC)
    if not is_enabled():
        return {
            "ok": True,
            "youtube_enabled": False,
            "videos": [],
            "stale": False,
            "message": "YouTube не подключён в настройках.",
        }

    cache = _cache_row(slug)
    if refresh or not (cache and cache.get("fresh")):
        if allow_fetch:
            _, error = refresh_topic_videos(info, user_id=user_id, settings=settings)
            cache = _cache_row(slug)
        else:
            error = None
    else:
        error = None

    videos = cached_videos(slug, limit=limit)
    return {
        "ok": True,
        "youtube_enabled": True,
        "videos": videos,
        "stale": not bool(cache and cache.get("fresh")),
        "cached": bool(videos),
        "error": error,
        "message": error or "",
        "cache": {
            "status": (cache or {}).get("status"),
            "checked_at": (cache or {}).get("checked_at"),
            "found": (cache or {}).get("found"),
            "selected": (cache or {}).get("selected"),
        },
    }


# ------------------------------------------------------------------ ручные ссылки
def add_manual_video(
    slug: str, value: str, *, settings: dict[str, Any] | None = None
) -> tuple[dict[str, Any] | None, str | None]:
    settings = settings or get_settings()
    info = _topic_info(slug)
    if not info:
        return None, "Тема не найдена"
    if not is_enabled():
        return None, "Сначала подключите YouTube и сохраните ключ API."
    video_id = parse_video_id(value)
    if not video_id:
        return None, "Не удалось распознать ссылку на YouTube."
    count = query_one(
        "SELECT COUNT(*) AS c FROM topic_videos WHERE topic_slug = ? AND source = 'manual'",
        (slug,),
    )
    if count and int(count["c"]) >= MAX_MANUAL_PER_TOPIC:
        return None, f"Для одной темы можно добавить не больше {MAX_MANUAL_PER_TOPIC} ссылок."
    details, error = _fetch_details([video_id], settings=settings)
    if error:
        return None, error
    if not details:
        return None, "Видео не найдено или недоступно."
    video = details[0]
    if video.get("privacy") != "public":
        return None, "Видео не является публичным."
    if not video.get("embeddable"):
        return None, "Автор запретил встраивание этого видео."
    if _region_blocked(
        video, str(settings.get("region_code") or "BY")
    ):
        return None, "Видео недоступно для встраивания в вашем регионе."
    _insert_video(slug, video, source="manual", position=0, query="manual")
    row = query_one(
        "SELECT * FROM topic_videos WHERE topic_slug = ? AND video_id = ?",
        (slug, video_id),
    )
    return (_video_payload(row) if row else None), None


def block_video(video_row_id: int) -> tuple[bool, str]:
    """Скрыть автоматическое видео или удалить ручную ссылку."""
    row = query_one("SELECT * FROM topic_videos WHERE id = ?", (video_row_id,))
    if not row:
        return False, "Видео не найдено"
    if row["source"] == "manual":
        execute("DELETE FROM topic_videos WHERE id = ?", (video_row_id,))
        return True, "Ручная ссылка удалена."
    execute("UPDATE topic_videos SET blocked = 1 WHERE id = ?", (video_row_id,))
    return True, "Видео скрыто. При обновлении кэша оно не вернётся."


def unblock_video(video_row_id: int) -> tuple[bool, str]:
    row = query_one("SELECT * FROM topic_videos WHERE id = ?", (video_row_id,))
    if not row:
        return False, "Видео не найдено"
    execute("UPDATE topic_videos SET blocked = 0 WHERE id = ?", (video_row_id,))
    return True, "Видео снова показывается."


# ------------------------------------------------------------------ статистика и прогрев
def stats() -> dict[str, Any]:
    total_topics = query_one("SELECT COUNT(*) AS c FROM topics")
    with_videos = query_one(
        """SELECT COUNT(DISTINCT topic_slug) AS c FROM topic_videos
            WHERE blocked = 0"""
    )
    fresh = query_one(
        "SELECT COUNT(*) AS c FROM topic_video_cache WHERE expires_at > datetime('now')"
    )
    errors = query_one(
        "SELECT COUNT(*) AS c FROM topic_video_cache WHERE status = 'error'"
    )
    manual = query_one(
        "SELECT COUNT(*) AS c FROM topic_videos WHERE source = 'manual' AND blocked = 0"
    )
    auto = query_one(
        "SELECT COUNT(*) AS c FROM topic_videos WHERE source = 'auto' AND blocked = 0"
    )
    last_error = query_one(
        """SELECT c.error, c.checked_at, t.title FROM topic_video_cache c
             LEFT JOIN topics t ON t.slug = c.topic_slug
            WHERE c.status = 'error' AND c.error <> ''
            ORDER BY c.checked_at DESC LIMIT 1"""
    )
    return {
        "topics": int(total_topics["c"]) if total_topics else 0,
        "with_videos": int(with_videos["c"]) if with_videos else 0,
        "fresh": int(fresh["c"]) if fresh else 0,
        "errors": int(errors["c"]) if errors else 0,
        "manual": int(manual["c"]) if manual else 0,
        "auto": int(auto["c"]) if auto else 0,
        "last_error": dict(last_error) if last_error else None,
    }


def topic_rows(limit: int = 200, search: str = "") -> list[dict[str, Any]]:
    sql = """SELECT t.slug, t.title, t.grade, s.name AS subject_name,
                    (SELECT COUNT(*) FROM topic_videos v
                      WHERE v.topic_slug = t.slug AND v.blocked = 0) AS videos,
                    (SELECT COUNT(*) FROM topic_videos v
                      WHERE v.topic_slug = t.slug AND v.source = 'manual'
                        AND v.blocked = 0) AS manual,
                    c.status, c.error, c.checked_at, c.expires_at,
                    CASE WHEN c.expires_at > datetime('now') THEN 1 ELSE 0 END AS fresh
               FROM topics t
          LEFT JOIN subjects s ON s.id = t.subject_id
          LEFT JOIN topic_video_cache c ON c.topic_slug = t.slug"""
    params: list[Any] = []
    if search:
        sql += " WHERE t.title LIKE ?"
        params.append(f"%{search}%")
    sql += " ORDER BY (videos = 0) DESC, t.grade, t.order_index, t.id LIMIT ?"
    params.append(max(1, min(500, int(limit))))
    return [dict(row) for row in query_all(sql, params)]


def manual_rows(limit: int = 100) -> list[dict[str, Any]]:
    rows = query_all(
        """SELECT v.*, t.title AS topic_title
             FROM topic_videos v LEFT JOIN topics t ON t.slug = v.topic_slug
            WHERE v.source = 'manual'
            ORDER BY v.id DESC LIMIT ?""",
        (max(1, min(500, int(limit))),),
    )
    return [_video_payload(row) | {"topic_slug": row["topic_slug"],
                                   "topic_title": row["topic_title"]}
            for row in rows]


def warm_topics(limit: int = 5, *, user_id: int | None = None) -> dict[str, Any]:
    """Подобрать видео для тем, где кэша нет или он устарел.

    Ограничение в 5 тем за запуск бережёт дневную квоту YouTube: один
    поисковый запрос стоит около 100 units из 10 000.
    """
    limit = max(1, min(MAX_WARM_TOPICS, int(limit or 5)))
    rows = query_all(
        """SELECT t.slug FROM topics t
             LEFT JOIN topic_video_cache c ON c.topic_slug = t.slug
            WHERE c.topic_slug IS NULL OR c.expires_at <= datetime('now')
            ORDER BY (c.topic_slug IS NULL) DESC, t.grade, t.order_index, t.id
            LIMIT ?""",
        (limit,),
    )
    results = []
    stopped = ""
    for row in rows:
        videos, error = refresh_topic_videos(row["slug"], user_id=user_id)
        results.append({
            "slug": row["slug"],
            "count": len(videos),
            "error": error or "",
        })
        if error and any(word in error.lower() for word in ("quota", "keyinvalid", "key invalid", "403")):
            stopped = error
            break
    return {"processed": len(results), "results": results, "stopped": stopped}


def refresh_all_topic_cache(slug: str, *, user_id: int | None = None) -> tuple[int, str | None]:
    videos, error = refresh_topic_videos(slug, user_id=user_id)
    return len(videos), error
