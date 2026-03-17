"""Crafting location mappings based on crafting skill."""
from typing import Dict, Tuple


# Crafting skill to (x, y) coordinates mapping
CRAFTING_LOCATIONS: Dict[str, Tuple[int, int]] = {
    "weaponcrafting": (2, 1),
    "mining": (1, 5),
    "gearcrafting": (3, 1),
    "jewelrycrafting": (1, 3),
    "woodcutting": (-2, -3),
    "cooking": (1, 1),
    "alchemy": (2, 3),
}


def get_crafting_location(skill: str) -> Tuple[int, int]:
    """Get the coordinates for a crafting skill.

    Args:
        skill: Crafting skill name.

    Returns:
        Tuple of (x, y) coordinates.

    Raises:
        ValueError: If the crafting skill is not found.
    """
    if skill not in CRAFTING_LOCATIONS:
        available = ", ".join(CRAFTING_LOCATIONS.keys())
        raise ValueError(
            f"Unknown crafting skill '{skill}'. Available skills: {available}"
        )

    return CRAFTING_LOCATIONS[skill]