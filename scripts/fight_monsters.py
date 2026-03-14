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
        
        # Get monster code from command line argument or environment variable
        monster_code = None
        fight_count = 1

        # Check command line arguments first
        if len(sys.argv) > 1:
            monster_code = sys.argv[1]
        if len(sys.argv) > 2:
            try:
                fight_count = int(sys.argv[2])
            except ValueError:
                logger.error(f"Invalid fight count '{sys.argv[2]}'; must be an integer")
                return 1

        # Then check environment variables (for GitHub Actions or local env)
        if not monster_code:
            if os.getenv("MONSTER_CODE"):
                monster_code = os.getenv("MONSTER_CODE")
            elif os.getenv("MONSTER_NAME"):
                monster_code = os.getenv("MONSTER_NAME")

        if not fight_count:
            fight_count_env = os.getenv("MONSTER_FIGHT_COUNT") or os.getenv("MONSTER_COUNT")
            if fight_count_env:
                try:
                    fight_count = int(fight_count_env)
                except ValueError:
                    logger.error(f"Invalid fight count '{fight_count_env}'; must be an integer")
                    return 1

        if not monster_code:
            logger.error("Monster code not provided. Use: python fight_monsters.py <monster_code> [times]")
            logger.error("Or set MONSTER_CODE (or MONSTER_NAME) environment variable")
            return 1

        if fight_count <= 0:
            logger.error("Fight count must be a positive integer")
            return 1

        logger.info(f"Target monster: {monster_code} (x{fight_count})")

        # Initialize API client
        with APIClient(
            api_key=settings.api_key,
            base_url=settings.api_base_url,
            max_retries=settings.max_retries,
            timeout=settings.request_timeout,
        ) as client:
            # Initialize service
            combat_service = CombatService(client, settings.character_name)

            # Fight the monster multiple times (movement + recovery handled inside service)
            success = combat_service.fight_monster_by_code(monster_code, count=fight_count)
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
