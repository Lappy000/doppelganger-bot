"""
Unit tests for profile models and merging logic.

Run with: python -m pytest tests/
"""

import json
from datetime import datetime

from doppelganger.profiles.models import (
    create_profile,
    merge_profile_updates,
    PROFILE_SCHEMA,
    FIELD_LIMITS,
    LIST_FIELDS,
)


class TestCreateProfile:
    """Tests for profile creation."""

    def test_creates_profile_with_id_and_name(self):
        profile = create_profile(12345, "Alice")
        assert profile["user_id"] == 12345
        assert profile["name"] == "Alice"

    def test_creates_profile_with_empty_lists(self):
        profile = create_profile(1, "Test")
        for field in LIST_FIELDS:
            assert profile[field] == [], f"{field} should be empty list"

    def test_creates_profile_with_zero_message_count(self):
        profile = create_profile(1, "Test")
        assert profile["message_count"] == 0

    def test_creates_profile_with_timestamp(self):
        profile = create_profile(1, "Test")
        assert profile["last_updated"] is not None
        # Should be a valid ISO timestamp
        datetime.fromisoformat(profile["last_updated"])

    def test_profile_has_all_schema_fields(self):
        profile = create_profile(1, "Test")
        for key in PROFILE_SCHEMA:
            assert key in profile, f"Missing field: {key}"

    def test_profiles_are_independent(self):
        """Ensure created profiles don't share mutable state."""
        p1 = create_profile(1, "A")
        p2 = create_profile(2, "B")
        p1["interests"].append("coding")
        assert "coding" not in p2["interests"]


class TestMergeProfileUpdates:
    """Tests for profile update merging."""

    def test_merges_new_traits(self):
        profile = create_profile(1, "Test")
        profile["personality_traits"] = ["sarcastic"]

        updates = {"personality_traits": ["competitive", "lazy"]}
        merge_profile_updates(profile, updates)

        assert "sarcastic" in profile["personality_traits"]
        assert "competitive" in profile["personality_traits"]
        assert "lazy" in profile["personality_traits"]

    def test_deduplicates_list_items(self):
        profile = create_profile(1, "Test")
        profile["interests"] = ["gaming", "coding"]

        updates = {"interests": ["gaming", "music"]}
        merge_profile_updates(profile, updates)

        assert profile["interests"].count("gaming") == 1
        assert "music" in profile["interests"]

    def test_respects_field_limits(self):
        profile = create_profile(1, "Test")
        limit = FIELD_LIMITS["personality_traits"]

        # Add more items than the limit
        profile["personality_traits"] = [f"trait_{i}" for i in range(limit)]
        updates = {"personality_traits": ["one_more_trait"]}
        merge_profile_updates(profile, updates)

        assert len(profile["personality_traits"]) <= limit

    def test_updates_humor_style(self):
        profile = create_profile(1, "Test")
        updates = {"humor_style": "dry sarcasm"}
        merge_profile_updates(profile, updates)
        assert profile["humor_style"] == "dry sarcasm"

    def test_tracks_mood_history(self):
        profile = create_profile(1, "Test")
        updates = {"mood": "energetic"}
        merge_profile_updates(profile, updates)

        assert len(profile["mood_history"]) == 1
        assert "energetic" in profile["mood_history"][0]

    def test_mood_history_has_timestamp(self):
        profile = create_profile(1, "Test")
        updates = {"mood": "chill"}
        merge_profile_updates(profile, updates)

        entry = profile["mood_history"][0]
        assert "(" in entry and ")" in entry  # has timestamp format

    def test_ignores_empty_updates(self):
        profile = create_profile(1, "Test")
        profile["interests"] = ["gaming"]

        updates = {"interests": [], "personality_traits": None}
        merge_profile_updates(profile, updates)

        assert profile["interests"] == ["gaming"]

    def test_strips_whitespace_from_items(self):
        profile = create_profile(1, "Test")
        updates = {"interests": ["  gaming  ", " coding "]}
        merge_profile_updates(profile, updates)

        assert "gaming" in profile["interests"]
        assert "coding" in profile["interests"]

    def test_skips_empty_string_items(self):
        profile = create_profile(1, "Test")
        updates = {"interests": ["", "  ", "gaming"]}
        merge_profile_updates(profile, updates)

        assert "" not in profile["interests"]
        assert "gaming" in profile["interests"]

    def test_updates_last_updated_timestamp(self):
        profile = create_profile(1, "Test")
        old_timestamp = profile["last_updated"]

        updates = {"interests": ["new_thing"]}
        merge_profile_updates(profile, updates)

        assert profile["last_updated"] >= old_timestamp

    def test_handles_missing_fields_in_updates(self):
        """Updates dict might not contain all fields."""
        profile = create_profile(1, "Test")
        profile["interests"] = ["gaming"]

        updates = {"personality_traits": ["brave"]}
        merge_profile_updates(profile, updates)

        assert profile["interests"] == ["gaming"]
        assert "brave" in profile["personality_traits"]

    def test_serializable_to_json(self):
        """Merged profiles should be JSON-serializable."""
        profile = create_profile(1, "Test")
        updates = {
            "personality_traits": ["smart"],
            "mood": "happy",
            "humor_style": "witty",
        }
        merge_profile_updates(profile, updates)

        # Should not raise
        json.dumps(profile, ensure_ascii=False)
