"""Resource gathering service."""
import logging
import time
from src.client.api_client import APIClient, APIError
from src.services.banking_service import BankingService
from src.services.movement_service import MovementService
from src.models.resource_locations import get_resource_location

logger = logging.getLogger(__name__)


class ResourceService:
    """Service for managing resource gathering."""

    def __init__(self, api_client: APIClient, character_name: str):
        """Initialize ResourceService.

        Args:
            api_client: API client instance.
            character_name: Name of the character to control.
        """
        self.api_client = api_client
        self.character_name = character_name
        self.movement_service = MovementService(api_client, character_name)
        self.banking_service = BankingService(api_client, character_name)

    def _move_to_resource(self, resource_code: str) -> bool:
        # Get resource coordinates
        x, y = get_resource_location(resource_code)
        logger.info(f"Resource {resource_code} is at ({x}, {y})")

        # Move to resource location
        if not self.movement_service.move_to_location(x, y):
            logger.error("Failed to move to resource location")
            return False
        
        return True

    def _gather_once(self, resource_code: str, attempt: int, allow_retry: bool = True) -> bool:
        """Attempt a single gather action, optionally retrying after banking if inventory is full."""
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/gathering",
                data={}
            )
            logger.debug(f"Gather result {attempt}: {response}")

            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info(f"Waiting {cooldown_seconds} seconds for gather cooldown...")
                time.sleep(cooldown_seconds)

            return True

        except APIError as e:
            # On inventory full, deposit the gathered item and retry once
            if allow_retry and e.status_code == 497:
                logger.warning("Inventory is full; depositing gathered item to bank and retrying...")
                if not self.banking_service.deposit_item(resource_code):
                    logger.error("Failed to deposit item to bank; aborting gather.")
                    return False
                
                if not self._move_to_resource(resource_code):
                    return False

                return self._gather_once(resource_code, attempt, allow_retry=False)

            logger.error(f"Failed to gather on attempt {attempt}: {e}")
            return False

        except Exception as e:
            logger.error(f"Failed to gather on attempt {attempt}: {e}")
            return False

    def gather_resource(self, resource_code: str, amount: int = 1) -> bool:
        """Gather a specific resource multiple times.

        Args:
            resource_code: Code of the resource to gather.
            amount: Number of times to gather.

        Returns:
            True if successful, False otherwise.
        """
        logger.info(f"Gathering {resource_code} {amount} times...")

        try:
            if not self._move_to_resource(resource_code):
                return False

            # Gather the specified amount of times
            for i in range(amount):
                logger.info(f"Gathering attempt {i + 1}/{amount}...")
                if not self._gather_once(resource_code, i + 1):
                    return False

            logger.info(f"Successfully gathered {resource_code} {amount} times")
            return True

        except ValueError as e:
            logger.error(f"Resource location error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error gathering resource: {e}")
            return False
