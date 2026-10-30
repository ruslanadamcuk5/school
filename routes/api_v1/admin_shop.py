"""API: админка магазина — рейтинг стараний, подарки, каталог и события.

Повторяет возможности веб-страницы ``/admin/shop``, но отдаёт данные JSON,
чтобы всё управление магазином было доступно из Android-приложения.
"""
from __future__ import annotations

from datetime import date, timedelta

from flask import jsonify

from database import execute, query_all
from services import shop as shop_service
from services import shop_insights

from . import bp
from .deps import current_user, fail, json_body, require_user

EVENT_KINDS = {"double_coins", "double_xp", "discount"}

REASONS = [
    {"icon": "🔥", "text": "Занимался каждый день недели"},
    {"icon": "⚡", "text": "Держит серию дней"},
    {"icon": "🎯", "text": "Высокая точность ответов"},
    {"icon": "📈", "text": "Активность выросла"},
    {"icon": "🌱", "text": "Вернулся после паузы"},
    {"icon": "💪", "text": "Много заданий за неделю"},
]


def _log(action: str, entity: str = "", entity_id: str = "", details: str = "") -> None:
    user = current_user()
    execute(
        "INSERT INTO audit_log (user_id, action, entity, entity_id, details) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            int(user["id"]) if user else None,
            action,
            entity,
            entity_id,
            details,
        ),
    )


def _event_payload(row) -> dict:
    data = dict(row)
    return {
        "id": int(data["id"]),
        "title": data.get("title") or "",
        "description": data.get("description") or "",
        "icon": data.get("icon") or "🎉",
        "kind": data.get("kind") or "double_coins",
        "value": float(data.get("value") or 0),
        "starts_on": data.get("starts_on"),
        "ends_on": data.get("ends_on"),
        "is_active": bool(data.get("is_active")),
        "created_at": data.get("created_at"),
    }


def _item_payload(item: dict, override: dict | None) -> dict:
    fields = (
        "key", "category", "kind", "slot", "name", "icon", "tagline",
        "description", "coins", "xp", "level", "rarity", "rarity_name",
        "rarity_icon",
    )
    data = {field: item.get(field) for field in fields}
    data["is_active"] = bool(item.get("is_active", 1))
    data["avatars"] = item.get("avatars") or []
    data["final_coins"] = shop_service.price_for(item)["coins"]
    data["override"] = override
    return data


def _payload() -> dict:
    """Полное состояние админки магазина одним ответом."""
    overrides = shop_service.overrides_map()
    catalog = shop_service.catalog_items(active_only=False)
    events = query_all(
        "SELECT * FROM shop_events ORDER BY is_active DESC, id DESC LIMIT 20"
    )
    today = date.today()
    return {
        "summary": shop_insights.summary(),
        "board": shop_insights.leaderboard(),
        "catalog": [
            _item_payload(item, overrides.get(item["key"]))
            for item in catalog
        ],
        "categories": [
            {
                "key": category["key"],
                "name": category["name"],
                "icon": category["icon"],
            }
            for category in shop_service.CATEGORIES
        ],
        "events": [_event_payload(row) for row in events],
        "gifts": shop_service.recent_gifts(40),
        "featured_key": shop_service.featured_key(),
        "announcement": shop_service.get_setting("announcement", ""),
        "reasons": REASONS,
        "today": today.isoformat(),
        "default_end": (today + timedelta(days=2)).isoformat(),
    }


def _ok(message: str = "", status: int = 200):
    data = {"ok": True, **_payload()}
    if message:
        data["message"] = message
    return jsonify(data), status


def _changed(message: str = ""):
    """Ответ на изменение: сообщение и свежее состояние магазина."""
    data = {"ok": True, "shop": _payload()}
    if message:
        data["message"] = message
    return jsonify(data)


def _float(value, default: float) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _int(value, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


@bp.get("/admin/shop")
@require_user("admin")
def shop_admin_get():
    return _ok()


# ------------------------------------------------------------------ каталог
@bp.post("/admin/shop/items/<item_key>")
@require_user("admin")
def shop_admin_save_item(item_key: str):
    data = json_body()
    try:
        shop_service.save_override(item_key, data)
    except shop_service.ShopError as exc:
        fail(exc.status, exc.code, exc.message)
    _log("update", "shop_item", item_key, str(data.get("name") or ""))
    return _changed("Товар обновлён")


@bp.post("/admin/shop/items/<item_key>/reset")
@require_user("admin")
def shop_admin_reset_item(item_key: str):
    if shop_service.get_item(item_key) is None:
        fail(404, "unknown_item", "Такого товара нет в магазине")
    shop_service.reset_override(item_key)
    _log("reset", "shop_item", item_key)
    return _changed("Настройки товара сброшены к каталогу")


# ------------------------------------------------------------------ витрина
@bp.put("/admin/shop/featured")
@require_user("admin")
def shop_admin_featured():
    key = str(json_body().get("item_key") or "").strip()
    if key and shop_service.get_item(key) is None:
        fail(404, "unknown_item", "Такого товара нет в магазине")
    shop_service.set_setting("featured_key", key)
    shop_service.set_setting(
        "featured_day", date.today().isoformat() if key else ""
    )
    _log("update", "shop_featured", key)
    return _changed("Товар дня обновлён")


@bp.put("/admin/shop/announcement")
@require_user("admin")
def shop_admin_announcement():
    text = str(json_body().get("announcement") or "").strip()[:300]
    shop_service.set_setting("announcement", text)
    _log("update", "shop_settings", "announcement")
    return _changed("Объявление для детей сохранено")


# ------------------------------------------------------------------ события
@bp.post("/admin/shop/events")
@require_user("admin")
def shop_admin_create_event():
    data = json_body()
    title = str(data.get("title") or "").strip()
    if not title:
        fail(400, "title_required", "Придумай название события")
    kind = str(data.get("kind") or "double_coins").strip()
    if kind not in EVENT_KINDS:
        kind = "double_coins"
    starts_on = str(data.get("starts_on") or date.today().isoformat())[:10]
    ends_on = str(data.get("ends_on") or starts_on)[:10]
    if ends_on < starts_on:
        fail(400, "bad_dates", "Дата окончания раньше начала")
    value = _float(data.get("value"), 2.0)
    if kind == "discount":
        value = max(5.0, min(70.0, value))
    else:
        value = max(1.1, min(5.0, value))
    event_id = execute(
        """INSERT INTO shop_events
               (title, description, icon, kind, value, starts_on, ends_on,
                is_active, created_by)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
        (
            title[:120],
            str(data.get("description") or "").strip()[:500],
            str(data.get("icon") or "🎉").strip()[:8],
            kind,
            value,
            starts_on,
            ends_on,
            current_user()["id"] if current_user() else None,
        ),
    )
    _log("create", "shop_event", str(event_id), title)
    return _changed("Живое событие запущено")


@bp.post("/admin/shop/events/<int:event_id>/stop")
@require_user("admin")
def shop_admin_stop_event(event_id: int):
    execute("UPDATE shop_events SET is_active = 0 WHERE id = ?", (event_id,))
    _log("update", "shop_event", str(event_id), "stopped")
    return _changed("Событие остановлено")


# ------------------------------------------------------------------ подарки
@bp.post("/admin/shop/gifts")
@require_user("admin")
def shop_admin_create_gift():
    data = json_body()
    learner_id = _int(data.get("learner_id"))
    try:
        gift_id = shop_service.create_gift(
            learner_id,
            str(data.get("item_key") or "").strip(),
            str(data.get("reason") or ""),
            str(data.get("message") or ""),
            max(0, _int(data.get("coins"))),
            max(0, _int(data.get("xp"))),
            gifted_by=current_user()["id"] if current_user() else 0,
        )
    except shop_service.ShopError as exc:
        fail(exc.status, exc.code, exc.message)
    _log(
        "gift",
        "learner",
        str(learner_id),
        f"{str(data.get('item_key') or '').strip()}:{str(data.get('reason') or '')[:80]}",
    )
    return _changed(
        f"Подарок #{gift_id} отправлен — ребёнок увидит его в магазине"
    )


@bp.post("/admin/shop/gifts/<int:gift_id>/cancel")
@require_user("admin")
def shop_admin_cancel_gift(gift_id: int):
    shop_service.cancel_gift(gift_id)
    _log("update", "shop_gift", str(gift_id), "cancelled")
    return _changed("Подарок отменён")
