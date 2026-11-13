"""Combat weapon selection and equipment."""
import logging
from typing import Any, Dict

from src.client.api_client import APIClient
from src.services.character_service import CharacterService
from src.domain.combat.damage import (
    estimate_weapon_expected_damage,
    item_effects,
)
from src.services.items.item_catalog_service import ItemCatalogService

logger = logging.getLogger(__name__)


class CombatEquipmentService:
    """Equip the owned weapon with the highest estimated damage."""

    def __init__(
        self,
        api_client: APIClient,
        character_service: CharacterService,
        item_service: ItemCatalogService,
    ):
        self.api_client = api_client
        self.character_service = character_service
        self.item_service = item_service

    def equip_best_weapon(self, monster_code: str) -> bool:
        """Equip the owned weapon with the highest expected damage against a monster."""
        try:
            character_data = self.character_service.get_character_data()
            monster_response = self.api_client.get(f"/monsters/{monster_code}")
        except Exception as e:
            logger.warning("Could not load combat data for %s: %s", monster_code, e)
            return False

        monster_data = monster_response.get("data")
        if not isinstance(monster_data, dict):
            logger.warning(
                "No monster data returned for %s; keeping current weapon.",
                monster_code,
            )
            return False

        inventory = character_data.get("inventory", []) or []
        inventory_codes = {
            entry.get("code")
            for entry in inventory
            if isinstance(entry, dict)
            and entry.get("code")
            and (entry.get("quantity", 0) or 0) > 0
        }
        equipped_code = character_data.get("weapon_slot")
        available_codes = inventory_codes | ({equipped_code} if equipped_code else set())
        weapon_data: Dict[str, Dict[str, Any]] = {}
        try:
            for item_code in available_codes:
                item_data = self.item_service.get_item(item_code)
                if not isinstance(item_data, dict):
                    logger.warning(
                        "Item data for '%s' is unavailable; keeping current weapon.",
                        item_code,
                    )
                    return False
                if item_data.get("type") == "weapon":
                    weapon_data[item_code] = item_data
        except Exception as e:
            logger.warning("Could not load owned weapon data: %s", e)
            return False

        current_weapon_effects = item_effects(weapon_data.get(equipped_code, {}))
        candidates = sorted(
            [
                (
                    estimate_weapon_expected_damage(
                        character_data,
                        current_weapon_effects,
                        item_effects(item_data),
                        monster_data,
                    ),
                    weapon_code,
                )
                for weapon_code, item_data in weapon_data.items()
            ],
            reverse=True,
        )

        if not candidates:
            logger.info("No owned combat weapon found; continuing without changing equipment.")
            return False

        logger.info(
            "Weapon damage estimates against %s: %s",
            monster_code,
            ", ".join(f"{code}={damage:.2f}" for damage, code in candidates),
        )
        if equipped_code and any(
            damage == candidates[0][0] and code == equipped_code
            for damage, code in candidates
        ):
            logger.info("Best available weapon '%s' is already equipped.", equipped_code)
            return True

        for _, weapon_code in candidates:
            if weapon_code == equipped_code:
                logger.info("Using currently equipped weapon '%s' as fallback.", weapon_code)
                return True

            logger.info("Equipping best available combat weapon '%s'.", weapon_code)
            if self.character_service.equip_item(weapon_code):
                return True
            logger.warning(
                "Could not equip combat weapon '%s'; trying another.",
                weapon_code,
            )

        logger.warning("No available combat weapon could be equipped.")
        return False
