import unittest

from scripts.bootstrap import build_services
from src.services.inventory.bank_service import BankService
from tests.fake_game_api import FakeGameAPI


class InvalidBankResponseAPI(FakeGameAPI):
    def get(self, endpoint, params=None):
        if endpoint == "/my/bank/items":
            return {"data": None}
        return super().get(endpoint, params)


class UnexpectedBankAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        if "/action/bank/" in endpoint:
            raise RuntimeError("bank transport unavailable")
        return super().post(endpoint, data, params)


class NoCooldownBankAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        response = super().post(endpoint, data, params)
        if "/action/bank/" in endpoint:
            response["data"].pop("cooldown", None)
        return response


class BankServiceTests(unittest.TestCase):
    def make_bank(self, api):
        services = build_services(api, "tester", (), 0)
        return BankService(
            api,
            "tester",
            services.combat.movement_service,
            services.character,
        )

    def test_withdraw_and_deposit_move_only_available_positive_quantities(self):
        api = FakeGameAPI(inventory={"copper_ore": 3})
        api.bank["shrimp"] = 4
        bank = self.make_bank(api)

        self.assertEqual(bank.get_bank_item_quantity("shrimp"), 4)
        self.assertTrue(bank.withdraw_items({"shrimp": 2, "copper_ore": 0}))
        self.assertTrue(bank.deposit_items({"copper_ore": 10, "missing": 1}))

        self.assertEqual(api.inventory, {"shrimp": 2})
        self.assertEqual(api.bank, {"shrimp": 2, "copper_ore": 3})

    def test_empty_transfer_is_success_without_moving(self):
        api = FakeGameAPI()
        bank = self.make_bank(api)

        self.assertTrue(bank.withdraw_items({"shrimp": 0}))
        self.assertTrue(bank.deposit_items({"shrimp": 1}))
        self.assertEqual(api.moves, [])

    def test_transfer_api_errors_do_not_report_success(self):
        api = FakeGameAPI(inventory={"copper_ore": 1})
        api.bank["shrimp"] = 1
        api.fail_actions.update({"bank/deposit/item", "bank/withdraw/item"})
        bank = self.make_bank(api)

        self.assertFalse(bank.withdraw_items({"shrimp": 1}))
        self.assertFalse(bank.deposit_items({"copper_ore": 1}))
        self.assertEqual(api.inventory, {"copper_ore": 1})
        self.assertEqual(api.bank, {"shrimp": 1})

    def test_move_failure_prevents_bank_action(self):
        api = FakeGameAPI(inventory={"copper_ore": 1})
        api.fail_actions.add("move")
        bank = self.make_bank(api)

        self.assertFalse(bank.withdraw_items({"shrimp": 1}))
        self.assertFalse(bank.deposit_items({"copper_ore": 1}))
        self.assertEqual(api.inventory, {"copper_ore": 1})
        self.assertEqual(api.bank, {})

    def test_invalid_bank_inventory_shape_is_reported(self):
        bank = self.make_bank(InvalidBankResponseAPI())

        with self.assertRaisesRegex(ValueError, "Invalid bank inventory response"):
            bank.get_bank_item_quantity("shrimp")

    def test_unexpected_bank_transport_errors_return_false(self):
        api = UnexpectedBankAPI(inventory={"copper_ore": 1})
        api.bank["shrimp"] = 1
        bank = self.make_bank(api)

        self.assertFalse(bank.withdraw_items({"shrimp": 1}))
        self.assertFalse(bank.deposit_items({"copper_ore": 1}))
        self.assertEqual(api.inventory, {"copper_ore": 1})
        self.assertEqual(api.bank, {"shrimp": 1})

    def test_transfers_work_when_action_response_omits_cooldown(self):
        api = NoCooldownBankAPI(inventory={"copper_ore": 1})
        api.bank["shrimp"] = 1
        bank = self.make_bank(api)

        self.assertTrue(bank.withdraw_items({"shrimp": 1}))
        self.assertTrue(bank.deposit_items({"copper_ore": 1}))
        self.assertEqual(api.inventory, {"shrimp": 1})
        self.assertEqual(api.bank, {"copper_ore": 1})


if __name__ == "__main__":
    unittest.main()
