"""
Background scheduler — periodic tasks for proactive bot behavior.

Handles:
- Breaking long silences with conversation starters
- Occasional spontaneous messages
- Quiet hours enforcement
"""

import asyncio
import logging
import random
from datetime import datetime
from typing import Optional

from telegram import Bot

from doppelganger.config import (
    GROUP_CHAT_ID,
    SILENCE_THRESHOLD_MINUTES,
    MIN_SPONTANEOUS_INTERVAL,
    QUIET_HOURS_START,
    QUIET_HOURS_END,
)
from doppelganger.storage.tracker import ConversationTracker
from doppelganger.profiles.manager import ProfileManager

logger = logging.getLogger("doppelganger.scheduler.background")


class BotScheduler:
    """Background scheduler for proactive bot behavior.

    Runs a periodic check loop that decides whether to:
    - Break a long silence
    - Send a random spontaneous message
    - Do nothing (respect quiet hours and cooldowns)
    """

    def __init__(
        self,
        bot: Bot,
        tracker: ConversationTracker,
        profile_manager: ProfileManager,
    ) -> None:
        """Initialize the scheduler.

        Args:
            bot: Telegram Bot instance for sending messages.
            tracker: Conversation tracker for timing info.
            profile_manager: Profile manager for generating contextual messages.
        """
        self._bot = bot
        self._tracker = tracker
        self._profile_manager = profile_manager
        self._running = False

    async def run(self) -> None:
        """Start the background check loop.

        This runs indefinitely — designed to be launched as an asyncio task.
        Checks are spaced randomly (5-15 min) for natural-feeling behavior.
        """
        self._running = True
        logger.info("Scheduler loop started")

        while self._running:
            try:
                await self._check_and_act()
            except Exception:
                logger.exception("Scheduler check failed")

            # Random interval between checks (5-15 minutes)
            wait_seconds = random.randint(5, 15) * 60
            await asyncio.sleep(wait_seconds)

    def stop(self) -> None:
        """Signal the scheduler to stop."""
        self._running = False
        logger.info("Scheduler stopping")

    def _is_quiet_hours(self) -> bool:
        """Check if current time is within quiet hours.

        Returns:
            True if bot should stay silent.
        """
        hour = datetime.now().hour
        if QUIET_HOURS_START <= QUIET_HOURS_END:
            return QUIET_HOURS_START <= hour <= QUIET_HOURS_END
        else:
            # Handles wrap-around (e.g., 22:00 to 06:00)
            return hour >= QUIET_HOURS_START or hour <= QUIET_HOURS_END

    async def _check_and_act(self) -> None:
        """Evaluate conditions and decide whether to send a message."""
        # Respect quiet hours
        if self._is_quiet_hours():
            logger.debug("Quiet hours — skipping")
            return

        silence_duration = self._tracker.get_silence_duration()
        bot_silence = self._tracker.get_time_since_bot_message()

        # Don't spam — respect minimum interval
        if bot_silence < MIN_SPONTANEOUS_INTERVAL:
            logger.debug(
                f"Bot spoke {bot_silence:.1f} min ago "
                f"(min interval: {MIN_SPONTANEOUS_INTERVAL}) — skipping"
            )
            return

        # Priority 1: Break long silence
        if silence_duration >= SILENCE_THRESHOLD_MINUTES:
            logger.info(
                f"Breaking silence ({silence_duration:.0f} min quiet)"
            )
            await self._break_silence()
            return

        # Priority 2: Occasional random message (10% chance, 30+ min silence)
        if silence_duration > 30 and random.random() < 0.10:
            logger.info("Sending spontaneous message")
            await self._send_spontaneous()

    async def _break_silence(self) -> None:
        """Generate and send a silence-breaking message."""
        from doppelganger.ai.engine import generate_silence_breaker

        profiles_summary = self._profile_manager.get_profiles_summary()
        message = await generate_silence_breaker(profiles_summary)

        if message:
            await self._send_message(message)
            logger.info(f"Silence breaker sent: {message[:80]}")

    async def _send_spontaneous(self) -> None:
        """Generate and send a random spontaneous message."""
        from doppelganger.ai.engine import generate_response

        profiles_summary = self._profile_manager.get_profiles_summary()
        recent = self._tracker.get_recent_messages(20)

        message = await generate_response(
            profiles_summary=profiles_summary,
            recent_messages=recent,
            trigger_type="silence",
        )

        if message:
            await self._send_message(message)
            logger.info(f"Spontaneous message sent: {message[:80]}")

    async def _send_message(self, text: str) -> None:
        """Send a message to the group and log it.

        Args:
            text: Message text to send.
        """
        try:
            await self._bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=text,
            )
            await self._tracker.log_message(
                user_id=0,
                user_name="Bot",
                message_text=text,
                is_bot=True,
            )
        except Exception:
            logger.exception("Failed to send scheduled message")
