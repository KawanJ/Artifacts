"""One-fight API operation."""
import logging
import time
from typing import Any, Dict

from src.client.api_client import APIClient

logger = logging.getLogger(__name__)


class FightService:
    """Perform one fight and honor the action cooldown."""

    def __init__(
        self,
        api_client: APIClient,
        character_name: str,
    ):
        self.api_client = api_client
        self.character_name = character_name

    def fight_once(self) -> Dict[str, Any] | None:
        """Perform one fight at the character's current location."""
        logger.info("Starting fight...")
        response = self.api_client.post(
            f"/my/{self.character_name}/action/fight",
            data={},
        )
        logger.debug("Fight result: %s", response)
        fight_data = response.get("data", {})
        if not isinstance(fight_data, dict):
            logger.error("Fight response did not contain valid data.")
            return None

        cooldown_data = fight_data.get("cooldown")
        if cooldown_data and "total_seconds" in cooldown_data:
            cooldown_seconds = cooldown_data["total_seconds"]
            logger.info("Waiting %s seconds for fight cooldown...", cooldown_seconds)
            time.sleep(cooldown_seconds)

        return fight_data
