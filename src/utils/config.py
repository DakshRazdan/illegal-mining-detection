"""
src/utils/config.py — YAML + .env config loader.
Single source of truth for all settings across the pipeline.
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Load .env from project root
_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")


def load_settings(config_path: str | None = None) -> dict[str, Any]:
    """Load settings.yaml and return as dict."""
    if config_path is None:
        config_path = _ROOT / "config" / "settings.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def get_env(key: str, default: str | None = None, required: bool = False) -> str | None:
    """Get env variable. Raises if required and missing."""
    value = os.getenv(key, default)
    if required and value is None:
        raise EnvironmentError(f"Required env variable '{key}' is not set. Check .env file.")
    return value


# Singleton — loaded once on import
SETTINGS: dict[str, Any] = load_settings()

__all__ = ["SETTINGS", "load_settings", "get_env"]
