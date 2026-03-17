"""Monster location mappings."""
from typing import Dict, Tuple


# Monster code to (x, y) coordinates mapping
MONSTER_LOCATIONS: Dict[str, Tuple[int, int]] = {
    "chicken": (0, 1),
    "yellow_slime": (1, -2),
    "blue_slime": (0, -2),
    "green_slime": (0, -1),
    "red_slime": (1, -1),
    "king_slime": (3, -1),
    "cow": (0, 2),
    "wolf": (-2, 1),
    "pig": (-3, -3),
    "sheep": (5, 12),
}


def get_monster_location(monster_code: str) -> Tuple[int, int]:
    """Get the coordinates for a monster by code.
    
    Args:
        monster_code: Code of the monster.
        
    Returns:
        Tuple of (x, y) coordinates.
        
    Raises:
        ValueError: If monster code is not found.
    """
    if monster_code not in MONSTER_LOCATIONS:
        available_monsters = ", ".join(MONSTER_LOCATIONS.keys())
        raise ValueError(
            f"Unknown monster '{monster_code}'. "
            f"Available monsters: {available_monsters}"
        )
    
    return MONSTER_LOCATIONS[monster_code]