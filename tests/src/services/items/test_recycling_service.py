import unittest

from src.services.items.recycling_service import RecyclingService
from tests.fake_game_api import FakeGameAPI


class NoCooldownRecycleAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        response = super().post(endpoint, data, params)
        if endpoint.endswith("/action/recycling"):
            response["data"].pop("cooldown", None)
        return response


class RecyclingServiceTests(unittest.TestCase):
    def test_recycling_consumes_item_and_increases_its_crafting_skill(self):
        api = FakeGameAPI(inventory={"wooden_staff": 1})
        service = RecyclingService(api, "tester")

        self.assertTrue(service.recycle_item("wooden_staff"))

        self.assertEqual(api.inventory, {})
        self.assertEqual(api.character["weaponcrafting_level"], 1)

    def test_recycling_api_failure_does_not_change_character_state(self):
        api = FakeGameAPI(inventory={"wooden_staff": 1})
        api.fail_actions.add("recycling")
        service = RecyclingService(api, "tester")

        self.assertFalse(service.recycle_item("wooden_staff"))
        self.assertEqual(api.inventory, {"wooden_staff": 1})
        self.assertEqual(api.character["weaponcrafting_level"], 0)

    def test_recycling_succeeds_when_response_has_no_cooldown(self):
        api = NoCooldownRecycleAPI(inventory={"wooden_staff": 1})

        self.assertTrue(RecyclingService(api, "tester").recycle_item("wooden_staff"))
        self.assertEqual(api.inventory, {})
        self.assertEqual(api.character["weaponcrafting_level"], 1)


if __name__ == "__main__":
    unittest.main()
