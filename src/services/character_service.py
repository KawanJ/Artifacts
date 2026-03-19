"""Character service for fetching player data."""
import logging
import time
from typing import Dict, Any

from src.client.api_client import APIClient

logger = logging.getLogger(__name__)


class CharacterService:
    """Service for interacting with character data."""

    # Healing items mapping (code -> heal amount)
    HEALING_ITEMS: Dict[str, int] = {
        "apple": 50,
        "cooked_chicken": 80,
        "fried_eggs": 150,
    }

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
        level = data.get(f"{skill_name}_level", {}) or {}
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

    def get_available_healing_items(self) -> Dict[str, tuple[int, int]]:
        """Return available healing items (code -> (quantity, heal_amount))."""
        inventory = self.get_inventory()
        result: Dict[str, tuple[int, int]] = {}
        for code, heal_amount in self.HEALING_ITEMS.items():
            qty = inventory.get(code, 0)
            if qty > 0:
                result[code] = (qty, heal_amount)
        logger.debug(f"Available healing items: {result}")
        return result

    def use_healing_item(self, item_code: str, quantity: int = 1) -> bool:
        """Use a healing item via the API.

        This assumes the API supports a healing item use endpoint; update as needed.
        """
        logger.info(f"Using healing item: {item_code} x{quantity}")
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/use",
                data={"code": item_code, "quantity": quantity},
            )
            logger.debug(f"Use item response: {response}")

            # Handle cooldown if provided
            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info(f"Waiting {cooldown_seconds} seconds after using healing item...")
                time.sleep(cooldown_seconds)

            return True
        except Exception as e:
            logger.error(f"Failed to use healing item {item_code}: {e}")
            return False

    def equip_item(self, item_code: str, slot: str = "weapon") -> bool:
        """Equip an item in the specified slot."""
        logger.info(f"Equipping item '{item_code}' into slot '{slot}'")
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/equip",
                data={"code": item_code, "slot": slot},
            )
            logger.debug(f"Equip response: {response}")

            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info(f"Waiting {cooldown_seconds} seconds after equipping item...")
                time.sleep(cooldown_seconds)

            return True
        except Exception as e:
            logger.error(f"Failed to equip item {item_code}: {e}")
            return False
