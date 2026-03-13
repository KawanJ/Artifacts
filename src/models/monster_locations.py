"""Monster location mappings."""
from typing import Dict, Tuple


# Monster name to (x, y) coordinates mapping
MONSTER_LOCATIONS: Dict[str, Tuple[int, int]] = {
    "Chicken": (0, 1),
}


def get_monster_location(monster_name: str) -> Tuple[int, int]:
    """Get the coordinates for a monster by name.
    
    Args:
        monster_name: Name of the monster.
        
    Returns:
        Tuple of (x, y) coordinates.
        
    Raises:
        ValueError: If monster name is not found.
    """
    if monster_name not in MONSTER_LOCATIONS:
        available_monsters = ", ".join(MONSTER_LOCATIONS.keys())
        raise ValueError(
            f"Unknown monster '{monster_name}'. "
            f"Available monsters: {available_monsters}"
        )
    
    return MONSTER_LOCATIONS[monster_name]