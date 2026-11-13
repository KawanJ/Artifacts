import unittest

from scripts.bootstrap import build_services
from src.services.combat.combat_equipment_service import CombatEquipmentService
from tests.fake_game_api import FakeGameAPI


class CombatEquipmentServiceTests(unittest.TestCase):
    def make_equipment(self, api):
        services = build_services(api, "tester", (), 0)
        return CombatEquipmentService(
            api,
            services.character,
            services.combat.food_service.item_service,
        )

    def test_equips_owned_weapon_with_highest_damage_estimate(self):
        api = FakeGameAPI(
            inventory={"wooden_staff": 1, "flame_sword": 1}
        )
        api.items["flame_sword"] = {
            "code": "flame_sword",
            "type": "weapon",
            "effects": [{"code": "attack_fire", "value": 5}],
        }
        api.character["weapon_slot"] = "wooden_staff"
        equipment = self.make_equipment(api)

        self.assertTrue(equipment.equip_best_weapon("chicken"))
        self.assertEqual(api.character["weapon_slot"], "flame_sword")

    def test_keeps_current_weapon_when_best_weapon_cannot_be_equipped(self):
        api = FakeGameAPI(
            inventory={"wooden_staff": 1, "flame_sword": 1}
        )
        api.items["flame_sword"] = {
            "code": "flame_sword",
            "type": "weapon",
            "effects": [{"code": "attack_fire", "value": 5}],
        }
        api.character["weapon_slot"] = "wooden_staff"
        api.fail_actions.add("equip")
        equipment = self.make_equipment(api)

        self.assertTrue(equipment.equip_best_weapon("chicken"))
        self.assertEqual(api.character["weapon_slot"], "wooden_staff")

    def test_missing_monster_or_weapon_data_does_not_claim_success(self):
        api = FakeGameAPI()
        equipment = self.make_equipment(api)
        self.assertFalse(equipment.equip_best_weapon("missing_monster"))

        api = FakeGameAPI(inventory={"wooden_staff": 1})
        api.items["wooden_staff"] = None
        self.assertFalse(self.make_equipment(api).equip_best_weapon("chicken"))

    def test_api_read_failure_and_empty_weapon_inventory_are_handled(self):
        api = FakeGameAPI()
        api.fail_get_endpoints.add("/monsters/chicken")
        self.assertFalse(self.make_equipment(api).equip_best_weapon("chicken"))

        api = FakeGameAPI()
        self.assertFalse(self.make_equipment(api).equip_best_weapon("chicken"))

    def test_currently_equipped_best_weapon_is_left_untouched(self):
        api = FakeGameAPI(inventory={"wooden_staff": 1})
        api.character["weapon_slot"] = "wooden_staff"

        self.assertTrue(self.make_equipment(api).equip_best_weapon("chicken"))
        self.assertEqual(api.character["weapon_slot"], "wooden_staff")
        self.assertEqual(api.equip_attempts, 0)

    def test_item_catalog_exception_and_failed_all_equips_return_false(self):
        api = FakeGameAPI(inventory={"wooden_staff": 1})
        api.fail_get_endpoints.add("/items/wooden_staff")
        self.assertFalse(self.make_equipment(api).equip_best_weapon("chicken"))

        api = FakeGameAPI(inventory={"wooden_staff": 1})
        api.fail_actions.add("equip")
        self.assertFalse(self.make_equipment(api).equip_best_weapon("chicken"))
        self.assertIsNone(api.character["weapon_slot"])


if __name__ == "__main__":
    unittest.main()
