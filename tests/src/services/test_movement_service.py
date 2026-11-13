import unittest

from src.client.api_client import APIError
from src.services.movement_service import MovementService
from tests.fake_game_api import FakeGameAPI


class AlreadyThereAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        if endpoint.endswith("/action/move"):
            raise APIError("already at the destination", status_code=490)
        return super().post(endpoint, data, params)


class UnexpectedMoveAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        if endpoint.endswith("/action/move"):
            raise RuntimeError("transport unavailable")
        return super().post(endpoint, data, params)


class DifferentAlreadyThereAPI(FakeGameAPI):
    def post(self, endpoint, data=None, params=None):
        if endpoint.endswith("/action/move"):
            raise APIError("destination is occupied", status_code=490)
        return super().post(endpoint, data, params)


class MovementServiceTests(unittest.TestCase):
    def test_successful_move_updates_character_location(self):
        api = FakeGameAPI()
        service = MovementService(api, "tester")

        self.assertTrue(service.move_to_location(2, 3))

        self.assertEqual((api.character["x"], api.character["y"]), (2, 3))

    def test_already_at_destination_is_treated_as_success(self):
        api = AlreadyThereAPI()
        service = MovementService(api, "tester")

        self.assertTrue(service.move_to_location(2, 3))
        self.assertEqual(api.moves, [])

    def test_other_api_errors_fail_the_move(self):
        api = FakeGameAPI()
        api.fail_actions.add("move")
        service = MovementService(api, "tester")

        self.assertFalse(service.move_to_location(2, 3))
        self.assertEqual((api.character["x"], api.character["y"]), (0, 0))

    def test_unexpected_transport_error_fails_without_moving_character(self):
        api = UnexpectedMoveAPI()

        self.assertFalse(MovementService(api, "tester").move_to_location(2, 3))
        self.assertEqual((api.character["x"], api.character["y"]), (0, 0))

    def test_unrelated_status_490_is_not_mistaken_for_already_there(self):
        api = DifferentAlreadyThereAPI()

        self.assertFalse(MovementService(api, "tester").move_to_location(2, 3))


if __name__ == "__main__":
    unittest.main()
