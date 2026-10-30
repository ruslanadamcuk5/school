"""Магазин: покупки за монеты и опыт, косметика и полезные усилители.

Идея для детей 1–4 классов: опыт не «сгорает» при покупке — уровень считается
по сумме заработанного опыта (``xp + xp_spent``), а тратится только свободный
остаток. Поэтому ребёнок никогда не «падает» в уровне из-за покупки.

Каталог живёт в коде (``CATALOG``): так его удобно версионировать и тестировать.
В базе хранятся только покупки, количество расходуемых предметов и активные
усилители.
"""
from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta, timezone
from typing import Any

from config import get_config
from database import connect, execute, query_all, query_one
from services.learners import AVATARS
from services.progress import level_for_xp, level_info

DISCOUNT_PERCENT = 25
CHEST_MIN_COINS = 10
CHEST_MAX_COINS = 20
CHEST_MIN_XP = 2
CHEST_MAX_XP = 6

CATEGORIES = [
    {"key": "perks", "name": "Учёба", "icon": "🎓",
     "hint": "Помощники, которые реально помогают решать задания"},
    {"key": "minecraft", "name": "Minecraft", "icon": "⛏",
     "hint": "Алмазы, зачарования, криперы и кубические приключения"},
    {"key": "style", "name": "Стиль", "icon": "🎨",
     "hint": "Аватары, рамки, титулы и темы оформления"},
    {"key": "pets", "name": "Питомцы", "icon": "🐾",
     "hint": "Друзья, которые растут вместе с тобой"},
]

RARITY = {
    "common": {"name": "Обычный", "icon": "⚪", "css": "common"},
    "rare": {"name": "Редкий", "icon": "🔵", "css": "rare"},
    "epic": {"name": "Эпический", "icon": "🟣", "css": "epic"},
    "legendary": {"name": "Легендарный", "icon": "🟠", "css": "legendary"},
}

# Постоянные бонусы Minecraft-предметов.
PERMANENT_COIN_BOOST = 1.15
PERMANENT_XP_BOOST = 1.15

# thresholds — сколько верных ответов нужно питомцу для следующей ступени.
PET_STAGES = [
    (0, "Малыш", "🐣"),
    (20, "Друг", "🌟"),
    (60, "Помощник", "🎒"),
    (150, "Защитник", "🛡"),
    (300, "Легенда", "👑"),
]


def _perk(key: str, name: str, icon: str, coins: int, tagline: str,
          description: str, *, kind: str = "perk", xp: int = 0, level: int = 1,
          repeatable: bool = False, max_owned: int = 1, value: float = 0.0,
          duration_minutes: int = 0, category: str = "perks") -> dict[str, Any]:
    return {
        "key": key,
        "category": category,
        "kind": kind,
        "slot": "",
        "name": name,
        "icon": icon,
        "tagline": tagline,
        "description": description,
        "coins": coins,
        "xp": xp,
        "level": level,
        "repeatable": repeatable,
        "max_owned": max_owned,
        "value": value,
        "duration_minutes": duration_minutes,
        "avatars": [],
        "accent": "",
    }


def _style(key: str, name: str, icon: str, coins: int, tagline: str,
           description: str, *, kind: str, slot: str = "", accent: str = "",
           xp: int = 0, level: int = 1, avatars: list[str] | None = None,
           category: str = "style") -> dict[str, Any]:
    return {
        "key": key,
        "category": category,
        "kind": kind,
        "slot": slot,
        "name": name,
        "icon": icon,
        "tagline": tagline,
        "description": description,
        "coins": coins,
        "xp": xp,
        "level": level,
        "repeatable": False,
        "max_owned": 1,
        "value": 0.0,
        "duration_minutes": 0,
        "avatars": list(avatars or []),
        "accent": accent,
    }


def _pet(key: str, name: str, icon: str, coins: int, tagline: str,
         description: str, *, xp: int = 0, level: int = 1,
         category: str = "pets") -> dict[str, Any]:
    return {
        "key": key,
        "category": category,
        "kind": "pet",
        "slot": "pet",
        "name": name,
        "icon": icon,
        "tagline": tagline,
        "description": description,
        "coins": coins,
        "xp": xp,
        "level": level,
        "repeatable": False,
        "max_owned": 1,
        "value": 0.0,
        "duration_minutes": 0,
        "avatars": [],
        "accent": "",
    }


CATALOG: list[dict[str, Any]] = [
    # ------------------------------------------------------------ учёба
    _perk(
        "boost_xp", "Двойной опыт", "⚡", 80,
        "30 минут опыта ×2",
        "Каждый верный ответ приносит в два раза больше опыта. Отлично перед "
        "новой темой!",
        kind="boost", repeatable=True, max_owned=99, value=2.0,
        duration_minutes=30,
    ),
    _perk(
        "boost_coins", "Двойные монеты", "🪙", 70,
        "30 минут монет ×2",
        "Каждый верный ответ приносит в два раза больше монет. Копи на большую "
        "мечту быстрее!",
        kind="boost", repeatable=True, max_owned=99, value=2.0,
        duration_minutes=30,
    ),
    _perk(
        "hint_pack", "Мешок подсказок", "💡", 40,
        "+3 подсказки",
        "Три дополнительные подсказки. Можно потратить в любой теме, когда "
        "задание совсем не поддаётся.",
        kind="hint_pack", repeatable=True, max_owned=30, value=3,
    ),
    _perk(
        "streak_shield", "Щит серии", "🛡", 120,
        "Спасёт огонёк",
        "Если один день не получится позаниматься, серия дней не сгорит. "
        "Щит сработает сам.",
        kind="shield", repeatable=True, max_owned=10,
    ),
    _perk(
        "smart_hint", "Умные подсказки", "🧠", 300,
        "Навсегда +1 подсказка",
        "В каждом задании будет на одну подсказку больше. Покупается один раз "
        "и остаётся навсегда.",
        kind="unlock", level=2,
    ),
    # ------------------------------------------------------------ стиль
    _style(
        "pack_space", "Космический набор", "🚀", 120,
        "5 аватаров",
        "Покоряй математические галактики: 🚀 👽 🛸 🪐 🌟",
        kind="avatar_pack", avatars=["🚀", "👽", "🛸", "🪐", "🌟"],
    ),
    _style(
        "pack_dino", "Парк динозавров", "🦕", 120,
        "5 аватаров",
        "Древние друзья придут на помощь: 🦕 🦖 🐊 🦎 🐍",
        kind="avatar_pack", avatars=["🦕", "🦖", "🐊", "🦎", "🐍"],
    ),
    _style(
        "pack_ocean", "Океан друзей", "🐬", 120,
        "5 аватаров",
        "Погружайся в глубины: 🐬 🦈 🐠 🐡 🐋",
        kind="avatar_pack", avatars=["🐬", "🦈", "🐠", "🐡", "🐋"],
    ),
    _style(
        "pack_magic", "Волшебный набор", "🧚", 200,
        "5 аватаров",
        "Немного магии для уроков: 🧚 🧞 🧙 🧝 🐉",
        kind="avatar_pack", avatars=["🧚", "🧞", "🧙", "🧝", "🐉"],
    ),
    _style(
        "frame_gold", "Золотая рамка", "🥇", 90,
        "Рамка профиля",
        "Сияющая золотая рамка вокруг твоего аватара.",
        kind="frame", slot="frame", accent="gold",
    ),
    _style(
        "frame_neon", "Неоновая рамка", "🌈", 150,
        "Рамка профиля",
        "Радужное неоновое свечение — тебя видно издалека.",
        kind="frame", slot="frame", accent="neon", level=2,
    ),
    _style(
        "frame_fire", "Огненная рамка", "🔥", 180,
        "Рамка профиля",
        "Рамка из живого огня для настоящих героев задач.",
        kind="frame", slot="frame", accent="fire", level=3,
    ),
    _style(
        "title_fast", "Титул «Быстрый как молния»", "⚡", 80,
        "Титул в профиле",
        "Покажи всем, как быстро ты решаешь примеры.",
        kind="title", slot="title", accent="fast",
    ),
    _style(
        "title_genius", "Титул «Юный гений»", "🧠", 120,
        "Титул в профиле",
        "Для тех, кто щёлкает задачки как орешки.",
        kind="title", slot="title", accent="genius", level=2,
    ),
    _style(
        "title_explorer", "Титул «Отважный исследователь»", "🧭", 120,
        "Титул в профиле",
        "Каждая новая тема — это открытие. Иди вперёд!",
        kind="title", slot="title", accent="explorer", level=2,
    ),
    _style(
        "theme_ocean", "Тема «Океан»", "🌊", 250,
        "Оформление сайта",
        "Морская волна красок на всех страницах: спокойно и красиво.",
        kind="theme", slot="theme", accent="ocean", xp=80, level=2,
    ),
    _style(
        "theme_space", "Тема «Космос»", "🌌", 300,
        "Оформление сайта",
        "Тёмное небо, звёзды и фиолетовые туманности. Для мечтателей.",
        kind="theme", slot="theme", accent="space", xp=100, level=3,
    ),
    # ------------------------------------------------------------ питомцы
    _pet(
        "pet_cat", "Кот-учёный", "🐱", 250,
        "Мурчит, когда решаешь",
        "Кот обожает примеры и растёт, когда ты отвечаешь верно. "
        "От 20 верных ответов он становится Другом.",
    ),
    _pet(
        "pet_owl", "Сова-умница", "🦉", 350,
        "Ночной знаток",
        "Сова видит ошибки издалека. Растёт вместе с твоим опытом.",
        level=2,
    ),
    _pet(
        "pet_dragon", "Дракончик", "🐲", 400,
        "Настоящий друг",
        "Маленький дракон вырастет в Легенду. Самый верный друг ученика.",
        xp=120, level=4,
    ),
    # ------------------------------------------------------- Minecraft
    _perk(
        "mc_pickaxe", "Алмазная кирка", "⛏", 320,
        "Навсегда +15% монет",
        "Кирка добывает больше монет за каждый верный ответ. Бонус действует "
        "всегда и складывается с усилителями.",
        kind="boost_perm", value=PERMANENT_COIN_BOOST, level=2,
        category="minecraft",
    ),
    _perk(
        "mc_enchant", "Зачарование «Острота ума»", "📘", 360,
        "Навсегда +15% опыта",
        "Стол зачарований усиливает каждый верный ответ. Опыт капает быстрее, "
        "а уровень растёт сам собой.",
        kind="boost_perm", value=PERMANENT_XP_BOOST, level=3,
        category="minecraft",
    ),
    _perk(
        "mc_potion", "Зелье мудрости", "🧪", 55,
        "+5 подсказок",
        "Светящееся зелье добавляет пять подсказок. Работает в любой теме, "
        "когда задача совсем не поддаётся.",
        kind="hint_pack", repeatable=True, max_owned=99, value=5,
        category="minecraft",
    ),
    _perk(
        "mc_tnt", "ТНТ-сюрприз", "🧨", 60,
        "Взрыв подарков",
        "Подожги фитиль и получи случайную награду: монеты, опыт или сразу "
        "и то и другое. Каждый раз — новый взрыв эмоций!",
        kind="lootbox", repeatable=True, max_owned=999, level=1,
        category="minecraft",
    ),
    _style(
        "pack_minecraft", "Набор «Мобы»", "🧟", 180,
        "5 аватаров",
        "Мобы выходят на охоту: 🧟 🐷 🐺 💎 🧨",
        kind="avatar_pack", avatars=["🧟", "🐷", "🐺", "💎", "🧨"], level=2,
        category="minecraft",
    ),
    _style(
        "frame_diamond", "Алмазная рамка", "💎", 220,
        "Рамка профиля",
        "Рамка из настоящих алмазов. Блестит так, что видно из другого мира.",
        kind="frame", slot="frame", accent="diamond", level=2,
        category="minecraft",
    ),
    _style(
        "theme_minecraft", "Тема «Кубический мир»", "🧱", 400,
        "Оформление сайта",
        "Пиксельный мир, блоки и травяные холмы. Включай режим строителя!",
        kind="theme", slot="theme", accent="minecraft", level=3,
        category="minecraft",
    ),
    _pet(
        "pet_creeper", "Крипер-питомец", "🟩", 420,
        "Тихий, но верный",
        "Крипер не взрывается — он охраняет твою серию и растёт вместе с тобой.",
        level=2, category="minecraft",
    ),
]

CATALOG_BY_KEY: dict[str, dict[str, Any]] = {item["key"]: item for item in CATALOG}


class ShopError(Exception):
    """Ошибка покупки с машинным кодом и текстом для ребёнка."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


# ------------------------------------------------------------------ утилиты
def get_item(key: str) -> dict[str, Any] | None:
    """Товар с учётом админских правок (цена, название, доступность)."""
    base = CATALOG_BY_KEY.get(str(key or "").strip())
    if base is None:
        return None
    item = dict(base)
    item["custom_discount"] = 0
    item["is_active"] = 1
    try:
        row = query_one("SELECT * FROM shop_item_overrides WHERE item_key = ?", (item["key"],))
    except Exception:  # pragma: no cover - база ещё не инициализирована
        row = None
    if row is not None:
        for field, alias in (
            ("name", "name"), ("icon", "icon"), ("tagline", "tagline"),
            ("description", "description"),
        ):
            value = row[field]
            if value:
                item[alias] = value
        if row["price_coins"] is not None:
            item["coins"] = int(row["price_coins"])
        if row["price_xp"] is not None:
            item["xp"] = int(row["price_xp"])
        if row["level"] is not None:
            item["level"] = max(1, int(row["level"]))
        if row["discount_percent"] is not None:
            item["custom_discount"] = max(0, min(90, int(row["discount_percent"])))
        item["is_active"] = 1 if row["is_active"] else 0
    item["rarity"] = rarity_key(item)
    item["rarity_name"] = RARITY[item["rarity"]]["name"]
    item["rarity_icon"] = RARITY[item["rarity"]]["icon"]
    return item


def rarity_key(item: dict[str, Any]) -> str:
    """Редкость выводится из цены и уровня — без ручных таблиц."""
    level = int(item.get("level") or 1)
    coins = int(item.get("coins") or 0)
    if level >= 4 or coins >= 400:
        return "legendary"
    if level >= 3 or coins >= 250:
        return "epic"
    if level >= 2 or coins >= 120:
        return "rare"
    return "common"


def catalog_items(*, active_only: bool = True) -> list[dict[str, Any]]:
    items = [get_item(item["key"]) for item in CATALOG]
    out = [item for item in items if item is not None]
    if active_only:
        out = [item for item in out if item.get("is_active", 1)]
    return out


def get_setting(key: str, default: str = "") -> str:
    try:
        row = query_one("SELECT value FROM shop_settings WHERE key = ?", (key,))
    except Exception:  # pragma: no cover
        return default
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    execute(
        """INSERT INTO shop_settings (key, value, updated_at)
           VALUES (?, ?, datetime('now'))
           ON CONFLICT(key) DO UPDATE SET
               value = excluded.value, updated_at = datetime('now')""",
        (key, str(value)),
    )


def save_override(item_key: str, data: dict[str, Any]) -> None:
    if item_key not in CATALOG_BY_KEY:
        raise ShopError("unknown_item", "Такого товара нет в магазине", 404)

    def _num(name: str) -> int | None:
        raw = data.get(name)
        if raw is None or str(raw).strip() == "":
            return None
        try:
            return int(float(str(raw).replace(",", ".")))
        except (TypeError, ValueError):
            return None

    discount = _num("discount_percent")
    level = _num("level")
    execute(
        """INSERT INTO shop_item_overrides
               (item_key, price_coins, price_xp, discount_percent, level,
                name, icon, tagline, description, is_active, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(item_key) DO UPDATE SET
               price_coins = excluded.price_coins,
               price_xp = excluded.price_xp,
               discount_percent = excluded.discount_percent,
               level = excluded.level,
               name = excluded.name,
               icon = excluded.icon,
               tagline = excluded.tagline,
               description = excluded.description,
               is_active = excluded.is_active,
               updated_at = datetime('now')""",
        (
            item_key,
            _num("price_coins"),
            _num("price_xp"),
            max(0, min(90, discount)) if discount is not None else None,
            max(1, level) if level is not None else None,
            (data.get("name") or "").strip(),
            (data.get("icon") or "").strip()[:8],
            (data.get("tagline") or "").strip(),
            (data.get("description") or "").strip(),
            1 if data.get("is_active") else 0,
        ),
    )


def reset_override(item_key: str) -> None:
    execute("DELETE FROM shop_item_overrides WHERE item_key = ?", (item_key,))


def overrides_map() -> dict[str, dict[str, Any]]:
    try:
        rows = query_all("SELECT * FROM shop_item_overrides")
    except Exception:  # pragma: no cover
        return {}
    return {row["item_key"]: dict(row) for row in rows}


def day_key(day: str | None = None) -> str:
    return day or date.today().isoformat()


def total_xp(learner) -> int:
    """Весь заработанный опыт: свободный остаток + потраченный в магазине."""
    spent = 0
    try:
        spent = int(learner["xp_spent"] or 0)
    except (KeyError, IndexError, TypeError, ValueError):
        spent = 0
    return int(learner["xp"] or 0) + spent


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _level(learner) -> int:
    return level_for_xp(total_xp(learner))


# ------------------------------------------------------------ живые события
def active_event(day: str | None = None) -> dict[str, Any] | None:
    """Самое свежее событие, которое идёт сегодня."""
    today = day_key(day)
    try:
        row = query_one(
            """SELECT * FROM shop_events
                WHERE is_active = 1 AND starts_on <= ? AND ends_on >= ?
                ORDER BY id DESC LIMIT 1""",
            (today, today),
        )
    except Exception:  # pragma: no cover - база ещё не инициализирована
        row = None
    if row is None:
        return None
    event = dict(row)
    if event["kind"] == "double_coins":
        event["effect_text"] = f"Монеты ×{float(event['value']):g}"
        event["emoji"] = "🪙"
    elif event["kind"] == "double_xp":
        event["effect_text"] = f"Опыт ×{float(event['value']):g}"
        event["emoji"] = "⭐"
    else:
        event["effect_text"] = f"Скидка −{int(float(event['value']))}%"
        event["emoji"] = "🏷"
    try:
        end = datetime.strptime(event["ends_on"], "%Y-%m-%d").date()
        event["days_left"] = max(0, (end - date.today()).days + 1)
    except (TypeError, ValueError):
        event["days_left"] = 0
    return event


def event_multiplier(kind: str, event: dict[str, Any] | None = None) -> float:
    event = event if event is not None else active_event()
    if not event:
        return 1.0
    key = "double_xp" if kind == "xp" else "double_coins"
    if event["kind"] != key:
        return 1.0
    try:
        return max(1.0, float(event["value"]))
    except (TypeError, ValueError):
        return 1.0


# ------------------------------------------------------- ежедневная витрина
def featured_key(day: str | None = None) -> str:
    """Товар дня: выбор админа на сегодня или детерминированный автоматически."""
    day = day_key(day)
    saved = get_setting("featured_key", "")
    saved_day = get_setting("featured_day", "")
    if saved and (not saved_day or saved_day == day):
        item = get_item(saved)
        if item and item.get("is_active", 1) and int(item["coins"]) > 0:
            return saved
    keys = [item["key"] for item in catalog_items() if int(item["coins"]) > 0]
    if not keys:
        return ""
    digest = hashlib.sha256(f"shop-featured:{day}".encode("utf-8")).digest()
    return keys[int.from_bytes(digest[:4], "big") % len(keys)]


def price_for(item: dict[str, Any], day: str | None = None, *,
              featured: str | None = None,
              event: dict[str, Any] | None = None) -> dict[str, int]:
    day = day_key(day)
    base_coins = int(item["coins"])
    discount = int(item.get("custom_discount") or 0)
    if featured is None:
        featured = featured_key(day)
    if not discount and item["key"] == featured:
        discount = DISCOUNT_PERCENT
    if event is None:
        event = active_event(day)
    if event and event["kind"] == "discount":
        try:
            discount += int(float(event["value"]))
        except (TypeError, ValueError):
            pass
    discount = max(0, min(80, discount))
    coins = base_coins
    if coins and discount:
        coins = max(1, round(base_coins * (100 - discount) / 100))
    return {"coins": coins, "xp": int(item["xp"]), "discount": discount}


# ------------------------------------------------------------ состояние
def owned_map(learner_id: int) -> dict[str, Any]:
    rows = query_all("SELECT * FROM learner_items WHERE learner_id = ?", (learner_id,))
    return {row["item_key"]: row for row in rows}


def active_effects(learner_id: int) -> list[dict[str, Any]]:
    rows = query_all(
        """SELECT * FROM learner_effects
            WHERE learner_id = ? AND expires_at IS NOT NULL
              AND expires_at > datetime('now')
            ORDER BY expires_at""",
        (learner_id,),
    )
    out = []
    for row in rows:
        item = get_item(row["effect"])
        expires = _parse_ts(row["expires_at"])
        remaining = int((expires - _now()).total_seconds()) if expires else 0
        if remaining <= 0:
            continue
        out.append({
            "key": row["effect"],
            "name": item["name"] if item else row["effect"],
            "icon": item["icon"] if item else "✨",
            "remaining_seconds": remaining,
            "remaining_minutes": max(1, (remaining + 59) // 60),
        })
    return out


def multiplier(learner_id: int, kind: str) -> float:
    """Временный усилитель × постоянный бонус Minecraft × живое событие."""
    effect = "boost_xp" if kind == "xp" else "boost_coins"
    row = query_one(
        """SELECT value FROM learner_effects
            WHERE learner_id = ? AND effect = ? AND expires_at > datetime('now')""",
        (learner_id, effect),
    )
    value = 1.0
    try:
        if row:
            value *= float(row["value"])
    except (TypeError, ValueError):  # pragma: no cover - кривые данные
        pass
    perm_key = "mc_enchant" if kind == "xp" else "mc_pickaxe"
    perm = query_one(
        "SELECT 1 FROM learner_items WHERE learner_id = ? AND item_key = ?",
        (learner_id, perm_key),
    )
    if perm:
        value *= PERMANENT_XP_BOOST if kind == "xp" else PERMANENT_COIN_BOOST
    value *= event_multiplier(kind)
    return value


def apply_multiplier(learner_id: int, base: int, kind: str) -> int:
    return int(round(base * multiplier(learner_id, kind)))


def pet_stage(progress: int) -> dict[str, Any]:
    progress = max(0, int(progress or 0))
    index = 0
    for i, (threshold, _, _) in enumerate(PET_STAGES):
        if progress >= threshold:
            index = i
    threshold, name, icon = PET_STAGES[index]
    next_at = PET_STAGES[index + 1][0] if index + 1 < len(PET_STAGES) else None
    span = (next_at - threshold) if next_at else 1
    percent = 100 if next_at is None else int(100 * (progress - threshold) / max(1, span))
    return {
        "index": index + 1,
        "stage_name": name,
        "stage_icon": icon,
        "progress": progress,
        "next_at": next_at,
        "percent": max(0, min(100, percent)),
        "max": next_at is None,
    }


def decorations(learner_id: int) -> dict[str, Any]:
    """Надетые предметы для шапки сайта и профиля."""
    out: dict[str, Any] = {
        "frame": None, "frame_css": "", "title": "", "theme": "", "pet": None,
    }
    rows = query_all(
        "SELECT * FROM learner_items WHERE learner_id = ? AND equipped = 1",
        (learner_id,),
    )
    for row in rows:
        item = get_item(row["item_key"])
        if not item:
            continue
        if item["kind"] == "frame":
            out["frame"] = item["key"]
            out["frame_css"] = item["accent"]
        elif item["kind"] == "title":
            out["title"] = item["name"].replace("Титул «", "").rstrip("»")
        elif item["kind"] == "theme":
            out["theme"] = item["accent"]
        elif item["kind"] == "pet":
            stage = pet_stage(row["progress"] or 0)
            out["pet"] = {
                "key": item["key"],
                "icon": item["icon"],
                "name": item["name"],
                **stage,
            }
    return out


def available_avatars(learner_id: int) -> list[str]:
    avatars = list(AVATARS)
    for row in query_all("SELECT * FROM learner_items WHERE learner_id = ?", (learner_id,)):
        item = get_item(row["item_key"])
        if item and item["kind"] == "avatar_pack":
            for emoji in item["avatars"]:
                if emoji not in avatars:
                    avatars.append(emoji)
    return avatars


def _view(item: dict[str, Any], row, learner, day: str, *,
          featured: str | None = None,
          event: dict[str, Any] | None = None) -> dict[str, Any]:
    price = price_for(item, day, featured=featured, event=event)
    is_owned = bool(row) and (
        bool(row["quantity"] > 0) if item["repeatable"] else True
    )
    quantity = int(row["quantity"]) if row else 0
    equipped = bool(row["equipped"]) if row else False
    level = _level(learner)
    coins = int(learner["coins"] or 0)
    xp = int(learner["xp"] or 0)

    reason = ""
    if not item["repeatable"] and is_owned:
        reason = "Уже куплено"
    elif item["repeatable"] and quantity >= item["max_owned"]:
        reason = "Максимум"
    elif level < item["level"]:
        reason = f"Откроется на {item['level']} уровне"
    elif coins < price["coins"]:
        reason = f"Не хватает {price['coins'] - coins} 💰"
    elif xp < price["xp"]:
        reason = f"Не хватает {price['xp'] - xp} ⭐"

    stage = pet_stage(row["progress"] or 0) if (row and item["kind"] == "pet") else None
    return {
        **item,
        "price_coins": price["coins"],
        "price_xp": price["xp"],
        "base_coins": item["coins"],
        "discount": price["discount"],
        "owned": is_owned,
        "quantity": quantity,
        "equipped": equipped,
        "locked": level < item["level"],
        "reason": reason,
        "can_buy": not reason,
        "stage": stage,
    }


def chest_state(learner_id: int, day: str | None = None) -> dict[str, Any]:
    day = day_key(day)
    row = query_one("SELECT * FROM daily_chests WHERE learner_id = ?", (learner_id,))
    available = row is None or row["last_day"] != day
    return {
        "available": available,
        "last_day": row["last_day"] if row else None,
        "min_coins": CHEST_MIN_COINS,
        "max_coins": CHEST_MAX_COINS,
        "min_xp": CHEST_MIN_XP,
        "max_xp": CHEST_MAX_XP,
    }


# ------------------------------------------------------------ подарки
def _notify_gift(learner_id: int, gift_id: int, item: dict[str, Any] | None,
                 reason: str, message: str, gifted_by: int = 0) -> None:
    """Уведомить ребёнка и связанный аккаунт, не ломая выдачу подарка."""
    try:
        from services import notifications as notifications_service

        name = item["name"] if item else "особый подарок"
        title = "🎁 Подарок от администратора"
        body = f"Тебе подарок: {name}."
        if reason:
            body += f" За что: {reason}."
        if message:
            body += f" {message}"
        linked = query_one(
            "SELECT user_id FROM learner_accounts WHERE learner_id = ?", (learner_id,)
        )
        if linked:
            notifications_service.push(
                int(linked["user_id"]), "shop_gift", title, body,
                learner_id=learner_id, sender_id=gifted_by,
                link="/shop/#gifts",
                dedup_key=f"shop_gift:{gift_id}:user",
            )
        notifications_service.push(
            0, "shop_gift", title, body,
            learner_id=learner_id, sender_id=gifted_by,
            link="/shop/#gifts",
            dedup_key=f"shop_gift:{gift_id}:learner",
        )
    except Exception:  # pragma: no cover - уведомление не должно ломать подарок
        pass


def create_gift(learner_id: int, item_key: str, reason: str,
                message: str = "", coins: int = 0, xp: int = 0,
                gifted_by: int = 0) -> int:
    """Создать подарок. Ребёнок заберёт его сам в магазине."""
    learner = query_one("SELECT id FROM learners WHERE id = ?", (learner_id,))
    if learner is None:
        raise ShopError("no_learner", "Профиль ученика не найден", 404)
    reason = (reason or "").strip()[:500]
    if not reason:
        raise ShopError("reason_required", "Укажи, за что подарок", 400)
    item = get_item(item_key) if item_key else None
    coins = max(0, int(coins or 0))
    xp = max(0, int(xp or 0))
    if item is None and not coins and not xp:
        raise ShopError("empty_gift", "Выбери предмет или награду", 400)
    gift_id = execute(
        """INSERT INTO shop_gifts
               (learner_id, item_key, coins, xp, reason, message, gifted_by)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            learner_id, item["key"] if item else "", coins, xp,
            reason, (message or "").strip()[:500], gifted_by or 0,
        ),
    )
    _notify_gift(learner_id, gift_id, item, reason, (message or "").strip(), gifted_by)
    return gift_id


def gift_view(row, *, for_admin: bool = False) -> dict[str, Any]:
    item = get_item(row["item_key"]) if row["item_key"] else None
    data = {
        "id": int(row["id"]),
        "learner_id": int(row["learner_id"]),
        "item_key": row["item_key"] or "",
        "name": item["name"] if item else "Особый подарок",
        "icon": item["icon"] if item else "🎁",
        "tagline": item["tagline"] if item else "Награда от администратора",
        "rarity": item["rarity"] if item else "legendary",
        "rarity_name": item["rarity_name"] if item else "Особый",
        "reason": row["reason"] or "",
        "message": row["message"] or "",
        "coins": int(row["coins"] or 0),
        "xp": int(row["xp"] or 0),
        "status": row["status"],
        "created_at": row["created_at"],
        "claimed_at": row["claimed_at"],
    }
    if for_admin:
        learner = query_one("SELECT name, avatar, grade FROM learners WHERE id = ?",
                            (int(row["learner_id"]),))
        data["learner_name"] = learner["name"] if learner else "—"
        data["learner_avatar"] = learner["avatar"] if learner else "👤"
        data["learner_grade"] = learner["grade"] if learner else 0
    return data


def pending_gifts(learner_id: int) -> list[dict[str, Any]]:
    rows = query_all(
        """SELECT * FROM shop_gifts
            WHERE learner_id = ? AND status = 'pending'
            ORDER BY id""",
        (learner_id,),
    )
    return [gift_view(row) for row in rows]


def gifts_for_learner(learner_id: int, limit: int = 20) -> list[dict[str, Any]]:
    rows = query_all(
        """SELECT * FROM shop_gifts WHERE learner_id = ?
            ORDER BY id DESC LIMIT ?""",
        (learner_id, max(1, min(100, limit))),
    )
    return [gift_view(row) for row in rows]


def recent_gifts(limit: int = 30) -> list[dict[str, Any]]:
    rows = query_all(
        "SELECT * FROM shop_gifts ORDER BY id DESC LIMIT ?",
        (max(1, min(200, limit)),),
    )
    return [gift_view(row, for_admin=True) for row in rows]


def cancel_gift(gift_id: int) -> None:
    execute(
        "UPDATE shop_gifts SET status = 'cancelled' WHERE id = ? AND status = 'pending'",
        (gift_id,),
    )


def claim_gift(learner_id: int, gift_id: int) -> dict[str, Any]:
    """Забрать подарок: предмет и/или бонусные монеты с опытом."""
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM shop_gifts WHERE id = ? AND learner_id = ?",
            (gift_id, learner_id),
        ).fetchone()
        if row is None:
            raise ShopError("no_gift", "Подарок не найден", 404)
        if row["status"] != "pending":
            raise ShopError("gift_claimed", "Этот подарок уже открыт", 409)
        item = get_item(row["item_key"]) if row["item_key"] else None
        coins = int(row["coins"] or 0)
        xp = int(row["xp"] or 0)
        loot = None
        if item is not None and item["kind"] == "lootbox":
            # Подаренный ТНТ-лутбокс открывается сразу: иначе ребёнок получил бы
            # пустую коробку, ведь лутбокс не хранится в инвентаре.
            loot = _lootbox_reward()
            coins += int(loot["coins"])
            xp += int(loot["xp"])
        if coins or xp:
            conn.execute(
                "UPDATE learners SET coins = coins + ?, xp = xp + ? WHERE id = ?",
                (coins, xp, learner_id),
            )
        if item is not None and item["kind"] != "lootbox":
            _grant_item(conn, learner_id, item)
        conn.execute(
            "UPDATE shop_gifts SET status = 'claimed', claimed_at = datetime('now') "
            "WHERE id = ?",
            (gift_id,),
        )
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:  # pragma: no cover
            pass
        raise
    finally:
        conn.close()

    claimed = dict(row)
    claimed["status"] = "claimed"
    gift = gift_view(claimed)
    parts = []
    if item is not None:
        parts.append(f"{item['icon']} «{item['name']}»")
    if loot:
        parts.append(loot["label"].rstrip("!"))
    if coins:
        parts.append(f"💰 {coins} монет")
    if xp:
        parts.append(f"⭐ {xp} опыта")
    message = "Подарок открыт: " + ", ".join(parts) + "!"
    if gift["reason"]:
        message += f" За что: {gift['reason']}."
    learner = query_one("SELECT * FROM learners WHERE id = ?", (learner_id,))
    return {
        "gift": gift,
        "loot": loot,
        "message": message,
        "balance": {
            "coins": int(learner["coins"] or 0),
            "xp": int(learner["xp"] or 0),
        },
    }


def claim_all_gifts(learner_id: int) -> dict[str, Any]:
    gifts = pending_gifts(learner_id)
    opened = []
    for gift in gifts:
        opened.append(claim_gift(learner_id, int(gift["id"])))
    return {
        "count": len(opened),
        "messages": [item["message"] for item in opened],
        "message": opened[-1]["message"] if opened else "Подарков пока нет.",
        "gifts": [item["gift"] for item in opened],
    }


def shop_state(learner_id: int, day: str | None = None) -> dict[str, Any]:
    day = day_key(day)
    learner = query_one("SELECT * FROM learners WHERE id = ?", (learner_id,))
    if learner is None:
        raise ShopError("no_learner", "Профиль ученика не найден", 404)
    owned = owned_map(learner_id)
    featured = featured_key(day)
    event = active_event(day)
    price_event = event or {}
    views = [
        _view(item, owned.get(item["key"]), learner, day,
              featured=featured, event=price_event)
        for item in catalog_items()
    ]
    by_key = {view["key"]: view for view in views}
    categories = []
    for category in CATEGORIES:
        items = [view for view in views if view["category"] == category["key"]]
        if items:
            categories.append({**category, "items": items})
    permanent = [view for view in views if not view["repeatable"]]
    collected = len([view for view in permanent if view["owned"]])
    decor = decorations(learner_id)
    pending = pending_gifts(learner_id)
    return {
        "balance": {
            "coins": int(learner["coins"] or 0),
            "xp": int(learner["xp"] or 0),
        },
        "total_xp": total_xp(learner),
        "level": _level(learner),
        "level_info": level_info(total_xp(learner)),
        "items": views,
        "by_key": by_key,
        "categories": categories,
        "featured": by_key.get(featured),
        "discount_percent": DISCOUNT_PERCENT,
        "effects": active_effects(learner_id),
        "decor": decor,
        "avatars": available_avatars(learner_id),
        "chest": chest_state(learner_id, day),
        "collection": {
            "owned": collected,
            "total": len(permanent),
            "percent": int(100 * collected / len(permanent)) if permanent else 0,
        },
        "pet": decor.get("pet"),
        "event": event,
        "announcement": get_setting("announcement", ""),
        "gifts": pending,
        "gift_count": len(pending),
        "gift_history": gifts_for_learner(learner_id, 8),
    }


def headline(learner_id: int) -> dict[str, Any]:
    """Короткая сводка для карты тем и главной страницы."""
    learner = query_one("SELECT * FROM learners WHERE id = ?", (learner_id,))
    if learner is None:
        return {}
    day = day_key()
    featured = get_item(featured_key(day))
    price = price_for(featured, day) if featured else None
    return {
        "coins": int(learner["coins"] or 0),
        "xp": int(learner["xp"] or 0),
        "featured": featured,
        "featured_price": price,
        "chest_available": chest_state(learner_id, day)["available"],
    }


# ----------------------------------------------------------------- покупки
def _check_can_buy(conn, learner_id: int, item: dict[str, Any], price: dict[str, int]):
    if not item.get("is_active", 1):
        raise ShopError("item_disabled", "Этот товар сейчас недоступен", 404)
    learner = conn.execute("SELECT * FROM learners WHERE id = ?", (learner_id,)).fetchone()
    if learner is None:
        raise ShopError("no_learner", "Профиль ученика не найден", 404)
    row = conn.execute(
        "SELECT * FROM learner_items WHERE learner_id = ? AND item_key = ?",
        (learner_id, item["key"]),
    ).fetchone()
    if not item["repeatable"] and row is not None:
        raise ShopError("already_owned", "Этот предмет уже есть в коллекции", 409)
    if item["repeatable"] and row is not None and row["quantity"] >= item["max_owned"]:
        raise ShopError("max_owned", "Больше купить нельзя — уже максимум", 409)
    if _level(learner) < item["level"]:
        raise ShopError(
            "level_locked",
            f"Предмет откроется на {item['level']} уровне",
            403,
        )
    if int(learner["coins"] or 0) < price["coins"]:
        raise ShopError("not_enough_coins", "Не хватает монет", 409)
    if int(learner["xp"] or 0) < price["xp"]:
        raise ShopError("not_enough_xp", "Не хватает опыта", 409)
    return learner, row


def _activate_boost(conn, learner_id: int, item: dict[str, Any]) -> None:
    minutes = int(item["duration_minutes"] or 30)
    row = conn.execute(
        "SELECT expires_at FROM learner_effects WHERE learner_id = ? AND effect = ?",
        (learner_id, item["key"]),
    ).fetchone()
    start = _now()
    expires = _parse_ts(row["expires_at"]) if row else None
    if expires and expires > start:
        start = expires
    finish = (start + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT INTO learner_effects (learner_id, effect, value, expires_at, updated_at)
           VALUES (?, ?, ?, ?, datetime('now'))
           ON CONFLICT(learner_id, effect) DO UPDATE SET
               value = excluded.value,
               expires_at = excluded.expires_at,
               updated_at = datetime('now')""",
        (learner_id, item["key"], float(item["value"] or 2.0), finish),
    )


def _grant_item(conn, learner_id: int, item: dict[str, Any]) -> bool:
    """Выдать предмет без списания денег. Возвращает True, если он надет."""
    row = conn.execute(
        "SELECT * FROM learner_items WHERE learner_id = ? AND item_key = ?",
        (learner_id, item["key"]),
    ).fetchone()
    equipped = False
    if item["kind"] == "boost":
        _activate_boost(conn, learner_id, item)
    elif item["kind"] == "lootbox":
        return False
    elif item["repeatable"]:
        add = int(item["value"] or 1)
        if row is None:
            conn.execute(
                "INSERT INTO learner_items (learner_id, item_key, quantity) "
                "VALUES (?, ?, ?)",
                (learner_id, item["key"], add),
            )
        else:
            conn.execute(
                "UPDATE learner_items SET quantity = quantity + ?, "
                "updated_at = datetime('now') WHERE id = ?",
                (add, row["id"]),
            )
    else:
        if row is None:
            conn.execute(
                "INSERT INTO learner_items (learner_id, item_key, quantity, slot) "
                "VALUES (?, ?, 1, ?)",
                (learner_id, item["key"], item["slot"]),
            )
        if item["slot"]:
            busy = conn.execute(
                "SELECT 1 FROM learner_items WHERE learner_id = ? AND slot = ? "
                "AND equipped = 1 AND item_key <> ?",
                (learner_id, item["slot"], item["key"]),
            ).fetchone()
            # Питомца не меняем молча: ребёнок сам выберет, кто гуляет с ним.
            if not busy or item["slot"] != "pet":
                conn.execute(
                    "UPDATE learner_items SET equipped = 0 "
                    "WHERE learner_id = ? AND slot = ?",
                    (learner_id, item["slot"]),
                )
                conn.execute(
                    "UPDATE learner_items SET equipped = 1 "
                    "WHERE learner_id = ? AND item_key = ?",
                    (learner_id, item["key"]),
                )
                equipped = True
    return equipped


def _lootbox_reward() -> dict[str, Any]:
    """ТНТ-сюрприз: необидный рандом, всегда что-то полезное."""
    roll = random.SystemRandom().randint(1, 100)
    if roll <= 8:
        return {"coins": 150, "xp": 25, "label": "💥 ДЖЕКПОТ!"}
    if roll <= 35:
        return {"coins": 0, "xp": 35, "label": "⭐ Опытный взрыв!"}
    if roll <= 70:
        return {"coins": 70, "xp": 0, "label": "💰 Монетный взрыв!"}
    return {"coins": 35, "xp": 15, "label": "🎉 Отличный взрыв!"}


def purchase(learner_id: int, key: str, day: str | None = None) -> dict[str, Any]:
    """Купить предмет. Все проверки и списание — в одной транзакции."""
    item = get_item(key)
    if item is None:
        raise ShopError("unknown_item", "Такого товара нет в магазине", 404)
    day = day_key(day)
    price = price_for(item, day)

    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _check_can_buy(conn, learner_id, item, price)

        conn.execute(
            "UPDATE learners SET coins = coins - ?, xp = xp - ?, xp_spent = xp_spent + ? "
            "WHERE id = ?",
            (price["coins"], price["xp"], price["xp"], learner_id),
        )
        conn.execute(
            """INSERT INTO shop_purchases (learner_id, item_key, paid_coins, paid_xp)
               VALUES (?, ?, ?, ?)""",
            (learner_id, item["key"], price["coins"], price["xp"]),
        )

        loot = None
        if item["kind"] == "lootbox":
            loot = _lootbox_reward()
            conn.execute(
                "UPDATE learners SET coins = coins + ?, xp = xp + ? WHERE id = ?",
                (loot["coins"], loot["xp"], learner_id),
            )
            equipped = False
        else:
            equipped = _grant_item(conn, learner_id, item)
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:  # pragma: no cover - соединение уже закрыто
            pass
        raise
    finally:
        conn.close()

    learner = query_one("SELECT * FROM learners WHERE id = ?", (learner_id,))
    message = _purchase_message(item, equipped=equipped, loot=loot)
    return {
        "item": item,
        "price": price,
        "equipped": equipped,
        "loot": loot,
        "message": message,
        "balance": {
            "coins": int(learner["coins"] or 0),
            "xp": int(learner["xp"] or 0),
        },
        "total_xp": total_xp(learner),
        "level": _level(learner),
    }


def _purchase_message(item: dict[str, Any], equipped: bool,
                      loot: dict[str, Any] | None = None) -> str:
    if item["kind"] == "lootbox" and loot:
        parts = []
        if loot["coins"]:
            parts.append(f"💰 {loot['coins']} монет")
        if loot["xp"]:
            parts.append(f"⭐ {loot['xp']} опыта")
        return f"{item['icon']} {loot['label']} " + " и ".join(parts) + "!"
    if item["kind"] == "boost":
        minutes = item["duration_minutes"] or 30
        return f"{item['icon']} «{item['name']}» включён на {minutes} минут!"
    if item["kind"] == "hint_pack":
        return f"💡 В копилке +{int(item['value'] or 3)} подсказок. Они ждут тебя в заданиях!"
    if item["kind"] == "shield":
        return "🛡 Щит серии готов. Один пропущенный день больше не страшен!"
    if item["kind"] == "boost_perm":
        if item["key"] == "mc_pickaxe":
            return f"{item['icon']} Кирка добывает на 15% больше монет — навсегда!"
        return f"{item['icon']} Зачарование включено: +15% опыта навсегда!"
    if item["kind"] == "pet":
        if equipped:
            return f"{item['icon']} «{item['name']}» теперь живёт с тобой!"
        return f"{item['icon']} «{item['name']}» теперь в твоей коллекции!"
    if equipped:
        return f"{item['icon']} «{item['name']}» куплено и сразу надето!"
    return f"{item['icon']} «{item['name']}» теперь твоё!"


# ------------------------------------------------------------ надевание
def equip(learner_id: int, key: str) -> dict[str, Any]:
    item = get_item(key)
    if item is None or not item["slot"]:
        raise ShopError("not_equippable", "Этот предмет нельзя надеть", 400)
    row = query_one(
        "SELECT * FROM learner_items WHERE learner_id = ? AND item_key = ?",
        (learner_id, key),
    )
    if row is None:
        raise ShopError("not_owned", "Сначала купи этот предмет", 403)
    execute(
        "UPDATE learner_items SET equipped = 0, updated_at = datetime('now') "
        "WHERE learner_id = ? AND slot = ? AND item_key <> ?",
        (learner_id, item["slot"], key),
    )
    execute(
        "UPDATE learner_items SET equipped = 1, updated_at = datetime('now') "
        "WHERE learner_id = ? AND item_key = ?",
        (learner_id, key),
    )
    return {"item": item, "message": f"{item['icon']} «{item['name']}» надето!"}


def unequip(learner_id: int, slot: str) -> None:
    execute(
        "UPDATE learner_items SET equipped = 0, updated_at = datetime('now') "
        "WHERE learner_id = ? AND slot = ?",
        (learner_id, slot),
    )


def set_avatar(learner_id: int, avatar: str) -> str:
    avatar = (avatar or "").strip()
    if avatar not in available_avatars(learner_id):
        raise ShopError("avatar_locked", "Этот аватар ещё не открыт", 403)
    execute("UPDATE learners SET avatar = ? WHERE id = ?", (avatar, learner_id))
    return avatar


# ------------------------------------------------------------ подсказки
def hints_budget(learner_id: int) -> tuple[int, int]:
    """(базовые подсказки на задание, дополнительные из мешка)."""
    base = int(get_config().MAX_HINTS)
    owned = owned_map(learner_id)
    if "smart_hint" in owned:
        base += 1
    row = owned.get("hint_pack")
    credits = int(row["quantity"]) if row else 0
    return base, max(0, credits)


def consume_hint_credit(learner_id: int) -> bool:
    row = query_one(
        "SELECT id, quantity FROM learner_items "
        "WHERE learner_id = ? AND item_key = 'hint_pack' AND quantity > 0",
        (learner_id,),
    )
    if row is None:
        return False
    execute(
        "UPDATE learner_items SET quantity = quantity - 1, updated_at = datetime('now') "
        "WHERE id = ? AND quantity > 0",
        (row["id"],),
    )
    return True


# ------------------------------------------------------------ щит серии
def consume_shield(learner_id: int) -> bool:
    row = query_one(
        "SELECT id FROM learner_items "
        "WHERE learner_id = ? AND item_key = 'streak_shield' AND quantity > 0",
        (learner_id,),
    )
    if row is None:
        return False
    execute(
        "UPDATE learner_items SET quantity = quantity - 1, updated_at = datetime('now') "
        "WHERE id = ? AND quantity > 0",
        (row["id"],),
    )
    return True


# ------------------------------------------------------------ питомец
def bump_pet(learner_id: int) -> None:
    execute(
        "UPDATE learner_items SET progress = progress + 1, updated_at = datetime('now') "
        "WHERE learner_id = ? AND slot = 'pet' AND equipped = 1",
        (learner_id,),
    )


# ------------------------------------------------------------ сундук
def claim_chest(learner_id: int, day: str | None = None) -> dict[str, Any]:
    day = day_key(day)
    digest = hashlib.sha256(f"chest:{day}:{learner_id}".encode("utf-8")).digest()
    coins = CHEST_MIN_COINS + digest[0] % (CHEST_MAX_COINS - CHEST_MIN_COINS + 1)
    xp = CHEST_MIN_XP + digest[1] % (CHEST_MAX_XP - CHEST_MIN_XP + 1)

    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        learner = conn.execute(
            "SELECT * FROM learners WHERE id = ?", (learner_id,)
        ).fetchone()
        if learner is None:
            raise ShopError("no_learner", "Профиль ученика не найден", 404)
        row = conn.execute(
            "SELECT * FROM daily_chests WHERE learner_id = ?", (learner_id,)
        ).fetchone()
        if row is not None and row["last_day"] == day:
            raise ShopError("chest_claimed", "Сегодня сундук уже открыт", 409)
        conn.execute(
            "UPDATE learners SET coins = coins + ?, xp = xp + ? WHERE id = ?",
            (coins, xp, learner_id),
        )
        conn.execute(
            """INSERT INTO daily_chests (learner_id, last_day, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(learner_id) DO UPDATE SET
                   last_day = excluded.last_day,
                   updated_at = datetime('now')""",
            (learner_id, day),
        )
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:  # pragma: no cover
            pass
        raise
    finally:
        conn.close()

    learner = query_one("SELECT * FROM learners WHERE id = ?", (learner_id,))
    return {
        "coins": coins,
        "xp": xp,
        "message": f"🎁 В сундуке {coins} монет и {xp} опыта!",
        "balance": {
            "coins": int(learner["coins"] or 0),
            "xp": int(learner["xp"] or 0),
        },
    }


# ------------------------------------------------------------ очистка
def reset_learner(learner_id: int) -> None:
    for table in ("learner_items", "shop_purchases", "learner_effects", "daily_chests"):
        execute(f"DELETE FROM {table} WHERE learner_id = ?", (learner_id,))
    # Подарки — история отношений с ребёнком: выданные оставляем, ожидающие
    # отменяем, чтобы после сброса не выдать предметы старого прогресса.
    execute(
        "UPDATE shop_gifts SET status = 'cancelled' "
        "WHERE learner_id = ? AND status = 'pending'",
        (learner_id,),
    )


def gift_api(gift: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "id", "name", "icon", "tagline", "rarity", "rarity_name", "reason",
        "message", "coins", "xp", "status", "created_at", "claimed_at",
    )
    return {key: gift.get(key) for key in fields}


def api_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Компактная сериализация для Android."""
    fields = (
        "key", "category", "kind", "slot", "name", "icon", "tagline",
        "description", "price_coins", "price_xp", "discount", "level",
        "owned", "quantity", "equipped", "locked", "reason", "can_buy",
        "repeatable", "avatars", "stage", "rarity", "rarity_name",
        "rarity_icon", "base_coins",
    )

    def strip(view: dict[str, Any]) -> dict[str, Any]:
        return {key: view.get(key) for key in fields}

    return {
        "balance": state["balance"],
        "total_xp": state["total_xp"],
        "level": state["level"],
        "level_info": state["level_info"],
        "categories": [
            {
                "key": category["key"],
                "name": category["name"],
                "icon": category["icon"],
                "items": [strip(view) for view in category["items"]],
            }
            for category in state["categories"]
        ],
        "featured": strip(state["featured"]) if state.get("featured") else None,
        "discount_percent": state["discount_percent"],
        "effects": state["effects"],
        "decor": state["decor"],
        "avatars": state["avatars"],
        "chest": state["chest"],
        "collection": state["collection"],
        "pet": state.get("pet"),
        "event": state.get("event"),
        "announcement": state.get("announcement") or "",
        "gifts": [gift_api(gift) for gift in state.get("gifts", [])],
        "gift_count": state.get("gift_count", 0),
        "gift_history": [gift_api(gift) for gift in state.get("gift_history", [])],
    }
