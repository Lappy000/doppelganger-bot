"""
Configuration module for Doppelganger Bot.

Loads settings from environment variables with sensible defaults.
All configuration is centralized here — no magic values elsewhere.
"""

import os
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file from project root
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")


# === Telegram Configuration ===

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
GROUP_CHAT_ID: int = int(os.getenv("GROUP_CHAT_ID", "0"))


# === LLM Provider Configuration ===

LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "1000"))
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.85"))


# === Bot Behavior ===

RANDOM_REPLY_CHANCE: float = float(os.getenv("RANDOM_REPLY_CHANCE", "0.15"))
SILENCE_THRESHOLD_MINUTES: int = int(os.getenv("SILENCE_THRESHOLD_MINUTES", "120"))
MIN_SPONTANEOUS_INTERVAL: int = int(os.getenv("MIN_SPONTANEOUS_INTERVAL", "10"))
PROFILE_UPDATE_INTERVAL: int = int(os.getenv("PROFILE_UPDATE_INTERVAL", "10"))


# === Schedule & Quiet Hours ===

QUIET_HOURS_START: int = int(os.getenv("QUIET_HOURS_START", "2"))
QUIET_HOURS_END: int = int(os.getenv("QUIET_HOURS_END", "9"))


# === Paths ===

DATA_DIR: Path = _project_root / "data"
PROFILES_DIR: Path = DATA_DIR / "profiles"
DB_PATH: Path = DATA_DIR / "conversation_log.db"

# Ensure data directories exist
PROFILES_DIR.mkdir(parents=True, exist_ok=True)


# === Logging ===

LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
BOT_NAME: str = os.getenv("BOT_NAME", "Doppelganger")


def setup_logging() -> logging.Logger:
    """Configure application-wide logging."""
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Suppress noisy HTTP libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

    logger = logging.getLogger("doppelganger")
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    return logger


def validate_config() -> list[str]:
    """Validate required configuration. Returns list of errors."""
    errors: list[str] = []

    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is not set")
    if not GROUP_CHAT_ID:
        errors.append("GROUP_CHAT_ID is not set")
    if not LLM_API_KEY:
        errors.append("LLM_API_KEY is not set")
    if not LLM_BASE_URL:
        errors.append("LLM_BASE_URL is not set")

    return errors
