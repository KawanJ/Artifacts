"""Combat service for fighting monsters."""
import logging
import time
from typing import Dict, Any, Optional

from src.client.api_client import APIClient
from src.models.monster_locations import get_monster_location
from src.services.character_service import CharacterService
from src.services.movement_service import MovementService

logger = logging.getLogger(__name__)


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

    def fight_monster(self) -> Dict[str, Any]:
        """Fight a monster at current location.
        
        Returns:
            Response data if successful, empty dict otherwise.
        """
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
            
            return response
        except Exception as e:
            logger.error(f"Failed to fight monster: {e}")
            return {}

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
            # Get monster coordinates
            x, y = get_monster_location(monster_code)
            logger.info(f"Monster {monster_code} is at ({x}, {y})")

            # Move to location once
            if not self.movement_service.move_to_location(x, y):
                logger.error("Failed to move to monster location")
                return False

            # If only fighting once, just fight then rest
            if count == 1:
                fight_response = self.fight_monster()
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
            fight_response = self.fight_monster()
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
                fight_response = self.fight_monster()
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
