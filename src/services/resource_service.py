"""Resource gathering service."""
import logging
import time
from typing import Mapping

from src.client.api_client import APIClient, APIError
from src.services.banking_service import BankingService
from src.services.character_service import CharacterService
from src.services.item_service import ItemService
from src.services.movement_service import MovementService
from src.models.gathering_tools import GATHERING_TOOLS
from src.models.resource_locations import get_resource_location

logger = logging.getLogger(__name__)


class ResourceService:
    """Service for managing resource gathering."""

    def __init__(self, api_client: APIClient, character_name: str):
        """Initialize ResourceService.

        Args:
            api_client: API client instance.
            character_name: Name of the character to control.
        """
        self.api_client = api_client
        self.character_name = character_name
        self.movement_service = MovementService(api_client, character_name)
        self.banking_service = BankingService(api_client, character_name)
        self.character_service = CharacterService(api_client, character_name)
        self.item_service = ItemService(api_client)

    def _move_to_resource(self, resource_code: str) -> bool:
        # Get resource coordinates
        x, y = get_resource_location(resource_code)
        logger.info(f"Resource {resource_code} is at ({x}, {y})")

        # Move to resource location
        if not self.movement_service.move_to_location(x, y):
            logger.error("Failed to move to resource location")
            return False
        
        return True

    def _equip_gathering_tool(self, subtype: str | None) -> None:
        """Equip the strongest owned tool for this gathering skill, if available."""
        tools = GATHERING_TOOLS.get(subtype or "")
        if not tools:
            logger.info(
                f"No gathering tool catalogue for subtype '{subtype}'; continuing without a tool."
            )
            return

        try:
            character_data = self.character_service.get_character_data()
        except Exception as e:
            logger.warning(f"Could not determine an available gathering tool: {e}")
            return

        inventory = character_data.get("inventory", []) or []
        inventory_codes = {
            entry.get("code")
            for entry in inventory
            if isinstance(entry, dict) and (entry.get("quantity", 0) or 0) > 0
        }
        equipped_code = character_data.get("weapon_slot")
        available_codes = inventory_codes | ({equipped_code} if equipped_code else set())
        candidates = sorted(
            (effect_value, tool_code)
            for tool_code, effect_value in tools.items()
            if tool_code in available_codes
        )

        if not candidates:
            logger.info(
                f"No owned tool for {subtype} gathering; continuing without a tool."
            )
            return

        for _, tool_code in candidates:
            if tool_code == equipped_code:
                logger.info(f"Best available gathering tool '{tool_code}' is already equipped.")
                return

            logger.info(f"Equipping best available {subtype} tool '{tool_code}'.")
            if self.character_service.equip_item(tool_code):
                return
            logger.warning(f"Could not equip gathering tool '{tool_code}'; trying another.")

        logger.warning("No available gathering tool could be equipped; continuing without one.")

    def _gather_once(
        self,
        resource_code: str,
        attempt: int,
        keep_items: Mapping[str, int],
        allow_retry: bool = True,
    ) -> bool:
        """Attempt a single gather action, optionally retrying after banking if inventory is full."""
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/gathering",
                data={}
            )
            logger.debug(f"Gather result {attempt}: {response}")

            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info(f"Waiting {cooldown_seconds} seconds for gather cooldown...")
                time.sleep(cooldown_seconds)

            return True

        except APIError as e:
            if allow_retry and e.status_code == 497:
                logger.warning(
                    "Inventory is full; depositing unneeded items and retrying..."
                )
                if not self.banking_service.deposit_unneeded_items(keep_items):
                    logger.error("Failed to deposit unneeded items; aborting gather.")
                    return False
                
                if not self._move_to_resource(resource_code):
                    return False

                return self._gather_once(
                    resource_code,
                    attempt,
                    keep_items,
                    allow_retry=False,
                )

            logger.error(f"Failed to gather on attempt {attempt}: {e}")
            return False

        except Exception as e:
            logger.error(f"Failed to gather on attempt {attempt}: {e}")
            return False

    def gather_resource(
        self,
        resource_code: str,
        amount: int = 1,
        keep_items: Mapping[str, int] | None = None,
    ) -> bool:
        """Gather a specific resource multiple times.

        Args:
            resource_code: Code of the resource to gather.
            amount: Number of times to gather.
            keep_items: Quantities reserved by the containing workflow.

        Returns:
            True if successful, False otherwise.
        """
        keep_items = keep_items or {}
        success = False
        try:
            success = self._gather_resource(resource_code, amount, keep_items)
        except Exception as e:
            logger.error("Unexpected error gathering resource: %s", e, exc_info=True)

        if not self.banking_service.deposit_unneeded_items(keep_items):
            logger.error("Failed to deposit unneeded items after gathering.")
            return False
        return success

    def _gather_resource(
        self,
        resource_code: str,
        amount: int,
        keep_items: Mapping[str, int],
    ) -> bool:
        logger.info(f"Gathering {resource_code} {amount} times...")

        try:
            if not self._move_to_resource(resource_code):
                return False

            # Try to determine the correct gathering tool from item metadata
            subtype = None
            try:
                item_data = self.item_service.get_item(resource_code)
                subtype = item_data.get("subtype") if isinstance(item_data, dict) else None
            except Exception as e:
                logger.warning(f"Could not fetch item data for {resource_code}: {e}")

            self._equip_gathering_tool(subtype)

            # Gather the specified amount of times
            for i in range(amount):
                logger.info(f"Gathering attempt {i + 1}/{amount}...")
                if not self._gather_once(resource_code, i + 1, keep_items):
                    return False

            logger.info(f"Successfully gathered {resource_code} {amount} times")
            return True

        except ValueError as e:
            logger.error(f"Resource location error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error gathering resource: {e}")
            return False
