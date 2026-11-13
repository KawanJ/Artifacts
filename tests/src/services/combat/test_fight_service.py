import unittest

from src.client.api_client import APIError
from src.services.combat.fight_service import FightService
from tests.fake_game_api import FakeGameAPI


class InvalidFightResponseAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        if endpoint.endswith("/action/fight"):
            return {"data": []}
        return super().post(endpoint, data, params)


class NoCooldownFightAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        response = super().post(endpoint, data, params)
        if endpoint.endswith("/action/fight"):
            response["data"].pop("cooldown", None)
        return response


class FightServiceTests(unittest.TestCase):
    def test_fight_returns_action_data_and_records_one_fight(self):
        api = FakeGameAPI()
        service = FightService(api, "tester")

        result = service.fight_once()

        self.assertIn("fight", result)
        self.assertEqual(api.fights, [(0, 0)])

    def test_malformed_fight_response_returns_none(self):
        service = FightService(InvalidFightResponseAPI(), "tester")

        self.assertIsNone(service.fight_once())

    def test_fight_succeeds_when_response_omits_cooldown(self):
        api = NoCooldownFightAPI()

        self.assertIn("fight", FightService(api, "tester").fight_once())
        self.assertEqual(api.fights, [(0, 0)])

    def test_action_error_is_propagated_for_combat_coordinator(self):
        api = FakeGameAPI()
        api.fail_actions.add("fight")
        service = FightService(api, "tester")

        with self.assertRaises(APIError):
            service.fight_once()
        self.assertEqual(api.fights, [])


if __name__ == "__main__":
    unittest.main()
