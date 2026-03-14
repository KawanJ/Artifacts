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