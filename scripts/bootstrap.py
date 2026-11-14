"""Construction of the shared services used by the command-line scripts."""

from dataclasses import dataclass
from typing import Tuple

from src.client.api_client import APIClient
from src.services.inventory.bank_service import BankService
from src.services.character_service import CharacterService
from src.services.combat.combat_equipment_service import CombatEquipmentService
from src.services.combat.combat_food_service import CombatFoodService
from src.services.combat.combat_recovery_service import CombatRecoveryService
from src.services.combat.combat_service import CombatService
from src.services.combat.fight_service import FightService
from src.services.crafting_service import CraftingService
from src.services.inventory.inventory_cleanup_service import InventoryCleanupService
from src.services.items.item_catalog_service import ItemCatalogService
from src.services.movement_service import MovementService
from src.services.items.recycling_service import RecyclingService
from src.services.resource_service import ResourceService
from src.services.task_service import TaskService


def extract_character_argument(
    arguments: list[str],
    default_character: str,
) -> tuple[list[str], str]:
    """Remove an optional --character argument and return its selected name."""
    remaining = []
    character_name = default_character
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--character":
            if (
                index + 1 >= len(arguments)
                or arguments[index + 1].startswith("--")
            ):
                raise ValueError("--character requires a name.")
            character_name = arguments[index + 1] or default_character
            index += 2
        elif argument.startswith("--character="):
            character_name = argument.split("=", 1)[1] or default_character
            index += 1
        else:
            remaining.append(argument)
            index += 1
    return remaining, character_name


@dataclass
class AutomationServices:
    """Top-level services shared by the command-line scripts."""

    resource: ResourceService
    crafting: CraftingService
    combat: CombatService
    character: CharacterService
    recycling: RecyclingService
    tasks: TaskService


def build_services(
    api_client: APIClient,
    character_name: str,
    combat_food_allowlist: Tuple[str, ...],
    combat_food_count: int,
) -> AutomationServices:
    """Build the dependency graph once at the script entry point."""
    movement = MovementService(api_client, character_name)
    character = CharacterService(api_client, character_name)
    items = ItemCatalogService(api_client)
    bank = BankService(api_client, character_name, movement, character)
    cleanup = InventoryCleanupService(bank, character, items)

    resource = ResourceService(
        api_client,
        character_name,
        movement,
        cleanup,
        character,
        items,
    )
    food = CombatFoodService(
        api_client,
        character_name,
        combat_food_allowlist,
        combat_food_count,
        bank,
        character,
        items,
        movement,
        resource,
    )
    equipment = CombatEquipmentService(api_client, character, items)
    fight = FightService(api_client, character_name)
    recovery = CombatRecoveryService(
        api_client,
        character_name,
        character,
        food,
        equipment,
    )
    combat = CombatService(
        api_client,
        character_name,
        movement,
        character,
        cleanup,
        equipment,
        fight,
        food,
        recovery,
    )
    crafting = CraftingService(
        movement,
        cleanup,
        items,
        character,
        resource,
        combat,
        api_client,
        character_name,
    )

    tasks = TaskService(
        api_client,
        character_name,
        movement,
        character,
        cleanup,
        items,
        resource,
        crafting,
    )

    return AutomationServices(
        resource=resource,
        crafting=crafting,
        combat=combat,
        character=character,
        recycling=RecyclingService(api_client, character_name),
        tasks=tasks,
    )
