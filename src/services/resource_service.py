"""Resource gathering service."""
import logging
import time
from typing import Dict, Any
from src.client.api_client import APIClient
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

    def gather_resource(self, resource_name: str, amount: int = 1) -> bool:
        """Gather a specific resource multiple times.
        
        Args:
            resource_name: Name of the resource to gather.
            amount: Number of times to gather.
        
        Returns:
            True if successful, False otherwise.
        """
        logger.info(f"Gathering {resource_name} {amount} times...")
        
        try:
            # Get resource coordinates
            x, y = get_resource_location(resource_name)
            logger.info(f"Resource {resource_name} is at ({x}, {y})")
            
            # Move to resource location
            if not self.movement_service.move_to_location(x, y):
                logger.error("Failed to move to resource location")
                return False
            
            # Gather the specified amount of times
            for i in range(amount):
                logger.info(f"Gathering attempt {i + 1}/{amount}...")
                try:
                    response = self.api_client.post(
                        f"/my/{self.character_name}/action/gathering",
                        data={}
                    )
                    logger.info(f"Gather result {i + 1}: {response}")
                    
                    # Check for cooldown and wait if necessary
                    cooldown_data = response.get("data", {}).get("cooldown")
                    if cooldown_data and "total_seconds" in cooldown_data:
                        cooldown_seconds = cooldown_data["total_seconds"]
                        logger.info(f"Waiting {cooldown_seconds} seconds for gather cooldown...")
                        time.sleep(cooldown_seconds)
                    
                except Exception as e:
                    logger.error(f"Failed to gather on attempt {i + 1}: {e}")
                    return False
            
            logger.info(f"Successfully gathered {resource_name} {amount} times")
            return True
            
        except ValueError as e:
            logger.error(f"Resource location error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error gathering resource: {e}")
            return False
