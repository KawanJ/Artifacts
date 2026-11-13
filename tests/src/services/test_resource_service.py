import unittest

from scripts.bootstrap import build_services
from src.client.api_client import APIError
from tests.fake_game_api import FakeGameAPI


class UnexpectedGatherAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        if endpoint.endswith("/action/gathering"):
            raise RuntimeError("gather transport unavailable")
        return super().post(endpoint, data, params)


class NoCooldownGatherAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        response = super().post(endpoint, data, params)
        if endpoint.endswith("/action/gathering"):
            response["data"].pop("cooldown", None)
        return response


class RetryMovementFailureAPI(FakeGameAPI):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.move_attempts = 0

    def post(self, endpoint, data=None, params=None):
        if endpoint.endswith("/action/move"):
            self.move_attempts += 1
            if self.move_attempts == 3:
                raise APIError("retry move failed", status_code=500)
        return super().post(endpoint, data, params)


class ResourceServiceTests(unittest.TestCase):
    def test_gathering_equips_strongest_owned_tool_and_banks_resource(self):
        api = FakeGameAPI(
            inventory={"voidstone_pickaxe": 1, "copper_pickaxe": 1}
        )
        resource = build_services(api, "tester", (), 0).resource

        self.assertTrue(resource.gather_resource("copper_ore"))

        self.assertEqual(api.character["weapon_slot"], "voidstone_pickaxe")
        self.assertEqual(api.inventory["voidstone_pickaxe"], 1)
        self.assertEqual(api.inventory["copper_pickaxe"], 1)
        self.assertEqual(api.bank, {"copper_ore": 1})

    def test_best_tool_already_equipped_is_not_equipped_again(self):
        api = FakeGameAPI(inventory={"voidstone_pickaxe": 1})
        api.character["weapon_slot"] = "voidstone_pickaxe"
        resource = build_services(api, "tester", (), 0).resource

        self.assertTrue(resource.gather_resource("copper_ore"))
        self.assertEqual(api.equip_attempts, 0)

    def test_gather_succeeds_when_action_response_omits_cooldown(self):
        api = NoCooldownGatherAPI()
        resource = build_services(api, "tester", (), 0).resource

        self.assertTrue(resource.gather_resource("copper_ore"))
        self.assertEqual(api.bank, {"copper_ore": 1})

    def test_unknown_gathering_subtype_continues_without_a_tool(self):
        api = FakeGameAPI()
        resource = build_services(api, "tester", (), 0).resource

        self.assertTrue(resource.gather_resource("sunflower"))
        self.assertEqual(api.gathered, {"sunflower": 1})
        self.assertEqual(api.bank, {"sunflower": 1})

    def test_move_failure_prevents_gathering(self):
        api = FakeGameAPI()
        api.fail_actions.add("move")
        resource = build_services(api, "tester", (), 0).resource

        self.assertFalse(resource.gather_resource("copper_ore"))
        self.assertEqual(api.gather_attempts, 0)

    def test_tool_lookup_failure_does_not_prevent_gathering(self):
        api = FakeGameAPI()
        api.fail_once_get_endpoints.add("/characters/tester")
        resource = build_services(api, "tester", (), 0).resource

        self.assertTrue(resource.gather_resource("copper_ore"))
        self.assertEqual(api.bank, {"copper_ore": 1})

    def test_resource_metadata_failure_is_nonfatal_when_gathering_can_continue(self):
        api = FakeGameAPI()
        api.fail_once_get_endpoints.add("/items/copper_ore")
        resource = build_services(api, "tester", (), 0).resource

        self.assertTrue(resource.gather_resource("copper_ore"))
        self.assertEqual(api.bank, {"copper_ore": 1})

    def test_tool_equipment_failure_continues_without_tool(self):
        api = FakeGameAPI(inventory={"voidstone_pickaxe": 1})
        api.fail_actions.add("equip")
        resource = build_services(api, "tester", (), 0).resource

        self.assertTrue(resource.gather_resource("copper_ore"))
        self.assertEqual(api.gathered, {"copper_ore": 1})
        self.assertNotEqual(api.character["weapon_slot"], "voidstone_pickaxe")

    def test_full_inventory_is_cleaned_and_gather_retried_once(self):
        api = FakeGameAPI(
            inventory={f"material_{index}": 1 for index in range(20)}
        )
        resource = build_services(api, "tester", (), 0).resource

        self.assertTrue(resource.gather_resource("copper_ore"))

        self.assertEqual(api.gather_attempts, 2)
        self.assertEqual(api.gathered, {"copper_ore": 1})
        self.assertEqual(api.bank.get("material_0"), 1)
        self.assertEqual(api.bank.get("copper_ore"), 1)
        self.assertEqual(api.inventory, {})

    def test_unknown_resource_and_failed_gather_return_false(self):
        api = FakeGameAPI()
        resource = build_services(api, "tester", (), 0).resource

        self.assertFalse(resource.gather_resource("unknown_resource"))

        api.fail_actions.add("gathering")
        self.assertFalse(resource.gather_resource("copper_ore"))
        self.assertEqual(api.gathered, {})

    def test_failed_cleanup_after_gather_reports_failure_but_keeps_resource(self):
        api = FakeGameAPI()
        api.fail_actions.add("bank/deposit/item")
        resource = build_services(api, "tester", (), 0).resource

        self.assertFalse(resource.gather_resource("copper_ore"))
        self.assertEqual(api.inventory, {"copper_ore": 1})

    def test_full_inventory_is_not_retried_when_cleanup_cannot_deposit(self):
        api = FakeGameAPI(
            inventory={f"material_{index}": 1 for index in range(20)}
        )
        api.fail_actions.add("bank/deposit/item")
        resource = build_services(api, "tester", (), 0).resource

        self.assertFalse(resource.gather_resource("copper_ore"))
        self.assertEqual(api.gather_attempts, 1)
        self.assertEqual(len(api.inventory), 20)

    def test_full_inventory_retry_is_limited_to_one_attempt(self):
        api = FakeGameAPI(
            inventory={f"material_{index}": 1 for index in range(20)}
        )
        resource = build_services(api, "tester", (), 0).resource

        self.assertFalse(
            resource.gather_resource(
                "copper_ore",
                keep_items={f"material_{index}": 1 for index in range(20)},
            )
        )
        self.assertEqual(api.gather_attempts, 2)
        self.assertEqual(len(api.inventory), 20)

    def test_failed_move_back_to_resource_aborts_full_inventory_retry(self):
        api = RetryMovementFailureAPI(
            inventory={f"material_{index}": 1 for index in range(20)}
        )
        resource = build_services(api, "tester", (), 0).resource

        self.assertFalse(resource.gather_resource("copper_ore"))
        self.assertEqual(api.gather_attempts, 1)

    def test_unexpected_gather_transport_error_returns_false(self):
        api = UnexpectedGatherAPI()
        resource = build_services(api, "tester", (), 0).resource

        self.assertFalse(resource.gather_resource("copper_ore"))
        self.assertEqual(api.inventory, {})

    def test_invalid_quantity_and_unexpected_service_failure_still_cleanup(self):
        api = FakeGameAPI()
        resource = build_services(api, "tester", (), 0).resource
        self.assertFalse(resource.gather_resource("copper_ore", "invalid"))

        def unexpected_failure(resource_code, amount, keep_items):
            raise RuntimeError("unexpected gathering failure")

        resource._gather_resource = unexpected_failure
        self.assertFalse(resource.gather_resource("copper_ore"))
        self.assertEqual(api.inventory, {})


if __name__ == "__main__":
    unittest.main()
