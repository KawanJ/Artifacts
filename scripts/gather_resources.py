#!/usr/bin/env python3
"""Script to gather resources - runs via GitHub Actions workflow."""
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
    """Main entry point for the gather resources action."""
    logger.info("Starting resource gathering automation...")
    
    try:
        # Validate settings
        settings.validate()
        logger.info(f"Settings: {settings}")

        arguments, character_name = extract_character_argument(
            sys.argv[1:],
            settings.character_name,
        )
        
        # Get resource code and amount from command line arguments
        if len(arguments) < 2:
            logger.error(
                "Usage: python gather_resources.py <resource_code> <amount> "
                "[--character NAME]"
            )
            logger.error("Example: python gather_resources.py copper_ore 5")
            return 1
            
        resource_code = arguments[0]
        try:
            amount = int(arguments[1])
            if amount <= 0:
                raise ValueError("Amount must be positive")
        except ValueError as e:
            logger.error(f"Invalid amount '{arguments[1]}': {e}")
            return 1
            
        logger.info(f"Gathering {amount}x {resource_code}")
        
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
            
            # Gather the resource
            success = services.resource.gather_resource(resource_code, amount)
            if success:
                logger.info("✓ Resource gathering completed successfully")
            else:
                logger.warning("⚠ Resource gathering may have failed")
                return 1
        
        logger.info("Resource gathering automation finished")
        return 0
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
