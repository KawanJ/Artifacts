"""Character service for fetching player data."""
import logging
import time
from typing import Dict, Any

from src.client.api_client import APIClient

logger = logging.getLogger(__name__)


class CharacterService:
    """Service for interacting with character data."""

    def __init__(self, api_client: APIClient, character_name: str):
        """Initialize CharacterService.

        Args:
            api_client: API client instance.
            character_name: Name of the character to fetch.
        """
        self.api_client = api_client
        self.character_name = character_name

    def get_character_data(self) -> Dict[str, Any]:
        """Fetch full character data from the API."""
        logger.info(f"Fetching character data for: {self.character_name}")
        response = self.api_client.get(f"/characters/{self.character_name}")
        logger.debug(f"Character data: {response}")
        return response.get("data", {})

    def get_hp_status(self) -> tuple[int, int]:
        """Return (current_hp, max_hp) for the character."""
        data = self.get_character_data()
        hp = data.get("hp", 0) or 0
        max_hp = data.get("max_hp", 0) or 0
        logger.debug(f"HP status: {hp}/{max_hp}")
        return hp, max_hp

    def get_skill_level(self, skill_name: str) -> int:
        """Return the current level for the given skill."""
        data = self.get_character_data()
        level = data.get(f"{skill_name}_level", 0) or 0
        logger.debug(f"Skill '{skill_name}' level: {level}")
        return level

    def get_inventory(self) -> Dict[str, int]:
        """Return a mapping of item codes to quantities in the character inventory."""
        data = self.get_character_data()
        inventory = data.get("inventory", []) or []
        result: Dict[str, int] = {}
        for item in inventory:
            code = item.get("code")
            quantity = item.get("quantity", 0) or 0
            if code:
                result[code] = result.get(code, 0) + quantity
        logger.debug(f"Inventory summary: {result}")
        return result

    def get_inventory_space(self) -> int:
        """Return the number of items that can still fit in the inventory."""
        data = self.get_character_data()
        maximum = int(data.get("inventory_max_items", 0) or 0)
        inventory = data.get("inventory", []) or []
        used = sum(
            int(item.get("quantity", 0) or 0)
            for item in inventory
        )
        return maximum - used

    def use_item(self, item_code: str, quantity: int = 1) -> bool:
        """Use an item via the character action endpoint."""
        logger.info("Using item: %s x%s", item_code, quantity)
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/use",
                data={"code": item_code, "quantity": quantity},
            )
            logger.debug("Use item response: %s", response)
            self._wait_for_cooldown(response, "using item")
            return True
        except Exception as e:
            logger.error("Failed to use item %s: %s", item_code, e)
            return False

    def equip_item(self, item_code: str, slot: str = "weapon") -> bool:
        """Equip an item in the specified slot."""
        logger.info("Equipping item '%s' into slot '%s'", item_code, slot)
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/equip",
                data=[{"code": item_code, "slot": slot}],
            )
            logger.debug("Equip response: %s", response)
            self._wait_for_cooldown(response, "equipping item")
            return True
        except Exception as e:
            logger.error("Failed to equip item %s: %s", item_code, e)
            return False

    @staticmethod
    def _wait_for_cooldown(response: Dict[str, Any], action: str) -> None:
        cooldown = response.get("data", {}).get("cooldown")
        if cooldown and "total_seconds" in cooldown:
            seconds = cooldown["total_seconds"]
            logger.info("Waiting %s seconds after %s...", seconds, action)
            time.sleep(seconds)
