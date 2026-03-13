"""Movement service for character movement actions."""
import logging
import time
from typing import Dict, Any
from src.client.api_client import APIClient, APIError

logger = logging.getLogger(__name__)


class MovementService:
    """Service for managing character movement."""

    def __init__(self, api_client: APIClient, character_name: str):
        """Initialize MovementService.

        Args:
            api_client: API client instance.
            character_name: Name of the character to control.
        """
        self.api_client = api_client
        self.character_name = character_name

    def move_to_location(self, x: int, y: int) -> bool:
        """Move character to specified coordinates.

        Args:
            x: X coordinate to move to.
            y: Y coordinate to move to.

        Returns:
            True if successful, False otherwise.
        """
        logger.info(f"Moving to location ({x}, {y})...")
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/move",
                data={"x": x, "y": y}
            )
            logger.info(f"Move result: {response}")

            # Check for cooldown and wait if necessary
            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info(f"Waiting {cooldown_seconds} seconds for move cooldown...")
                time.sleep(cooldown_seconds)

            return True
        except APIError as e:
            # If character is already at destination (490), treat as success
            if e.status_code == 490 and "already at the destination" in str(e.message):
                logger.info("Character is already at the destination, continuing...")
                return True
            else:
                logger.error(f"Failed to move to location: {e}")
                return False
        except Exception as e:
            logger.error(f"Failed to move to location: {e}")
            return False