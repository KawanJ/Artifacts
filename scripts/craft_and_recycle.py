#!/usr/bin/env python3
"""Script to craft items and immediately recycle them (runs via GitHub Actions workflow)."""
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import settings
from src.client.api_client import APIClient
from src.services.crafting_service import CraftingService
from src.services.item_service import ItemService

# Configure logging for GitHub Actions
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the craft and recycle action."""
    logger.info("Starting craft-and-recycle automation...")

    try:
        # Validate settings
        settings.validate()
        logger.info(f"Settings: {settings}")

        # Parse arguments
        if len(sys.argv) < 2:
            logger.error("Usage: python craft_and_recycle.py <item_code> [cycles]")
            logger.error("Example: python craft_and_recycle.py wooden_staff 5")
            return 1

        item_code = sys.argv[1]
        cycles = 1
        if len(sys.argv) > 2:
            try:
                cycles = int(sys.argv[2])
            except ValueError:
                logger.error(f"Invalid cycles '{sys.argv[2]}'; must be an integer")
                return 1

        logger.info(f"Crafting and recycling {item_code} 1x per cycle, {cycles} cycle(s)")

        with APIClient(
            api_key=settings.api_key,
            base_url=settings.api_base_url,
            max_retries=settings.max_retries,
            timeout=settings.request_timeout,
        ) as client:
            crafting_service = CraftingService(client, settings.character_name)
            item_service = ItemService(client)

            for cycle in range(1, cycles + 1):
                logger.info(f"Cycle {cycle}/{cycles}: crafting {item_code} x1")
                if not crafting_service.craft_item(item_code, quantity=1):
                    logger.error("✗ Crafting failed")
                    return 1

                logger.info(f"Cycle {cycle}/{cycles}: recycling {item_code} x1")
                if not item_service.recycle_item(settings.character_name, item_code, quantity=1):
                    logger.error("✗ Recycling failed")
                    return 1

            logger.info("✓ Craft-and-recycle automation completed successfully")
            return 0

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
