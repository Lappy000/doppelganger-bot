"""
Conversation tracker — SQLite-backed message logging with in-memory buffer.

Provides both persistent storage (SQLite) and fast in-memory access
(deque buffer) for recent messages. Tracks timing for silence detection
and spam prevention.
"""

import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Optional

import aiosqlite

from doppelganger.config import DB_PATH

logger = logging.getLogger("doppelganger.storage.tracker")

# SQL schema for the messages table
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    user_name TEXT NOT NULL,
    message_text TEXT NOT NULL,
    reply_to_message_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_bot BOOLEAN DEFAULT FALSE
)
"""

# Buffer size for in-memory recent messages
_BUFFER_SIZE = 50


class ConversationTracker:
    """Tracks conversation messages with dual storage strategy.

    Messages are stored in:
    1. SQLite database (persistent, queryable, full history)
    2. In-memory deque (fast access to last N messages)

    Also tracks timing metadata for response decisions.
    """

    def __init__(self) -> None:
        """Initialize the tracker (call `initialize()` before use)."""
        self._buffer: deque[dict[str, Any]] = deque(maxlen=_BUFFER_SIZE)
        self._last_message_time: Optional[datetime] = None
        self._last_bot_message_time: Optional[datetime] = None
        self._db_path = str(DB_PATH)

    async def initialize(self) -> None:
        """Initialize the database and load recent messages into buffer.

        Must be called once during application startup.
        """
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_TABLE_SQL)
            await db.commit()

            # Load recent messages into memory buffer
            async with db.execute(
                "SELECT user_id, user_name, message_text, timestamp, is_bot "
                "FROM messages ORDER BY id DESC LIMIT ?",
                (_BUFFER_SIZE,),
            ) as cursor:
                rows = await cursor.fetchall()

            # Insert in chronological order (rows are DESC)
            for row in reversed(rows):
                msg = {
                    "user_id": row[0],
                    "name": row[1],
                    "text": row[2],
                    "timestamp": row[3],
                    "is_bot": bool(row[4]),
                }
                self._buffer.append(msg)

                # Track timing from loaded messages
                if row[4]:  # is_bot
                    self._last_bot_message_time = datetime.now()
                self._last_message_time = datetime.now()

        logger.info(
            f"Conversation tracker initialized ({len(self._buffer)} messages loaded)"
        )

    async def log_message(
        self,
        user_id: int,
        user_name: str,
        message_text: str,
        is_bot: bool = False,
        reply_to_message_id: Optional[int] = None,
    ) -> None:
        """Log a message to both storage layers.

        Args:
            user_id: Telegram user ID (0 for bot messages).
            user_name: Display name of the sender.
            message_text: The message content.
            is_bot: Whether this is a bot-generated message.
            reply_to_message_id: ID of the message being replied to.
        """
        now = datetime.now()

        # Add to in-memory buffer
        msg_data = {
            "user_id": user_id,
            "name": user_name,
            "text": message_text,
            "timestamp": now.isoformat(),
            "is_bot": is_bot,
        }
        self._buffer.append(msg_data)

        # Update timing
        self._last_message_time = now
        if is_bot:
            self._last_bot_message_time = now

        # Persist to SQLite
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "INSERT INTO messages "
                    "(user_id, user_name, message_text, reply_to_message_id, is_bot) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (user_id, user_name, message_text, reply_to_message_id, is_bot),
                )
                await db.commit()
        except Exception:
            logger.exception("Failed to persist message to database")

    def get_recent_messages(self, count: int = 30) -> list[dict[str, Any]]:
        """Get the most recent messages from the buffer.

        Args:
            count: Maximum number of messages to return.

        Returns:
            List of message dicts (oldest first).
        """
        return list(self._buffer)[-count:]

    def get_silence_duration(self) -> float:
        """Get minutes since the last message in the group.

        Returns:
            Minutes of silence. Returns infinity if no messages tracked.
        """
        if not self._last_message_time:
            return float("inf")
        delta = datetime.now() - self._last_message_time
        return delta.total_seconds() / 60.0

    def get_time_since_bot_message(self) -> float:
        """Get minutes since the bot's last message.

        Returns:
            Minutes since bot spoke. Returns infinity if bot hasn't spoken.
        """
        if not self._last_bot_message_time:
            return float("inf")
        delta = datetime.now() - self._last_bot_message_time
        return delta.total_seconds() / 60.0

    async def get_user_stats(
        self,
        user_id: int,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get message statistics for a specific user.

        Args:
            user_id: Telegram user ID.
            days: Number of days to look back.

        Returns:
            Dict with 'count' and 'messages_sample' keys.
        """
        async with aiosqlite.connect(self._db_path) as db:
            since = (datetime.now() - timedelta(days=days)).isoformat()

            async with db.execute(
                "SELECT COUNT(*), GROUP_CONCAT(message_text, ' | ') "
                "FROM messages WHERE user_id = ? AND timestamp > ?",
                (user_id, since),
            ) as cursor:
                row = await cursor.fetchone()
                return {
                    "count": row[0] or 0,
                    "messages_sample": (row[1] or "")[:500],
                }

    async def clear_history(self, keep_last: int = 10) -> None:
        """Clear conversation history, keeping the most recent messages.

        Args:
            keep_last: Number of recent messages to preserve.
        """
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                DELETE FROM messages
                WHERE id NOT IN (
                    SELECT id FROM messages
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (keep_last,),
            )
            await db.commit()

        # Rebuild in-memory buffer
        self._buffer.clear()
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT user_id, user_name, message_text, timestamp, is_bot "
                "FROM messages ORDER BY id DESC LIMIT ?",
                (keep_last,),
            ) as cursor:
                rows = await cursor.fetchall()

            for row in reversed(rows):
                self._buffer.append({
                    "user_id": row[0],
                    "name": row[1],
                    "text": row[2],
                    "timestamp": row[3],
                    "is_bot": bool(row[4]),
                })

        logger.info(f"History cleared (kept last {keep_last} messages)")

    async def get_message_count(self) -> int:
        """Get total number of messages in the database.

        Returns:
            Total message count.
        """
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM messages") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
