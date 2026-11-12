"""Monster location mappings."""
from typing import Dict, Tuple


# One overworld spawn per monster, sourced from the maps API.
MONSTER_LOCATIONS: Dict[str, Tuple[int, int]] = {
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