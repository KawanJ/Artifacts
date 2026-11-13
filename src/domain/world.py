"""World coordinates for resources, monsters, crafting stations, and the bank."""

from typing import Dict, Tuple

Position = Tuple[int, int]

BANK_LOCATION: Position = (4, 1)

CRAFTING_LOCATIONS: Dict[str, Position] = {
    "weaponcrafting": (2, 1),
    "mining": (1, 5),
    "gearcrafting": (3, 1),
    "jewelrycrafting": (1, 3),
    "woodcutting": (-2, -3),
    "cooking": (1, 1),
    "alchemy": (2, 3),
}

RESOURCE_LOCATIONS: Dict[str, Position] = {
    "copper_ore": (2, 0),
    "iron_ore": (1, 7),
    "ash_wood": (-1, 0),
    "spruce_wood": (2, 6),
    "gudgeon": (4, 2),
    "shrimp": (5, 2),
    "trout": (7, 12),
    "bass": (6, 12),
    "salmon": (-3, -4),
    "swordfish": (-4, 19),
    "sunflower": (2, 2),
}

MONSTER_LOCATIONS: Dict[str, Position] = {
    "blue_slime": (0, -2),
    "chicken": (0, 1),
    "cow": (0, 2),
    "cultist_acolyte": (0, 13),
    "cursed_tree": (9, 6),
    "cyclops": (7, -3),
    "death_knight": (8, 7),
    "desert_scorpion": (0, 18),
    "dryad": (-5, 8),
    "flying_snake": (5, 4),
    "goblin": (2, -4),
    "goblin_wolfrider": (2, -5),
    "green_slime": (0, -1),
    "grimlet": (4, 10),
    "hellhound": (-1, 13),
    "highwayman": (2, 8),
    "imp": (0, 12),
    "king_slime": (3, -1),
    "mushmush": (5, 3),
    "ogre": (8, -4),
    "orc": (7, -4),
    "owlbear": (10, 1),
    "pig": (-3, -3),
    "red_slime": (1, -1),
    "sand_snake": (-1, 18),
    "sandwarden": (-3, 19),
    "sheep": (5, 12),
    "skeleton": (8, 6),
    "spider": (-3, 12),
    "vampire": (10, 6),
    "wolf": (-2, 1),
    "yellow_slime": (1, -2),
}


def _get_location(code: str, locations: Dict[str, Position], kind: str) -> Position:
    try:
        return locations[code]
    except KeyError:
        available = ", ".join(locations)
        raise ValueError(
            f"Unknown {kind} '{code}'. Available {kind}s: {available}"
        ) from None


def get_crafting_location(skill: str) -> Position:
    """Return coordinates for a crafting skill."""
    return _get_location(skill, CRAFTING_LOCATIONS, "crafting skill")


def get_resource_location(resource_code: str) -> Position:
    """Return coordinates for a resource code."""
    return _get_location(resource_code, RESOURCE_LOCATIONS, "resource")


def get_monster_location(monster_code: str) -> Position:
    """Return coordinates for a monster code."""
    return _get_location(monster_code, MONSTER_LOCATIONS, "monster")
