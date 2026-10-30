"""API: магазин для Android (1–4 классы).

Каталог живёт в коде, покупки за монеты и опыт, ежедневный сундук,
усилители, рамки/титулы/темы, аватары и питомцы.
"""
from __future__ import annotations

from flask import jsonify

from services import shop as shop_service

from . import bp
from .deps import fail, json_body, learner, require_learner


@bp.get("/shop")
@require_learner
def shop_get():
    profile = learner()
    try:
        state = shop_service.shop_state(int(profile["id"]))
        return jsonify({"ok": True, **shop_service.api_payload(state)})
    except shop_service.ShopError as exc:
        fail(exc.status, exc.code, exc.message)


@bp.post("/shop/buy")
@require_learner
def shop_buy():
    profile = learner()
    body = json_body()
    key = (body.get("item_key") or body.get("key") or "").strip()
    if not key:
        fail(400, "bad_request", "Не указан товар")
    try:
        result = shop_service.purchase(int(profile["id"]), key)
        state = shop_service.shop_state(int(profile["id"]))
        return jsonify({"ok": True, **result, "shop": shop_service.api_payload(state)})
    except shop_service.ShopError as exc:
        fail(exc.status, exc.code, exc.message)


@bp.post("/shop/equip")
@require_learner
def shop_equip():
    profile = learner()
    body = json_body()
    key = (body.get("item_key") or body.get("key") or "").strip()
    slot = (body.get("slot") or "").strip()
    try:
        if key:
            result = shop_service.equip(int(profile["id"]), key)
        elif slot:
            shop_service.unequip(int(profile["id"]), slot)
            result = {"message": "Предмет снят."}
        else:
            fail(400, "bad_request", "Укажи предмет или слот")
        state = shop_service.shop_state(int(profile["id"]))
        return jsonify({"ok": True, **result, "shop": shop_service.api_payload(state)})
    except shop_service.ShopError as exc:
        fail(exc.status, exc.code, exc.message)


@bp.post("/shop/avatar")
@require_learner
def shop_avatar():
    profile = learner()
    body = json_body()
    try:
        emoji = shop_service.set_avatar(int(profile["id"]), body.get("avatar") or "")
        state = shop_service.shop_state(int(profile["id"]))
        return jsonify({"ok": True, "avatar": emoji, "shop": shop_service.api_payload(state)})
    except shop_service.ShopError as exc:
        fail(exc.status, exc.code, exc.message)


@bp.post("/shop/chest")
@require_learner
def shop_chest():
    profile = learner()
    try:
        result = shop_service.claim_chest(int(profile["id"]))
        state = shop_service.shop_state(int(profile["id"]))
        return jsonify({"ok": True, **result, "shop": shop_service.api_payload(state)})
    except shop_service.ShopError as exc:
        fail(exc.status, exc.code, exc.message)
