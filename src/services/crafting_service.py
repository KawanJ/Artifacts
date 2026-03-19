"""Crafting service for item crafting."""
import logging
import time
from typing import Any, Dict, Optional

from src.client.api_client import APIClient
from src.models.crafting_locations import get_crafting_location
from src.services.character_service import CharacterService
from src.services.combat_service import CombatService
from src.services.item_service import ItemService
from src.services.movement_service import MovementService
from src.services.resource_service import ResourceService

logger = logging.getLogger(__name__)


class CraftingService:
    """Service for managing crafting operations."""

    def __init__(self, api_client: APIClient, character_name: str):
        """Initialize CraftingService.
        
        Args:
            api_client: API client instance.
            character_name: Name of the character to control.
        """
        self.api_client = api_client
        self.character_name = character_name
        self.movement_service = MovementService(api_client, character_name)
        self.item_service = ItemService(api_client)
        self.resource_service = ResourceService(api_client, character_name)
        self.character_service = CharacterService(api_client, character_name)
        self.combat_service = CombatService(api_client, character_name)

    def _craft_once(self, item_code: str, quantity: int = 1) -> bool:
        """Perform a craft action for the given item code (optionally multiple at once)."""
        logger.info(f"Crafting item: {item_code} x{quantity}")
        response = self.api_client.post(
            f"/my/{self.character_name}/action/crafting",
            data={"code": item_code, "quantity": quantity},
        )
        logger.debug(f"Crafting result: {response}")

        # Check for cooldown and wait if necessary
        cooldown_data = response.get("data", {}).get("cooldown")
        if cooldown_data and "total_seconds" in cooldown_data:
            cooldown_seconds = cooldown_data["total_seconds"]
            logger.info(f"Waiting {cooldown_seconds} seconds for crafting cooldown...")
            time.sleep(cooldown_seconds)

        return True

    def _gather_required_resources(
        self,
        item_data: Dict[str, Any],
        multiplier: int = 1,
        inventory: Optional[Dict[str, int]] = None,
    ) -> bool:
        """Gather all base resources required by an item (recursively).

        Args:
            item_data: Item metadata returned by the API.
            multiplier: How many times the item will be crafted.
            inventory: Current inventory map ({code: quantity}).

        Returns:
            True if gathering succeeded, False otherwise.
        """
        if inventory is None:
            inventory = {}

        craft_info = item_data.get("craft")
        if not craft_info:
            return True

        for required in craft_info.get("items", []):
            required_code = required.get("code")
            required_quantity = required.get("quantity", 0) * multiplier

            if not required_code or required_quantity <= 0:
                continue

            # First use anything already in inventory
            available = inventory.get(required_code, 0)
            if available >= required_quantity:
                inventory[required_code] = available - required_quantity
                logger.info(
                    f"Using existing inventory for {required_code}: "
                    f"{required_quantity} (remaining: {inventory[required_code]})"
                )
                continue

            # Use everything in inventory and craft/gather the rest
            if available > 0:
                required_quantity -= available
                inventory[required_code] = 0
                logger.info(
                    f"Used {available}x {required_code} from inventory; "
                    f"need {required_quantity} more"
                )

            required_item = self.item_service.get_item(required_code)
            if not required_item:
                logger.error(f"Failed to fetch item metadata for {required_code}")
                return False

            required_type = required_item.get("type")
            required_subtype = required_item.get("subtype")

            # If this item itself can be crafted, recurse
            if required_item.get("craft"):
                if not self.craft_item(required_code, required_quantity, inventory=inventory):
                    return False
                continue

            # If it's a resource, gather it
            if required_type == "resource":
                if required_subtype == "mob":
                    logger.info(
                        f"Farming mob drop required resource: {required_code} x{required_quantity}"
                    )
                    monster_code = self.combat_service.get_monster_code_for_drop(required_code)
                    if not monster_code:
                        logger.warning(
                            f"No direct monster mapping for mob drop {required_code}, trying fallback prefix logic"
                        )

                    if not self.combat_service.farm_drops(required_code, required_quantity, monster_code=monster_code):
                        return False
                    continue
                else:
                    logger.info(
                        f"Gathering required resource: {required_code} x{required_quantity}"
                    )
                    if not self.resource_service.gather_resource(required_code, required_quantity):
                        return False
                    continue

            # Unknown item type; log and continue
            logger.warning(
                f"Unknown required item type '{required_type}' for {required_code}; skipping"
            )

        return True

    def craft_item(
        self,
        item_code: str,
        quantity: int = 1,
        inventory: Optional[Dict[str, int]] = None,
    ) -> bool:
        """Craft an item (including all dependencies) by code.

        This will:
        1) Recursively gather/craft required inputs
        2) Move to the correct crafting location based on skill
        3) Craft the target item the requested number of times

        Args:
            item_code: Code of the item to craft.
            quantity: Number of items to craft.
            inventory: Optional inventory map to consume from.

        Returns:
            True if successful, False otherwise.
        """
        try:
            item_data = self.item_service.get_item(item_code)
            if not item_data:
                logger.error(f"Failed to fetch item metadata for {item_code}")
                return False

            craft_info = item_data.get("craft")
            if not craft_info:
                logger.error(f"Item {item_code} is not craftable")
                return False

            # Build inventory lookup once (only for subcrafting / ingredient resolution)
            if inventory is None:
                inventory = self.character_service.get_inventory()

            # Gather/craft all required inputs
            if not self._gather_required_resources(item_data, multiplier=quantity, inventory=inventory):
                return False

            # Move to crafting location based on skill
            skill = craft_info.get("skill")
            try:
                x, y = get_crafting_location(skill)
            except ValueError as e:
                logger.error(e)
                return False

            if not self.movement_service.move_to_location(x, y):
                logger.error("Failed to move to crafting location")
                return False

            # Craft the item the requested number of times (API supports bulk quantity)
            if not self._craft_once(item_code, quantity=quantity):
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to craft item {item_code}: {e}")
            return False
