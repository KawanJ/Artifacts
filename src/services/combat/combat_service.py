"""Combat service for fighting monsters."""
import logging
import math
from typing import Any, Callable, Dict, Mapping

from src.client.api_client import APIClient
from src.config.settings import settings
from src.services.banking_service import BankingService
from src.services.character_service import CharacterService
from src.services.combat.combat_action_service import CombatActionService
from src.services.combat.combat_damage import estimate_damage_per_turn
from src.services.combat.combat_equipment_service import CombatEquipmentService
from src.services.combat.combat_food_service import CombatFoodService
from src.services.combat.combat_recovery_service import CombatRecoveryService
from src.services.item_service import ItemService
from src.services.movement_service import MovementService

logger = logging.getLogger(__name__)


class CombatService:
    """Service for managing combat and monster fights."""

    def __init__(self, api_client: APIClient, character_name: str):
        """Initialize CombatService.
        
        Args:
            api_client: API client instance.
            character_name: Name of the character to control.
        """
        self.api_client = api_client
        self.character_name = character_name
        self.movement_service = MovementService(api_client, character_name)
        self.character_service = CharacterService(api_client, character_name)
        self.banking_service = BankingService(api_client, character_name)
        self.item_service = ItemService(api_client)
        self.equipment_service = CombatEquipmentService(
            api_client,
            self.character_service,
            self.item_service,
        )
        self.action_service = CombatActionService(
            api_client,
            character_name,
            self.banking_service,
            self.movement_service,
        )
        self.food_service = CombatFoodService(
            api_client,
            character_name,
            settings.combat_food_allowlist,
            settings.combat_food_count,
        )
        self.recovery_service = CombatRecoveryService(
            api_client,
            character_name,
            self.food_service,
            self.equipment_service,
        )

    def _minimum_hp_to_fight(self, monster_code: str) -> int:
        """Estimate HP needed to survive the fight using minimum player damage."""
        character_data = self.character_service.get_character_data()
        monster_response = self.api_client.get(f"/monsters/{monster_code}")
        monster_data = monster_response.get("data")
        if not isinstance(monster_data, dict):
            raise ValueError(f"No monster data returned for {monster_code}")

        max_hp = int(character_data.get("max_hp", 0) or 0)
        monster_hp = int(monster_data.get("hp", 0) or 0)
        if max_hp <= 0 or monster_hp <= 0:
            raise ValueError(f"Invalid HP data for combat with {monster_code}")

        minimum_player_damage = estimate_damage_per_turn(
            character_data, monster_data, critical=False
        )
        maximum_monster_damage = estimate_damage_per_turn(
            monster_data, character_data, critical=True
        )
        if minimum_player_damage <= 0:
            logger.warning(
                "Could not estimate positive minimum damage against %s; requiring full HP.",
                monster_code,
            )
            return max_hp

        turns_to_defeat = math.ceil(monster_hp / minimum_player_damage)
        maximum_fight_damage = turns_to_defeat * maximum_monster_damage
        required_hp = maximum_fight_damage + 1
        if required_hp > max_hp:
            logger.warning(
                "Worst-case estimated damage from %s (%s HP) exceeds max HP (%s); "
                "preparing at max HP.",
                monster_code,
                maximum_fight_damage,
                max_hp,
            )
            return max_hp

        logger.info(
            "Estimated fight threshold for %s: %s HP "
            "(minimum player damage %s/turn, maximum monster damage %s/turn, %s turns).",
            monster_code,
            required_hp,
            minimum_player_damage,
            maximum_monster_damage,
            turns_to_defeat,
        )
        return max(1, required_hp)

    def get_monster_code_for_drop(self, drop_code: str) -> str | None:
        """Get a monster code for an item by querying the API's drop filter."""
        response = self.api_client.get("/monsters", params={"drop": drop_code})
        monsters = response.get("data")
        if not isinstance(monsters, list):
            return None

        for monster in monsters:
            if not isinstance(monster, dict) or not isinstance(monster.get("code"), str):
                continue
            drops = monster.get("drops", [])
            if isinstance(drops, list) and any(
                isinstance(drop, dict) and drop.get("code") == drop_code
                for drop in drops
            ):
                return monster["code"]

        return None

    def fight_monster(
        self,
        monster_code: str,
        keep_items: Mapping[str, int] | None = None,
    ) -> Dict[str, Any] | None:
        """Fight a monster at current location.

        Returns:
            Fight response data if successful, None otherwise.
        """
        return self.action_service.fight_once(monster_code, keep_items=keep_items)

    def farm_drops(
        self,
        target_item_code: str,
        target_quantity: int,
        monster_code: str | None = None,
        keep_items: Mapping[str, int] | None = None,
    ) -> bool:
        """Provision food, farm drops, then return unused run-provisioned food."""
        if target_quantity <= 0:
            logger.info("No drops required; skipping combat drop farming.")
            return True
        workflow_keep_items = dict(keep_items or {})
        workflow_keep_items[target_item_code] = max(
            workflow_keep_items.get(target_item_code, 0),
            target_quantity,
        )
        success = False
        try:
            success = self._run_with_food(
                lambda: self._farm_drops(
                    target_item_code,
                    target_quantity,
                    monster_code,
                    workflow_keep_items,
                ),
                workflow_keep_items,
            )
        except Exception as e:
            logger.error("Drop-farming workflow failed: %s", e, exc_info=True)
        if not self.banking_service.deposit_unneeded_items(workflow_keep_items):
            logger.error("Failed to deposit unneeded items after drop farming.")
            success = False
        return success

    def _farm_drops(
        self,
        target_item_code: str,
        target_quantity: int,
        monster_code: str | None = None,
        keep_items: Mapping[str, int] | None = None,
    ) -> bool:
        """Fight monsters until required drop quantity is achieved.

        Args:
            target_item_code: Item code of required drop (e.g., raw_chicken).
            target_quantity: Amount of item to collect.
            monster_code: Optional monster code to fight; if missing, inferred from target_item_code.

        Returns:
            True if target quantity reached, False otherwise.
        """
        monster_code = monster_code or self.get_monster_code_for_drop(target_item_code)
        if not monster_code:
            logger.error(f"Cannot determine which monster drops '{target_item_code}'.")
            return False

        if not self.equipment_service.equip_best_weapon(monster_code):
            logger.warning("Unable to equip combat weapon; continuing without a dedicated weapon.")

        if not self.action_service.move_to_monster(monster_code):
            return False

        required_hp = self._minimum_hp_to_fight(monster_code)
        collected = 0
        attempts = 0
        while collected < target_quantity:
            attempts += 1
            logger.info(f"Combat drop farm attempt {attempts}: collected {collected}/{target_quantity} {target_item_code}")
            if not self.recovery_service.recover_to_hp(required_hp, monster_code):
                logger.error("Failed to reach the required HP before farming fight")
                return False

            fight_response = self.fight_monster(monster_code, keep_items=keep_items)
            if not fight_response:
                logger.error("Fight failed during drop farm; aborting")
                return False

            # parse drop count
            drops = []
            fight_info = fight_response.get("fight", {})
            characters = fight_info.get("characters", [])
            if characters and isinstance(characters, list):
                first_char = characters[0]
                drops = first_char.get("drops", []) or []

            for drop in drops:
                if drop.get("code") == target_item_code:
                    qty = int(drop.get("quantity", 0))
                    collected += qty
                    logger.info(f"Received {qty}x {target_item_code} from fight; total collected is now {collected}")

            # if no relevant drops but fight succeeded, continue
            if collected >= target_quantity:
                if not self.rest():
                    logger.error("Failed to rest after the final drop-farming fight")
                    return False
                logger.info(f"Target drop quantity reached: {collected}/{target_quantity}")
                return True

        return True

    def rest(self) -> bool:
        """Rest to recover health/mana."""
        return self.recovery_service.rest()

    def _run_with_food(
        self,
        operation: Callable[[], bool],
        keep_items: Mapping[str, int] | None = None,
    ) -> bool:
        """Run one combat workflow with food provisioned and leftovers returned."""
        success = False
        try:
            if not self.food_service.prepare_food(keep_items=keep_items):
                return False
            success = operation()
        finally:
            if not self.food_service.return_unused_food():
                logger.error("Could not return unused combat food to the bank.")
                success = False
        return success

    def fight_monster_by_code(self, monster_code: str, count: int = 1) -> bool:
        """Provision food, fight a monster multiple times, then return leftovers."""
        if count <= 0:
            logger.error("Fight count must be positive.")
            return False
        success = False
        try:
            success = self._run_with_food(
                lambda: self._fight_monster_by_code(monster_code, count),
                keep_items={},
            )
        except Exception as e:
            logger.error("Combat workflow failed: %s", e, exc_info=True)
        if not self.banking_service.deposit_unneeded_items():
            logger.error("Failed to deposit unneeded items after combat.")
            success = False
        return success

    def _fight_monster_by_code(self, monster_code: str, count: int = 1) -> bool:
        """Move to monster location and fight it multiple times.

        Args:
            monster_code: Code of the monster to fight.
            count: Number of times to fight.

        Returns:
            True if successful, False otherwise.
        """
        logger.info(f"Fighting monster: {monster_code} x{count}")

        try:
            # Ensure combat gear is in place for fight loops
            self.equipment_service.equip_best_weapon(monster_code)

            if not self.action_service.move_to_monster(monster_code):
                return False

            required_hp = self._minimum_hp_to_fight(monster_code)
            for attempt in range(1, count + 1):
                logger.info(f"Fight attempt {attempt}/{count} for {monster_code}")
                if not self.recovery_service.recover_to_hp(required_hp, monster_code):
                    logger.error("Failed to reach the required HP before fight")
                    return False

                fight_response = self.fight_monster(monster_code)
                if not fight_response:
                    logger.error("Failed to fight monster")
                    return False

                if attempt == count and not self.rest():
                    logger.error("Failed to rest after the final fight")
                    return False

            logger.info(f"Successfully fought {monster_code} {count} time(s)")
            return True

        except ValueError as e:
            logger.error(f"Monster location error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error fighting monster: {e}")
            return False
