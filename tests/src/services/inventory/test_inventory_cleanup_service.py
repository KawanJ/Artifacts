import unittest

from scripts.bootstrap import build_services
from src.services.character_service import CharacterService
from src.services.inventory.bank_service import BankService
from src.services.inventory.inventory_cleanup_service import InventoryCleanupService
from src.services.items.item_catalog_service import ItemCatalogService
from src.services.movement_service import MovementService
from tests.fake_game_api import FakeGameAPI


class InvalidCharacterResponseAPI(FakeGameAPI):
    def get(self, endpoint, params=None):
        if endpoint.startswith("/characters/"):
            return {"data": None}
        return super().get(endpoint, params)


class MalformedInventoryAPI(FakeGameAPI):
    def get(self, endpoint, params=None):
        if endpoint.startswith("/characters/"):
            return {
                "data": {
                    "inventory": [
                        None,
                        {"code": "", "quantity": 4},
                        {"code": "empty_stack", "quantity": 0},
                    ]
                }
            }
        return super().get(endpoint, params)


class InventoryCleanupServiceTests(unittest.TestCase):
    def test_cleanup_reserves_requested_items_and_protects_gear(self):
        api = FakeGameAPI(
            inventory={
                "copper_ore": 5,
                "wooden_staff": 1,
                "voidstone_pickaxe": 1,
                "unworn_weapon": 1,
                "cooked_shrimp": 2,
            }
        )
        api.items["unworn_weapon"] = {
            "code": "unworn_weapon",
            "type": "weapon",
        }
        api.character["weapon_slot"] = "wooden_staff"
        character = CharacterService(api, "tester")
        movement = MovementService(api, "tester")
        bank = BankService(api, "tester", movement, character)
        items = ItemCatalogService(api)
        cleanup = InventoryCleanupService(bank, character, items)

        self.assertTrue(cleanup.deposit_unneeded_items({"copper_ore": 2}))

        self.assertEqual(
            api.inventory,
            {
                "copper_ore": 2,
                "wooden_staff": 1,
                "voidstone_pickaxe": 1,
                "unworn_weapon": 1,
            },
        )
        self.assertEqual(api.bank, {"copper_ore": 3, "cooked_shrimp": 2})

    def test_incomplete_character_or_item_data_aborts_without_depositing(self):
        api = FakeGameAPI(inventory={"copper_ore": 2})
        services = build_services(api, "tester", (), 0)
        api.fail_get_endpoints.add("/characters/tester")

        self.assertFalse(services.combat.cleanup_service.deposit_unneeded_items())
        self.assertEqual(api.inventory, {"copper_ore": 2})

        api.fail_get_endpoints.clear()
        api.items["copper_ore"] = None
        self.assertFalse(services.combat.cleanup_service.deposit_unneeded_items())
        self.assertEqual(api.inventory, {"copper_ore": 2})

    def test_bank_failure_leaves_inventory_untouched(self):
        api = FakeGameAPI(inventory={"copper_ore": 2})
        api.fail_actions.add("bank/deposit/item")
        cleanup = build_services(api, "tester", (), 0).combat.cleanup_service

        self.assertFalse(cleanup.deposit_unneeded_items())
        self.assertEqual(api.inventory, {"copper_ore": 2})
        self.assertEqual(api.bank, {})

    def test_no_unneeded_items_is_a_success_without_bank_travel(self):
        api = FakeGameAPI(inventory={"voidstone_pickaxe": 1})
        cleanup = build_services(api, "tester", (), 0).combat.cleanup_service

        self.assertTrue(cleanup.deposit_unneeded_items())
        self.assertEqual(api.moves, [])
        self.assertEqual(api.inventory, {"voidstone_pickaxe": 1})

    def test_invalid_character_response_aborts_cleanup(self):
        api = InvalidCharacterResponseAPI()
        cleanup = build_services(api, "tester", (), 0).combat.cleanup_service

        self.assertFalse(cleanup.deposit_unneeded_items())
        self.assertEqual(api.bank, {})

    def test_malformed_and_empty_inventory_entries_are_ignored(self):
        api = MalformedInventoryAPI()
        cleanup = build_services(api, "tester", (), 0).combat.cleanup_service

        self.assertTrue(cleanup.deposit_unneeded_items())
        self.assertEqual(api.moves, [])

    def test_item_inspection_exception_aborts_without_partial_deposit(self):
        api = FakeGameAPI(inventory={"copper_ore": 2, "shrimp": 1})
        api.fail_get_endpoints.add("/items/shrimp")
        cleanup = build_services(api, "tester", (), 0).combat.cleanup_service

        self.assertFalse(cleanup.deposit_unneeded_items())
        self.assertEqual(api.inventory, {"copper_ore": 2, "shrimp": 1})
        self.assertEqual(api.bank, {})


if __name__ == "__main__":
    unittest.main()
