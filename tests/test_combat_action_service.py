import unittest
from unittest.mock import Mock, patch

from src.client.api_client import APIError
from src.services.combat.combat_action_service import CombatActionService


class CombatActionServiceTests(unittest.TestCase):
    def test_inventory_retry_move_failure_returns_none(self):
        api_client = Mock()
        api_client.post.side_effect = APIError("Inventory full", status_code=497)
        banking_service = Mock()
        banking_service.deposit_common_items.return_value = True
        action_service = CombatActionService(
            api_client,
            "character",
            banking_service,
            Mock(),
        )

        with patch.object(action_service, "move_to_monster", return_value=False):
            result = action_service.fight_once("monster")

        self.assertIsNone(result)

    def test_successful_fight_returns_response_data(self):
        fight_data = {"fight": {"result": "win"}}
        api_client = Mock()
        api_client.post.return_value = {"data": fight_data}
        action_service = CombatActionService(
            api_client,
            "character",
            Mock(),
            Mock(),
        )

        self.assertEqual(action_service.fight_once("monster"), fight_data)


if __name__ == "__main__":
    unittest.main()
