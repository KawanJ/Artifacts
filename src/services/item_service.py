"""Item service for fetching item metadata."""
import logging
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