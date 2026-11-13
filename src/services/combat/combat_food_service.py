"""Food provisioning for combat runs."""
import logging
import math
import time
from typing import Any, Dict, List, Mapping, Tuple

from src.client.api_client import APIClient
from src.domain.world import RESOURCE_LOCATIONS, get_crafting_location
from src.services.inventory.bank_service import BankService
from src.services.character_service import CharacterService
from src.services.items.item_catalog_service import ItemCatalogService
from src.services.movement_service import MovementService
from src.services.resource_service import ResourceService

logger = logging.getLogger(__name__)


class CombatFoodService:
    """Prepare allowlisted healing items for a combat run and return leftovers."""

    def __init__(
        self,
        api_client: APIClient,
        character_name: str,
        allowed_food_codes: Tuple[str, ...],
        target_quantity: int,
        banking_service: BankService,
        character_service: CharacterService,
        item_service: ItemCatalogService,
        movement_service: MovementService,
        resource_service: ResourceService,
    ):
        self.api_client = api_client
        self.character_name = character_name
        self.allowed_food_codes = allowed_food_codes
        self.target_quantity = target_quantity
        self.banking_service = banking_service
        self.character_service = character_service
        self.item_service = item_service
        self.movement_service = movement_service
        self.resource_service = resource_service
        self.food_data: Dict[str, Dict[str, Any]] = {}
        self.heal_amounts: Dict[str, int] = {}
        self.baseline_inventory: Dict[str, int] = {}
        self.provisioned_quantities: Dict[str, int] = {}
        self.used_quantities: Dict[str, int] = {}
        self._provisioning_started = False
        self.reserved_items: Dict[str, int] = {}

    def _load_food_data(self) -> bool:
        """Load and validate every item explicitly allowed for combat."""
        self.food_data = {}
        self.heal_amounts = {}
        for code in self.allowed_food_codes:
            item_data = self.item_service.get_item(code)
            if not isinstance(item_data, dict):
                logger.error("Could not load allowlisted combat food '%s'.", code)
                return False

            heal_amount = next(
                (
                    effect.get("value")
                    for effect in item_data.get("effects", []) or []
                    if isinstance(effect, dict)
                    and effect.get("code") == "heal"
                    and isinstance(effect.get("value"), (int, float))
                    and effect["value"] > 0
                ),
                None,
            )
            if heal_amount is None:
                logger.error("Allowlisted item '%s' has no positive healing effect.", code)
                return False

            self.food_data[code] = item_data
            self.heal_amounts[code] = int(heal_amount)
        return True

    def get_available_healing_items(self) -> Dict[str, Tuple[int, int]]:
        """Return allowlisted foods in inventory as code -> (quantity, heal)."""
        inventory = self.character_service.get_inventory()
        return {
            code: (inventory.get(code, 0), heal_amount)
            for code, heal_amount in self.heal_amounts.items()
            if inventory.get(code, 0) > 0
        }

    def record_food_used(self, item_code: str) -> None:
        """Track one successfully consumed food item during the current run."""
        self.used_quantities[item_code] = self.used_quantities.get(item_code, 0) + 1

    def _fish_food_candidates(
        self, character_data: Dict[str, Any]
    ) -> List[Tuple[int, str, str, int, int]]:
        """Return eligible cooked-fish recipes, best healing value first."""
        fishing_level = int(character_data.get("fishing_level", 0) or 0)
        cooking_level = int(character_data.get("cooking_level", 0) or 0)
        candidates: List[Tuple[int, str, str, int, int]] = []

        for food_code, food_data in self.food_data.items():
            recipe = food_data.get("craft")
            if not isinstance(recipe, dict) or recipe.get("skill") != "cooking":
                continue
            ingredients = recipe.get("items", [])
            if not isinstance(ingredients, list) or len(ingredients) != 1:
                continue

            ingredient = ingredients[0]
            if not isinstance(ingredient, dict):
                continue
            fish_code = ingredient.get("code")
            if not isinstance(fish_code, str) or fish_code not in RESOURCE_LOCATIONS:
                continue

            fish_data = self.item_service.get_item(fish_code)
            if not isinstance(fish_data, dict) or fish_data.get("subtype") != "fishing":
                continue

            required_fishing = int(fish_data.get("level", 0) or 0)
            required_cooking = int(recipe.get("level", 0) or 0)
            if fishing_level < required_fishing or cooking_level < required_cooking:
                continue

            fish_quantity = int(ingredient.get("quantity", 0) or 0)
            output_quantity = int(recipe.get("quantity", 1) or 1)
            if fish_quantity <= 0 or output_quantity <= 0:
                continue
            candidates.append(
                (
                    self.heal_amounts[food_code],
                    food_code,
                    fish_code,
                    fish_quantity,
                    output_quantity,
                )
            )

        return sorted(candidates, reverse=True)

    def _cook_food(
        self,
        quantity_needed: int,
        character_data: Dict[str, Any],
        keep_items: Mapping[str, int],
    ) -> int:
        """Fish and cook the best allowlisted recipe for the character's skills."""
        candidates = self._fish_food_candidates(character_data)
        if not candidates:
            logger.warning(
                "No allowlisted fish recipe is available at fishing level %s "
                "and cooking level %s.",
                character_data.get("fishing_level", 0),
                character_data.get("cooking_level", 0),
            )
            return 0

        _, food_code, fish_code, fish_per_craft, food_per_craft = candidates[0]
        craft_count = math.ceil(quantity_needed / food_per_craft)
        fish_quantity = craft_count * fish_per_craft
        logger.info(
            "Preparing %s x%s from %s x%s.",
            food_code,
            craft_count * food_per_craft,
            fish_code,
            fish_quantity,
        )
        gather_keep_items = dict(keep_items)
        gather_keep_items[fish_code] = (
            gather_keep_items.get(fish_code, 0) + fish_quantity
        )
        if not self.resource_service.gather_resource(
            fish_code,
            fish_quantity,
            keep_items=gather_keep_items,
        ):
            logger.warning("Could not gather %s; continuing with banked food only.", fish_code)
            return 0

        x, y = get_crafting_location("cooking")
        if not self.movement_service.move_to_location(x, y):
            logger.warning("Could not reach the cooking workshop; continuing with banked food only.")
            return 0

        try:
            response = self.api_client.post(
                f"/my/{self.character_name}/action/crafting",
                data={"code": food_code, "quantity": craft_count},
            )
            cooldown = response.get("data", {}).get("cooldown")
            if cooldown and "total_seconds" in cooldown:
                seconds = cooldown["total_seconds"]
                logger.info("Waiting %s seconds for cooking cooldown...", seconds)
                time.sleep(seconds)
        except Exception as e:
            logger.warning("Could not cook %s: %s", food_code, e)
            return 0

        produced = craft_count * food_per_craft
        self.provisioned_quantities[food_code] = (
            self.provisioned_quantities.get(food_code, 0) + produced
        )
        return produced

    def _provision_to_target(
        self,
        character_data: Dict[str, Any] | None = None,
        inventory: Dict[str, int] | None = None,
        keep_items: Mapping[str, int] | None = None,
    ) -> bool:
        """Top up current inventory to the configured target."""
        if not self.allowed_food_codes:
            logger.warning("Combat food allowlist is empty; recovery will use resting.")
            return True
        if not self.food_data and not self._load_food_data():
            return False
        if self.target_quantity == 0:
            logger.info("Combat food provisioning is disabled.")
            return True

        if inventory is None:
            inventory = self.character_service.get_inventory()
        current_food_count = sum(
            inventory.get(code, 0) for code in self.allowed_food_codes
        )
        remaining = max(0, self.target_quantity - current_food_count)
        if remaining:
            try:
                bank_quantities = {
                    code: self.banking_service.get_bank_item_quantity(code)
                    for code in self.allowed_food_codes
                }
            except Exception as e:
                logger.error("Could not inspect bank food inventory: %s", e)
                return False

            withdraw: Dict[str, int] = {}
            for code in sorted(
                self.allowed_food_codes,
                key=lambda food_code: self.heal_amounts[food_code],
                reverse=True,
            ):
                quantity = min(bank_quantities[code], remaining)
                if quantity > 0:
                    withdraw[code] = quantity
                    remaining -= quantity
                if remaining == 0:
                    break

            if withdraw:
                if not self.banking_service.withdraw_items(withdraw):
                    return False
                self.provisioned_quantities.update(withdraw)

        if remaining:
            if character_data is None:
                character_data = self.character_service.get_character_data()
            cook_keep_items = dict(keep_items or {})
            current_inventory = self.character_service.get_inventory()
            for code in self.allowed_food_codes:
                cook_keep_items[code] = max(
                    cook_keep_items.get(code, 0),
                    current_inventory.get(code, 0),
                )
            self._cook_food(remaining, character_data, cook_keep_items)

        return True

    def prepare_food(
        self,
        keep_items: Mapping[str, int] | None = None,
    ) -> bool:
        """Withdraw food and cook any shortfall before a combat run."""
        self.reserved_items = dict(keep_items or {})
        self.baseline_inventory = self.character_service.get_inventory()
        for code in self.allowed_food_codes:
            baseline_quantity = self.baseline_inventory.get(code, 0)
            if baseline_quantity:
                self.reserved_items[code] = (
                    self.reserved_items.get(code, 0) + baseline_quantity
                )
        self.provisioned_quantities = {}
        self.used_quantities = {}
        self._provisioning_started = True
        return self._provision_to_target(
            inventory=self.baseline_inventory,
            keep_items=self.reserved_items,
        )

    def replenish_food(self) -> bool:
        """Top up depleted food between fights and return to the current location."""
        if not self._provisioning_started or self.target_quantity == 0:
            return False

        character_data = self.character_service.get_character_data()
        x = character_data.get("x")
        y = character_data.get("y")
        if not isinstance(x, int) or not isinstance(y, int):
            raise ValueError("Character location is unavailable for food replenishment.")

        provided_before = sum(self.provisioned_quantities.values())
        succeeded = False
        try:
            succeeded = self._provision_to_target(
                character_data,
                keep_items=self.reserved_items,
            )
        finally:
            if not self.movement_service.move_to_location(x, y):
                raise RuntimeError(
                    "Could not return to the fight location after food replenishment."
                )

        provided_after = sum(self.provisioned_quantities.values())
        return succeeded and provided_after > provided_before

    def return_unused_food(self) -> bool:
        """Deposit unused run-provisioned food without touching prior inventory."""
        if not self._provisioning_started:
            return True
        if not self.provisioned_quantities:
            self.baseline_inventory = {}
            self.used_quantities = {}
            self.reserved_items = {}
            self._provisioning_started = False
            return True

        inventory = self.character_service.get_inventory()
        to_deposit = {}
        for code, provisioned in self.provisioned_quantities.items():
            baseline_quantity = self.baseline_inventory.get(code, 0)
            used_provisioned = max(
                0,
                self.used_quantities.get(code, 0) - baseline_quantity,
            )
            unused = max(0, provisioned - used_provisioned)
            quantity = min(unused, inventory.get(code, 0))
            if quantity > 0:
                to_deposit[code] = quantity
        succeeded = self.banking_service.deposit_items(to_deposit)
        if succeeded:
            self.provisioned_quantities = {}
            self.baseline_inventory = {}
            self.used_quantities = {}
            self.reserved_items = {}
            self._provisioning_started = False
        return succeeded
