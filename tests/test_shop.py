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
        self.assertEqual(categories, {"perks", "style", "pets", "minecraft"})
        self.assertGreaterEqual(len(shop_service.catalog_items()), 28)
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

    def test_minecraft_items_have_rarity_and_permanent_boosts(self):
        learner_id = make_learner(coins=5000, xp=700)
        mc_items = [item for item in shop_service.catalog_items()
                    if item["category"] == "minecraft"]
        self.assertGreaterEqual(len(mc_items), 8)
        self.assertTrue(all(item["rarity"] in shop_service.RARITY for item in mc_items))

        shop_service.purchase(learner_id, "mc_pickaxe")
        shop_service.purchase(learner_id, "mc_enchant")
        _, coins = progress_service.reward_amounts(learner_id)
        # 2 монеты × 1.15 и 10 опыта × 1.15 с округлением.
        self.assertEqual(coins, 2)
        xp, _ = progress_service.reward_amounts(learner_id)
        self.assertEqual(xp, 12)

    def test_tnt_lootbox_gives_random_reward(self):
        learner_id = make_learner(coins=1000, xp=1000)
        result = shop_service.purchase(learner_id, "mc_tnt")
        self.assertEqual(result["item"]["kind"], "lootbox")
        self.assertIsNotNone(result["loot"])
        self.assertGreaterEqual(result["loot"]["coins"] + result["loot"]["xp"], 0)
        self.assertTrue("взрыв" in result["message"].lower() or "джекпот" in result["message"].lower())
        self.assertIsNone(shop_service.owned_map(learner_id).get("mc_tnt"))

    def test_admin_overrides_change_price_disable_and_reset(self):
        learner_id = make_learner(coins=100, xp=0)
        shop_service.save_override(
            "frame_gold",
            {"price_coins": "0", "discount_percent": "10", "level": "1",
             "is_active": "1", "name": "Особая рамка"},
        )
        state = shop_service.shop_state(learner_id)
        frame = state["by_key"]["frame_gold"]
        self.assertEqual(frame["name"], "Особая рамка")
        self.assertEqual(frame["price_coins"], 0)
        self.assertEqual(frame["discount"], 10)

        shop_service.save_override("frame_gold", {"is_active": ""})
        state = shop_service.shop_state(learner_id)
        self.assertNotIn("frame_gold", state["by_key"])
        with self.assertRaises(shop_service.ShopError) as ctx:
            shop_service.purchase(learner_id, "frame_gold")
        self.assertEqual(ctx.exception.code, "item_disabled")

        shop_service.reset_override("frame_gold")
        self.assertIn("frame_gold", shop_service.shop_state(learner_id)["by_key"])

    def test_featured_choice_and_discount_event(self):
        learner_id = make_learner(coins=5000, xp=0)
        shop_service.set_setting("featured_key", "theme_ocean")
        shop_service.set_setting("featured_day", shop_service.day_key())
        featured = shop_service.shop_state(learner_id)["featured"]
        self.assertEqual(featured["key"], "theme_ocean")
        self.assertEqual(featured["discount"], shop_service.DISCOUNT_PERCENT)

        execute(
            """INSERT INTO shop_events
                   (title, description, icon, kind, value, starts_on, ends_on, is_active)
               VALUES ('Скидочная неделя', '', '🏷', 'discount', 15,
                       date('now'), date('now', '+2 day'), 1)"""
        )
        state = shop_service.shop_state(learner_id)
        self.assertIsNotNone(state["event"])
        ocean = state["by_key"]["theme_ocean"]
        self.assertEqual(ocean["discount"], shop_service.DISCOUNT_PERCENT + 15)

    def test_event_double_coins_affects_rewards(self):
        learner_id = make_learner(coins=1000, xp=1000)
        execute(
            """INSERT INTO shop_events
                   (title, description, icon, kind, value, starts_on, ends_on, is_active)
               VALUES ('Монетная лихорадка', '', '🪙', 'double_coins', 2,
                       date('now'), date('now', '+1 day'), 1)"""
        )
        _, coins = progress_service.reward_amounts(learner_id)
        self.assertEqual(coins, 4)

    def test_gift_is_created_notified_and_claimed(self):
        learner_id = make_learner(coins=0, xp=0)
        gift_id = shop_service.create_gift(
            learner_id, "frame_gold", "За серию 5 дней и точность 90%",
            "Ты молодец!", coins=25, xp=10, gifted_by=1,
        )
        pending = shop_service.pending_gifts(learner_id)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["name"], "Золотая рамка")
        self.assertEqual(pending[0]["reason"], "За серию 5 дней и точность 90%")
        notice = query_one(
            "SELECT * FROM app_notifications WHERE learner_id = ? AND kind = 'shop_gift'",
            (learner_id,),
        )
        self.assertIsNotNone(notice)
        self.assertIn("Золотая рамка", notice["body"])

        result = shop_service.claim_gift(learner_id, gift_id)
        self.assertIn("Подарок открыт", result["message"])
        row = learner_row(learner_id)
        self.assertEqual(row["coins"], 25)
        self.assertEqual(row["xp"], 10)
        self.assertIn("frame_gold", shop_service.owned_map(learner_id))
        self.assertEqual(shop_service.pending_gifts(learner_id), [])
        with self.assertRaises(shop_service.ShopError) as ctx:
            shop_service.claim_gift(learner_id, gift_id)
        self.assertEqual(ctx.exception.code, "gift_claimed")

    def test_gift_of_lootbox_opens_with_reward(self):
        learner_id = make_learner(coins=0, xp=0)
        gift_id = shop_service.create_gift(
            learner_id, "mc_tnt", "За смелость на контрольной", coins=5,
        )
        result = shop_service.claim_gift(learner_id, gift_id)
        self.assertIsNotNone(result["loot"])
        row = learner_row(learner_id)
        self.assertGreaterEqual(row["coins"], 5)
        self.assertGreaterEqual(row["coins"] + row["xp"], 5)
        self.assertIn("ТНТ", result["message"])

    def test_insights_rank_effort_and_suggest_gift(self):
        from services import shop_insights

        good = make_learner(coins=100, xp=100)
        lazy = make_learner(coins=100, xp=100)
        for index in range(30):
            progress_service.record_attempt(
                good, "addition", None, None, True, "1", "1", 900, 0
            )
        execute(
            """INSERT INTO attempts (learner_id, topic_slug, correct, created_at)
               VALUES (?, 'addition', 1, datetime('now', '-3 day'))""",
            (good,),
        )
        execute("UPDATE learners SET streak_days = 5 WHERE id = ?", (good,))
        progress_service.record_attempt(lazy, "addition", None, None, False, "2", "1", 3000, 0)
        board = shop_insights.leaderboard()
        self.assertEqual(board[0]["id"], good)
        self.assertGreaterEqual(board[0]["accuracy"], 90)
        self.assertTrue(board[0]["reasons"])
        self.assertTrue(board[0]["ideas"])
        self.assertTrue(board[0]["deserving"])


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

    def test_child_sees_and_opens_gift(self):
        self._make_learner()
        learner = query_one("SELECT * FROM learners ORDER BY id DESC LIMIT 1")
        gift_id = shop_service.create_gift(
            learner["id"], "pack_minecraft", "За старание на этой неделе",
            "Ты собрал целый набор мобов!", coins=15,
        )
        page = self.client.get("/shop/")
        html = page.get_data(as_text=True)
        self.assertIn("Тебе подарок", html)
        self.assertIn("За старание на этой неделе", html)

        token = self._csrf("/shop/")
        response = self.client.post(
            f"/shop/gift/{gift_id}/claim",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Подарок открыт", response.get_data(as_text=True))
        row = learner_row(learner["id"])
        self.assertEqual(row["coins"], 15)
        self.assertIn("pack_minecraft", shop_service.owned_map(learner["id"]))

    def test_admin_shop_page_and_gift_form(self):
        from services import auth as auth_service

        auth_service.create_user("shop_admin", "math2025", auth_service.ROLE_ADMIN,
                                 first_name="Админ")
        self._make_learner()
        learner = query_one("SELECT * FROM learners ORDER BY id DESC LIMIT 1")

        token = self._csrf("/login")
        self.client.post(
            "/login",
            data={"csrf_token": token, "login": "shop_admin", "password": "math2025"},
            follow_redirects=True,
        )
        page = self.client.get("/admin/shop")
        self.assertEqual(page.status_code, 200)
        html = page.get_data(as_text=True)
        self.assertIn("Магазин, подарки и события", html)
        self.assertIn("Minecraft", html)
        self.assertIn("Кто из детей больше старается", html)

        token = self._csrf("/admin/shop")
        response = self.client.post(
            "/admin/shop",
            data={
                "csrf_token": token,
                "action": "gift",
                "learner_id": str(learner["id"]),
                "item_key": "theme_minecraft",
                "reason": "За пять дней занятий подряд",
                "message": "Строй свой кубический мир!",
                "coins": "20",
                "xp": "5",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Подарок", response.get_data(as_text=True))
        pending = shop_service.pending_gifts(learner["id"])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["item_key"], "theme_minecraft")
        self.assertEqual(pending[0]["coins"], 20)


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
        token, _ = self._family()
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

    def test_shop_api_lists_and_claims_gift(self):
        token, learner_id = self._family()
        gift_id = shop_service.create_gift(
            learner_id, "frame_diamond", "За точность 95%", coins=10,
        )
        headers = {"Authorization": f"Bearer {token}"}
        body = self.client.get("/api/v1/shop", headers=headers).get_json()
        self.assertEqual(body["gift_count"], 1)
        self.assertEqual(body["gifts"][0]["name"], "Алмазная рамка")

        response = self.client.post(
            "/api/v1/shop/gifts/claim",
            headers=headers,
            json={"gift_id": gift_id},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertIn("Подарок открыт", payload["message"])
        self.assertEqual(payload["shop"]["gift_count"], 0)

    def test_system_end_to_end_round_uses_boost_but_keeps_xp_spent(self):
        """Верный ответ в игре начисляет опыт с усилителем и не трогает xp_spent."""
        _, learner_id = self._family()
        shop_service.purchase(learner_id, "boost_xp")
        before = learner_row(learner_id)
        xp, _ = progress_service.reward_amounts(learner_id)
        execute("UPDATE learners SET xp = xp + ? WHERE id = ?", (xp, learner_id))
        after = learner_row(learner_id)
        self.assertEqual(after["xp"] - before["xp"], 20)
        self.assertEqual(after["xp_spent"], before["xp_spent"])


if __name__ == "__main__":
    unittest.main()


class TestShopAdminApi(ShopTestCase):
    """JSON API админки магазина для Android-приложения."""

    def setUp(self):
        fresh_db()
        from app import create_app
        from services import auth as auth_service

        application = create_app("testing")
        application.config["TESTING"] = True
        self.client = application.test_client()
        auth_service.create_user(
            "shop_admin", "secret123", auth_service.ROLE_ADMIN, first_name="Админ"
        )
        self.learner_id = make_learner(coins=100, xp=100)
        self.token = self._login("shop_admin", "secret123")

    def _login(self, login: str, password: str) -> str:
        response = self.client.post(
            "/api/v1/auth/login", json={"login": login, "password": password}
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()["token"]

    def _headers(self, token: str | None = None) -> dict:
        return {"Authorization": f"Bearer {token or self.token}"}

    def test_admin_shop_requires_admin(self):
        self.assertEqual(self.client.get("/api/v1/admin/shop").status_code, 401)

        from services import auth as auth_service

        auth_service.create_user("shop_teacher", "secret123", "teacher")
        teacher_token = self._login("shop_teacher", "secret123")
        response = self.client.get(
            "/api/v1/admin/shop", headers=self._headers(teacher_token)
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_dashboard_returns_ranking_catalog_and_settings(self):
        response = self.client.get("/api/v1/admin/shop", headers=self._headers())
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertIn("pending", body["summary"])
        self.assertTrue(body["board"])
        self.assertEqual(body["board"][0]["id"], self.learner_id)
        self.assertTrue(body["board"][0]["ideas"])
        self.assertTrue(body["reasons"])
        self.assertTrue(body["catalog"])
        self.assertEqual(
            {category["key"] for category in body["categories"]},
            {"perks", "minecraft", "style", "pets"},
        )
        self.assertIsInstance(body["featured_key"], str)
        self.assertIn("gifts", body)
        self.assertIn("announcement", body)
        self.assertIn("today", body)
        self.assertIn("default_end", body)

    def test_item_override_save_and_reset(self):
        response = self.client.post(
            "/api/v1/admin/shop/items/frame_gold",
            headers=self._headers(),
            json={
                "name": "Золотая рамка недели",
                "price_coins": 5,
                "discount_percent": 10,
                "level": 2,
                "is_active": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertIn("message", body)
        item = next(
            entry for entry in body["shop"]["catalog"] if entry["key"] == "frame_gold"
        )
        self.assertEqual(item["name"], "Золотая рамка недели")
        self.assertEqual(item["coins"], 5)
        self.assertFalse(item["is_active"])
        self.assertEqual(item["override"]["discount_percent"], 10)

        reset = self.client.post(
            "/api/v1/admin/shop/items/frame_gold/reset", headers=self._headers()
        )
        self.assertEqual(reset.status_code, 200, reset.get_data(as_text=True))
        item = next(
            entry
            for entry in reset.get_json()["shop"]["catalog"]
            if entry["key"] == "frame_gold"
        )
        self.assertEqual(item["name"], "Золотая рамка")
        self.assertEqual(item["coins"], 90)
        self.assertTrue(item["is_active"])
        self.assertIsNone(item["override"])

    def test_featured_and_announcement(self):
        response = self.client.put(
            "/api/v1/admin/shop/featured",
            headers=self._headers(),
            json={"item_key": "frame_gold"},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["shop"]["featured_key"], "frame_gold")

        response = self.client.put(
            "/api/v1/admin/shop/announcement",
            headers=self._headers(),
            json={"announcement": "На выходных двойные монеты!"},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(
            response.get_json()["shop"]["announcement"],
            "На выходных двойные монеты!",
        )
        self.assertEqual(shop_service.get_setting("announcement"), "На выходных двойные монеты!")

    def test_event_create_and_stop(self):
        response = self.client.post(
            "/api/v1/admin/shop/events",
            headers=self._headers(),
            json={
                "title": "Монетная лихорадка",
                "description": "Все выходные монеты удваиваются",
                "icon": "🪙",
                "kind": "double_coins",
                "value": 2,
                "starts_on": "2026-01-01",
                "ends_on": "2026-01-03",
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        events = response.get_json()["shop"]["events"]
        event = next(row for row in events if row["title"] == "Монетная лихорадка")
        self.assertTrue(event["is_active"])
        self.assertEqual(event["kind"], "double_coins")

        stop = self.client.post(
            f"/api/v1/admin/shop/events/{event['id']}/stop",
            headers=self._headers(),
        )
        self.assertEqual(stop.status_code, 200, stop.get_data(as_text=True))
        event = next(
            row
            for row in stop.get_json()["shop"]["events"]
            if row["id"] == event["id"]
        )
        self.assertFalse(event["is_active"])

        bad = self.client.post(
            "/api/v1/admin/shop/events",
            headers=self._headers(),
            json={"title": "Плохие даты", "starts_on": "2026-02-02", "ends_on": "2026-02-01"},
        )
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.get_json()["error"], "bad_dates")

    def test_gift_create_and_cancel(self):
        response = self.client.post(
            "/api/v1/admin/shop/gifts",
            headers=self._headers(),
            json={
                "learner_id": self.learner_id,
                "item_key": "frame_gold",
                "reason": "За 6 дней занятий и серию 5 дней",
                "message": "Ты настоящий герой недели!",
                "coins": 25,
                "xp": 10,
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(len(shop_service.pending_gifts(self.learner_id)), 1)
        gift = body["shop"]["gifts"][0]
        self.assertEqual(gift["learner_name"], "Тест")
        self.assertEqual(gift["reason"], "За 6 дней занятий и серию 5 дней")

        cancel = self.client.post(
            f"/api/v1/admin/shop/gifts/{gift['id']}/cancel",
            headers=self._headers(),
        )
        self.assertEqual(cancel.status_code, 200, cancel.get_data(as_text=True))
        self.assertEqual(shop_service.pending_gifts(self.learner_id), [])
        self.assertEqual(cancel.get_json()["shop"]["gifts"][0]["status"], "cancelled")

        no_reason = self.client.post(
            "/api/v1/admin/shop/gifts",
            headers=self._headers(),
            json={"learner_id": self.learner_id, "coins": 5},
        )
        self.assertEqual(no_reason.status_code, 400)
        self.assertEqual(no_reason.get_json()["error"], "reason_required")
