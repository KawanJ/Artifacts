import unittest

from scripts.bootstrap import build_services
from src.client.api_client import APIError
from tests.fake_game_api import FakeGameAPI


class MalformedMonsterListAPI(FakeGameAPI):
    def get(self, endpoint, params=None):
        if endpoint == "/monsters":
            return {
                "data": [
                    None,
                    {"code": 5, "drops": []},
                    {"code": "invalid_drops", "drops": "raw_chicken"},
                    {
                        "code": "chicken",
                        "drops": [None, {"code": "raw_chicken"}],
                    },
                ]
            }
        return super().get(endpoint, params)


class RetryFailureAPI(FakeGameAPI):
    def __init__(self):
        super().__init__()
        self.fight_attempts = 0

    def post(self, endpoint, data=None, params=None):
        if endpoint.endswith("/action/fight"):
            self.fight_attempts += 1
            status = 497 if self.fight_attempts == 1 else 400
            raise APIError("Simulated fight failure", status_code=status)
        return super().post(endpoint, data, params)


class FullInventoryCleanupFailureAPI(FakeGameAPI):
    def __init__(self):
        super().__init__(inventory={"material": 1})
        self.fail_actions.update({"fight", "bank/deposit/item"})
        self.fail_once_actions.add("fight")
        self.fail_statuses["fight"] = 497


class UnexpectedFightAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        if endpoint.endswith("/action/fight"):
            raise RuntimeError("fight transport unavailable")
        return super().post(endpoint, data, params)


class MalformedFirstFightAPI(FakeGameAPI):
    def __init__(self, fight_drops):
        super().__init__(fight_drops=fight_drops)
        self.fight_attempts = 0

    def post(self, endpoint, data=None, params=None):
        if endpoint.endswith("/action/fight"):
            self.fight_attempts += 1
            if self.fight_attempts == 1:
                self.fights.append((self.character["x"], self.character["y"]))
                return {
                    "data": {
                        "cooldown": {"total_seconds": 0},
                        "fight": {"characters": "invalid"},
                    }
                }
        return super().post(endpoint, data, params)


class CombatServiceTests(unittest.TestCase):
    def make_combat(self, api, food_codes=(), food_count=0):
        return build_services(api, "tester", food_codes, food_count).combat

    def test_food_is_fished_between_fights_after_run_provision_is_consumed(self):
        api = FakeGameAPI(fight_damage=20)
        api.bank["cooked_shrimp"] = 1
        api.monsters["chicken"]["attack_fire"] = 90
        combat = self.make_combat(api, ("cooked_shrimp",), 1)

        self.assertTrue(combat.fight_monster_by_code("chicken", count=2))

        self.assertEqual(api.fights, [(0, 1), (0, 1)])
        self.assertEqual(api.gathered, {"shrimp": 1})
        self.assertEqual(api.crafted, {"cooked_shrimp": 1})
        self.assertEqual(api.moves[-3:], [(5, 2), (1, 1), (0, 1)])
        self.assertEqual(api.character["hp"], api.character["max_hp"])
        self.assertEqual(api.inventory, {})
        self.assertEqual(api.bank, {})

    def test_full_inventory_during_fight_deposits_junk_and_retries(self):
        api = FakeGameAPI(inventory={"material": 3})
        api.fail_actions.add("fight")
        api.fail_once_actions.add("fight")
        api.fail_statuses["fight"] = 497
        combat = self.make_combat(api)

        self.assertTrue(combat.fight_monster_by_code("chicken"))

        self.assertEqual(api.fights, [(0, 1)])
        self.assertEqual(api.inventory, {})
        self.assertEqual(api.bank, {"material": 3})
        self.assertEqual(api.moves[-2:], [(4, 1), (0, 1)])

    def test_drop_farming_uses_api_drop_data_and_keeps_requested_quantity(self):
        unrelated_drop = {"code": "ash_wood", "quantity": 1}
        drop = {"code": "raw_chicken", "quantity": 1}
        api = FakeGameAPI(
            inventory={"wooden_staff": 1},
            fight_drops=[unrelated_drop, drop],
        )
        api.monsters["chicken"]["drops"] = [drop]
        combat = self.make_combat(api)

        self.assertTrue(combat.farm_drops("raw_chicken", 1))

        self.assertEqual(api.fights, [(0, 1)])
        self.assertEqual(api.inventory, {"wooden_staff": 1, "raw_chicken": 1})
        self.assertEqual(api.character["weapon_slot"], "wooden_staff")
        self.assertEqual(api.bank, {"ash_wood": 1})

    def test_drop_farming_skips_combat_when_no_items_are_needed(self):
        api = FakeGameAPI()
        combat = self.make_combat(api)

        self.assertTrue(combat.farm_drops("raw_chicken", 0))
        self.assertEqual(api.fights, [])

        api = FakeGameAPI()
        api.fail_actions.add("move")
        combat = self.make_combat(api)
        self.assertFalse(
            combat.farm_drops("raw_chicken", 1, monster_code="chicken")
        )
        self.assertEqual(api.fights, [])

    def test_drop_source_is_confirmed_against_monster_drops(self):
        api = FakeGameAPI()
        api.monsters["chicken"]["drops"] = [{"code": "raw_chicken"}]
        combat = self.make_combat(api)

        self.assertEqual(combat.get_monster_code_for_drop("raw_chicken"), "chicken")
        self.assertIsNone(combat.get_monster_code_for_drop("missing_drop"))

    def test_drop_lookup_ignores_malformed_api_records(self):
        combat = self.make_combat(MalformedMonsterListAPI())

        self.assertEqual(combat.get_monster_code_for_drop("raw_chicken"), "chicken")

    def test_drop_lookup_returns_none_for_non_list_api_response(self):
        api = FakeGameAPI()
        api.get = lambda endpoint, params=None: {"data": None}

        self.assertIsNone(self.make_combat(api).get_monster_code_for_drop("raw_chicken"))

    def test_minimum_hp_uses_full_hp_when_damage_cannot_be_estimated(self):
        api = FakeGameAPI()
        services = build_services(api, "tester", (), 0)
        api.character["attack_fire"] = 0

        self.assertEqual(services.combat._minimum_hp_to_fight("chicken"), 100)

        api.character["attack_fire"] = 10
        api.monsters["chicken"]["attack_fire"] = 200
        self.assertEqual(services.combat._minimum_hp_to_fight("chicken"), 100)

    def test_invalid_monster_combat_data_is_rejected(self):
        api = FakeGameAPI()
        services = build_services(api, "tester", (), 0)
        api.monsters["chicken"] = None

        with self.assertRaisesRegex(ValueError, "No monster data"):
            services.combat._minimum_hp_to_fight("chicken")

        api.monsters["chicken"] = {"code": "chicken", "hp": 10}
        api.character["max_hp"] = 0
        with self.assertRaisesRegex(ValueError, "Invalid HP data"):
            services.combat._minimum_hp_to_fight("chicken")

    def test_non_full_inventory_fight_error_is_not_retried(self):
        api = FakeGameAPI()
        api.fail_actions.add("fight")
        services = build_services(api, "tester", (), 0)
        api.fail_statuses["fight"] = 400

        self.assertIsNone(services.combat.fight_monster("chicken"))
        self.assertEqual(api.fights, [])

        self.assertIsNone(self.make_combat(UnexpectedFightAPI()).fight_monster("chicken"))

    def test_inventory_full_retry_failure_is_reported(self):
        api = RetryFailureAPI()
        combat = self.make_combat(api)

        self.assertIsNone(combat.fight_monster("chicken"))
        self.assertEqual(api.fight_attempts, 2)

    def test_inventory_full_fight_aborts_when_cleanup_or_return_move_fails(self):
        combat = self.make_combat(FullInventoryCleanupFailureAPI())
        self.assertIsNone(combat.fight_monster("chicken"))

        api = FakeGameAPI(inventory={"material": 1})
        api.fail_once_actions.add("fight")
        api.fail_actions.add("fight")
        api.fail_statuses["fight"] = 497
        combat = self.make_combat(api)
        original_post = api.post

        def fail_return_move(endpoint, data=None, params=None):
            if endpoint.endswith("/action/move") and len(api.moves) == 1:
                raise APIError("cannot return to monster", status_code=500)
            return original_post(endpoint, data, params)

        api.post = fail_return_move
        self.assertIsNone(combat.fight_monster("chicken"))
        self.assertEqual(api.fights, [])

    def test_drop_farming_fails_if_no_monster_drops_the_target(self):
        api = FakeGameAPI()
        combat = self.make_combat(api)

        self.assertFalse(combat.farm_drops("missing_drop", 1))
        self.assertEqual(api.fights, [])

    def test_drop_farming_stops_when_data_location_or_recovery_fails(self):
        api = FakeGameAPI()
        api.fail_get_endpoints.add("/monsters/chicken")
        combat = self.make_combat(api)
        self.assertFalse(combat.farm_drops("raw_chicken", 1, monster_code="chicken"))

        api = FakeGameAPI()
        combat = self.make_combat(api)
        self.assertFalse(combat.farm_drops("raw_chicken", 1, monster_code="unknown"))

        api = FakeGameAPI(hp=0, rest_heals=False)
        combat = self.make_combat(api)
        api.monsters["chicken"]["attack_fire"] = 90
        self.assertFalse(
            combat.farm_drops("raw_chicken", 1, monster_code="chicken")
        )
        self.assertEqual(api.fights, [])

    def test_farm_continues_until_requested_drop_quantity_is_reached(self):
        drop = {"code": "raw_chicken", "quantity": 1}
        api = FakeGameAPI(fight_drops=[drop])
        api.monsters["chicken"]["drops"] = [drop]
        combat = self.make_combat(api)

        self.assertTrue(combat.farm_drops("raw_chicken", 2))
        self.assertEqual(len(api.fights), 2)
        self.assertEqual(api.inventory, {"raw_chicken": 2})

    def test_malformed_fight_result_is_skipped_until_a_drop_is_received(self):
        drop = {"code": "raw_chicken", "quantity": 1}
        api = MalformedFirstFightAPI([drop])
        api.monsters["chicken"]["drops"] = [drop]
        combat = self.make_combat(api)

        self.assertTrue(combat.farm_drops("raw_chicken", 1))
        self.assertEqual(api.fight_attempts, 2)
        self.assertEqual(api.inventory, {"raw_chicken": 1})

    def test_drop_farming_reports_fight_rest_and_cleanup_failures(self):
        api = FakeGameAPI()
        api.fail_actions.add("fight")
        combat = self.make_combat(api)
        self.assertFalse(
            combat.farm_drops("raw_chicken", 1, monster_code="chicken")
        )

        drop = {"code": "raw_chicken", "quantity": 1}
        api = FakeGameAPI(fight_drops=[drop])
        api.monsters["chicken"]["drops"] = [drop]
        api.fail_actions.add("rest")
        combat = self.make_combat(api)
        self.assertFalse(combat.farm_drops("raw_chicken", 1))

        api = FakeGameAPI(inventory={"material": 1})
        api.fail_actions.add("bank/deposit/item")
        combat = self.make_combat(api)
        self.assertFalse(combat.farm_drops("missing_drop", 1))
        self.assertEqual(api.inventory, {"material": 1})

    def test_invalid_fight_count_and_food_preparation_failure_stop_run(self):
        api = FakeGameAPI()
        combat = self.make_combat(api)
        self.assertFalse(combat.fight_monster_by_code("chicken", count=0))
        self.assertEqual(api.fights, [])

        api.items["cooked_shrimp"]["effects"] = []
        combat = self.make_combat(api, ("cooked_shrimp",), 1)
        self.assertFalse(combat.fight_monster_by_code("chicken"))
        self.assertEqual(api.fights, [])

    def test_food_return_failure_and_provision_read_exception_fail_run(self):
        api = FakeGameAPI()
        api.bank["cooked_shrimp"] = 1
        api.fail_actions.add("bank/deposit/item")
        combat = self.make_combat(api, ("cooked_shrimp",), 1)

        self.assertFalse(combat.fight_monster_by_code("chicken"))
        self.assertEqual(api.inventory, {"cooked_shrimp": 1})

        api = FakeGameAPI()
        api.fail_get_endpoints.add("/characters/tester")
        combat = self.make_combat(api, ("cooked_shrimp",), 1)
        self.assertFalse(combat.fight_monster_by_code("chicken"))
        self.assertEqual(api.fights, [])

    def test_move_recovery_and_final_rest_failures_stop_combat(self):
        api = FakeGameAPI()
        api.fail_actions.add("move")
        combat = self.make_combat(api)
        self.assertFalse(combat.fight_monster_by_code("chicken"))
        self.assertEqual(api.fights, [])

        api = FakeGameAPI(hp=0, rest_heals=False)
        combat = self.make_combat(api)
        self.assertFalse(combat.fight_monster_by_code("chicken"))
        self.assertEqual(api.fights, [])

        api = FakeGameAPI()
        api.fail_actions.add("rest")
        combat = self.make_combat(api)
        self.assertFalse(combat.fight_monster_by_code("chicken"))
        self.assertEqual(api.fights, [(0, 1)])

    def test_unknown_monster_and_unexpected_api_failure_stop_combat(self):
        api = FakeGameAPI()
        combat = self.make_combat(api)
        self.assertFalse(combat.fight_monster_by_code("unknown_monster"))
        self.assertEqual(api.fights, [])

        api = FakeGameAPI()
        api.fail_get_endpoints.add("/monsters/chicken")
        combat = self.make_combat(api)
        self.assertFalse(combat.fight_monster_by_code("chicken"))
        self.assertEqual(api.fights, [])

    def test_failed_cleanup_changes_successful_fight_result_to_failure(self):
        api = FakeGameAPI(inventory={"material": 1})
        api.fail_actions.add("bank/deposit/item")
        combat = self.make_combat(api)

        self.assertFalse(combat.fight_monster_by_code("chicken"))
        self.assertEqual(api.fights, [(0, 1)])
        self.assertEqual(api.inventory, {"material": 1})


if __name__ == "__main__":
    unittest.main()
