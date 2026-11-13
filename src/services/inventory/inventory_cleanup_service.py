"""Inventory cleanup for completed tasks and full-inventory recovery."""

import logging
from typing import Dict, Mapping

from src.domain.catalogs.gathering_tools import GATHERING_TOOLS
from src.services.inventory.bank_service import BankService
from src.services.character_service import CharacterService
from src.services.items.item_catalog_service import ItemCatalogService

logger = logging.getLogger(__name__)


class InventoryCleanupService:
    """Deposit unneeded inventory while protecting equipped gear and reserved items."""

    def __init__(
        self,
        bank_service: BankService,
        character_service: CharacterService,
        item_service: ItemCatalogService,
    ):
        self.bank_service = bank_service
        self.character_service = character_service
        self.item_service = item_service

    def deposit_unneeded_items(
        self,
        keep_items: Mapping[str, int] | None = None,
    ) -> bool:
        """Deposit inventory except reserved quantities, tools, and equipped items."""
        keep_items = keep_items or {}
        try:
            character_data = self.character_service.get_character_data()
        except Exception as e:
            logger.error("Could not inspect character inventory for cleanup: %s", e)
            return False
        if not isinstance(character_data, dict):
            logger.error("Character inventory response is invalid; aborting cleanup.")
            return False

        inventory: Dict[str, int] = {}
        for entry in character_data.get("inventory", []) or []:
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
                logger.error(
                    "Could not inspect inventory item '%s'; aborting cleanup.", code
                )
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
        return self.bank_service.deposit_items(items_to_deposit)
