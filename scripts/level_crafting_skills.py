#!/usr/bin/env python3
"""Script to craft items, recycle them, and stop when the specified crafting skill increases."""
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import settings
from src.client.api_client import APIClient
from src.services.crafting_service import CraftingService
from src.services.character_service import CharacterService
from src.services.item_service import ItemService

# Configure logging for GitHub Actions
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the level-crafting-skills action."""
    logger.info("Starting level-crafting-skills automation...")

    try:
        # Validate settings
        settings.validate()
        logger.info(f"Settings: {settings}")

        # Parse arguments
        if len(sys.argv) < 3:
            logger.error("Usage: python level_crafting_skills.py <skill> <item_code>")
            logger.error("Example: python level_crafting_skills.py weaponcrafting wooden_staff")
            return 1

        skill = sys.argv[1]
        item_code = sys.argv[2]

        logger.info(f"Upgrading skill '{skill}' by crafting {item_code}")

        with APIClient(
            api_key=settings.api_key,
            base_url=settings.api_base_url,
            max_retries=settings.max_retries,
            timeout=settings.request_timeout,
        ) as client:
            crafting_service = CraftingService(client, settings.character_name)
            item_service = ItemService(client)
            character_service = CharacterService(client, settings.character_name)

            # Starting skill level
            start_level = character_service.get_skill_level(skill)
            logger.info(f"Starting {skill} level: {start_level}")

            cycle = 0
            while True:
                cycle += 1
                logger.info(f"Cycle {cycle}: crafting {item_code} x1")
                if not crafting_service.craft_item(item_code, quantity=1):
                    logger.error("✗ Crafting failed")
                    return 1

                logger.info(f"Cycle {cycle}: recycling {item_code} x1")
                if not item_service.recycle_item(settings.character_name, item_code, quantity=1):
                    logger.error("✗ Recycling failed")
                    return 1

                current_level = character_service.get_skill_level(skill)
                if current_level > start_level:
                    logger.info(f"Skill '{skill}' increased from {start_level} to {current_level}; stopping.")
                    return 0

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
