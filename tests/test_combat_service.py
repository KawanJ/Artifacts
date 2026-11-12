import unittest
from unittest.mock import Mock

from src.services.combat_service import CombatService


class CombatRecoveryTests(unittest.TestCase):
    def make_service(self, hp, max_hp, healing_items):
        service = CombatService.__new__(CombatService)
        service.character_service = Mock()
        current_hp = [hp]
        service.character_service.get_hp_status.side_effect = lambda: (current_hp[0], max_hp)
        service.character_service.get_available_healing_items.return_value = healing_items
        service.character_service.use_healing_item.side_effect = lambda code: (
            current_hp.__setitem__(
                0, min(max_hp, current_hp[0] + healing_items[code][1])
            )
            or True
        )
        service.rest = Mock(side_effect=lambda: current_hp.__setitem__(0, max_hp) or True)
        return service

    def test_uses_non_overflowing_heal_to_reach_fight_threshold(self):
        service = self.make_service(80, 100, {"apple": (1, 20)})

        self.assertTrue(service._recover_to_hp(100))

        service.character_service.use_healing_item.assert_called_once_with("apple")
        service.rest.assert_not_called()

    def test_rests_instead_of_overflowing_healing_item(self):
        service = self.make_service(80, 100, {"fried_eggs": (1, 150)})

        self.assertTrue(service._recover_to_hp(100))

        service.character_service.use_healing_item.assert_not_called()
        service.rest.assert_called_once_with()


class FightThresholdTests(unittest.TestCase):
    def test_uses_minimum_player_damage_and_maximum_monster_damage(self):
        service = CombatService.__new__(CombatService)
        service.character_service = Mock()
        service.character_service.get_character_data.return_value = {
            "max_hp": 100,
            "attack_fire": 10,
            "res_fire": 20,
        }
        service.api_client = Mock()
        service.api_client.get.return_value = {
            "data": {"hp": 21, "attack_fire": 5, "critical_strike": 1}
        }

        self.assertEqual(service._minimum_hp_to_fight("test_monster"), 19)


if __name__ == "__main__":
    unittest.main()
