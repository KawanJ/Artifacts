#!/usr/bin/env python3
"""Accept or resume and complete one item task."""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.client.api_client import APIClient
from src.config.settings import settings
from scripts.bootstrap import build_services, extract_character_argument

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    """Run one item task and return a process status."""
    logger.info("Starting item task automation...")
    try:
        settings.validate()
        arguments, character_name = extract_character_argument(
            sys.argv[1:],
            os.getenv("ITEM_TASK_CHARACTER_NAME") or settings.character_name,
        )
        if arguments:
            logger.error("Unexpected arguments: %s", arguments)
            return 1
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
            if not services.tasks.run_item_task():
                logger.error("Item task automation failed.")
                return 1

        logger.info("Item task automation finished successfully.")
        return 0
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        return 1
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
