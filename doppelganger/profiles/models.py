"""
Profile data models and schema definitions.

Defines the structure of a user personality profile
and provides factory functions for creating new profiles.
"""

from datetime import datetime
from typing import Any


# Profile schema with all tracked personality dimensions
PROFILE_SCHEMA: dict[str, Any] = {
    "user_id": None,
    "name": "",
    "personality_traits": [],       # Character traits (e.g., "sarcastic", "competitive")
    "interests": [],                # Hobbies and interests
    "dislikes": [],                 # Things they dislike
    "humor_style": "",              # How they joke (e.g., "dry wit", "self-deprecation")
    "speech_patterns": [],          # Characteristic phrases and mannerisms
    "recurring_topics": [],         # Topics they frequently bring up
    "fun_facts": [],                # Memorable facts and stories
    "roast_material": [],           # Material for friendly roasting
    "mood_history": [],             # Recent mood observations
    "relationship_with_others": {}, # How they interact with specific people
    "last_active": None,            # ISO timestamp of last activity
    "message_count": 0,             # Total messages tracked
    "last_updated": None,           # ISO timestamp of last profile update
    "recent_quotes": [],            # Notable recent quotes
}

# Maximum items per list field to prevent unbounded growth
FIELD_LIMITS: dict[str, int] = {
    "personality_traits": 20,
    "interests": 20,
    "dislikes": 15,
    "speech_patterns": 15,
    "recurring_topics": 15,
    "fun_facts": 15,
    "roast_material": 15,
    "mood_history": 10,
    "recent_quotes": 10,
}

# Fields that are lists and can be merged
LIST_FIELDS: list[str] = [
    "personality_traits",
    "interests",
    "dislikes",
    "speech_patterns",
    "recurring_topics",
    "roast_material",
    "fun_facts",
]


def create_profile(user_id: int, name: str) -> dict[str, Any]:
    """Create a new blank profile for a user.

    Args:
        user_id: Telegram user ID.
        name: Display name for the user.

    Returns:
        A new profile dict with default values.
    """
    profile = {}
    for key, default in PROFILE_SCHEMA.items():
        if isinstance(default, list):
            profile[key] = []
        elif isinstance(default, dict):
            profile[key] = {}
        else:
            profile[key] = default

    profile["user_id"] = user_id
    profile["name"] = name
    profile["last_updated"] = datetime.now().isoformat()
    return profile


def merge_profile_updates(
    profile: dict[str, Any],
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Merge LLM-extracted updates into an existing profile.

    Handles deduplication and field size limits to prevent
    profiles from growing unboundedly.

    Args:
        profile: The existing profile to update.
        updates: New data extracted by the LLM.

    Returns:
        The updated profile dict (mutated in place and returned).
    """
    # Merge list fields with deduplication
    for field in LIST_FIELDS:
        new_items = updates.get(field)
        if not new_items or not isinstance(new_items, list):
            continue

        existing = set(profile.get(field, []))
        for item in new_items:
            if isinstance(item, str) and item.strip():
                existing.add(item.strip())

        max_items = FIELD_LIMITS.get(field, 20)
        profile[field] = list(existing)[-max_items:]

    # Merge scalar string fields
    if updates.get("humor_style"):
        profile["humor_style"] = updates["humor_style"]

    # Track mood history
    if updates.get("mood"):
        timestamp = datetime.now().strftime("%m/%d %H:%M")
        mood_entry = f"{updates['mood']} ({timestamp})"
        profile.setdefault("mood_history", []).append(mood_entry)
        max_moods = FIELD_LIMITS.get("mood_history", 10)
        profile["mood_history"] = profile["mood_history"][-max_moods:]

    profile["last_updated"] = datetime.now().isoformat()
    return profile
