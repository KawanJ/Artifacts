#!/usr/bin/env python3
"""Script to craft items - runs via GitHub Actions workflow."""
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config.settings import settings
from src.client.api_client import APIClient
from src.services.crafting_service import CraftingService

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
        
        # Get item code from command line argument
        if len(sys.argv) < 2:
            logger.error("Usage: python craft_items.py <item_code>")
            logger.error("Example: python craft_items.py wooden_staff")
            return 1
            
        item_code = sys.argv[1]
        logger.info(f"Crafting item: {item_code}")
        
        # Initialize API client
        with APIClient(
            api_key=settings.api_key,
            base_url=settings.api_base_url,
            max_retries=settings.max_retries,
            timeout=settings.request_timeout,
        ) as client:
            # Initialize service
            crafting_service = CraftingService(client, settings.character_name)
            
            # Craft the item
            success = crafting_service.craft_item(item_code)
            if success:
                logger.info("✓ Item crafting completed successfully")
            else:
                logger.warning("⚠ Item crafting may have failed")
        
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
