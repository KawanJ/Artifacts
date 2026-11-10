"""Season-maintained gathering tools and their gathering effect values."""
from typing import Dict


# Verified against game item data on 2026-11-10; refresh at the start of each season.
# Values are the item's gathering effects; lower (more negative) values are stronger.
GATHERING_TOOLS: Dict[str, Dict[str, int]] = {
    "mining": {
        "voidstone_pickaxe": -70,
        "adamantite_pickaxe": -60,
        "mithril_pickaxe": -50,
        "gold_pickaxe": -40,
        "steel_pickaxe": -30,
        "iron_pickaxe": -20,
        "copper_pickaxe": -10,
    },
    "woodcutting": {
        "voidstone_axe": -70,
        "adamantite_axe": -60,
        "mithril_axe": -50,
        "gold_axe": -40,
        "steel_axe": -30,
        "iron_axe": -20,
        "copper_axe": -10,
    },
    "fishing": {
        "voidstone_fishing_rod": -70,
        "adamantite_fishing_rod": -60,
        "mithril_fishing_rod": -50,
        "gold_fishing_rod": -40,
        "steel_fishing_rod": -30,
        "spruce_fishing_rod": -20,
        "fishing_net": -10,
    },
    "alchemy": {
        "voidstone_gloves": -70,
        "adamantite_gloves": -60,
        "mithril_gloves": -50,
        "golden_gloves": -40,
        "steel_gloves": -30,
        "leather_gloves": -20,
        "apprentice_gloves": -10,
    },
}
