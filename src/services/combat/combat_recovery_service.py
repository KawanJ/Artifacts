"""Health recovery service for combat runs."""
import logging
import time

from src.client.api_client import APIClient
from src.services.character_service import CharacterService
from src.services.combat.combat_equipment_service import CombatEquipmentService
from src.services.combat.combat_food_service import CombatFoodService

logger = logging.getLogger(__name__)


class CombatRecoveryService:
    """Recover character health using combat food and resting."""

    def __init__(
        self,
        api_client: APIClient,
        character_name: str,
        character_service: CharacterService,
        food_service: CombatFoodService,
        equipment_service: CombatEquipmentService,
    ):
        self.api_client = api_client
        self.character_name = character_name
        self.character_service = character_service
        self.food_service = food_service
        self.equipment_service = equipment_service

    def rest(self) -> bool:
        """Rest to recover health/mana."""
        logger.info("Resting to recover...")
        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/rest",
                data={},
            )
            logger.debug("Rest result: %s", response)

            cooldown_data = response.get("data", {}).get("cooldown")
            if cooldown_data and "total_seconds" in cooldown_data:
                cooldown_seconds = cooldown_data["total_seconds"]
                logger.info("Waiting %s seconds for rest cooldown...", cooldown_seconds)
                time.sleep(cooldown_seconds)

            return True
        except Exception as e:
            logger.error("Failed to rest: %s", e)
            return False

    def recover_to_hp(self, target_hp: int, monster_code: str | None = None) -> bool:
        """Recover to a target HP using non-overflowing healing items before resting."""
        hp, max_hp = self.character_service.get_hp_status()
        target_hp = min(max(target_hp, 1), max_hp)
        if hp >= target_hp:
            logger.debug("HP is already at the required fight threshold.")
            return True

        healing_items = self.food_service.get_available_healing_items()
        refill_attempted = False
        while hp < target_hp:
            missing_hp = max_hp - hp
            usable_items = [
                (code, qty, heal)
                for code, (qty, heal) in healing_items.items()
                if qty > 0 and heal <= missing_hp
            ]
            if usable_items:
                code, qty, heal_amount = min(usable_items, key=lambda item: item[2])
                logger.info(
                    "Using healing item '%s' (heal %s) without overflow; current HP=%s/%s.",
                    code,
                    heal_amount,
                    hp,
                    max_hp,
                )
                if not self.character_service.use_item(code):
                    logger.warning("Failed to use healing item; falling back to rest.")
                    healing_items[code] = (0, heal_amount)
                    continue
                self.food_service.record_food_used(code)
                healing_items[code] = (qty - 1, heal_amount)
                hp, max_hp = self.character_service.get_hp_status()
                continue

            if (
                not refill_attempted
                and not any(quantity > 0 for quantity, _ in healing_items.values())
            ):
                refill_attempted = True
                if self.food_service.replenish_food():
                    if monster_code and not self.equipment_service.equip_best_weapon(
                        monster_code
                    ):
                        logger.warning(
                            "Could not re-equip a combat weapon after food replenishment."
                        )
                    healing_items = self.food_service.get_available_healing_items()
                    if any(quantity > 0 for quantity, _ in healing_items.values()):
                        refill_attempted = False
                        continue

            logger.info("No non-overflowing healing item available; resting.")
            if not self.rest():
                return False
            new_hp, max_hp = self.character_service.get_hp_status()
            if new_hp <= hp:
                logger.error("Rest did not increase HP toward the required fight threshold.")
                return False
            hp = new_hp

        return hp >= target_hp
