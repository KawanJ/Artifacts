"""Resource location mappings."""
from typing import Dict, Tuple


# Resource name to (x, y) coordinates mapping
RESOURCE_LOCATIONS: Dict[str, Tuple[int, int]] = {
    "Ash Tree": (-1, 0),
}


def get_resource_location(resource_name: str) -> Tuple[int, int]:
    """Get the coordinates for a resource by name.

    Args:
        resource_name: Name of the resource.

    Returns:
        Tuple of (x, y) coordinates.

    Raises:
        ValueError: If resource name is not found.
    """
    if resource_name not in RESOURCE_LOCATIONS:
        available_resources = ", ".join(RESOURCE_LOCATIONS.keys())
        raise ValueError(
            f"Unknown resource '{resource_name}'. "
            f"Available resources: {available_resources}"
        )

    return RESOURCE_LOCATIONS[resource_name]