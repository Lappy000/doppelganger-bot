"""
Profile storage layer for Doppelganger Bot.

Handles persistence of personality profiles as JSON files.
Each user gets their own profile file, keyed by Telegram user ID.
No raw messages are ever stored - only extracted features.
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class StyleMetrics:
    """Quantitative writing style measurements."""

    avg_message_length: float = 0.0
    avg_word_length: float = 0.0
    avg_sentence_length: float = 0.0
    capitalization_ratio: float = 0.0  # How often they capitalize
    punctuation_density: float = 0.0  # Punctuation chars per message
    question_ratio: float = 0.0  # How often messages are questions
    exclamation_ratio: float = 0.0
    ellipsis_usage: float = 0.0  # Frequency of "..."
    avg_messages_per_burst: float = 1.0  # Consecutive messages in a row


@dataclass
class PersonalityProfile:
    """Complete personality profile for a single user."""

    user_id: int = 0
    username: str = ""
    display_name: str = ""
    chat_id: int = 0

    # Core metrics
    style: StyleMetrics = field(default_factory=StyleMetrics)
    total_messages_analyzed: int = 0
    first_seen: float = 0.0
    last_updated: float = 0.0

    # Vocabulary fingerprint (word -> relative frequency)
    top_words: dict = field(default_factory=dict)
    unique_phrases: list = field(default_factory=list)  # Distinctive multi-word patterns
    filler_words: dict = field(default_factory=dict)  # "like", "um", "basically" etc.

    # Emoji & reaction patterns
    emoji_frequencies: dict = field(default_factory=dict)
    emoji_per_message: float = 0.0

    # Topic preferences (topic -> affinity score 0-1)
    topic_affinities: dict = field(default_factory=dict)

    # Slang and informal language
    slang_terms: dict = field(default_factory=dict)
    abbreviations: dict = field(default_factory=dict)  # "u", "rn", "ngl" etc.

    # Response behavior
    reply_speed_avg: float = 0.0  # Seconds between being mentioned and replying
    conversation_starter_ratio: float = 0.0
    agrees_ratio: float = 0.0  # How often they agree vs disagree
    humor_score: float = 0.0  # Frequency of jokes/humor markers

    # Temporal patterns
    active_hours: dict = field(default_factory=dict)  # hour -> message count
    active_days: dict = field(default_factory=dict)  # day_of_week -> message count

    def to_dict(self) -> dict:
        """Serialize profile to dictionary."""
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "PersonalityProfile":
        """Deserialize profile from dictionary."""
        style_data = data.pop("style", {})
        style = StyleMetrics(**style_data)
        profile = cls(style=style, **data)
        return profile

    def get_summary(self) -> str:
        """Generate a human-readable summary of this profile."""
        lines = [
            f"👤 Profile: {self.display_name} (@{self.username})",
            f"📊 Messages analyzed: {self.total_messages_analyzed}",
            f"",
            f"✍️ Writing Style:",
            f"  • Avg message length: {self.style.avg_message_length:.0f} chars",
            f"  • Avg word length: {self.style.avg_word_length:.1f} chars",
            f"  • Questions: {self.style.question_ratio*100:.0f}% of messages",
            f"  • Exclamations: {self.style.exclamation_ratio*100:.0f}%",
            f"  • Capitalization: {'proper' if self.style.capitalization_ratio > 0.5 else 'lowercase vibes'}",
            f"",
            f"🔤 Top words: {', '.join(list(self.top_words.keys())[:10])}",
            f"😀 Fav emojis: {' '.join(list(self.emoji_frequencies.keys())[:8])}",
            f"💬 Slang: {', '.join(list(self.slang_terms.keys())[:8])}",
        ]

        if self.topic_affinities:
            top_topics = sorted(self.topic_affinities.items(), key=lambda x: x[1], reverse=True)[:5]
            lines.append(f"📌 Topics: {', '.join(t[0] for t in top_topics)}")

        if self.active_hours:
            peak_hour = max(self.active_hours.items(), key=lambda x: x[1])[0]
            lines.append(f"🕐 Most active: {peak_hour}:00")

        return "\n".join(lines)


class ProfileStorage:
    """Manages reading/writing personality profiles to disk."""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, PersonalityProfile] = {}
        logger.info(f"ProfileStorage initialized at {self.data_dir}")

    def _get_path(self, user_id: int, chat_id: int) -> Path:
        """Get file path for a user's profile in a specific chat."""
        return self.data_dir / f"profile_{chat_id}_{user_id}.json"

    def _cache_key(self, user_id: int, chat_id: int) -> str:
        return f"{chat_id}:{user_id}"

    def load_profile(self, user_id: int, chat_id: int) -> Optional[PersonalityProfile]:
        """Load a user's profile from disk or cache."""
        key = self._cache_key(user_id, chat_id)

        if key in self._cache:
            return self._cache[key]

        path = self._get_path(user_id, chat_id)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            profile = PersonalityProfile.from_dict(data)
            self._cache[key] = profile
            return profile
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.error(f"Failed to load profile {path}: {e}")
            return None

    def save_profile(self, profile: PersonalityProfile) -> None:
        """Save a profile to disk and update cache."""
        profile.last_updated = time.time()
        path = self._get_path(profile.user_id, profile.chat_id)
        key = self._cache_key(profile.user_id, profile.chat_id)

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(profile.to_dict(), f, indent=2, ensure_ascii=False)
            self._cache[key] = profile
            logger.debug(f"Saved profile for user {profile.user_id} in chat {profile.chat_id}")
        except OSError as e:
            logger.error(f"Failed to save profile: {e}")

    def get_or_create_profile(
        self, user_id: int, chat_id: int, username: str = "", display_name: str = ""
    ) -> PersonalityProfile:
        """Load existing profile or create a new one."""
        profile = self.load_profile(user_id, chat_id)
        if profile is None:
            profile = PersonalityProfile(
                user_id=user_id,
                username=username,
                display_name=display_name,
                chat_id=chat_id,
                first_seen=time.time(),
                last_updated=time.time(),
            )
            self.save_profile(profile)
        return profile

    def list_profiles(self, chat_id: int) -> list[PersonalityProfile]:
        """List all profiles for a given chat."""
        profiles = []
        pattern = f"profile_{chat_id}_*.json"
        for path in self.data_dir.glob(pattern):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profiles.append(PersonalityProfile.from_dict(data))
            except Exception as e:
                logger.warning(f"Skipping corrupted profile {path}: {e}")
        return profiles

    def delete_profile(self, user_id: int, chat_id: int) -> bool:
        """Delete a user's profile (for opt-out)."""
        path = self._get_path(user_id, chat_id)
        key = self._cache_key(user_id, chat_id)
        self._cache.pop(key, None)

        if path.exists():
            path.unlink()
            logger.info(f"Deleted profile for user {user_id} in chat {chat_id}")
            return True
        return False

    def get_chat_stats(self, chat_id: int) -> dict:
        """Get aggregate stats for a chat."""
        profiles = self.list_profiles(chat_id)
        if not profiles:
            return {"total_users": 0, "total_messages": 0}

        return {
            "total_users": len(profiles),
            "total_messages": sum(p.total_messages_analyzed for p in profiles),
            "top_users": sorted(
                [(p.display_name, p.total_messages_analyzed) for p in profiles],
                key=lambda x: x[1],
                reverse=True,
            )[:10],
            "oldest_profile": min(p.first_seen for p in profiles),
            "newest_update": max(p.last_updated for p in profiles),
        }
