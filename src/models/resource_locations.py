"""Resource location mappings."""
from typing import Dict, Tuple


# Resource code to (x, y) coordinates mapping
RESOURCE_LOCATIONS: Dict[str, Tuple[int, int]] = {
    "copper_ore": (2, 0),
    "ash_wood": (-1, 0),
}


def get_resource_location(resource_code: str) -> Tuple[int, int]:
    """Get the coordinates for a resource by code.

    Args:
        resource_code: Code of the resource.

    Returns:
        Tuple of (x, y) coordinates.

    Raises:
        ValueError: If resource code is not found.
    """
    if resource_code not in RESOURCE_LOCATIONS:
        available_resources = ", ".join(RESOURCE_LOCATIONS.keys())
        raise ValueError(
            f"Unknown resource '{resource_code}'. "
            f"Available resources: {available_resources}"
        )

    return RESOURCE_LOCATIONS[resource_code]