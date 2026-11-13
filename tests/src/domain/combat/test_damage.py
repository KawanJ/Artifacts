import unittest

from src.domain.combat.damage import (
    estimate_damage_per_turn,
    item_effects,
    round_damage,
)


class CombatDamageTests(unittest.TestCase):
    def test_damage_applies_bonus_resistance_and_critical_rounding(self):
        attacker = {
            "attack_fire": 10,
            "dmg": 10,
            "critical_strike": 1,
        }
        target = {"res_fire": 20}

        self.assertEqual(estimate_damage_per_turn(attacker, target, critical=False), 9)
        self.assertEqual(estimate_damage_per_turn(attacker, target, critical=True), 14)

    def test_rounding_and_negative_resistance_damage_floor(self):
        self.assertEqual(round_damage(2.5), 3)
        self.assertEqual(
            estimate_damage_per_turn(
                {"attack_fire": 3},
                {"res_fire": 150},
                critical=False,
            ),
            0,
        )

    def test_item_effects_sums_repeated_numeric_effects_and_ignores_irrelevant_data(self):
        effects = item_effects(
            {
                "effects": [
                    {"code": "attack_fire", "value": 2},
                    {"code": "attack_fire", "value": 3},
                    {"code": "heal", "value": 50},
                    {"code": "dmg", "value": "invalid"},
                    None,
                ]
            }
        )

        self.assertEqual(effects, {"attack_fire": 5.0})


if __name__ == "__main__":
    unittest.main()
