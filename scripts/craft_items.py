#!/usr/bin/env python3
"""Script to craft items - runs via GitHub Actions workflow."""
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import settings
from src.client.api_client import APIClient
from scripts.bootstrap import build_services, extract_character_argument

# Configure logging for GitHub Actions
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the craft items action."""
    logger.info("Starting item crafting automation...")
    
    try:
        # Validate settings
        settings.validate()
        logger.info(f"Settings: {settings}")
        
        arguments, character_name = extract_character_argument(
            sys.argv[1:],
            settings.character_name,
        )

        # Get item code and optional quantity from command line arguments
        if len(arguments) < 1:
            logger.error(
                "Usage: python craft_items.py <item_code> [quantity] "
                "[--character NAME]"
            )
            logger.error("Example: python craft_items.py wooden_staff 3 --character NAME")
            return 1

        item_code = arguments[0]
        quantity = 1
        if len(arguments) > 1:
            try:
                quantity = int(arguments[1])
            except ValueError:
                logger.error(f"Invalid quantity '{arguments[1]}'; must be an integer")
                return 1

        logger.info(f"Crafting item: {item_code} x{quantity}")
        
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

            # Craft the item
            success = services.crafting.craft_item(item_code, quantity=quantity)
            if success:
                logger.info("✓ Item crafting completed successfully")
            else:
                logger.warning("⚠ Item crafting may have failed")
                return 1
        
        logger.info("Item crafting automation finished")
        return 0
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
