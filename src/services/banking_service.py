"""Banking service for depositing items into the bank."""

import logging
import time
from typing import Dict

from src.client.api_client import APIClient, APIError
from src.services.character_service import CharacterService
from src.services.movement_service import MovementService

logger = logging.getLogger(__name__)


class BankingService:
    """Service for depositing items into the bank."""

    # Bank coordinates in the world
    BANK_LOCATION = (4, 1)

    def __init__(self, api_client: APIClient, character_name: str):
        """Initialize banking service.

        Args:
            api_client: API client instance.
            character_name: Name of the character to operate on.
        """
        self.api_client = api_client
        self.character_name = character_name
        self.movement_service = MovementService(api_client, character_name)
        self.character_service = CharacterService(api_client, character_name)

    def deposit_item(self, item_code: str) -> bool:
        """Deposit all of a specific item from inventory into the bank.

        Args:
            item_code: Item code to deposit.

        Returns:
            True if deposit succeeded or item was not present, False otherwise.
        """
        inventory = self.character_service.get_inventory()
        item_qty = inventory.get(item_code, 0)
        if item_qty <= 0:
            logger.info(f"No '{item_code}' in inventory to deposit.")
            return True

        x, y = self.BANK_LOCATION
        if not self.movement_service.move_to_location(x, y):
            logger.error("Failed to move to the bank location.")
            return False

        logger.info(f"Depositing {item_qty}x '{item_code}' to bank...")
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/bank/deposit/item",
                data=[{"code": item_code, "quantity": item_qty}],
            )
            logger.debug(f"Bank deposit response: {response}")

            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info(f"Waiting {cooldown_seconds} seconds for deposit cooldown...")
                time.sleep(cooldown_seconds)
            return True
        except APIError as e:
            logger.error(f"Failed to deposit items to bank: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during bank deposit: {e}")
            return False
