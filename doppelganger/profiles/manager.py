"""
Profile manager — CRUD operations and AI-driven profile updates.

Handles loading, saving, and updating personality profiles.
Profiles are stored as individual JSON files for simplicity
and easy inspection/editing.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from doppelganger.config import PROFILES_DIR, PROFILE_UPDATE_INTERVAL
from doppelganger.profiles.models import (
    create_profile,
    merge_profile_updates,
    FIELD_LIMITS,
)

logger = logging.getLogger("doppelganger.profiles.manager")


class ProfileManager:
    """Manages user personality profiles.

    Profiles are persisted as JSON files in the configured profiles directory.
    Each user gets their own file (user_{id}.json) for easy inspection.
    """

    def __init__(self, profiles_dir: Optional[Path] = None) -> None:
        """Initialize the profile manager.

        Args:
            profiles_dir: Directory for profile storage. Defaults to config value.
        """
        self._dir = profiles_dir or PROFILES_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[int, dict[str, Any]] = {}
        self._load_all()

    def _profile_path(self, user_id: int) -> Path:
        """Get the file path for a user's profile."""
        return self._dir / f"user_{user_id}.json"

    def _load_all(self) -> None:
        """Load all existing profiles into memory cache."""
        for path in self._dir.glob("user_*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    profile = json.load(f)
                user_id = profile.get("user_id")
                if user_id is not None:
                    self._cache[user_id] = profile
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning(f"Failed to load profile {path.name}: {exc}")

        logger.info(f"Loaded {len(self._cache)} existing profiles")

    def get_profile(self, user_id: int) -> dict[str, Any]:
        """Get a user's profile, creating a blank one if it doesn't exist.

        Args:
            user_id: Telegram user ID.

        Returns:
            The user's profile dict.
        """
        if user_id in self._cache:
            return self._cache[user_id]

        # Check disk (in case it was created externally)
        path = self._profile_path(user_id)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    profile = json.load(f)
                self._cache[user_id] = profile
                return profile
            except (json.JSONDecodeError, KeyError):
                pass

        # Create new profile
        profile = create_profile(user_id, f"User_{user_id}")
        self._cache[user_id] = profile
        self._save(user_id)
        return profile

    def _save(self, user_id: int) -> None:
        """Persist a profile to disk.

        Args:
            user_id: Telegram user ID of the profile to save.
        """
        profile = self._cache.get(user_id)
        if profile is None:
            return

        path = self._profile_path(user_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(profile, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.error(f"Failed to save profile for {user_id}: {exc}")

    def get_all_profiles(self) -> dict[int, dict[str, Any]]:
        """Get all loaded profiles.

        Returns:
            Dict mapping user_id to profile data.
        """
        return dict(self._cache)

    def find_profile_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Find a profile by display name (case-insensitive).

        Args:
            name: The name to search for.

        Returns:
            The matching profile dict, or None.
        """
        name_lower = name.lower().strip()
        for profile in self._cache.values():
            if profile.get("name", "").lower() == name_lower:
                return profile
        return None

    def get_profiles_summary(self) -> str:
        """Generate a formatted summary of all profiles for LLM context.

        Returns:
            Multi-line string with key info about each tracked user.
        """
        if not self._cache:
            return "No profiles available yet."

        summary_parts: list[str] = []

        for user_id, profile in self._cache.items():
            lines = [f"• {profile['name']}"]

            if profile.get("personality_traits"):
                traits = ", ".join(profile["personality_traits"][:5])
                lines.append(f"  Personality: {traits}")

            if profile.get("interests"):
                interests = ", ".join(profile["interests"][:5])
                lines.append(f"  Interests: {interests}")

            if profile.get("dislikes"):
                dislikes = ", ".join(profile["dislikes"][:4])
                lines.append(f"  Dislikes: {dislikes}")

            if profile.get("speech_patterns"):
                patterns = ", ".join(profile["speech_patterns"][:4])
                lines.append(f"  Speech style: {patterns}")

            if profile.get("humor_style"):
                lines.append(f"  Humor: {profile['humor_style']}")

            if profile.get("recurring_topics"):
                topics = ", ".join(profile["recurring_topics"][:4])
                lines.append(f"  Talks about: {topics}")

            if profile.get("roast_material"):
                roasts = "; ".join(profile["roast_material"][-3:])
                lines.append(f"  Roast material: {roasts}")

            if profile.get("fun_facts"):
                facts = "; ".join(profile["fun_facts"][-3:])
                lines.append(f"  Facts: {facts}")

            if profile.get("recent_quotes"):
                quotes = "; ".join(profile["recent_quotes"][-3:])
                lines.append(f"  Recent quotes: \"{quotes}\"")

            if profile.get("mood_history"):
                lines.append(f"  Last mood: {profile['mood_history'][-1]}")

            lines.append(f"  Messages: {profile['message_count']}")
            summary_parts.append("\n".join(lines))

        return "\n\n".join(summary_parts)

    async def process_message(
        self,
        user_id: int,
        user_name: str,
        message_text: str,
        context_messages: list[dict[str, Any]],
    ) -> None:
        """Process a new message — update counts and trigger analysis.

        This is the main entry point called for every message.
        It updates the message count, stores notable quotes,
        and periodically triggers deep LLM analysis.

        Args:
            user_id: Telegram user ID of the message author.
            user_name: Display name of the author.
            message_text: The message text content.
            context_messages: Recent chat messages for context.
        """
        profile = self.get_profile(user_id)

        # Update name if we have a better one
        if user_name and profile["name"].startswith("User_"):
            profile["name"] = user_name

        # Increment counters
        profile["message_count"] += 1
        profile["last_active"] = datetime.now().isoformat()

        # Store notable quotes (messages > 30 chars are more interesting)
        if len(message_text) > 30:
            profile.setdefault("recent_quotes", []).append(message_text[:200])
            max_quotes = FIELD_LIMITS.get("recent_quotes", 10)
            profile["recent_quotes"] = profile["recent_quotes"][-max_quotes:]

        # Periodic deep analysis via LLM
        if profile["message_count"] % PROFILE_UPDATE_INTERVAL == 0:
            await self._deep_analysis(profile, message_text, context_messages)

        self._cache[user_id] = profile
        self._save(user_id)

    async def _deep_analysis(
        self,
        profile: dict[str, Any],
        message_text: str,
        context_messages: list[dict[str, Any]],
    ) -> None:
        """Run LLM-powered personality extraction.

        Called every N messages per user to extract new personality
        traits, interests, speech patterns, and roast material.

        Args:
            profile: The user's current profile.
            message_text: Latest message text.
            context_messages: Recent chat context.
        """
        # Import here to avoid circular imports
        from doppelganger.ai.engine import extract_profile_updates

        try:
            updates = await extract_profile_updates(
                current_profile=profile,
                new_message=message_text,
                context_messages=context_messages,
            )

            if updates:
                merge_profile_updates(profile, updates)
                logger.info(
                    f"Profile updated for {profile['name']} "
                    f"(msg #{profile['message_count']})"
                )
        except Exception:
            logger.exception(
                f"Deep analysis failed for {profile['name']}"
            )
