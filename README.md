# Artifacts MMO Automation

Python scripts for automating tasks in Artifacts MMO game.

## Repository Structure

```
├── .github/workflows/          # GitHub Actions workflows
├── src/
│   ├── client/                 # API client
│   ├── services/               # Business logic services
│   ├── models/                 # Data models and mappings
│   └── config/                 # Configuration management
├── scripts/                    # Executable scripts
├── requirements.txt            # Python dependencies
├── .env.example               # Environment configuration template
└── README.md
```

## Local Setup

### Prerequisites
- Python 3.13+
- Artifacts MMO API key

### Installation
```bash
# Clone repository
git clone <repository-url>
cd artifacts

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API key and character name
```

## Local Usage

### Environment Setup
```bash
export ARTIFACTS_API_KEY=your_api_key_here
export ARTIFACTS_CHARACTER_NAME=your_character_name
```

### Run Scripts
```bash
# Gather resources
python scripts/gather_resources.py copper_ore 5

# Fight monsters (use the monster code)
python scripts/fight_monsters.py chicken

# Craft items
python scripts/craft_items.py wooden_staff
```

## File Overview

- **scripts/**: Entry points for different automation tasks
- **src/client/**: HTTP client for API communication
- **src/services/**: Game logic (combat, gathering, crafting, movement)
- **src/models/**: Data structures and location mappings
- **src/config/**: Environment variable management
- **.github/workflows/**: GitHub Actions for remote execution

## Gathering Tools

Gathering tool codes and their bonuses are maintained locally in
`src/models/gathering_tools.py`; the automation does not fetch tool catalogue
data from the API. At the start of each game season, refresh this table from
the current item data. The resource's gathering subtype is still read from its
item metadata, and the character inventory/equipment is checked to select the
strongest listed tool the character owns. If no listed tool is available or
equip attempts fail, gathering continues without one.

## Combat Weapons

Before fighting, the combat service reads the target monster's elemental
resistances and fetches item data for weapons in the character's inventory and
weapon slot. It estimates expected damage using the character's current combat
stats, each weapon's effects, resistance, and critical-strike chance, then
equips the highest-damage available weapon. If combat data cannot be fetched,
it logs a warning and continues with the current equipment.

Before each fight, combat recovery estimates the turns needed to defeat the
monster using the character's minimum damage per turn, then estimates worst-case
incoming damage using the monster's maximum damage per turn. It uses available
healing items that will not overflow HP and rests when needed to reach the
resulting HP threshold. If the estimate exceeds maximum HP, it prepares at
maximum HP.

Combat runs provision up to 25 healing items from the bank before fighting and
return unused provisioned food afterward. Only item codes in
`COMBAT_FOOD_ALLOWLIST` are withdrawn or used; its default is
`cooked_gudgeon,cooked_shrimp,cooked_trout,cooked_bass,cooked_salmon,cooked_swordfish`.
If the bank cannot provide the requested amount, the service fishes and cooks
the best allowlisted fish meal supported by the character's fishing and cooking
levels. During a multi-fight loop, if all allowlisted food is consumed, the
service tops up supplies between fights and returns to the fight location;
resting remains the fallback if more food cannot be obtained. Set
`COMBAT_FOOD_COUNT` to change the target, or set it to `0` to disable
provisioning. Food already in inventory before a combat run is not deposited
back as part of cleanup.

## Combat Drop Farming

When crafting requires a mob resource, the combat service looks up its source
monster through the API's monster drop filter instead of relying on a local
item-to-monster mapping.
