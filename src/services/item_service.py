"""Item service for fetching item metadata."""
import logging
import time
from typing import Dict, Any
from src.client.api_client import APIClient

logger = logging.getLogger(__name__)


class ItemService:
    """Service for fetching item metadata from the API."""

    def __init__(self, api_client: APIClient):
        """Initialize ItemService.

        Args:
            api_client: API client instance.
        """
        self.api_client = api_client

    def get_item(self, item_code: str) -> Dict[str, Any]:
        """Fetch item details for the given item code.

        Args:
            item_code: The item code to fetch (e.g. "copper_bar").

        Returns:
            The parsed JSON response as a dictionary.
        """
        logger.info(f"Fetching item data for: {item_code}")
        response = self.api_client.get(f"/items/{item_code}")
        logger.debug(f"Item data for {item_code}: {response}")
        return response.get("data")

    def recycle_item(self, character_name: str, item_code: str, quantity: int = 1) -> bool:
        """Recycle a crafted item via the API.

        Args:
            character_name: Name of the character performing the recycle.
            item_code: Code of the item to recycle.
            quantity: Number of items to recycle.

        Returns:
            True if recycle succeeded, False otherwise.
        """
        logger.info(f"Recycling item: {item_code} x{quantity}")
        try:
            response = self.api_client.post(
                f"/my/{character_name}/action/recycling",
                data={"code": item_code, "quantity": quantity},
            )
            logger.debug(f"Recycle response: {response}")

            # Handle cooldown if provided
            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info(f"Waiting {cooldown_seconds} seconds after recycling...")
                time.sleep(cooldown_seconds)

            return True
        except Exception as e:
            logger.error(f"Failed to recycle item {item_code}: {e}")
            return False
