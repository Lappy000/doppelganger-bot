"""
Configuration management for Doppelganger Bot.

All settings are loaded from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMConfig:
    """Configuration for the LLM provider."""

    provider: str = "openai"  # openai, anthropic, or any openai-compatible
    api_key: str = ""
    api_base: Optional[str] = None  # Custom base URL for compatible APIs
    model: str = "gpt-4o-mini"
    max_tokens: int = 300
    temperature: float = 0.85

    @classmethod
    def from_env(cls) -> "LLMConfig":
        return cls(
            provider=os.getenv("LLM_PROVIDER", "openai"),
            api_key=os.getenv("LLM_API_KEY", ""),
            api_base=os.getenv("LLM_API_BASE"),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "300")),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.85")),
        )


@dataclass
class BotConfig:
    """Main bot configuration."""

    telegram_token: str = ""
    data_dir: str = "./data/profiles"
    min_messages_for_profile: int = 20
    profile_update_interval: int = 10  # Update profile every N messages
    max_vocab_size: int = 500  # Top N words to track per user
    max_phrases_tracked: int = 200  # Top N phrases to track
    max_emoji_tracked: int = 50
    message_batch_size: int = 50  # Messages to buffer before analysis
    admin_user_ids: list = field(default_factory=list)
    opted_out_users: set = field(default_factory=set)
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "BotConfig":
        admin_ids_raw = os.getenv("ADMIN_USER_IDS", "")
        admin_ids = [int(x.strip()) for x in admin_ids_raw.split(",") if x.strip()]

        return cls(
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            data_dir=os.getenv("DATA_DIR", "./data/profiles"),
            min_messages_for_profile=int(os.getenv("MIN_MESSAGES_FOR_PROFILE", "20")),
            profile_update_interval=int(os.getenv("PROFILE_UPDATE_INTERVAL", "10")),
            max_vocab_size=int(os.getenv("MAX_VOCAB_SIZE", "500")),
            max_phrases_tracked=int(os.getenv("MAX_PHRASES_TRACKED", "200")),
            max_emoji_tracked=int(os.getenv("MAX_EMOJI_TRACKED", "50")),
            message_batch_size=int(os.getenv("MESSAGE_BATCH_SIZE", "50")),
            admin_user_ids=admin_ids,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )


@dataclass
class AppConfig:
    """Root configuration combining all sub-configs."""

    bot: BotConfig
    llm: LLMConfig

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            bot=BotConfig.from_env(),
            llm=LLMConfig.from_env(),
        )

    def validate(self) -> list[str]:
        """Return a list of configuration errors, empty if valid."""
        errors = []
        if not self.bot.telegram_token:
            errors.append("TELEGRAM_BOT_TOKEN is required")
        if not self.llm.api_key:
            errors.append("LLM_API_KEY is required")
        return errors
