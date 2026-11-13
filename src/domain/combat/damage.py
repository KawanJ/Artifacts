"""Pure damage estimates used by combat preparation and equipment selection."""
import math
from typing import Any, Dict

ELEMENTS = ("fire", "earth", "water", "air")
OFFENSIVE_STATS = (
    "attack_fire",
    "attack_earth",
    "attack_water",
    "attack_air",
    "dmg",
    "dmg_fire",
    "dmg_earth",
    "dmg_water",
    "dmg_air",
    "critical_strike",
)


def item_effects(item_data: Dict[str, Any]) -> Dict[str, float]:
    """Return the numeric effects relevant to weapon damage calculations."""
    effects: Dict[str, float] = {}
    for effect in item_data.get("effects", []) or []:
        if not isinstance(effect, dict):
            continue
        code = effect.get("code")
        value = effect.get("value")
        if code in OFFENSIVE_STATS and isinstance(value, (int, float)):
            effects[code] = effects.get(code, 0) + float(value)
    return effects


def round_damage(value: float) -> int:
    """Round damage with the game's half-up rule."""
    return math.floor(value + 0.5)


def estimate_damage_per_turn(
    attacker_data: Dict[str, Any],
    target_data: Dict[str, Any],
    critical: bool,
) -> int:
    """Estimate damage per turn against a target, with or without a critical hit."""
    total_damage = 0
    critical_strike = float(attacker_data.get("critical_strike", 0) or 0)
    for element in ELEMENTS:
        attack = round_damage(
            float(attacker_data.get(f"attack_{element}", 0) or 0)
            * (
                1
                + (
                    float(attacker_data.get("dmg", 0) or 0)
                    + float(attacker_data.get(f"dmg_{element}", 0) or 0)
                )
                / 100
            )
        )
        resistance = float(target_data.get(f"res_{element}", 0) or 0)
        damage = max(0, round_damage(attack * (1 - resistance / 100)))
        if critical and critical_strike > 0:
            damage = round_damage(damage * 1.5)
        total_damage += damage
    return total_damage


def estimate_weapon_expected_damage(
    character_data: Dict[str, Any],
    current_weapon_effects: Dict[str, float],
    candidate_effects: Dict[str, float],
    monster_data: Dict[str, Any],
) -> float:
    """Estimate one-turn damage after replacing the currently equipped weapon."""
    stats = {
        stat: float(character_data.get(stat, 0) or 0)
        - current_weapon_effects.get(stat, 0)
        + candidate_effects.get(stat, 0)
        for stat in OFFENSIVE_STATS
    }
    crit_chance = min(max(stats["critical_strike"], 0), 100) / 100
    expected_damage = 0.0

    for element in ELEMENTS:
        attack = round_damage(
            stats[f"attack_{element}"]
            * (1 + (stats["dmg"] + stats[f"dmg_{element}"]) / 100)
        )
        resistance = float(monster_data.get(f"res_{element}", 0) or 0)
        damage = round_damage(attack * (1 - resistance / 100))
        critical_damage = round_damage(damage * 1.5)
        expected_damage += (
            damage * (1 - crit_chance) + critical_damage * crit_chance
        )

    return expected_damage
