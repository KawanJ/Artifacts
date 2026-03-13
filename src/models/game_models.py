"""Data models for Artifacts MMO API responses."""
from dataclasses import dataclass
from typing import Dict, Any, Optional, List


@dataclass
class GameResource:
    """Represents a game resource (item, ore, herb, etc.)."""

    id: str
    name: str
    quantity: int
    location: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameResource":
        """Create a GameResource from API response data."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            quantity=data.get("quantity", 0),
            location=data.get("location"),
        )


@dataclass
class Monster:
    """Represents a monster/enemy in the game."""

    id: str
    name: str
    level: int
    health: int
    experience_reward: int
    location: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Monster":
        """Create a Monster from API response data."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            level=data.get("level", 1),
            health=data.get("health", 0),
            experience_reward=data.get("experience_reward", 0),
            location=data.get("location"),
        )


@dataclass
class CraftingRecipe:
    """Represents a crafting recipe."""

    id: str
    name: str
    ingredients: Dict[str, int]
    output: str
    output_quantity: int = 1

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CraftingRecipe":
        """Create a CraftingRecipe from API response data."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            ingredients=data.get("ingredients", {}),
            output=data.get("output", ""),
            output_quantity=data.get("output_quantity", 1),
        )


@dataclass
class PlayerInventory:
    """Represents player inventory."""

    max_slots: int
    items: List[GameResource]

    @property
    def used_slots(self) -> int:
        """Calculate the number of used inventory slots."""
        return len(self.items)

    @property
    def available_slots(self) -> int:
        """Calculate the number of available inventory slots."""
        return self.max_slots - self.used_slots

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerInventory":
        """Create a PlayerInventory from API response data."""
        items = [
            GameResource.from_dict(item)
            for item in data.get("items", [])
        ]
        return cls(
            max_slots=data.get("max_slots", 20),
            items=items,
        )
