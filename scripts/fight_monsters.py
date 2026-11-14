#!/usr/bin/env python3
"""Script to fight monsters - runs via GitHub Actions workflow."""
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import settings
from src.client.api_client import APIClient
from scripts.bootstrap import build_services, extract_character_argument

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

        arguments, character_name = extract_character_argument(
            sys.argv[1:],
            settings.character_name,
        )
        
        # Get monster code from command line argument or environment variable
        monster_code = None
        fight_count = None

        # Check command line arguments first
        if len(arguments) > 0:
            monster_code = arguments[0]
        if len(arguments) > 1:
            try:
                fight_count = int(arguments[1])
            except ValueError:
                logger.error(f"Invalid fight count '{arguments[1]}'; must be an integer")
                return 1

        # Then check environment variables (for GitHub Actions or local env)
        if not monster_code:
            if os.getenv("MONSTER_CODE"):
                monster_code = os.getenv("MONSTER_CODE")
            elif os.getenv("MONSTER_NAME"):
                monster_code = os.getenv("MONSTER_NAME")

        if fight_count is None:
            fight_count_env = os.getenv("MONSTER_FIGHT_COUNT") or os.getenv("MONSTER_COUNT")
            if fight_count_env:
                try:
                    fight_count = int(fight_count_env)
                except ValueError:
                    logger.error(f"Invalid fight count '{fight_count_env}'; must be an integer")
                    return 1
            else:
                fight_count = 1

        if not monster_code:
            logger.error(
                "Monster code not provided. Use: python fight_monsters.py "
                "<monster_code> [times] [--character NAME]"
            )
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
            services = build_services(
                client,
                character_name,
                settings.combat_food_allowlist,
                settings.combat_food_count,
            )

            # Fight the monster multiple times (movement + recovery handled inside service)
            success = services.combat.fight_monster_by_code(
                monster_code,
                count=fight_count,
            )
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
