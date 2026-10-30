"""Магазин: витрина, покупки, надевание предметов и сундук дня."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from services import learners as learners_service
from services import shop as shop_service

bp = Blueprint("shop", __name__, url_prefix="/shop")


def _learner():
    return learners_service.current_learner()


@bp.route("/")
def index():
    learner = _learner()
    if learner is None:
        return redirect(url_for("main.welcome"))
    state = shop_service.shop_state(learner["id"])
    return render_template(
        "shop.html",
        learner=learner,
        shop=state,
        chest_opened=request.args.get("chest") == "1",
        bought=request.args.get("bought", ""),
        gift_opened=request.args.get("gift", ""),
    )


@bp.post("/buy")
def buy():
    learner = _learner()
    if learner is None:
        return redirect(url_for("main.welcome"))
    key = (request.form.get("item_key") or "").strip()
    try:
        result = shop_service.purchase(learner["id"], key)
    except shop_service.ShopError as exc:
        flash(exc.message, "error")
        return redirect(url_for("shop.index") + f"#{key}")
    flash(result["message"], "success")
    return redirect(url_for("shop.index", bought=key) + f"#{key}")


@bp.post("/equip")
def equip():
    learner = _learner()
    if learner is None:
        return redirect(url_for("main.welcome"))
    key = (request.form.get("item_key") or "").strip()
    slot = (request.form.get("slot") or "").strip()
    try:
        if key:
            result = shop_service.equip(learner["id"], key)
            flash(result["message"], "success")
        elif slot:
            shop_service.unequip(learner["id"], slot)
            flash("Предмет снят.", "info")
    except shop_service.ShopError as exc:
        flash(exc.message, "error")
    return redirect(url_for("shop.index"))


@bp.post("/avatar")
def avatar():
    learner = _learner()
    if learner is None:
        return redirect(url_for("main.welcome"))
    try:
        emoji = shop_service.set_avatar(
            learner["id"], request.form.get("avatar") or ""
        )
        flash(f"Новый аватар: {emoji}", "success")
    except shop_service.ShopError as exc:
        flash(exc.message, "error")
    return redirect(url_for("shop.index"))


@bp.post("/gift/<int:gift_id>/claim")
def claim_gift(gift_id: int):
    learner = _learner()
    if learner is None:
        return redirect(url_for("main.welcome"))
    try:
        result = shop_service.claim_gift(learner["id"], gift_id)
        flash(result["message"], "success")
        return redirect(url_for("shop.index", gift=gift_id) + "#gifts")
    except shop_service.ShopError as exc:
        flash(exc.message, "error")
    return redirect(url_for("shop.index") + "#gifts")


@bp.post("/chest")
def chest():
    learner = _learner()
    if learner is None:
        return redirect(url_for("main.welcome"))
    try:
        result = shop_service.claim_chest(learner["id"])
        flash(result["message"], "success")
    except shop_service.ShopError as exc:
        flash(exc.message, "info")
    return redirect(url_for("shop.index", chest=1))
