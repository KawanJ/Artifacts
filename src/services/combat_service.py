"""Combat service for fighting monsters."""
import logging
import time
from typing import Dict, Any

from src.client.api_client import APIClient, APIError
from src.models.monster_locations import get_monster_location
from src.services.banking_service import BankingService
from src.services.character_service import CharacterService
from src.services.movement_service import MovementService

logger = logging.getLogger(__name__)


class CombatService:
    """Service for managing combat and monster fights."""

    # Default weapon to equip before combat loops.
    COMBAT_WEAPON_CODE = "iron_sword"

    # Static mapping from mob-drop item codes to monster codes.
    MOB_DROP_TO_MONSTER: Dict[str, str] = {
        "raw_chicken": "chicken",
        "feather": "chicken",
        "yellow_slimeball": "yellow_slime",
        # Extend this map as needed for your game content.
    }

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

    def _equip_combat_weapon(self) -> bool:
        """Equip the default combat weapon before starting combat loop."""
        if not self.COMBAT_WEAPON_CODE:
            return True

        logger.info(f"Equipping combat weapon: {self.COMBAT_WEAPON_CODE}")
        success = self.character_service.equip_item(self.COMBAT_WEAPON_CODE)
        if not success:
            logger.warning(f"Failed to equip combat weapon {self.COMBAT_WEAPON_CODE}")
        return success

    def get_monster_code_for_drop(self, drop_code: str) -> str | None:
        """Get monster code for a mob drop item code using the mapping."""
        return self.MOB_DROP_TO_MONSTER.get(drop_code)

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

        if not self._equip_combat_weapon():
            logger.warning("Unable to equip combat weapon; continuing without a dedicated weapon.")

        if not self._move_to_monster(monster_code):
            return False

        collected = 0
        attempts = 0
        next_hit_estimate = 0
        while collected < target_quantity:
            attempts += 1
            logger.info(f"Combat drop farm attempt {attempts}: collected {collected}/{target_quantity} {target_item_code}")
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

            # Recover between fights (simplified with heal/rest call)
            if next_hit_estimate == 0:
                hp, max_hp = self.character_service.get_hp_status()
                next_hit_estimate = max_hp - hp
                logger.debug(f"Estimated next hit damage after first fight: {next_hit_estimate}")

            if not self._heal_or_rest(next_hit_estimate):
                logger.error("Failed to recover between fights during farming")
                return False

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

    def _heal_or_rest(self, expected_next_hit: int) -> bool:
        """Heal using healing items if possible, otherwise rest.

        Args:
            expected_next_hit: Estimated damage of the next incoming hit.

        Returns:
            True if recovery succeeded, False otherwise.
        """
        hp, max_hp = self.character_service.get_hp_status()
        missing_hp = max_hp - hp

        # If there are no upcoming fights (expected_next_hit <= 0), just rest.
        if expected_next_hit <= 0:
            logger.debug("No upcoming hit expected; resting.")
            return self.rest()

        if missing_hp <= 0:
            logger.debug("HP is full; no healing needed.")
            return True

        healing_items = self.character_service.get_available_healing_items()
        # Helper to decide if current HP can survive the next hit
        def can_survive(current_hp: int) -> bool:
            return current_hp > expected_next_hit

        # Apply healing while possible until we can survive the next hit
        # using smallest heal items first.
        while True:
            hp, max_hp = self.character_service.get_hp_status()
            missing_hp = max_hp - hp

            # If we can already survive next hit, attempt to apply a non-overflow heal (smallest) once.
            if can_survive(hp):
                # Find smallest item that does not overflow
                non_overflow_items = [
                    (code, qty, heal)
                    for code, (qty, heal) in healing_items.items()
                    if qty > 0 and heal <= missing_hp
                ]
                if non_overflow_items:
                    code, qty, heal_amount = min(non_overflow_items, key=lambda t: t[2])
                    logger.info(
                        f"Using healing item '{code}' (heal {heal_amount}) without overflow; "
                        f"current HP={hp}/{max_hp}"
                    )
                    if self.character_service.use_healing_item(code):
                        healing_items[code] = (qty - 1, heal_amount)
                        continue
                    logger.warning("Failed to use healing item; falling back to rest.")
                    return self.rest()

                # No non-overflow items available; we can survive next hit, so continue
                return True

            # If we cannot survive the next hit, attempt to heal using smallest available item (even if it overflows)
            usable_items = [
                (code, qty, heal)
                for code, (qty, heal) in healing_items.items()
                if qty > 0
            ]
            if usable_items:
                code, qty, heal_amount = min(usable_items, key=lambda t: t[2])
                logger.info(
                    f"Healing needed to survive next hit (expected {expected_next_hit}). "
                    f"Using '{code}' (heal {heal_amount})"
                )
                if self.character_service.use_healing_item(code):
                    healing_items[code] = (qty - 1, heal_amount)
                    continue
                logger.warning("Failed to use healing item; falling back to rest.")
                return self.rest()

            # No healing items remain; fall back to rest
            logger.info("Out of healing items; resting instead.")
            return self.rest()

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
            self._equip_combat_weapon()

            if not self._move_to_monster(monster_code):
                return False

            # If only fighting once, just fight then rest
            if count == 1:
                fight_response = self.fight_monster(monster_code)
                if not fight_response:
                    logger.error("Failed to fight monster")
                    return False
                if not self.rest():
                    logger.error("Failed to rest after fight")
                    return False
                logger.info(f"Successfully fought {monster_code} once")
                return True

            # Multi-fight: compute expected hit damage from the first fight and use that for recovery logic
            max_hp = self.character_service.get_hp_status()[1]

            # First fight -> compute expected hit
            fight_response = self.fight_monster(monster_code)
            if not fight_response:
                logger.error("Failed to fight monster")
                return False
            after_first_hp = self.character_service.get_hp_status()[0]
            expected_next_hit = max_hp - after_first_hp
            logger.debug(f"Expected next hit estimated as {expected_next_hit}")

            # Recover after first fight in preparation for next one
            if not self._heal_or_rest(expected_next_hit=expected_next_hit):
                logger.error("Failed to recover after fight")
                return False

            # Subsequent fights
            for attempt in range(2, count + 1):
                logger.info(f"Fight attempt {attempt}/{count} for {monster_code}")
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

                # Recover for next fight using expected_hit estimation
                if not self._heal_or_rest(expected_next_hit=expected_next_hit):
                    logger.error("Failed to recover after fight")
                    return False

            logger.info(f"Successfully fought {monster_code} {count} time(s)")
            return True

        except ValueError as e:
            logger.error(f"Monster location error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error fighting monster: {e}")
            return False
