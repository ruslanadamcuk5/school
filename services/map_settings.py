"""Настройки карты для GPS-контроля.

Администратор выбирает провайдера тайлов (OpenStreetMap, Яндекс или свои
тайлы), оформление и стартовый вид карты. Настройки хранятся в ``app_meta``
и используются и на сайте, и в Android-приложении.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urlparse

from database import get_meta, set_meta

META_KEY = "map_settings"

DEFAULT_SETTINGS: dict = {
    "provider": "osm",
    "tile_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "attribution": "© OpenStreetMap",
    "crs": "mercator",
    "min_zoom": 3,
    "max_zoom": 19,
    "center_lat": 53.9023,
    "center_lon": 27.5619,
    "zoom": 11,
}

PRESETS: list[dict] = [
    {
        "id": "osm",
        "name": "OpenStreetMap",
        "note": "Бесплатные тайлы, не требуют ключа.",
        "tile_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attribution": "© OpenStreetMap",
        "crs": "mercator",
        "max_zoom": 19,
    },
    {
        "id": "yandex",
        "name": "Яндекс Карты",
        "note": "Подробная карта Беларуси и России. Ключ не нужен.",
        "tile_url": (
            "https://core-renderer-tiles.maps.yandex.net/tiles"
            "?l=map&x={x}&y={y}&z={z}&scale=1&lang=ru_RU"
        ),
        "attribution": "© Яндекс",
        "crs": "yandex",
        "max_zoom": 19,
    },
    {
        "id": "custom",
        "name": "Свои тайлы",
        "note": "Любой сервер тайлов с подстановками {x}, {y} и {z}.",
        "tile_url": "",
        "attribution": "",
        "crs": "mercator",
        "max_zoom": 19,
    },
]

PROVIDER_IDS = {preset["id"] for preset in PRESETS}
CRS_VALUES = {"mercator", "yandex"}

# Базовые адреса, которые должны работать даже сразу после смены настроек.
BASE_TILE_ORIGINS = {
    "https://tile.openstreetmap.org",
    "https://*.tile.openstreetmap.org",
    "https://core-renderer-tiles.maps.yandex.net",
    "https://*.maps.yandex.net",
}


class MapSettingsError(ValueError):
    """Некорректные настройки карты."""


def _preset(provider: str) -> dict | None:
    for preset in PRESETS:
        if preset["id"] == provider:
            return preset
    return None


def _number(value, *, name: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise MapSettingsError(f"«{name}» должно быть числом")
    if not (minimum <= number <= maximum):
        raise MapSettingsError(f"«{name}» должно быть от {minimum:g} до {maximum:g}")
    return number


def _integer(value, *, name: str, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise MapSettingsError(f"«{name}» должно быть целым числом")
    if not (minimum <= number <= maximum):
        raise MapSettingsError(f"«{name}» должно быть от {minimum} до {maximum}")
    return number


def _clean_tile_url(value: str) -> str:
    url = (value or "").strip()
    if not url:
        raise MapSettingsError("Укажите адрес тайлов карты")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise MapSettingsError("Адрес тайлов должен начинаться с http:// или https://")
    for token in ("{x}", "{y}", "{z}"):
        if token not in url:
            raise MapSettingsError(
                "В адресе тайлов нужны подстановки {x}, {y} и {z}"
            )
    return url


def normalize(data: dict | None) -> dict:
    """Проверить и привести настройки к единому виду."""
    source = dict(DEFAULT_SETTINGS)
    if isinstance(data, dict):
        source.update({key: value for key, value in data.items() if value is not None})

    provider = str(source.get("provider") or "osm").strip().lower()
    if provider not in PROVIDER_IDS:
        raise MapSettingsError("Неизвестный провайдер карты")
    preset = _preset(provider) or {}

    tile_url = str(source.get("tile_url") or "").strip()
    if not tile_url and preset.get("tile_url"):
        tile_url = str(preset["tile_url"])
    tile_url = _clean_tile_url(tile_url)

    attribution = str(source.get("attribution") or "").strip()[:200]
    if not attribution and preset.get("attribution"):
        attribution = str(preset["attribution"])

    crs = str(source.get("crs") or preset.get("crs") or "mercator").strip().lower()
    if crs not in CRS_VALUES:
        raise MapSettingsError("Проекция карты должна быть mercator или yandex")

    max_zoom = _integer(
        source.get("max_zoom") or preset.get("max_zoom") or 19,
        name="Максимальный масштаб",
        minimum=1,
        maximum=22,
    )
    min_zoom = _integer(
        source.get("min_zoom") or 1,
        name="Минимальный масштаб",
        minimum=0,
        maximum=max_zoom,
    )
    zoom = _integer(
        source.get("zoom") or DEFAULT_SETTINGS["zoom"],
        name="Начальный масштаб",
        minimum=max(0, min_zoom),
        maximum=max_zoom,
    )
    center_lat = _number(
        source.get("center_lat", DEFAULT_SETTINGS["center_lat"]),
        name="Широта центра",
        minimum=-90,
        maximum=90,
    )
    center_lon = _number(
        source.get("center_lon", DEFAULT_SETTINGS["center_lon"]),
        name="Долгота центра",
        minimum=-180,
        maximum=180,
    )
    return {
        "provider": provider,
        "tile_url": tile_url,
        "attribution": attribution,
        "crs": crs,
        "min_zoom": min_zoom,
        "max_zoom": max_zoom,
        "center_lat": round(center_lat, 6),
        "center_lon": round(center_lon, 6),
        "zoom": zoom,
    }


def get_settings() -> dict:
    raw = get_meta(META_KEY)
    if not raw:
        return dict(DEFAULT_SETTINGS)
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return dict(DEFAULT_SETTINGS)
    try:
        settings = normalize(data)
    except MapSettingsError:
        return dict(DEFAULT_SETTINGS)
    if isinstance(data, dict) and data.get("updated_at"):
        settings["updated_at"] = str(data["updated_at"])
    else:
        settings["updated_at"] = None
    return settings


def save_settings(data: dict) -> dict:
    settings = normalize(data)
    settings["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    set_meta(META_KEY, json.dumps(settings, ensure_ascii=False))
    return get_settings()


def public_settings() -> dict:
    """Настройки для сайта и приложения (без служебных полей)."""
    settings = get_settings()
    return {
        "provider": settings["provider"],
        "tile_url": settings["tile_url"],
        "attribution": settings["attribution"],
        "crs": settings["crs"],
        "min_zoom": settings["min_zoom"],
        "max_zoom": settings["max_zoom"],
        "center_lat": settings["center_lat"],
        "center_lon": settings["center_lon"],
        "zoom": settings["zoom"],
        "updated_at": settings.get("updated_at"),
    }


def presets() -> list[dict]:
    return [dict(preset) for preset in PRESETS]


def csp_origins() -> list[str]:
    """Источники тайлов для Content-Security-Policy (img-src)."""
    origins = set(BASE_TILE_ORIGINS)
    urls = [DEFAULT_SETTINGS["tile_url"], get_settings()["tile_url"]]
    for preset in PRESETS:
        if preset.get("tile_url"):
            urls.append(str(preset["tile_url"]))
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            origins.add(f"{parsed.scheme}://{parsed.netloc}")
    return sorted(origins)
