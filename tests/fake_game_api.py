"""Stateful in-memory API used by service and CLI integration tests."""

from typing import Any

from src.client.api_client import APIError
from src.domain.world import RESOURCE_LOCATIONS


class FakeGameAPI:
    """Small game simulator that applies requests to character and bank state."""

    def __init__(
        self,
        inventory: dict[str, int] | None = None,
        *,
        hp: int = 100,
        max_inventory_slots: int = 20,
        fight_damage: int = 0,
        fight_drops: list[dict[str, Any]] | None = None,
        rest_heals: bool = True,
        recycles_without_skill_gain: int = 0,
    ):
        self.inventory = dict(inventory or {})
        self.bank: dict[str, int] = {}
        self.max_inventory_slots = max_inventory_slots
        self.fight_damage = fight_damage
        self.fight_drops = list(fight_drops or [])
        self.rest_heals = rest_heals
        self.recycles_without_skill_gain = recycles_without_skill_gain
        self.fail_actions: set[str] = set()
        self.fail_once_actions: set[str] = set()
        self.fail_statuses: dict[str, int] = {}
        self.fail_get_endpoints: set[str] = set()
        self.fail_once_get_endpoints: set[str] = set()
        self.moves: list[tuple[int, int]] = []
        self.crafted: dict[str, int] = {}
        self.recycled: dict[str, int] = {}
        self.equip_attempts = 0
        self.character: dict[str, Any] = {
            "x": 0,
            "y": 0,
            "hp": hp,
            "max_hp": 100,
            "weapon_slot": None,
            "attack_fire": 10,
            "attack_earth": 0,
            "attack_water": 0,
            "attack_air": 0,
            "critical_strike": 0,
            "dmg": 0,
            "dmg_fire": 0,
            "dmg_earth": 0,
            "dmg_water": 0,
            "dmg_air": 0,
            "weaponcrafting_level": 0,
            "fishing_level": 10,
            "cooking_level": 10,
            "task": None,
            "task_type": None,
            "task_progress": 0,
            "task_total": 0,
            "inventory_max_items": max_inventory_slots,
        }
        self.task_offer: dict[str, Any] = {
            "code": "copper_ore",
            "type": "items",
            "total": 1,
            "rewards": {
                "gold": 150,
                "items": [{"code": "tasks_coin", "quantity": 2}],
            },
        }
        self.accepted_tasks = 0
        self.completed_tasks = 0
        self.items: dict[str, dict[str, Any]] = {
            "copper_ore": {
                "code": "copper_ore",
                "type": "resource",
                "subtype": "mining",
            },
            "wooden_staff": {
                "code": "wooden_staff",
                "type": "weapon",
                "effects": [{"code": "attack_fire", "value": 2}],
                "craft": {
                    "skill": "weaponcrafting",
                    "items": [{"code": "copper_ore", "quantity": 1}],
                    "quantity": 1,
                },
            },
            "cooked_shrimp": {
                "code": "cooked_shrimp",
                "type": "consumable",
                "effects": [{"code": "heal", "value": 10}],
                "craft": {
                    "skill": "cooking",
                    "level": 1,
                    "items": [{"code": "shrimp", "quantity": 1}],
                    "quantity": 1,
                },
            },
            "shrimp": {
                "code": "shrimp",
                "type": "resource",
                "subtype": "fishing",
                "level": 1,
            },
            "voidstone_pickaxe": {
                "code": "voidstone_pickaxe",
                "type": "tool",
            },
            "copper_pickaxe": {
                "code": "copper_pickaxe",
                "type": "tool",
            },
        }
        self.monsters: dict[str, dict[str, Any]] = {
            "chicken": {
                "code": "chicken",
                "hp": 10,
                "attack_fire": 1,
                "attack_earth": 0,
                "attack_water": 0,
                "attack_air": 0,
                "critical_strike": 0,
                "dmg": 0,
                "dmg_fire": 0,
                "dmg_earth": 0,
                "dmg_water": 0,
                "dmg_air": 0,
                "res_fire": 0,
                "res_earth": 0,
                "res_water": 0,
                "res_air": 0,
                "drops": [],
            }
        }
        self.gather_attempts = 0
        self.gathered: dict[str, int] = {}
        self.fights: list[tuple[int, int]] = []

    def __enter__(self) -> "FakeGameAPI":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        if endpoint in self.fail_get_endpoints:
            raise APIError(f"Simulated GET failure: {endpoint}", status_code=500)
        if endpoint in self.fail_once_get_endpoints:
            self.fail_once_get_endpoints.remove(endpoint)
            raise APIError(f"Simulated one-time GET failure: {endpoint}", status_code=500)
        if endpoint.startswith("/characters/"):
            return {
                "data": {
                    **self.character,
                    "inventory": [
                        {"code": code, "quantity": quantity}
                        for code, quantity in self.inventory.items()
                        if quantity > 0
                    ],
                }
            }
        if endpoint.startswith("/items/"):
            code = endpoint.rsplit("/", 1)[-1]
            return {
                "data": self.items.get(
                    code,
                    {"code": code, "type": "resource"},
                )
            }
        if endpoint == "/monsters":
            drop_code = params.get("drop")
            return {
                "data": [
                    monster
                    for monster in self.monsters.values()
                    if drop_code is None
                    or any(drop.get("code") == drop_code for drop in monster["drops"])
                ]
            }
        if endpoint.startswith("/monsters/"):
            code = endpoint.rsplit("/", 1)[-1]
            return {"data": self.monsters.get(code)}
        if endpoint == "/my/bank/items":
            item_code = params.get("item_code")
            return {
                "data": [
                    {"code": code, "quantity": quantity}
                    for code, quantity in self.bank.items()
                    if quantity > 0 and (item_code is None or code == item_code)
                ]
            }
        raise APIError(f"Unexpected GET endpoint: {endpoint}", status_code=404)

    def post(
        self,
        endpoint: str,
        data: dict[str, Any] | list[dict[str, Any]] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = data or {}
        if "/action/" in endpoint:
            action = endpoint.split("/action/", 1)[1]
            if action in self.fail_actions:
                status_code = self.fail_statuses.get(action, 400)
                if action in self.fail_once_actions:
                    self.fail_actions.remove(action)
                    self.fail_once_actions.remove(action)
                raise APIError(
                    f"Simulated {action} failure",
                    status_code=status_code,
                )
        if endpoint.endswith("/action/move"):
            self.character["x"] = data["x"]
            self.character["y"] = data["y"]
            self.moves.append((data["x"], data["y"]))
            return self._response()
        if endpoint.endswith("/action/task/new"):
            if self.character.get("task_type"):
                raise APIError("An active task already exists", status_code=400)
            self.accepted_tasks += 1
            self.character.update(
                {
                    "task": self.task_offer["code"],
                    "task_type": self.task_offer["type"],
                    "task_progress": 0,
                    "task_total": self.task_offer["total"],
                }
            )
            return self._response(
                {
                    "task": self.task_offer,
                    "character": self.character,
                }
            )
        if endpoint.endswith("/action/task/trade"):
            code, quantity = data["code"], data["quantity"]
            if (
                self.character.get("task_type") != "items"
                or code != self.character.get("task")
                or quantity > self.character["task_total"] - self.character["task_progress"]
            ):
                raise APIError("Items do not match the active task", status_code=400)
            self._remove(self.inventory, code, quantity)
            self.character["task_progress"] += quantity
            return self._response(
                {
                    "trade": {"code": code, "quantity": quantity},
                    "character": self.character,
                }
            )
        if endpoint.endswith("/action/task/complete"):
            if (
                not self.character.get("task_type")
                or self.character["task_progress"] < self.character["task_total"]
            ):
                raise APIError("The active task is not complete", status_code=400)
            rewards = self.task_offer.get("rewards", {})
            self.character["gold"] = self.character.get("gold", 0) + rewards.get(
                "gold", 0
            )
            for item in rewards.get("items", []):
                self._add(self.inventory, item["code"], item["quantity"])
            self.completed_tasks += 1
            self.character.update(
                {
                    "task": None,
                    "task_type": None,
                    "task_progress": 0,
                    "task_total": 0,
                }
            )
            return self._response({"rewards": rewards, "character": self.character})
        if endpoint.endswith("/action/gathering"):
            self.gather_attempts += 1
            resource_code = next(
                (
                    code
                    for code, position in RESOURCE_LOCATIONS.items()
                    if position == (self.character["x"], self.character["y"])
                ),
                None,
            )
            if resource_code is None:
                raise APIError("No resource at current location", status_code=400)
            if sum(self.inventory.values()) >= self.max_inventory_slots:
                raise APIError("Inventory is full", status_code=497)
            self._add(self.inventory, resource_code, 1)
            self._add(self.gathered, resource_code, 1)
            return self._response()
        if endpoint.endswith("/action/bank/deposit/item"):
            for entry in data:
                code, quantity = entry["code"], entry["quantity"]
                self._remove(self.inventory, code, quantity)
                self._add(self.bank, code, quantity)
            return self._response()
        if endpoint.endswith("/action/bank/withdraw/item"):
            for entry in data:
                code, quantity = entry["code"], entry["quantity"]
                self._remove(self.bank, code, quantity)
                self._add(self.inventory, code, quantity)
            return self._response()
        if endpoint.endswith("/action/crafting"):
            code, quantity = data["code"], data["quantity"]
            item = self.items[code]
            recipe = item["craft"]
            for ingredient in recipe.get("items", []):
                required = ingredient["quantity"] * quantity
                if self.inventory.get(ingredient["code"], 0) < required:
                    raise APIError("Missing crafting ingredients", status_code=400)
            for ingredient in recipe.get("items", []):
                self._remove(
                    self.inventory,
                    ingredient["code"],
                    ingredient["quantity"] * quantity,
                )
            self._add(
                self.inventory,
                code,
                recipe.get("quantity", 1) * quantity,
            )
            self._add(
                self.crafted,
                code,
                recipe.get("quantity", 1) * quantity,
            )
            return self._response()
        if endpoint.endswith("/action/recycling"):
            code, quantity = data["code"], data["quantity"]
            self._remove(self.inventory, code, quantity)
            self._add(self.recycled, code, quantity)
            skill = self.items[code].get("craft", {}).get("skill")
            if skill:
                if self.recycles_without_skill_gain:
                    self.recycles_without_skill_gain -= 1
                else:
                    key = f"{skill}_level"
                    self.character[key] = self.character.get(key, 0) + quantity
            return self._response()
        if endpoint.endswith("/action/equip"):
            self.equip_attempts += len(data)
            for item in data:
                self.character[f"{item['slot']}_slot"] = item["code"]
            return self._response()
        if endpoint.endswith("/action/use"):
            code, quantity = data["code"], data["quantity"]
            self._remove(self.inventory, code, quantity)
            heal = next(
                (
                    effect["value"]
                    for effect in self.items.get(code, {}).get("effects", [])
                    if effect.get("code") == "heal"
                ),
                0,
            )
            self.character["hp"] = min(
                self.character["max_hp"],
                self.character["hp"] + heal * quantity,
            )
            return self._response()
        if endpoint.endswith("/action/fight"):
            self.fights.append((self.character["x"], self.character["y"]))
            self.character["hp"] = max(
                0,
                self.character["hp"] - self.fight_damage,
            )
            for drop in self.fight_drops:
                self._add(
                    self.inventory,
                    drop["code"],
                    drop.get("quantity", 1),
                )
            return self._response(
                {
                    "fight": {
                        "characters": [{"drops": self.fight_drops}],
                    }
                }
            )
        if endpoint.endswith("/action/rest"):
            if self.rest_heals:
                self.character["hp"] = self.character["max_hp"]
            return self._response()
        raise APIError(f"Unexpected POST endpoint: {endpoint}", status_code=404)

    @staticmethod
    def _add(container: dict[str, int], code: str, quantity: int) -> None:
        container[code] = container.get(code, 0) + quantity

    @staticmethod
    def _remove(container: dict[str, int], code: str, quantity: int) -> None:
        if container.get(code, 0) < quantity:
            raise APIError(f"Not enough {code}", status_code=400)
        remaining = container[code] - quantity
        if remaining:
            container[code] = remaining
        else:
            container.pop(code)

    @staticmethod
    def _response(data: dict[str, Any] | None = None) -> dict[str, Any]:
        response_data = {"cooldown": {"total_seconds": 0}}
        if data:
            response_data.update(data)
        return {"data": response_data}
