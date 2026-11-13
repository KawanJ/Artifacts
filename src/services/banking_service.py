"""Banking service for depositing items into the bank."""

import logging
import time
from typing import Dict, Mapping

from src.client.api_client import APIClient, APIError
from src.models.gathering_tools import GATHERING_TOOLS
from src.services.character_service import CharacterService
from src.services.item_service import ItemService
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
        self.item_service = ItemService(api_client)

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

    def deposit_unneeded_items(
        self,
        keep_items: Mapping[str, int] | None = None,
    ) -> bool:
        """Deposit inventory except reserved quantities and tools or weapons."""
        keep_items = keep_items or {}
        try:
            character_data = self.character_service.get_character_data()
        except Exception as e:
            logger.error("Could not inspect character inventory for cleanup: %s", e)
            return False
        if not isinstance(character_data, dict):
            logger.error("Character inventory response is invalid; aborting cleanup.")
            return False
        inventory_entries = character_data.get("inventory", []) or []
        inventory: Dict[str, int] = {}
        for entry in inventory_entries:
            if not isinstance(entry, dict):
                continue
            code = entry.get("code")
            quantity = int(entry.get("quantity", 0) or 0)
            if code and quantity > 0:
                inventory[code] = inventory.get(code, 0) + quantity

        protected_codes = {
            code
            for key, code in character_data.items()
            if key.endswith("_slot") and isinstance(code, str) and code
        }
        protected_codes.update(
            tool_code
            for tools in GATHERING_TOOLS.values()
            for tool_code in tools
        )

        items_to_deposit: Dict[str, int] = {}
        for code, quantity in inventory.items():
            if code in protected_codes:
                continue

            try:
                item_data = self.item_service.get_item(code)
            except Exception:
                logger.exception(
                    "Could not inspect inventory item '%s'; aborting cleanup.", code
                )
                return False
            if not isinstance(item_data, dict):
                logger.error("Could not inspect inventory item '%s'; aborting cleanup.", code)
                return False
            if item_data.get("type") in {"tool", "weapon"}:
                continue

            reserved = max(0, int(keep_items.get(code, 0) or 0))
            quantity_to_deposit = max(0, quantity - reserved)
            if quantity_to_deposit:
                items_to_deposit[code] = quantity_to_deposit

        if not items_to_deposit:
            logger.info("No unneeded inventory items to deposit.")
            return True

        logger.info("Depositing unneeded inventory items: %s", items_to_deposit)
        return self.deposit_items(items_to_deposit)
