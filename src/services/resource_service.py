"""Resource gathering service."""
import logging
import time
from typing import Mapping

from src.client.api_client import APIClient, APIError
from src.domain.catalogs.gathering_tools import GATHERING_TOOLS
from src.domain.world import get_resource_location
from src.services.character_service import CharacterService
from src.services.inventory.inventory_cleanup_service import InventoryCleanupService
from src.services.items.item_catalog_service import ItemCatalogService
from src.services.movement_service import MovementService

logger = logging.getLogger(__name__)


class ResourceService:
    """Gather resources, managing tools, movement, and inventory along the way."""

    def __init__(
        self,
        api_client: APIClient,
        character_name: str,
        movement_service: MovementService,
        cleanup_service: InventoryCleanupService,
        character_service: CharacterService,
        item_service: ItemCatalogService,
    ):
        """Initialize the resource service with shared dependencies."""
        self.api_client = api_client
        self.character_name = character_name
        self.movement_service = movement_service
        self.cleanup_service = cleanup_service
        self.character_service = character_service
        self.item_service = item_service

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
        stop_when_inventory_full: bool = False,
    ) -> bool:
        """Attempt a single gather action, optionally retrying after banking if inventory is full."""
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/gathering",
                data={},
            )
            logger.debug("Gather result %s: %s", attempt, response)
            cooldown = response.get("data", {}).get("cooldown")
            if cooldown and "total_seconds" in cooldown:
                seconds = cooldown["total_seconds"]
                logger.info("Waiting %s seconds for gather cooldown...", seconds)
                time.sleep(seconds)
            return True

        except APIError as e:
            if allow_retry and e.status_code == 497:
                if stop_when_inventory_full:
                    logger.info(
                        "Inventory reached capacity; stopping this gathering batch."
                    )
                    return True
                logger.warning(
                    "Inventory is full; depositing unneeded items and retrying..."
                )
                if not self.cleanup_service.deposit_unneeded_items(keep_items):
                    logger.error("Failed to deposit unneeded items; aborting gather.")
                    return False
                
                if not self._move_to_resource(resource_code):
                    return False

                return self._gather_once(
                    resource_code,
                    attempt,
                    keep_items,
                    allow_retry=False,
                    stop_when_inventory_full=stop_when_inventory_full,
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
        stop_when_inventory_full: bool = False,
    ) -> bool:
        """Gather a specific resource multiple times.

        Args:
            resource_code: Code of the resource to gather.
            amount: Number of times to gather.
            keep_items: Quantities reserved by the calling operation.
            stop_when_inventory_full: End a partial batch when capacity is reached.

        Returns:
            True if successful, False otherwise.
        """
        keep_items = keep_items or {}
        success = False
        try:
            success = self._gather_resource(
                resource_code,
                amount,
                keep_items,
                stop_when_inventory_full,
            )
        except Exception as e:
            logger.error("Unexpected error gathering resource: %s", e, exc_info=True)

        if not self.cleanup_service.deposit_unneeded_items(keep_items):
            logger.error("Failed to deposit unneeded items after gathering.")
            return False
        return success

    def _gather_resource(
        self,
        resource_code: str,
        amount: int,
        keep_items: Mapping[str, int],
        stop_when_inventory_full: bool = False,
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
                inventory_space_before = (
                    self.character_service.get_inventory_space()
                    if stop_when_inventory_full
                    else None
                )
                if inventory_space_before is not None and inventory_space_before <= 0:
                    logger.info("Inventory is full; ending the gathering batch.")
                    break

                logger.info(f"Gathering attempt {i + 1}/{amount}...")
                if not self._gather_once(
                    resource_code,
                    i + 1,
                    keep_items,
                    stop_when_inventory_full=stop_when_inventory_full,
                ):
                    return False
                if stop_when_inventory_full:
                    inventory_space_after = self.character_service.get_inventory_space()
                    if inventory_space_after >= inventory_space_before:
                        logger.info(
                            "No inventory space for another gather result; "
                            "ending the gathering batch."
                        )
                        break
                    if inventory_space_after <= 0:
                        logger.info("Inventory is full; ending the gathering batch.")
                        break

            logger.info(f"Gathering batch for {resource_code} completed")
            return True

        except ValueError as e:
            logger.error(f"Resource location error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error gathering resource: {e}")
            return False
