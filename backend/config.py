import json
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent  # repo root
CONFIG_DIR = PROJECT_DIR
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "provider": "gemini",
    "api_key": "",
    "model": "gemini-3-flash-preview",
    "morning_time": "09:00",
    "evening_time": "21:00",
    "journal_dir": str(PROJECT_DIR / "journal"),
    "db_path": str(PROJECT_DIR / "lifepilot.db"),
}


def get_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2))
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_FILE) as f:
        stored = json.load(f)

    # Merge with defaults so new keys are always present
    config = DEFAULT_CONFIG.copy()
    config.update(stored)
    return config
