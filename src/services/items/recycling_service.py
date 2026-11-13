"""Recycling operations for crafted items."""

import logging
import time

from src.client.api_client import APIClient

logger = logging.getLogger(__name__)


class RecyclingService:
    """Recycle items using the character action endpoint."""

    def __init__(self, api_client: APIClient, character_name: str):
        self.api_client = api_client
        self.character_name = character_name

    def recycle_item(self, item_code: str, quantity: int = 1) -> bool:
        """Recycle a crafted item."""
        logger.info("Recycling item: %s x%s", item_code, quantity)
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/recycling",
                data={"code": item_code, "quantity": quantity},
            )
            logger.debug("Recycle response: %s", response)
            cooldown = response.get("data", {}).get("cooldown")
            if cooldown and "total_seconds" in cooldown:
                seconds = cooldown["total_seconds"]
                logger.info("Waiting %s seconds after recycling...", seconds)
                time.sleep(seconds)
            return True
        except Exception as e:
            logger.error("Failed to recycle item %s: %s", item_code, e)
            return False
