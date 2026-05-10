"""
Unit tests for conversation tracker.

Run with: python -m pytest tests/
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Patch DB_PATH before import
_test_db = tempfile.mktemp(suffix=".db")


class TestConversationTracker:
    """Tests for the ConversationTracker class."""

    @pytest.fixture
    async def tracker(self, tmp_path):
        """Create a fresh tracker with a temporary database."""
        db_path = str(tmp_path / "test.db")
        with patch("doppelganger.storage.tracker.DB_PATH", db_path):
            from doppelganger.storage.tracker import ConversationTracker
            t = ConversationTracker()
            t._db_path = db_path
            await t.initialize()
            yield t

    @pytest.mark.asyncio
    async def test_initialize_creates_table(self, tracker):
        """Database should be initialized with messages table."""
        import aiosqlite
        async with aiosqlite.connect(tracker._db_path) as db:
            async with db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ) as cursor:
                tables = [row[0] for row in await cursor.fetchall()]
        assert "messages" in tables

    @pytest.mark.asyncio
    async def test_log_and_retrieve_message(self, tracker):
        await tracker.log_message(
            user_id=123,
            user_name="Alice",
            message_text="Hello world",
        )
        messages = tracker.get_recent_messages(10)
        assert len(messages) == 1
        assert messages[0]["name"] == "Alice"
        assert messages[0]["text"] == "Hello world"

    @pytest.mark.asyncio
    async def test_buffer_order_is_chronological(self, tracker):
        for i in range(5):
            await tracker.log_message(
                user_id=1,
                user_name="User",
                message_text=f"msg_{i}",
            )
        messages = tracker.get_recent_messages(10)
        assert [m["text"] for m in messages] == [f"msg_{i}" for i in range(5)]

    @pytest.mark.asyncio
    async def test_bot_message_tracking(self, tracker):
        assert tracker.get_time_since_bot_message() == float("inf")

        await tracker.log_message(
            user_id=0,
            user_name="Bot",
            message_text="Hello!",
            is_bot=True,
        )
        assert tracker.get_time_since_bot_message() < 1.0

    @pytest.mark.asyncio
    async def test_silence_duration(self, tracker):
        assert tracker.get_silence_duration() == float("inf")

        await tracker.log_message(
            user_id=1,
            user_name="User",
            message_text="test",
        )
        assert tracker.get_silence_duration() < 1.0

    @pytest.mark.asyncio
    async def test_clear_history_keeps_recent(self, tracker):
        for i in range(20):
            await tracker.log_message(
                user_id=1,
                user_name="User",
                message_text=f"msg_{i}",
            )

        await tracker.clear_history(keep_last=5)
        messages = tracker.get_recent_messages(50)
        assert len(messages) == 5

    @pytest.mark.asyncio
    async def test_get_recent_respects_count(self, tracker):
        for i in range(10):
            await tracker.log_message(
                user_id=1,
                user_name="User",
                message_text=f"msg_{i}",
            )

        messages = tracker.get_recent_messages(3)
        assert len(messages) == 3
        # Should be the 3 most recent
        assert messages[-1]["text"] == "msg_9"
