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
    {"key": "style", "name": "Стиль", "icon": "🎨",
     "hint": "Аватары, рамки, титулы и темы оформления"},
    {"key": "pets", "name": "Питомцы", "icon": "🐾",
     "hint": "Друзья, которые растут вместе с тобой"},
]

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
          duration_minutes: int = 0) -> dict[str, Any]:
    return {
        "key": key,
        "category": "perks",
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
           xp: int = 0, level: int = 1, avatars: list[str] | None = None) -> dict[str, Any]:
    return {
        "key": key,
        "category": "style",
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
         description: str, *, xp: int = 0, level: int = 1) -> dict[str, Any]:
    return {
        "key": key,
        "category": "pets",
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
    return CATALOG_BY_KEY.get(str(key or "").strip())


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


# ------------------------------------------------------- ежедневная витрина
def featured_key(day: str | None = None) -> str:
    """Товар дня — детерминированно, чтобы у всех было одинаково."""
    day = day_key(day)
    keys = [item["key"] for item in CATALOG if item["coins"] > 0]
    digest = hashlib.sha256(f"shop-featured:{day}".encode("utf-8")).digest()
    return keys[int.from_bytes(digest[:4], "big") % len(keys)]


def price_for(item: dict[str, Any], day: str | None = None) -> dict[str, int]:
    day = day_key(day)
    coins = int(item["coins"])
    discount = 0
    if coins and item["key"] == featured_key(day):
        discount = DISCOUNT_PERCENT
        coins = max(1, round(coins * (100 - discount) / 100))
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
    effect = "boost_xp" if kind == "xp" else "boost_coins"
    row = query_one(
        """SELECT value FROM learner_effects
            WHERE learner_id = ? AND effect = ? AND expires_at > datetime('now')""",
        (learner_id, effect),
    )
    try:
        return float(row["value"]) if row else 1.0
    except (TypeError, ValueError):  # pragma: no cover - кривые данные
        return 1.0


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


def _view(item: dict[str, Any], row, learner, day: str) -> dict[str, Any]:
    price = price_for(item, day)
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


def shop_state(learner_id: int, day: str | None = None) -> dict[str, Any]:
    day = day_key(day)
    learner = query_one("SELECT * FROM learners WHERE id = ?", (learner_id,))
    if learner is None:
        raise ShopError("no_learner", "Профиль ученика не найден", 404)
    owned = owned_map(learner_id)
    views = [_view(item, owned.get(item["key"]), learner, day) for item in CATALOG]
    by_key = {view["key"]: view for view in views}
    categories = []
    for category in CATEGORIES:
        items = [view for view in views if view["category"] == category["key"]]
        categories.append({**category, "items": items})
    permanent = [view for view in views if not view["repeatable"]]
    collected = len([view for view in permanent if view["owned"]])
    decor = decorations(learner_id)
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
        "featured": by_key.get(featured_key(day)),
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
        learner, row = _check_can_buy(conn, learner_id, item, price)

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

        equipped = False
        if item["kind"] == "boost":
            _activate_boost(conn, learner_id, item)
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
    message = _purchase_message(item, equipped=equipped)
    return {
        "item": item,
        "price": price,
        "equipped": equipped,
        "message": message,
        "balance": {
            "coins": int(learner["coins"] or 0),
            "xp": int(learner["xp"] or 0),
        },
        "total_xp": total_xp(learner),
        "level": _level(learner),
    }


def _purchase_message(item: dict[str, Any], equipped: bool) -> str:
    if item["kind"] == "boost":
        minutes = item["duration_minutes"] or 30
        return f"{item['icon']} «{item['name']}» включён на {minutes} минут!"
    if item["kind"] == "hint_pack":
        return "💡 В копилке +3 подсказки. Они ждут тебя в заданиях!"
    if item["kind"] == "shield":
        return "🛡 Щит серии готов. Один пропущенный день больше не страшен!"
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


def api_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Компактная сериализация для Android."""
    fields = (
        "key", "category", "kind", "slot", "name", "icon", "tagline",
        "description", "price_coins", "price_xp", "discount", "level",
        "owned", "quantity", "equipped", "locked", "reason", "can_buy",
        "repeatable", "avatars", "stage",
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
    }
