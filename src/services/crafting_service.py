"""Crafting service for item crafting."""
import logging
import time
from typing import Dict, Any
from src.client.api_client import APIClient
from src.services.movement_service import MovementService

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

    def craft_item(self, item_code: str) -> bool:
        """Craft an item by code.
        
        Args:
            item_code: Code of the item to craft.
        
        Returns:
            True if successful, False otherwise.
        """
        logger.info(f"Crafting item: {item_code}")
        
        try:
            # Move to crafting location (2, 1)
            if not self.movement_service.move_to_location(2, 1):
                logger.error("Failed to move to crafting location")
                return False
            
            # Craft the item
            response = self.api_client.post(
                f"/my/{self.character_name}/action/crafting",
                data={"code": item_code}
            )
            logger.info(f"Crafting result: {response}")
            
            # Check for cooldown and wait if necessary
            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info(f"Waiting {cooldown_seconds} seconds for crafting cooldown...")
                time.sleep(cooldown_seconds)
            
            return True
        except Exception as e:
            logger.error(f"Failed to craft item: {e}")
            return False
