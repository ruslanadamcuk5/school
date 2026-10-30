"""Тесты магазина: покупки за опыт и монеты, эффекты, сундук, API.

Уровень должен считаться по всему заработанному опыту (xp + xp_spent),
поэтому покупка не понижает ребёнка в уровне. Эти тесты фиксируют правило.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP_DB = os.path.join(tempfile.gettempdir(), "edu_math_shop_test.db")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DATABASE_PATH", _TMP_DB)
os.environ.setdefault("SECRET_KEY", "shop-test-secret")

from database import execute, init_db, query_one  # noqa: E402
from services import learners as learners_service  # noqa: E402
from services import progress as progress_service  # noqa: E402
from services import shop as shop_service  # noqa: E402


def fresh_db() -> None:
    os.environ["DATABASE_PATH"] = _TMP_DB
    for suffix in ("", "-wal", "-shm"):
        path = _TMP_DB + suffix
        if os.path.exists(path):
            os.remove(path)
    init_db()


def make_learner(
    coins: int = 1000,
    xp: int = 1000,
    grade: int = 3,
    xp_spent: int = 0,
) -> int:
    learner_id = learners_service.create_learner("Тест", grade=grade)
    execute(
        "UPDATE learners SET coins = ?, xp = ?, xp_spent = ? WHERE id = ?",
        (coins, xp, xp_spent, learner_id),
    )
    return learner_id


def learner_row(learner_id: int):
    return query_one("SELECT * FROM learners WHERE id = ?", (learner_id,))


class ShopTestCase(unittest.TestCase):
    """Свой файл БД, но окружение других наборов не ломаем."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._previous_db = os.environ.get("DATABASE_PATH")
        super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._previous_db is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = cls._previous_db
        super().tearDownClass()

    def setUp(self):
        fresh_db()


class TestShopService(ShopTestCase):

    def test_catalog_has_all_categories_and_unique_keys(self):
        keys = [item["key"] for item in shop_service.CATALOG]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertGreaterEqual(len(keys), 20)
        categories = {item["category"] for item in shop_service.CATALOG}
        self.assertEqual(categories, {"perks", "style", "pets"})
        for item in shop_service.CATALOG:
            self.assertTrue(item["name"] and item["icon"])
            self.assertGreaterEqual(item["coins"], 0)
            self.assertGreaterEqual(item["level"], 1)

    def test_purchase_spends_balance_but_keeps_total_level(self):
        learner_id = make_learner(coins=1000, xp=1000)
        before_level = progress_service.level_for_xp(1000)

        result = shop_service.purchase(learner_id, "theme_ocean")

        row = learner_row(learner_id)
        self.assertEqual(row["xp"], 1000 - result["price"]["xp"])
        self.assertEqual(row["xp_spent"], result["price"]["xp"])
        self.assertEqual(row["coins"], 1000 - result["price"]["coins"])
        self.assertEqual(shop_service.total_xp(row), 1000)
        self.assertEqual(progress_service.level_for_xp(shop_service.total_xp(row)), before_level)
        self.assertEqual(result["level"], before_level)

    def test_cannot_buy_without_enough_coins(self):
        learner_id = make_learner(coins=10, xp=1000)
        with self.assertRaises(shop_service.ShopError) as ctx:
            shop_service.purchase(learner_id, "frame_gold")
        self.assertEqual(ctx.exception.code, "not_enough_coins")
        row = learner_row(learner_id)
        self.assertEqual(row["coins"], 10)
        self.assertEqual(row["xp"], 1000)

    def test_level_locked_item(self):
        learner_id = make_learner(coins=5000, xp=0)
        state = shop_service.shop_state(learner_id)
        smart = state["by_key"]["smart_hint"]
        self.assertTrue(smart["locked"])
        self.assertIn("уровне", smart["reason"])
        with self.assertRaises(shop_service.ShopError) as ctx:
            shop_service.purchase(learner_id, "smart_hint")
        self.assertEqual(ctx.exception.code, "level_locked")

    def test_hint_pack_adds_credits_and_is_consumed(self):
        learner_id = make_learner(coins=1000, xp=1000)
        base, credits = shop_service.hints_budget(learner_id)
        self.assertEqual((base, credits), (3, 0))

        shop_service.purchase(learner_id, "hint_pack")
        base, credits = shop_service.hints_budget(learner_id)
        self.assertEqual((base, credits), (3, 3))

        self.assertTrue(shop_service.consume_hint_credit(learner_id))
        _, credits = shop_service.hints_budget(learner_id)
        self.assertEqual(credits, 2)

    def test_smart_hint_is_permanent_and_adds_base_hint(self):
        learner_id = make_learner(coins=1000, xp=2000)
        shop_service.purchase(learner_id, "smart_hint")
        base, _ = shop_service.hints_budget(learner_id)
        self.assertEqual(base, 4)
        with self.assertRaises(shop_service.ShopError) as ctx:
            shop_service.purchase(learner_id, "smart_hint")
        self.assertEqual(ctx.exception.code, "already_owned")

    def test_shield_saves_streak_and_is_consumed(self):
        learner_id = make_learner(coins=1000, xp=1000)
        shop_service.purchase(learner_id, "streak_shield")
        execute(
            """UPDATE learners SET streak_days = 4, last_day = date('now', '-2 day')
               WHERE id = ?""",
            (learner_id,),
        )
        progress_service.touch_day(learner_id)
        row = learner_row(learner_id)
        self.assertEqual(row["streak_days"], 5)
        shield = query_one(
            "SELECT quantity FROM learner_items WHERE learner_id = ? AND item_key = 'streak_shield'",
            (learner_id,),
        )
        self.assertEqual(shield["quantity"], 0)

    def test_xp_boost_doubles_rewards_for_a_while(self):
        learner_id = make_learner(coins=1000, xp=1000)
        shop_service.purchase(learner_id, "boost_xp")
        xp, coins = progress_service.reward_amounts(learner_id)
        self.assertEqual(xp, 20)
        self.assertEqual(coins, 2)
        self.assertTrue(shop_service.active_effects(learner_id))

    def test_chest_can_be_opened_once_a_day(self):
        learner_id = make_learner(coins=0, xp=0)
        self.assertTrue(shop_service.chest_state(learner_id)["available"])
        result = shop_service.claim_chest(learner_id, day="2026-10-30")
        self.assertGreaterEqual(result["coins"], shop_service.CHEST_MIN_COINS)
        self.assertGreaterEqual(result["xp"], shop_service.CHEST_MIN_XP)
        self.assertFalse(shop_service.chest_state(learner_id, "2026-10-30")["available"])
        with self.assertRaises(shop_service.ShopError) as ctx:
            shop_service.claim_chest(learner_id, day="2026-10-30")
        self.assertEqual(ctx.exception.code, "chest_claimed")

    def test_featured_item_has_discount(self):
        key = shop_service.featured_key("2026-10-30")
        item = shop_service.get_item(key)
        price = shop_service.price_for(item, "2026-10-30")
        self.assertEqual(price["discount"], shop_service.DISCOUNT_PERCENT)
        self.assertLess(price["coins"], item["coins"])

    def test_decorations_and_avatar_pack(self):
        learner_id = make_learner(coins=5000, xp=5000)
        shop_service.purchase(learner_id, "pack_space")
        shop_service.set_avatar(learner_id, "🚀")
        self.assertEqual(learner_row(learner_id)["avatar"], "🚀")
        with self.assertRaises(shop_service.ShopError) as ctx:
            shop_service.set_avatar(learner_id, "🐉")
        self.assertEqual(ctx.exception.code, "avatar_locked")

        shop_service.purchase(learner_id, "frame_gold")
        decor = shop_service.decorations(learner_id)
        self.assertEqual(decor["frame"], "frame_gold")
        self.assertEqual(decor["frame_css"], "gold")

        shop_service.purchase(learner_id, "title_fast")
        self.assertEqual(shop_service.decorations(learner_id)["title"], "Быстрый как молния")

    def test_avatar_packs_do_not_overlap_free_avatars(self):
        free = set(learners_service.AVATARS)
        for item in shop_service.CATALOG:
            if item["kind"] != "avatar_pack":
                continue
            self.assertEqual(len(item["avatars"]), 5)
            self.assertFalse(
                free & set(item["avatars"]),
                f"{item['key']} дублирует бесплатные аватары",
            )

    def test_reset_progress_clears_shop_and_returns_to_level_one(self):
        learner_id = make_learner(coins=1000, xp=5000)
        shop_service.purchase(learner_id, "theme_ocean")
        shop_service.purchase(learner_id, "boost_xp")
        self.assertTrue(learner_row(learner_id)["xp_spent"] > 0)

        learners_service.reset_progress(learner_id)

        row = learner_row(learner_id)
        self.assertEqual(row["xp"], 0)
        self.assertEqual(row["xp_spent"], 0)
        self.assertEqual(row["coins"], 0)
        self.assertEqual(progress_service.level_for_xp(progress_service.total_xp(row)), 1)
        self.assertEqual(shop_service.owned_map(learner_id), {})
        self.assertFalse(shop_service.active_effects(learner_id))

    def test_pet_grows_with_correct_answers(self):
        learner_id = make_learner(coins=5000, xp=5000)
        shop_service.purchase(learner_id, "pet_cat")
        pet = shop_service.decorations(learner_id)["pet"]
        self.assertEqual(pet["key"], "pet_cat")
        self.assertEqual(pet["progress"], 0)

        for _ in range(20):
            shop_service.bump_pet(learner_id)
        pet = shop_service.decorations(learner_id)["pet"]
        self.assertEqual(pet["progress"], 20)
        self.assertEqual(pet["stage_name"], "Друг")


class TestShopWeb(ShopTestCase):
    def setUp(self):
        fresh_db()
        from app import create_app

        application = create_app("testing")
        application.config["TESTING"] = True
        self.client = application.test_client()

    def _csrf(self, path: str = "/") -> str:
        html = self.client.get(path).get_data(as_text=True)
        marker = 'name="csrf_token" value="'
        start = html.find(marker)
        if start < 0:
            return ""
        start += len(marker)
        return html[start : html.find('"', start)]

    def _make_learner(self) -> None:
        token = self._csrf("/")
        self.client.post(
            "/learners",
            data={"name": "Маша", "avatar": "🦊", "grade": "3", "csrf_token": token},
        )

    def test_shop_page_and_purchase(self):
        self._make_learner()
        learner = query_one("SELECT * FROM learners ORDER BY id DESC LIMIT 1")
        execute(
            "UPDATE learners SET coins = 500, xp = 500 WHERE id = ?", (learner["id"],)
        )

        page = self.client.get("/shop/")
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn("Магазин приключений", html)
        self.assertIn("Сундук дня", html)
        self.assertIn("Учёба", html)

        token = self._csrf("/shop/")
        response = self.client.post(
            "/shop/buy",
            data={"item_key": "frame_gold", "csrf_token": token},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        row = learner_row(learner["id"])
        self.assertEqual(row["coins"], 500 - 90)
        self.assertIn("Золотая рамка", self.client.get("/shop/").get_data(as_text=True))

    def test_shop_requires_learner(self):
        response = self.client.get("/shop/", follow_redirects=False)
        self.assertIn(response.status_code, (302, 303))


class TestShopApi(ShopTestCase):
    def setUp(self):
        fresh_db()
        from app import create_app

        application = create_app("testing")
        application.config["TESTING"] = True
        self.client = application.test_client()

    def _family(self) -> tuple[str, int]:
        response = self.client.post(
            "/api/v1/learners",
            headers={"X-Device-Id": "shop-test-device"},
            json={"name": "Петя", "grade": 3},
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        payload = response.get_json()
        learner_id = int(payload["learner"]["id"])
        execute(
            "UPDATE learners SET coins = 500, xp = 500 WHERE id = ?", (learner_id,)
        )
        return payload["token"], learner_id

    def test_shop_api_purchase_chest_and_equip(self):
        token, learner_id = self._family()
        headers = {"Authorization": f"Bearer {token}"}

        response = self.client.get("/api/v1/shop", headers=headers)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["balance"]["coins"], 500)
        self.assertTrue(body["categories"])
        self.assertNotIn("by_key", body)

        response = self.client.post(
            "/api/v1/shop/buy",
            headers=headers,
            json={"item_key": "frame_gold"},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["shop"]["balance"]["coins"], 410)

        response = self.client.post(
            "/api/v1/shop/equip",
            headers=headers,
            json={"item_key": "frame_gold"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["shop"]["decor"]["frame"], "frame_gold")

        response = self.client.post("/api/v1/shop/chest", headers=headers)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertGreater(response.get_json()["coins"], 0)
        again = self.client.post("/api/v1/shop/chest", headers=headers)
        self.assertEqual(again.status_code, 409)

    def test_shop_api_rejects_unknown_item_and_insufficient_funds(self):
        token, _ = self._family()
        headers = {"Authorization": f"Bearer {token}"}
        response = self.client.post(
            "/api/v1/shop/buy", headers=headers, json={"item_key": "nope"}
        )
        self.assertEqual(response.status_code, 404)

        execute("UPDATE learners SET coins = 0 WHERE name = 'Петя'")
        response = self.client.post(
            "/api/v1/shop/buy", headers=headers, json={"item_key": "frame_gold"}
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "not_enough_coins")

    def test_system_end_to_end_round_uses_boost_but_keeps_xp_spent(self):
        """Верный ответ в игре начисляет опыт с усилителем и не трогает xp_spent."""
        token, learner_id = self._family()
        headers = {"Authorization": f"Bearer {token}"}
        shop_service.purchase(learner_id, "boost_xp")
        before = learner_row(learner_id)
        xp, _ = progress_service.reward_amounts(learner_id)
        execute("UPDATE learners SET xp = xp + ? WHERE id = ?", (xp, learner_id))
        after = learner_row(learner_id)
        self.assertEqual(after["xp"] - before["xp"], 20)
        self.assertEqual(after["xp_spent"], before["xp_spent"])


if __name__ == "__main__":
    unittest.main()
