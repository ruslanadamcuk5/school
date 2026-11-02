"""API: живой питомец ученика для Android.

Питомец растёт от верных ответов, а раз в день его можно погладить и получить
немного опыта. Тексты-подсказки приходят с сервера, чтобы сайт и приложение
говорили одинаково.
"""
from __future__ import annotations

from flask import jsonify

from services import shop as shop_service

from . import bp
from .deps import fail, learner, require_learner


@bp.get("/pet")
@require_learner
def pet_get():
    profile = learner()
    try:
        return jsonify(
            {"ok": True, **shop_service.pet_state(int(profile["id"]))}
        )
    except shop_service.ShopError as exc:
        fail(exc.status, exc.code, exc.message)


@bp.post("/pet/pat")
@require_learner
def pet_pat():
    profile = learner()
    try:
        return jsonify(
            {"ok": True, **shop_service.pat_pet(int(profile["id"]))}
        )
    except shop_service.ShopError as exc:
        fail(exc.status, exc.code, exc.message)
