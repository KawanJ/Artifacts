import unittest

from scripts.bootstrap import build_services
from tests.fake_game_api import FakeGameAPI


class NoCooldownCraftAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        response = super().post(endpoint, data, params)
        if endpoint.endswith("/action/crafting"):
            response["data"].pop("cooldown", None)
        return response


class CraftingServiceTests(unittest.TestCase):
    def test_existing_ingredients_are_consumed_without_gathering(self):
        api = FakeGameAPI(inventory={"copper_ore": 2})
        crafting = build_services(api, "tester", (), 0).crafting

        self.assertTrue(crafting.craft_item("wooden_staff", 2))

        self.assertEqual(api.gathered, {})
        self.assertEqual(api.crafted, {"wooden_staff": 2})
        self.assertEqual(api.inventory, {"wooden_staff": 2})

    def test_caller_supplied_inventory_snapshot_is_consumed(self):
        api = FakeGameAPI(inventory={"copper_ore": 1})
        crafting = build_services(api, "tester", (), 0).crafting
        inventory_snapshot = {"copper_ore": 1}

        self.assertTrue(
            crafting.craft_item("wooden_staff", inventory=inventory_snapshot)
        )

        self.assertEqual(inventory_snapshot, {"copper_ore": 0})
        self.assertEqual(api.inventory, {"wooden_staff": 1})

    def test_nested_recipe_gathers_base_material_and_crafts_each_stage(self):
        api = FakeGameAPI()
        api.items["copper_bar"] = {
            "code": "copper_bar",
            "type": "material",
            "craft": {
                "skill": "mining",
                "items": [{"code": "copper_ore", "quantity": 2}],
                "quantity": 1,
            },
        }
        api.items["iron_sword"] = {
            "code": "iron_sword",
            "type": "weapon",
            "craft": {
                "skill": "weaponcrafting",
                "items": [{"code": "copper_bar", "quantity": 1}],
                "quantity": 1,
            },
        }
        crafting = build_services(api, "tester", (), 0).crafting

        self.assertTrue(crafting.craft_item("iron_sword"))

        self.assertEqual(api.gathered, {"copper_ore": 2})
        self.assertEqual(api.crafted, {"copper_bar": 1, "iron_sword": 1})
        self.assertEqual(api.inventory, {"iron_sword": 1})

    def test_partial_inventory_is_used_before_gathering_shortfall(self):
        api = FakeGameAPI(inventory={"copper_ore": 1})
        crafting = build_services(api, "tester", (), 0).crafting

        self.assertTrue(crafting.craft_item("wooden_staff", 2))

        self.assertEqual(api.gathered, {"copper_ore": 1})
        self.assertEqual(api.inventory, {"wooden_staff": 2})

    def test_mob_resource_dependency_is_farmed_before_crafting(self):
        drop = {"code": "raw_chicken", "quantity": 1}
        api = FakeGameAPI(fight_drops=[drop])
        api.items["raw_chicken"] = {
            "code": "raw_chicken",
            "type": "resource",
            "subtype": "mob",
        }
        api.items["chicken_stew"] = {
            "code": "chicken_stew",
            "type": "consumable",
            "craft": {
                "skill": "cooking",
                "items": [{"code": "raw_chicken", "quantity": 1}],
                "quantity": 1,
            },
        }
        api.monsters["chicken"]["drops"] = [drop]
        crafting = build_services(api, "tester", (), 0).crafting

        self.assertTrue(crafting.craft_item("chicken_stew"))

        self.assertEqual(api.fights, [(0, 1)])
        self.assertEqual(api.inventory, {"chicken_stew": 1})
        self.assertEqual(api.crafted, {"chicken_stew": 1})

    def test_recipe_withdraws_banked_ingredients_before_farming_shortfall(self):
        slime_drop = {"code": "yellow_slime", "quantity": 1}
        api = FakeGameAPI(
            inventory={"yellow_slime": 10, "junk": 9},
            fight_drops=[slime_drop],
        )
        api.items["yellow_slime"] = {
            "code": "yellow_slime",
            "type": "resource",
            "subtype": "mob",
        }
        api.items["copper_bar"] = {
            "code": "copper_bar",
            "type": "material",
            "craft": {
                "skill": "mining",
                "items": [{"code": "copper_ore", "quantity": 2}],
                "quantity": 1,
            },
        }
        api.items["recipe_item"] = {
            "code": "recipe_item",
            "type": "material",
            "craft": {
                "skill": "weaponcrafting",
                "items": [
                    {"code": "yellow_slime", "quantity": 2},
                    {"code": "copper_bar", "quantity": 5},
                ],
                "quantity": 1,
            },
        }
        api.monsters["chicken"]["drops"] = [slime_drop]
        services = build_services(api, "tester", (), 0)

        self.assertTrue(services.crafting.craft_item("recipe_item"))
        self.assertEqual(api.bank["yellow_slime"], 8)
        self.assertEqual(api.fights, [])

        self.assertTrue(services.recycling.recycle_item("recipe_item"))
        self.assertTrue(services.crafting.craft_item("recipe_item"))

        self.assertEqual(api.fights, [])
        self.assertEqual(api.bank["yellow_slime"], 6)
        self.assertEqual(api.inventory, {"recipe_item": 1})

    def test_missing_dependency_metadata_stops_before_crafting(self):
        api = FakeGameAPI()
        api.items["copper_ore"] = None
        crafting = build_services(api, "tester", (), 0).crafting

        self.assertFalse(crafting.craft_item("wooden_staff"))
        self.assertEqual(api.crafted, {})

    def test_missing_target_metadata_and_failed_nested_recipe_stop_crafting(self):
        api = FakeGameAPI()
        api.items["missing_output"] = None
        crafting = build_services(api, "tester", (), 0).crafting
        self.assertFalse(crafting.craft_item("missing_output"))

        api = FakeGameAPI()
        api.items["copper_bar"] = {
            "code": "copper_bar",
            "type": "material",
            "craft": {
                "skill": "mining",
                "items": [{"code": "missing_ore", "quantity": 1}],
            },
        }
        api.items["iron_sword"] = {
            "code": "iron_sword",
            "type": "weapon",
            "craft": {
                "skill": "weaponcrafting",
                "items": [{"code": "copper_bar", "quantity": 1}],
            },
        }
        api.items["missing_ore"] = None
        crafting = build_services(api, "tester", (), 0).crafting
        self.assertFalse(crafting.craft_item("iron_sword"))
        self.assertEqual(api.crafted, {})

    def test_uncraftable_item_and_unknown_crafting_station_fail_cleanly(self):
        api = FakeGameAPI()
        api.items["unstationed_item"] = {
            "code": "unstationed_item",
            "type": "material",
            "craft": {"skill": "unknown_skill", "items": []},
        }
        crafting = build_services(api, "tester", (), 0).crafting

        self.assertFalse(crafting.craft_item("copper_ore"))
        self.assertFalse(crafting.craft_item("unstationed_item"))
        self.assertEqual(api.crafted, {})

    def test_crafting_action_failure_leaves_no_output(self):
        api = FakeGameAPI(inventory={"copper_ore": 1})
        api.fail_actions.add("crafting")
        crafting = build_services(api, "tester", (), 0).crafting

        self.assertFalse(crafting.craft_item("wooden_staff"))
        self.assertEqual(api.inventory, {})
        self.assertEqual(api.bank, {"copper_ore": 1})
        self.assertEqual(api.crafted, {})

    def test_resource_gather_failure_and_crafting_travel_failure_stop_operation(self):
        api = FakeGameAPI()
        api.fail_actions.add("gathering")
        crafting = build_services(api, "tester", (), 0).crafting
        self.assertFalse(crafting.craft_item("wooden_staff"))

        api = FakeGameAPI(inventory={"copper_ore": 1})
        api.fail_actions.add("move")
        crafting = build_services(api, "tester", (), 0).crafting
        self.assertFalse(crafting.craft_item("wooden_staff"))
        self.assertEqual(api.crafted, {})

    def test_cleanup_failure_reports_failure_after_crafting(self):
        api = FakeGameAPI(inventory={"copper_ore": 1, "shrimp": 1})
        api.fail_actions.add("bank/deposit/item")
        crafting = build_services(api, "tester", (), 0).crafting

        self.assertFalse(crafting.craft_item("wooden_staff"))
        self.assertEqual(api.inventory, {"wooden_staff": 1, "shrimp": 1})
        self.assertEqual(api.crafted, {"wooden_staff": 1})

    def test_crafting_can_complete_with_api_response_without_cooldown(self):
        api = NoCooldownCraftAPI(inventory={"copper_ore": 1})
        crafting = build_services(api, "tester", (), 0).crafting

        self.assertTrue(crafting.craft_item("wooden_staff"))
        self.assertEqual(api.inventory, {"wooden_staff": 1})

    def test_mob_dependency_without_matching_monster_fails_before_fighting(self):
        api = FakeGameAPI()
        api.items["raw_chicken"] = {
            "code": "raw_chicken",
            "type": "resource",
            "subtype": "mob",
        }
        api.items["chicken_stew"] = {
            "code": "chicken_stew",
            "type": "consumable",
            "craft": {
                "skill": "cooking",
                "items": [{"code": "raw_chicken", "quantity": 1}],
            },
        }
        crafting = build_services(api, "tester", (), 0).crafting

        self.assertFalse(crafting.craft_item("chicken_stew"))
        self.assertEqual(api.fights, [])

    def test_resource_resolver_skips_empty_and_unknown_requirements(self):
        api = FakeGameAPI()
        api.items["mystery_material"] = {
            "code": "mystery_material",
            "type": "unknown",
        }
        crafting = build_services(api, "tester", (), 0).crafting

        self.assertTrue(
            crafting._gather_required_resources(
                {
                    "craft": {
                        "items": [
                            {"code": "", "quantity": 1},
                            {"code": "copper_ore", "quantity": 0},
                            {"code": "mystery_material", "quantity": 1},
                        ]
                    }
                }
            )
        )
        self.assertEqual(api.gathered, {})
        self.assertTrue(
            crafting._gather_required_resources(
                {"code": "unprocessed", "type": "resource"}
            )
        )


if __name__ == "__main__":
    unittest.main()
