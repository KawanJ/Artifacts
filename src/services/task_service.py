"""Automation for accepting and completing item delivery tasks."""

import logging
import time
from typing import Any, Dict, Mapping

from src.client.api_client import APIClient
from src.domain.world import ITEMS_TASK_MASTER_LOCATION
from src.services.character_service import CharacterService
from src.services.crafting_service import CraftingService
from src.services.inventory.inventory_cleanup_service import InventoryCleanupService
from src.services.items.item_catalog_service import ItemCatalogService
from src.services.movement_service import MovementService
from src.services.resource_service import ResourceService

logger = logging.getLogger(__name__)


class TaskService:
    """Run one item task, resuming an existing task when present."""

    def __init__(
        self,
        api_client: APIClient,
        character_name: str,
        movement_service: MovementService,
        character_service: CharacterService,
        cleanup_service: InventoryCleanupService,
        item_service: ItemCatalogService,
        resource_service: ResourceService,
        crafting_service: CraftingService,
    ):
        self.api_client = api_client
        self.character_name = character_name
        self.movement_service = movement_service
        self.character_service = character_service
        self.cleanup_service = cleanup_service
        self.item_service = item_service
        self.resource_service = resource_service
        self.crafting_service = crafting_service

    def run_item_task(self) -> bool:
        """Accept or resume an item task, deliver its items, and collect rewards."""
        try:
            if not self.movement_service.move_to_location(
                *ITEMS_TASK_MASTER_LOCATION
            ):
                return False

            character_data = self.character_service.get_character_data()
            if not character_data.get("task_type"):
                response = self.api_client.post(
                    f"/my/{self.character_name}/action/task/new"
                )
                self._wait_for_cooldown(response, "accepting a task")
                character_data = self.character_service.get_character_data()

            task_code = character_data["task"]
            total = int(character_data["task_total"])
            progress = int(character_data["task_progress"])
            logger.info(
                "Running item task %s: %s/%s already delivered.",
                task_code,
                progress,
                total,
            )

            while progress < total:
                free_capacity = self.character_service.get_inventory_space()
                if free_capacity <= 0:
                    logger.error("No inventory space remains for task item '%s'.", task_code)
                    return False

                inventory = self.character_service.get_inventory()
                if not self._produce_task_items(
                    task_code,
                    total - progress,
                    free_capacity,
                    inventory,
                ):
                    return False

                available = self.character_service.get_inventory().get(task_code, 0)
                quantity = min(total - progress, available)
                if not quantity:
                    logger.error("Production did not yield any '%s'.", task_code)
                    return False

                if not self.movement_service.move_to_location(
                    *ITEMS_TASK_MASTER_LOCATION
                ):
                    return False
                response = self.api_client.post(
                    f"/my/{self.character_name}/action/task/trade",
                    data={"code": task_code, "quantity": quantity},
                )
                self._wait_for_cooldown(response, "trading task items")
                progress = int(
                    self.character_service.get_character_data()["task_progress"]
                )

            response = self.api_client.post(
                f"/my/{self.character_name}/action/task/complete"
            )
            self._wait_for_cooldown(response, "completing a task")

            if not self.cleanup_service.deposit_unneeded_items():
                logger.error("Task completed, but reward inventory cleanup failed.")
                return False
            logger.info("Item task %s completed.", task_code)
            return True
        except Exception as e:
            logger.error("Item task workflow failed: %s", e, exc_info=True)
            return False

    def _produce_task_items(
        self,
        item_code: str,
        remaining: int,
        free_capacity: int,
        inventory: Mapping[str, int],
    ) -> bool:
        item_data = self.item_service.get_item(item_code)
        if item_data.get("craft"):
            return self._craft_task_batch(
                item_code,
                remaining,
                free_capacity,
                inventory,
            )

        if item_data.get("type") == "resource":
            batch_quantity = min(remaining, free_capacity)
            return self.resource_service.gather_resource(
                item_code,
                amount=batch_quantity,
                keep_items={item_code: remaining},
                stop_when_inventory_full=True,
            )

        logger.error(
            "Task item '%s' is neither a gatherable resource nor craftable.",
            item_code,
        )
        return False

    def _craft_task_batch(
        self,
        item_code: str,
        remaining: int,
        free_capacity: int,
        inventory: Mapping[str, int],
    ) -> bool:
        actions = min(remaining, free_capacity)
        while actions > 0:
            required = self._base_input_quantities(item_code, actions)
            missing = sum(
                max(0, quantity - inventory.get(code, 0))
                for code, quantity in required.items()
            )
            if missing + actions <= free_capacity:
                break
            actions -= 1

        if actions <= 0:
            logger.error(
                "Not enough inventory capacity to craft one batch of '%s'.",
                item_code,
            )
            return False
        logger.info("Crafting task batch %s x%s.", item_code, actions)
        return self.crafting_service.craft_item(item_code, quantity=actions)

    def _base_input_quantities(
        self,
        item_code: str,
        quantity: int,
    ) -> Dict[str, int]:
        """Estimate leaf ingredients needed for a requested number of outputs."""
        recipe = self.item_service.get_item(item_code).get("craft")
        if not recipe:
            return {item_code: quantity}

        result: Dict[str, int] = {}
        for ingredient in recipe["items"]:
            required = self._base_input_quantities(
                ingredient["code"],
                ingredient["quantity"] * quantity,
            )
            for code, amount in required.items():
                result[code] = result.get(code, 0) + amount
        return result

    @staticmethod
    def _wait_for_cooldown(response: Dict[str, Any], action: str) -> None:
        cooldown = response.get("data", {}).get("cooldown")
        if cooldown and "total_seconds" in cooldown:
            seconds = cooldown["total_seconds"]
            logger.info("Waiting %s seconds after %s...", seconds, action)
            time.sleep(seconds)
