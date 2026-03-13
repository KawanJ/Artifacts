#!/usr/bin/env python3
"""Script to fight monsters - runs via GitHub Actions workflow."""
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import settings
from src.client.api_client import APIClient
from src.services.combat_service import CombatService

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the fight monsters action."""
    logger.info("Starting monster combat automation...")
    
    try:
        # Validate settings
        settings.validate()
        logger.info(f"Settings: {settings}")
        
        # Get monster name from command line argument or environment variable
        monster_name = None
        
        # Check command line arguments first
        if len(sys.argv) > 1:
            monster_name = sys.argv[1]
        # Then check environment variable (for GitHub Actions)
        elif os.getenv("MONSTER_NAME"):
            monster_name = os.getenv("MONSTER_NAME")
        
        if not monster_name:
            logger.error("Monster name not provided. Use: python fight_monsters.py <monster_name>")
            logger.error("Or set MONSTER_NAME environment variable")
            return 1
        
        logger.info(f"Target monster: {monster_name}")
        
        # Initialize API client
        with APIClient(
            api_key=settings.api_key,
            base_url=settings.api_base_url,
            max_retries=settings.max_retries,
            timeout=settings.request_timeout,
        ) as client:
            # Initialize service
            combat_service = CombatService(client, settings.character_name)
            
            # Fight the monster
            success = combat_service.fight_monster_by_name(monster_name)
            
            if success:
                logger.info("✓ Monster combat completed successfully")
                return 0
            else:
                logger.error("✗ Monster combat failed")
                return 1
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
