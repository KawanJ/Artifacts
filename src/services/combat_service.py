"""Combat service for fighting monsters."""
import logging
import time
from typing import Dict, Any
from src.client.api_client import APIClient
from src.services.movement_service import MovementService
from src.models.monster_locations import get_monster_location

logger = logging.getLogger(__name__)


class CombatService:
    """Service for managing combat and monster fights."""

    def __init__(self, api_client: APIClient, character_name: str):
        """Initialize CombatService.
        
        Args:
            api_client: API client instance.
            character_name: Name of the character to control.
        """
        self.api_client = api_client
        self.character_name = character_name
        self.movement_service = MovementService(api_client, character_name)

    def fight_monster(self) -> Dict[str, Any]:
        """Fight a monster at current location.
        
        Returns:
            Response data if successful, empty dict otherwise.
        """
        logger.info("Starting fight...")
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/fight",
                data={}
            )
            logger.info(f"Fight result: {response}")
            
            # Check for cooldown and wait if necessary
            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info(f"Waiting {cooldown_seconds} seconds for fight cooldown...")
                time.sleep(cooldown_seconds)
            
            return response
        except Exception as e:
            logger.error(f"Failed to fight monster: {e}")
            return {}

    def rest(self) -> bool:
        """Rest to recover health/mana.
        
        Returns:
            True if successful, False otherwise.
        """
        logger.info("Resting to recover...")
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/rest",
                data={}
            )
            logger.info(f"Rest result: {response}")
            
            # Check for cooldown and wait if necessary
            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info(f"Waiting {cooldown_seconds} seconds for rest cooldown...")
                time.sleep(cooldown_seconds)
            
            return True
        except Exception as e:
            logger.error(f"Failed to rest: {e}")
            return False

    def fight_monster_by_name(self, monster_name: str) -> bool:
        """Move to monster location and fight it.
        
        Args:
            monster_name: Name of the monster to fight.
        
        Returns:
            True if successful, False otherwise.
        """
        logger.info(f"Fighting monster: {monster_name}")
        
        try:
            # Get monster coordinates
            x, y = get_monster_location(monster_name)
            logger.info(f"Monster {monster_name} is at ({x}, {y})")
            
            # Move to location
            if not self.movement_service.move_to_location(x, y):
                logger.error("Failed to move to monster location")
                return False
            
            # Fight the monster
            fight_response = self.fight_monster()
            if not fight_response:
                logger.error("Failed to fight monster")
                return False
            
            # Rest after fighting
            if not self.rest():
                logger.error("Failed to rest after fighting")
                return False
            
            logger.info(f"Successfully fought and rested after {monster_name}")
            return True
            
        except ValueError as e:
            logger.error(f"Monster location error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error fighting monster: {e}")
            return False
