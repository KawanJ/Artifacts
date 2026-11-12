"""Combat service for fighting monsters."""
import logging
import math
import time
from typing import Dict, Any

from src.client.api_client import APIClient, APIError
from src.models.monster_locations import get_monster_location
from src.services.banking_service import BankingService
from src.services.character_service import CharacterService
from src.services.item_service import ItemService
from src.services.movement_service import MovementService

logger = logging.getLogger(__name__)

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


class CombatService:
    """Service for managing combat and monster fights."""

    def __init__(self, api_client: APIClient, character_name: str):
        """Initialize CombatService.
        
        Args:
            api_client: API client instance.
            character_name: Name of the character to control.
        """
        self.api_client = api_client
        self.character_name = character_name
        self.movement_service = MovementService(api_client, character_name)
        self.character_service = CharacterService(api_client, character_name)
        self.banking_service = BankingService(api_client, character_name)
        self.item_service = ItemService(api_client)

    @staticmethod
    def _item_effects(item_data: Dict[str, Any]) -> Dict[str, float]:
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

    @staticmethod
    def _round_damage(value: float) -> int:
        """Round damage with the game's half-up rule."""
        return math.floor(value + 0.5)

    @classmethod
    def _damage_per_turn(
        cls,
        attacker_data: Dict[str, Any],
        target_data: Dict[str, Any],
        critical: bool,
    ) -> int:
        """Estimate damage per turn against a target, with or without a critical hit."""
        total_damage = 0
        critical_strike = float(attacker_data.get("critical_strike", 0) or 0)
        for element in ELEMENTS:
            attack = cls._round_damage(
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
            damage = max(0, cls._round_damage(attack * (1 - resistance / 100)))
            if critical and critical_strike > 0:
                damage = cls._round_damage(damage * 1.5)
            total_damage += damage
        return total_damage

    @classmethod
    def _weapon_expected_damage(
        cls,
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
            attack = cls._round_damage(
                stats[f"attack_{element}"]
                * (1 + (stats["dmg"] + stats[f"dmg_{element}"]) / 100)
            )
            resistance = float(monster_data.get(f"res_{element}", 0) or 0)
            damage = cls._round_damage(attack * (1 - resistance / 100))
            critical_damage = cls._round_damage(damage * 1.5)
            expected_damage += (
                damage * (1 - crit_chance) + critical_damage * crit_chance
            )

        return expected_damage

    def _minimum_hp_to_fight(self, monster_code: str) -> int:
        """Estimate HP needed to survive the fight using minimum player damage."""
        character_data = self.character_service.get_character_data()
        monster_response = self.api_client.get(f"/monsters/{monster_code}")
        monster_data = monster_response.get("data")
        if not isinstance(monster_data, dict):
            raise ValueError(f"No monster data returned for {monster_code}")

        max_hp = int(character_data.get("max_hp", 0) or 0)
        monster_hp = int(monster_data.get("hp", 0) or 0)
        if max_hp <= 0 or monster_hp <= 0:
            raise ValueError(f"Invalid HP data for combat with {monster_code}")

        minimum_player_damage = self._damage_per_turn(
            character_data, monster_data, critical=False
        )
        maximum_monster_damage = self._damage_per_turn(
            monster_data, character_data, critical=True
        )
        if minimum_player_damage <= 0:
            logger.warning(
                "Could not estimate positive minimum damage against %s; requiring full HP.",
                monster_code,
            )
            return max_hp

        turns_to_defeat = math.ceil(monster_hp / minimum_player_damage)
        maximum_fight_damage = turns_to_defeat * maximum_monster_damage
        required_hp = maximum_fight_damage + 1
        if required_hp > max_hp:
            logger.warning(
                "Worst-case estimated damage from %s (%s HP) exceeds max HP (%s); "
                "preparing at max HP.",
                monster_code,
                maximum_fight_damage,
                max_hp,
            )
            return max_hp

        logger.info(
            "Estimated fight threshold for %s: %s HP "
            "(minimum player damage %s/turn, maximum monster damage %s/turn, %s turns).",
            monster_code,
            required_hp,
            minimum_player_damage,
            maximum_monster_damage,
            turns_to_defeat,
        )
        return max(1, required_hp)

    def _equip_combat_weapon(self, monster_code: str) -> bool:
        """Equip the owned weapon with the highest expected damage against a monster."""
        try:
            character_data = self.character_service.get_character_data()
            monster_response = self.api_client.get(f"/monsters/{monster_code}")
        except Exception as e:
            logger.warning(f"Could not load combat data for {monster_code}: {e}")
            return False

        monster_data = monster_response.get("data")
        if not isinstance(monster_data, dict):
            logger.warning(f"No monster data returned for {monster_code}; keeping current weapon.")
            return False

        inventory = character_data.get("inventory", []) or []
        inventory_codes = {
            entry.get("code")
            for entry in inventory
            if isinstance(entry, dict)
            and entry.get("code")
            and (entry.get("quantity", 0) or 0) > 0
        }
        equipped_code = character_data.get("weapon_slot")
        available_codes = inventory_codes | ({equipped_code} if equipped_code else set())
        weapon_data: Dict[str, Dict[str, Any]] = {}
        try:
            for item_code in available_codes:
                item_data = self.item_service.get_item(item_code)
                if not isinstance(item_data, dict):
                    logger.warning(
                        f"Item data for '{item_code}' is unavailable; keeping current weapon."
                    )
                    return False
                if item_data.get("type") == "weapon":
                    weapon_data[item_code] = item_data
        except Exception as e:
            logger.warning(f"Could not load owned weapon data: {e}")
            return False

        current_weapon = weapon_data.get(equipped_code, {})
        current_weapon_effects = self._item_effects(current_weapon)
        candidates = sorted(
            [
                (
                    self._weapon_expected_damage(
                        character_data,
                        current_weapon_effects,
                        self._item_effects(item_data),
                        monster_data,
                    ),
                    weapon_code,
                )
                for weapon_code, item_data in weapon_data.items()
            ],
            reverse=True,
        )

        if not candidates:
            logger.info("No owned combat weapon found; continuing without changing equipment.")
            return False

        logger.info(
            "Weapon damage estimates against %s: %s",
            monster_code,
            ", ".join(f"{code}={damage:.2f}" for damage, code in candidates),
        )
        if equipped_code and any(
            damage == candidates[0][0] and code == equipped_code
            for damage, code in candidates
        ):
            logger.info(f"Best available weapon '{equipped_code}' is already equipped.")
            return True

        for _, weapon_code in candidates:
            if weapon_code == equipped_code:
                logger.info(f"Using currently equipped weapon '{weapon_code}' as fallback.")
                return True

            logger.info(f"Equipping best available combat weapon '{weapon_code}'.")
            if self.character_service.equip_item(weapon_code):
                return True
            logger.warning(f"Could not equip combat weapon '{weapon_code}'; trying another.")

        logger.warning("No available combat weapon could be equipped.")
        return False

    def get_monster_code_for_drop(self, drop_code: str) -> str | None:
        """Get a monster code for an item by querying the API's drop filter."""
        response = self.api_client.get("/monsters", params={"drop": drop_code})
        monsters = response.get("data")
        if not isinstance(monsters, list):
            return None

        for monster in monsters:
            if not isinstance(monster, dict) or not isinstance(monster.get("code"), str):
                continue
            drops = monster.get("drops", [])
            if isinstance(drops, list) and any(
                isinstance(drop, dict) and drop.get("code") == drop_code
                for drop in drops
            ):
                return monster["code"]

        return None

    def _move_to_monster(self, monster_code: str) -> bool:
        # Get monster coordinates
        x, y = get_monster_location(monster_code)
        logger.info(f"Monster {monster_code} is at ({x}, {y})")

        # Move to location once
        if not self.movement_service.move_to_location(x, y):
            logger.error("Failed to move to monster location")
            return False
        
        return True

    def _fight_once(self, monster_code: str, allow_retry: bool = True) -> Dict[str, Any]:
        """Perform a single fight; optionally retry once after banking common items."""
        logger.info("Starting fight...")
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/fight",
                data={}
            )
            logger.debug(f"Fight result: {response}")

            # Check for cooldown and wait if necessary
            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info(f"Waiting {cooldown_seconds} seconds for fight cooldown...")
                time.sleep(cooldown_seconds)

            return response.get("data", {})

        except APIError as e:
            # If inventory is full, deposit common items and retry once
            if allow_retry and e.status_code == 497:
                logger.warning("Inventory full during fight; depositing common items and retrying...")
                if not self.banking_service.deposit_common_items():
                    logger.error("Failed to deposit common items; aborting fight.")
                    return {}
                
                if not self._move_to_monster(monster_code):
                    return False
            
                return self._fight_once(monster_code, allow_retry=False)

            logger.error(f"Failed to fight monster: {e}")
            return {}

        except Exception as e:
            logger.error(f"Failed to fight monster: {e}")
            return {}

    def fight_monster(self, monster_code: str) -> Dict[str, Any]:
        """Fight a monster at current location.

        Returns:
            Response data if successful, empty dict otherwise.
        """
        return self._fight_once(monster_code)

    def farm_drops(self, target_item_code: str, target_quantity: int, monster_code: str | None = None) -> bool:
        """Fight monsters until required drop quantity is achieved.

        Args:
            target_item_code: Item code of required drop (e.g., raw_chicken).
            target_quantity: Amount of item to collect.
            monster_code: Optional monster code to fight; if missing, inferred from target_item_code.

        Returns:
            True if target quantity reached, False otherwise.
        """
        if target_quantity <= 0:
            logger.info("No drops required; skipping combat drop farming.")
            return True

        monster_code = monster_code or self.get_monster_code_for_drop(target_item_code)
        if not monster_code:
            logger.error(f"Cannot determine which monster drops '{target_item_code}'.")
            return False

        if not self._equip_combat_weapon(monster_code):
            logger.warning("Unable to equip combat weapon; continuing without a dedicated weapon.")

        if not self._move_to_monster(monster_code):
            return False

        required_hp = self._minimum_hp_to_fight(monster_code)
        collected = 0
        attempts = 0
        while collected < target_quantity:
            attempts += 1
            logger.info(f"Combat drop farm attempt {attempts}: collected {collected}/{target_quantity} {target_item_code}")
            if not self._recover_to_hp(required_hp):
                logger.error("Failed to reach the required HP before farming fight")
                return False

            fight_response = self._fight_once(monster_code)
            if not fight_response:
                logger.error("Fight failed during drop farm; aborting")
                return False

            # parse drop count
            drops = []
            fight_info = fight_response.get("fight", {})
            characters = fight_info.get("characters", [])
            if characters and isinstance(characters, list):
                first_char = characters[0]
                drops = first_char.get("drops", []) or []

            for drop in drops:
                if drop.get("code") == target_item_code:
                    qty = int(drop.get("quantity", 0))
                    collected += qty
                    logger.info(f"Received {qty}x {target_item_code} from fight; total collected is now {collected}")

            # if no relevant drops but fight succeeded, continue
            if collected >= target_quantity:
                self.rest()
                logger.info(f"Target drop quantity reached: {collected}/{target_quantity}")
                return True

        return True

    def rest(self) -> bool:
        """Rest to recover health/mana.

        Returns:
            True if successful, False otherwise.
        """
        logger.info("Resting to recover...")
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/rest",
                data={}
            )
            logger.debug(f"Rest result: {response}")

            # Check for cooldown and wait if necessary
            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info(f"Waiting {cooldown_seconds} seconds for rest cooldown...")
                time.sleep(cooldown_seconds)

            return True
        except Exception as e:
            logger.error(f"Failed to rest: {e}")
            return False

    def _recover_to_hp(self, target_hp: int) -> bool:
        """Recover to a target HP using non-overflowing healing items before resting.

        Args:
            target_hp: Minimum HP to have before the next fight.

        Returns:
            True if recovery succeeded, False otherwise.
        """
        hp, max_hp = self.character_service.get_hp_status()
        target_hp = min(max(target_hp, 1), max_hp)
        if hp >= target_hp:
            logger.debug("HP is already at the required fight threshold.")
            return True

        healing_items = self.character_service.get_available_healing_items()
        while hp < target_hp:
            missing_hp = max_hp - hp
            usable_items = [
                (code, qty, heal)
                for code, (qty, heal) in healing_items.items()
                if qty > 0 and heal <= missing_hp
            ]
            if usable_items:
                code, qty, heal_amount = min(usable_items, key=lambda item: item[2])
                logger.info(
                    "Using healing item '%s' (heal %s) without overflow; current HP=%s/%s.",
                    code,
                    heal_amount,
                    hp,
                    max_hp,
                )
                if not self.character_service.use_healing_item(code):
                    logger.warning("Failed to use healing item; falling back to rest.")
                    healing_items[code] = (0, heal_amount)
                    continue
                healing_items[code] = (qty - 1, heal_amount)
                hp, max_hp = self.character_service.get_hp_status()
                continue

            logger.info("No non-overflowing healing item available; resting.")
            if not self.rest():
                return False
            new_hp, max_hp = self.character_service.get_hp_status()
            if new_hp <= hp:
                logger.error("Rest did not increase HP toward the required fight threshold.")
                return False
            hp = new_hp

        return hp >= target_hp

    def fight_monster_by_code(self, monster_code: str, count: int = 1) -> bool:
        """Move to monster location and fight it multiple times.

        Args:
            monster_code: Code of the monster to fight.
            count: Number of times to fight.

        Returns:
            True if successful, False otherwise.
        """
        logger.info(f"Fighting monster: {monster_code} x{count}")

        try:
            # Ensure combat gear is in place for fight loops
            self._equip_combat_weapon(monster_code)

            if not self._move_to_monster(monster_code):
                return False

            required_hp = self._minimum_hp_to_fight(monster_code)
            for attempt in range(1, count + 1):
                logger.info(f"Fight attempt {attempt}/{count} for {monster_code}")
                if not self._recover_to_hp(required_hp):
                    logger.error("Failed to reach the required HP before fight")
                    return False

                fight_response = self.fight_monster(monster_code)
                if not fight_response:
                    logger.error("Failed to fight monster")
                    return False

                # Last fight: rest afterwards
                if attempt == count:
                    if not self.rest():
                        logger.error("Failed to rest after final fight")
                        return False
                    break

            logger.info(f"Successfully fought {monster_code} {count} time(s)")
            return True

        except ValueError as e:
            logger.error(f"Monster location error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error fighting monster: {e}")
            return False
