"""Combat API actions and inventory-full retry handling."""
import logging
import time
from typing import Any, Dict, Mapping

from src.client.api_client import APIClient, APIError
from src.models.monster_locations import get_monster_location
from src.services.banking_service import BankingService
from src.services.movement_service import MovementService

logger = logging.getLogger(__name__)


class CombatActionService:
    """Perform combat actions and handle their API-level retry behavior."""

    def __init__(
        self,
        api_client: APIClient,
        character_name: str,
        banking_service: BankingService,
        movement_service: MovementService,
    ):
        self.api_client = api_client
        self.character_name = character_name
        self.banking_service = banking_service
        self.movement_service = movement_service

    def move_to_monster(self, monster_code: str) -> bool:
        """Move to a monster's configured location."""
        x, y = get_monster_location(monster_code)
        logger.info("Monster %s is at (%s, %s)", monster_code, x, y)
        if not self.movement_service.move_to_location(x, y):
            logger.error("Failed to move to monster location")
            return False
        return True

    def fight_once(
        self,
        monster_code: str,
        allow_retry: bool = True,
        keep_items: Mapping[str, int] | None = None,
    ) -> Dict[str, Any] | None:
        """Perform one fight, retrying once after depositing items if inventory is full."""
        logger.info("Starting fight...")
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/fight",
                data={},
            )
            logger.debug("Fight result: %s", response)

            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info("Waiting %s seconds for fight cooldown...", cooldown_seconds)
                time.sleep(cooldown_seconds)

            fight_data = response.get("data", {})
            if not isinstance(fight_data, dict):
                logger.error("Fight response did not contain valid data.")
                return None
            return fight_data

        except APIError as e:
            if allow_retry and e.status_code == 497:
                logger.warning(
                    "Inventory full during fight; depositing unneeded items and retrying..."
                )
                if not self.banking_service.deposit_unneeded_items(keep_items):
                    logger.error("Failed to deposit unneeded items; aborting fight.")
                    return None

                if not self.move_to_monster(monster_code):
                    return None

                return self.fight_once(
                    monster_code,
                    keep_items=keep_items,
                    allow_retry=False,
                )

            logger.error("Failed to fight monster: %s", e)
            return None

        except Exception as e:
            logger.error("Failed to fight monster: %s", e)
            return None
