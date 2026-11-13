import unittest

from src.services.character_service import CharacterService
from tests.fake_game_api import FakeGameAPI


class CharacterSnapshotAPI(FakeGameAPI):
    def get(self, endpoint, params=None):
        if endpoint.startswith("/characters/"):
            return {
                "data": {
                    "inventory": [
                        {"code": "", "quantity": 3},
                        {"code": "cooked_shrimp", "quantity": 2},
                        {"code": "cooked_shrimp", "quantity": 3},
                    ]
                }
            }
        return super().get(endpoint, params)


class NoCooldownCharacterAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        response = super().post(endpoint, data, params)
        if endpoint.endswith("/action/use") or endpoint.endswith("/action/equip"):
            response["data"].pop("cooldown", None)
        return response


class CharacterServiceTests(unittest.TestCase):
    def test_inventory_skill_item_use_and_equipping_reflect_character_state(self):
        api = FakeGameAPI(inventory={"cooked_shrimp": 2, "wooden_staff": 1}, hp=30)
        service = CharacterService(api, "tester")

        self.assertEqual(
            service.get_inventory(),
            {"cooked_shrimp": 2, "wooden_staff": 1},
        )
        self.assertEqual(service.get_skill_level("weaponcrafting"), 0)
        self.assertTrue(service.use_item("cooked_shrimp"))
        self.assertEqual(service.get_hp_status(), (40, 100))
        self.assertEqual(service.get_inventory()["cooked_shrimp"], 1)

        self.assertTrue(service.equip_item("wooden_staff"))
        self.assertEqual(service.get_character_data()["weapon_slot"], "wooden_staff")

    def test_action_failure_is_not_reported_as_success(self):
        api = FakeGameAPI(inventory={"cooked_shrimp": 1})
        api.fail_actions.update({"use", "equip"})
        service = CharacterService(api, "tester")

        self.assertFalse(service.use_item("cooked_shrimp"))
        self.assertFalse(service.equip_item("wooden_staff"))
        self.assertEqual(service.get_inventory(), {"cooked_shrimp": 1})

    def test_inventory_sums_duplicate_entries_and_ignores_empty_codes(self):
        service = CharacterService(CharacterSnapshotAPI(), "tester")

        self.assertEqual(service.get_inventory(), {"cooked_shrimp": 5})

    def test_inventory_space_uses_capacity_and_carried_quantities(self):
        service = CharacterService(
            FakeGameAPI(inventory={"cooked_shrimp": 2}, max_inventory_slots=5),
            "tester",
        )

        self.assertEqual(service.get_inventory_space(), 3)

    def test_actions_succeed_when_api_omits_cooldown(self):
        api = NoCooldownCharacterAPI(inventory={"cooked_shrimp": 1, "wooden_staff": 1})
        service = CharacterService(api, "tester")

        self.assertTrue(service.use_item("cooked_shrimp"))
        self.assertTrue(service.equip_item("wooden_staff"))
        self.assertEqual(api.character["weapon_slot"], "wooden_staff")


if __name__ == "__main__":
    unittest.main()
