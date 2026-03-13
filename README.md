# Artifacts MMO Automation Bot

A Python-based automation framework for the Artifacts MMO game. Build game automation scripts that run via GitHub Actions HTTP API calls.

## Features

- **Simple Architecture**: Clean separation between client, services, and models
- **API Client**: HTTP client with retry logic, error handling, and response parsing
- **Service Layer**: Reusable game logic (resource gathering, combat, crafting)
- **GitHub Actions Integration**: Execute scripts via manual workflow triggers
- **Environment-based Configuration**: Secure API key management using GitHub Secrets
- **Comprehensive Logging**: Clear logging for debugging and monitoring

## Repository Structure

```
artifacts-bot/
├── .github/workflows/
│   ├── gather_resources.yml       # Manual trigger for gathering
│   ├── fight_monsters.yml         # Manual trigger for combat (with monster input)
│   ├── craft_items.yml            # Manual trigger for crafting
│   └── _template_action.yml       # Template for new workflows
├── src/
│   ├── client/
│   │   └── api_client.py          # HTTP client with auth and retries
│   ├── services/
│   │   ├── resource_service.py    # Resource gathering logic
│   │   ├── combat_service.py      # Combat logic (move + fight)
│   │   └── crafting_service.py    # Crafting logic
│   ├── models/
│   │   ├── game_models.py         # Data models for API responses
│   │   └── monster_locations.py   # Monster name to coordinates mapping
│   └── config/
│       └── settings.py             # Configuration and env vars
├── scripts/
│   ├── gather_resources.py        # Entry script for workflow
│   ├── fight_monsters.py          # Entry script for workflow (requires monster name)
│   └── craft_items.py             # Entry script for workflow
├── requirements.txt                # Python dependencies
├── .env.example                    # Example configuration
├── .gitignore
└── README.md
```

## Setup Instructions

### 1. Prerequisites

- Python 3.13+
- A GitHub repository (for using GitHub Actions)
- Artifacts MMO API key

### 2. Clone the Repository

```bash
git clone <your-repository-url>
cd artifacts-bot
```

### 3. Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Copy `.env.example` and add your API key:

```bash
cp .env.example .env
# Edit .env and add your ARTIFACTS_API_KEY and ARTIFACTS_CHARACTER_NAME
```

## Running Scripts Locally

To execute any script locally (just like the GitHub Actions workflow would):

### Option 1: Using Environment Variables

```bash
# Set the API key and character name in your current shell session
export ARTIFACTS_API_KEY=your_api_key_here
export ARTIFACTS_CHARACTER_NAME=Boomining

# Run the script
python scripts/gather_resources.py
```

### Option 2: Using .env file

Create a `.env` file with your configuration:

```
ARTIFACTS_API_KEY=your_api_key_here
ARTIFACTS_API_BASE_URL=https://api.artifactsmmo.com
ARTIFACTS_CHARACTER_NAME=Boomining
LOG_LEVEL=INFO
MAX_RETRIES=3
REQUEST_TIMEOUT=30
```

Then run the script:

```bash
python scripts/gather_resources.py
```

The script will automatically load variables from `.env`.

### Example: Running Each Script

```bash
# Gather resources (with resource name and amount)
python scripts/gather_resources.py "Copper Ore" 5
python scripts/gather_resources.py "Wood" 10

# Fight monsters (with monster name input)
python scripts/fight_monsters.py Chicken
python scripts/fight_monsters.py Goblin

# Craft items (with item code input)
python scripts/craft_items.py wooden_staff
python scripts/craft_items.py copper_sword
```

### Gather Resources Script Input Options

The gather resources script requires a resource name and amount:

**Command Line Arguments:**
```bash
python scripts/gather_resources.py "Copper Ore" 5
python scripts/gather_resources.py "Wood" 10
```

**Available Resources:**
- Copper Ore (1, 0)
- Iron Ore (2, 0)
- Coal (3, 0)
- Wood (0, 2)
- Apple (0, 3)

### Fight Monsters Script Input Options

The fight monsters script accepts monster names as input:

**Command Line Argument:**
```bash
python scripts/fight_monsters.py Chicken
python scripts/fight_monsters.py "Goblin"
```

**Environment Variable:**
```bash
export MONSTER_NAME=Chicken
python scripts/fight_monsters.py
```

**Available Monsters:**
- Chicken (0, 1)
- Cow (1, 1)
- Pig (2, 1)

### Craft Items Script Input Options

The craft items script requires an item code as input:

**Command Line Argument:**
```bash
python scripts/craft_items.py wooden_staff
python scripts/craft_items.py copper_sword
```

**Common Item Codes:**
- wooden_staff
- copper_sword
- iron_armor
- wooden_shield
- Sheep (3, 1)
- Goblin (4, 1)
- Orc (5, 1)
- Skeleton (6, 1)
- Zombie (7, 1)
- Spider (8, 1)
- Wolf (9, 1)
- Bear (10, 1)
- Dragon (11, 1)

### Windows PowerShell

```powershell
cd C:\Users\Asus\Desktop\Temp\Artifacts

# Create/activate venv
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install deps
pip install -r requirements.txt

# Set API key and character name
$env:ARTIFACTS_API_KEY = "your_api_key_here"
$env:ARTIFACTS_CHARACTER_NAME = "Boomining"

# Run script with monster name
python scripts/fight_monsters.py Chicken
```

### Debugging

For more detailed output, set LOG_LEVEL to DEBUG:

```bash
export LOG_LEVEL=DEBUG
python scripts/fight_monsters.py Chicken
```

## GitHub Actions Workflows

All workflows are manually triggered. No automatic scheduled execution.

### Running a Workflow

1. Go to the **Actions** tab in your GitHub repository
2. Select the desired workflow (e.g., "Fight Monsters")
3. Click **Run workflow**
4. **For Fight Monsters**: Enter the monster name (e.g., "Chicken", "Goblin")
5. Select the branch (usually main) and click **Run workflow**

The workflow will:
- Checkout your repository
- Set up Python 3.13
- Install dependencies
- Execute the corresponding script with the provided input
- Print logs to the GitHub Actions output

## GitHub Secrets Configuration

To enable GitHub Actions workflows, configure these repository secrets:

### Required Secrets:

1. **`ARTIFACTS_API_KEY`**: Your Artifacts MMO API key
2. **`ARTIFACTS_CHARACTER_NAME`**: Your character name (default: "Boomining")

### Steps:

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add both secrets as shown above
5. Click **Add secret**

The workflows will automatically use these secrets.

## Project Architecture

### Client Layer (`src/client/`)

The `APIClient` class handles all HTTP communication:

- **Authentication**: Automatically adds Bearer token to requests
- **Retry Logic**: Uses exponential backoff for transient failures (429, 5xx errors)
- **Error Handling**: Custom `APIError` exceptions with status codes
- **Response Parsing**: Automatic JSON parsing

Example usage:

```python
from src.client.api_client import APIClient

with APIClient(api_key="your_key") as client:
    response = client.get("/resources")
    print(response)
```

### Service Layer (`src/services/`)

High-level business logic for game operations:

- **MovementService**: Character movement with cooldown handling
- **ResourceService**: Moving to resource locations and gathering (handles cooldowns automatically)
- **CombatService**: Moving to monster locations, fighting, and resting (handles cooldowns automatically)
- **CraftingService**: Moving to crafting location and crafting items (handles cooldowns automatically)

Example usage:

```python
from src.client.api_client import APIClient
from src.services.combat_service import CombatService

client = APIClient(api_key="your_key")
service = CombatService(client, "Boomining")
success = service.fight_monster_by_name("Chicken")
# Automatically moves to (0, 1), waits for move cooldown, fights, waits for fight cooldown, then rests
```

Movement can also be used directly:

```python
from src.services.movement_service import MovementService

movement = MovementService(client, "Boomining")
success = movement.move_to_location(5, 10)  # Move to coordinates (5, 10)
```

### Data Models (`src/models/`)

Type-safe dataclasses for API responses and monster locations:

- `GameResource`: Items, ore, herbs
- `Monster`: Enemy creatures with level and health
- `CraftingRecipe`: Recipes with ingredients and outputs
- `PlayerInventory`: Player inventory management
- `MONSTER_LOCATIONS`: Dictionary mapping monster names to coordinates

### Configuration (`src/config/`)

Centralized settings management:

- Loads environment variables with validation
- Provides sensible defaults
- Raises errors for missing required settings

## Troubleshooting

### API Key Not Working

1. Verify the secret is added to GitHub Settings → Secrets
2. Check the API key format (should be a valid Bearer token)
3. Test locally:

```bash
export ARTIFACTS_API_KEY=your_key
export ARTIFACTS_CHARACTER_NAME=Boomining
python scripts/fight_monsters.py Chicken
```

### Workflow Not Running

1. Enable workflows in the Actions tab (may be disabled by default)
2. Check workflow logs for errors
3. Verify repository secrets are properly set

### Python Import Errors

1. Ensure you're in the virtual environment: `source venv/bin/activate`
2. Run from the repository root directory
3. Verify dependencies are installed: `pip install -r requirements.txt`
4. Check that `PYTHONPATH` includes the repo root:

```bash
export PYTHONPATH=$PWD
python scripts/fight_monsters.py Chicken
```

### API Timeouts

1. Increase `REQUEST_TIMEOUT` in `.env` (default: 30 seconds)
2. Check your network connection
3. Verify the API endpoint is accessible

### Monster Not Found

1. Check the monster name spelling (case-sensitive)
2. Verify the monster is in the `MONSTER_LOCATIONS` mapping
3. Add new monsters to `src/models/monster_locations.py` if needed

### Move Cooldown Timeouts

The script automatically handles move cooldowns by waiting the required time before fighting. This is normal behavior and ensures the API calls work correctly.

## Best Practices

1. **Secrets Management**: Never commit `.env` or API keys to version control
2. **Idempotency**: Design scripts to be safely run multiple times
3. **Logging**: Use appropriate log levels for debugging
4. **Error Handling**: Gracefully handle API errors
5. **Testing**: Test scripts locally before running in GitHub Actions
6. **Documentation**: Keep scripts and services well-commented

## Contributing

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Make your changes and test locally
3. Commit with clear messages: `git commit -m "Add my feature"`
4. Push and create a Pull Request

---

**Happy automating!** 🤖