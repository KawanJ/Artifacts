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

    # List of common items to deposit during long-running tasks (e.g. combat).
    # Update this list as needed.
    COMMON_ITEMS = [
        "apple",
        "raw_chicken",
        "egg",
        "feather",
        "sap",
        "topaz_stone",
        "emerald_stone",
        "ruby_stone",
        "sapphire_stone",
    ]

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
        return self.deposit_items(
            {item_code: self.character_service.get_inventory().get(item_code, 0)}
        )

    def get_bank_item_quantity(self, item_code: str) -> int:
        """Return the quantity of one item currently held in the bank."""
        response = self.api_client.get(
            "/my/bank/items",
            params={"item_code": item_code, "size": 1000},
        )
        items = response.get("data")
        if not isinstance(items, list):
            raise ValueError(f"Invalid bank inventory response for '{item_code}'.")
        return sum(
            int(item.get("quantity", 0) or 0)
            for item in items
            if isinstance(item, dict) and item.get("code") == item_code
        )

    def withdraw_items(self, quantities: Dict[str, int]) -> bool:
        """Withdraw specified item quantities from the bank."""
        items_to_withdraw = [
            {"code": code, "quantity": quantity}
            for code, quantity in quantities.items()
            if quantity > 0
        ]
        if not items_to_withdraw:
            return True
        x, y = self.BANK_LOCATION
        if not self.movement_service.move_to_location(x, y):
            logger.error("Failed to move to the bank to withdraw items.")
            return False

        logger.info("Withdrawing items from bank: %s", items_to_withdraw)
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/bank/withdraw/item",
                data=items_to_withdraw,
            )
            logger.debug("Bank withdrawal response: %s", response)

            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info("Waiting %s seconds for withdrawal cooldown...", cooldown_seconds)
                time.sleep(cooldown_seconds)
            return True
        except APIError as e:
            logger.error("Failed to withdraw items from bank: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error during bank withdrawal: %s", e)
            return False

    def deposit_items(self, quantities: Dict[str, int]) -> bool:
        """Deposit up to the specified quantities from inventory into the bank."""
        inventory = self.character_service.get_inventory()
        items_to_deposit = [
            {"code": code, "quantity": min(quantity, inventory.get(code, 0))}
            for code, quantity in quantities.items()
            if quantity > 0 and inventory.get(code, 0) > 0
        ]
        if not items_to_deposit:
            logger.info("No requested items found in inventory to deposit.")
            return True

        x, y = self.BANK_LOCATION
        if not self.movement_service.move_to_location(x, y):
            logger.error("Failed to move to the bank location.")
            return False

        logger.info("Depositing specified items: %s", items_to_deposit)
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/bank/deposit/item",
                data=items_to_deposit,
            )
            logger.debug("Bank deposit response: %s", response)

            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info("Waiting %s seconds for deposit cooldown...", cooldown_seconds)
                time.sleep(cooldown_seconds)
            return True
        except APIError as e:
            logger.error("Failed to deposit items to bank: %s", e)
            return False
        except Exception as e:
            logger.error("Unexpected error during bank deposit: %s", e)
            return False

    def deposit_common_items(self) -> bool:
        """Deposit commonly collected items into the bank.

        The list of common items can be updated in the `COMMON_ITEMS` class attribute.

        Returns:
            True if deposit succeeded (or no items existed), False otherwise.
        """
        inventory = self.character_service.get_inventory()

        items_to_deposit = []
        for code in self.COMMON_ITEMS:
            qty = inventory.get(code, 0)
            if qty > 0:
                items_to_deposit.append({"code": code, "quantity": qty})

        if not items_to_deposit:
            logger.info("No common items found in inventory to deposit.")
            return True

        x, y = self.BANK_LOCATION
        if not self.movement_service.move_to_location(x, y):
            logger.error("Failed to move to the bank location.")
            return False

        logger.info(f"Depositing common items to bank: {[i['code'] for i in items_to_deposit]}")
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/bank/deposit/item",
                data=items_to_deposit,
            )
            logger.debug(f"Bank deposit response: {response}")

            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info(f"Waiting {cooldown_seconds} seconds for deposit cooldown...")
                time.sleep(cooldown_seconds)
            return True
        except APIError as e:
            logger.error(f"Failed to deposit common items to bank: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during bank deposit: {e}")
            return False
