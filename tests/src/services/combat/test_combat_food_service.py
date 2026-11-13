import unittest

from scripts.bootstrap import build_services
from src.client.api_client import APIError
from tests.fake_game_api import FakeGameAPI


class CookingMovementFailureAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        if endpoint.endswith("/action/move") and (data["x"], data["y"]) == (1, 1):
            raise APIError("cooking workshop unavailable", status_code=500)
        return super().post(endpoint, data, params)


class ReturnToFightFailureAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        if endpoint.endswith("/action/move") and (data["x"], data["y"]) == (0, 1):
            raise APIError("cannot return to fight", status_code=500)
        return super().post(endpoint, data, params)


class NoCooldownCookingAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        response = super().post(endpoint, data, params)
        if endpoint.endswith("/action/crafting"):
            response["data"].pop("cooldown", None)
        return response


class CombatFoodServiceTests(unittest.TestCase):
    def make_food(self, api, codes=("cooked_shrimp",), target=1):
        return build_services(api, "tester", codes, target).combat.food_service

    def test_preparation_fills_shortfall_by_fishing_and_returns_only_run_food(self):
        api = FakeGameAPI(inventory={"cooked_shrimp": 1})
        api.bank["cooked_shrimp"] = 1
        food = self.make_food(api, target=3)

        self.assertTrue(food.prepare_food())

        self.assertEqual(api.inventory, {"cooked_shrimp": 3})
        self.assertEqual(api.gathered, {"shrimp": 1})
        self.assertEqual(api.crafted, {"cooked_shrimp": 1})
        self.assertEqual(api.bank, {})

        self.assertTrue(food.return_unused_food())

        self.assertEqual(api.inventory, {"cooked_shrimp": 1})
        self.assertEqual(api.bank, {"cooked_shrimp": 2})

    def test_allowlisted_item_without_healing_effect_fails_preparation(self):
        api = FakeGameAPI()
        api.items["cooked_shrimp"]["effects"] = [
            {"code": "attack_fire", "value": 2}
        ]
        food = self.make_food(api, target=2)

        self.assertFalse(food.prepare_food())
        self.assertEqual(api.inventory, {})
        self.assertEqual(api.bank, {})
        self.assertTrue(food.return_unused_food())

    def test_missing_allowlisted_catalog_entry_fails_preparation(self):
        api = FakeGameAPI()
        api.items["missing_food"] = None
        food = self.make_food(api, ("missing_food",), 1)

        self.assertFalse(food.prepare_food())
        self.assertTrue(food.return_unused_food())

    def test_existing_bank_food_is_returned_after_only_baseline_food_was_used(self):
        api = FakeGameAPI(inventory={"cooked_shrimp": 1}, hp=20)
        api.bank["cooked_shrimp"] = 2
        services = build_services(api, "tester", ("cooked_shrimp",), 3)
        food = services.combat.food_service
        self.assertTrue(food.prepare_food())

        self.assertTrue(services.combat.recovery_service.recover_to_hp(30))
        self.assertTrue(food.return_unused_food())

        self.assertEqual(api.inventory, {})
        self.assertEqual(api.bank, {"cooked_shrimp": 2})

    def test_cooks_the_highest_healing_recipe_the_character_can_make(self):
        api = FakeGameAPI()
        api.items["cooked_salmon"] = {
            "code": "cooked_salmon",
            "type": "consumable",
            "effects": [{"code": "heal", "value": 20}],
            "craft": {
                "skill": "cooking",
                "level": 1,
                "items": [{"code": "salmon", "quantity": 1}],
                "quantity": 1,
            },
        }
        api.items["salmon"] = {
            "code": "salmon",
            "type": "resource",
            "subtype": "fishing",
            "level": 1,
        }
        food = self.make_food(
            api,
            ("cooked_shrimp", "cooked_salmon"),
            1,
        )

        self.assertTrue(food.prepare_food())

        self.assertEqual(api.gathered, {"salmon": 1})
        self.assertEqual(api.crafted, {"cooked_salmon": 1})
        self.assertEqual(api.inventory, {"cooked_salmon": 1})

    def test_cooking_succeeds_when_cooldown_is_omitted(self):
        api = NoCooldownCookingAPI()
        food = self.make_food(api)

        self.assertTrue(food.prepare_food())

        self.assertEqual(api.crafted, {"cooked_shrimp": 1})

    def test_insufficient_skills_leave_food_unmade_for_rest_fallback(self):
        api = FakeGameAPI()
        api.character["fishing_level"] = 0
        food = self.make_food(api, target=1)

        self.assertTrue(food.prepare_food())

        self.assertEqual(api.gathered, {})
        self.assertEqual(api.crafted, {})
        self.assertEqual(api.inventory, {})

    def test_malformed_or_ineligible_recipes_are_never_cooked(self):
        api = FakeGameAPI()
        recipe_cases = {
            "no_recipe": None,
            "wrong_skill": {"skill": "mining", "items": []},
            "invalid_items": {"skill": "cooking", "items": None},
            "multiple_ingredients": {
                "skill": "cooking",
                "items": [
                    {"code": "shrimp", "quantity": 1},
                    {"code": "salmon", "quantity": 1},
                ],
            },
            "invalid_ingredient": {
                "skill": "cooking",
                "items": [None],
            },
            "unknown_fish": {
                "skill": "cooking",
                "items": [{"code": "unknown_fish", "quantity": 1}],
            },
            "wrong_subtype": {
                "skill": "cooking",
                "items": [{"code": "copper_ore", "quantity": 1}],
            },
            "zero_fish": {
                "skill": "cooking",
                "items": [{"code": "shrimp", "quantity": 0}],
            },
            "high_level": {
                "skill": "cooking",
                "level": 11,
                "items": [{"code": "shrimp", "quantity": 1}],
            },
        }
        for food_code, recipe in recipe_cases.items():
            api.items[food_code] = {
                "code": food_code,
                "type": "consumable",
                "effects": [{"code": "heal", "value": 5}],
                "craft": recipe,
            }
        api.items["copper_ore"]["subtype"] = "mining"
        food = self.make_food(api, tuple(recipe_cases), 1)

        self.assertTrue(food.prepare_food())

        self.assertEqual(api.gathered, {})
        self.assertEqual(api.crafted, {})
        self.assertEqual(api.inventory, {})

    def test_failed_fishing_cooking_or_cooking_travel_leaves_food_unprovisioned(self):
        api = FakeGameAPI()
        api.fail_actions.add("gathering")
        food = self.make_food(api)
        self.assertTrue(food.prepare_food())
        self.assertEqual(api.crafted, {})
        self.assertEqual(api.inventory, {})

        api = FakeGameAPI()
        api.fail_actions.add("crafting")
        food = self.make_food(api)
        self.assertTrue(food.prepare_food())
        self.assertEqual(api.gathered, {"shrimp": 1})
        self.assertEqual(api.crafted, {})

        api = CookingMovementFailureAPI()
        food = self.make_food(api)
        self.assertTrue(food.prepare_food())
        self.assertEqual(api.gathered, {"shrimp": 1})
        self.assertEqual(api.crafted, {})

    def test_zero_target_does_not_withdraw_or_cook_food(self):
        api = FakeGameAPI()
        api.bank["cooked_shrimp"] = 2
        food = self.make_food(api, target=0)

        self.assertTrue(food.prepare_food())

        self.assertEqual(api.bank, {"cooked_shrimp": 2})
        self.assertEqual(api.inventory, {})

    def test_existing_food_at_target_needs_no_bank_or_gathering_actions(self):
        api = FakeGameAPI(inventory={"cooked_shrimp": 2})
        api.bank["cooked_shrimp"] = 4
        food = self.make_food(api, target=2)

        self.assertTrue(food.prepare_food())

        self.assertEqual(api.inventory, {"cooked_shrimp": 2})
        self.assertEqual(api.bank, {"cooked_shrimp": 4})
        self.assertEqual(api.moves, [])
        self.assertEqual(api.gathered, {})

    def test_bank_read_and_withdraw_failures_abort_provisioning(self):
        api = FakeGameAPI()
        api.bank["cooked_shrimp"] = 1
        api.fail_get_endpoints.add("/my/bank/items")
        food = self.make_food(api)

        self.assertFalse(food.prepare_food())
        self.assertEqual(api.bank, {"cooked_shrimp": 1})

        api.fail_get_endpoints.clear()
        api.fail_actions.add("bank/withdraw/item")
        self.assertFalse(food.prepare_food())
        self.assertEqual(api.bank, {"cooked_shrimp": 1})

    def test_failed_return_can_be_retried_without_losing_provision_state(self):
        api = FakeGameAPI()
        api.bank["cooked_shrimp"] = 1
        food = self.make_food(api)
        self.assertTrue(food.prepare_food())
        api.fail_actions.add("bank/deposit/item")

        self.assertFalse(food.return_unused_food())
        self.assertEqual(api.inventory, {"cooked_shrimp": 1})

        api.fail_actions.clear()
        self.assertTrue(food.return_unused_food())
        self.assertEqual(api.inventory, {})
        self.assertEqual(api.bank, {"cooked_shrimp": 1})

    def test_replenishment_requires_valid_character_coordinates(self):
        api = FakeGameAPI()
        food = self.make_food(api)
        self.assertTrue(food.prepare_food())
        api.character["x"] = "unknown"

        with self.assertRaisesRegex(ValueError, "Character location is unavailable"):
            food.replenish_food()

    def test_failure_to_return_to_fight_location_is_explicit(self):
        api = ReturnToFightFailureAPI()
        api.bank["cooked_shrimp"] = 1
        food = self.make_food(api)
        self.assertTrue(food.prepare_food())
        api.character["x"], api.character["y"] = 0, 1
        self.assertTrue(food.character_service.use_item("cooked_shrimp"))
        food.record_food_used("cooked_shrimp")

        with self.assertRaisesRegex(RuntimeError, "Could not return to the fight location"):
            food.replenish_food()

        self.assertEqual(api.character["x"], 1)
        self.assertEqual(api.character["y"], 1)

    def test_replenishment_returns_false_when_no_food_can_be_added(self):
        api = FakeGameAPI()
        api.character["fishing_level"] = 0
        food = self.make_food(api)
        self.assertTrue(food.prepare_food())

        self.assertFalse(food.replenish_food())
        self.assertEqual(api.character["x"], 0)
        self.assertEqual(api.character["y"], 0)

    def test_return_without_an_active_provisioning_run_is_noop(self):
        food = self.make_food(FakeGameAPI())

        self.assertTrue(food.return_unused_food())


if __name__ == "__main__":
    unittest.main()
