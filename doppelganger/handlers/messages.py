"""
Message handler — processes incoming group messages.

Responsibilities:
- Log every message to the conversation tracker
- Update user personality profiles
- Decide whether the bot should respond
- Generate and send AI responses
"""

import asyncio
import logging
import random
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from doppelganger.config import (
    GROUP_CHAT_ID,
    RANDOM_REPLY_CHANCE,
)
from doppelganger.ai.engine import generate_response
from doppelganger.storage.tracker import ConversationTracker
from doppelganger.profiles.manager import ProfileManager

logger = logging.getLogger("doppelganger.handlers.messages")


def determine_trigger(
    update: Update,
    bot_username: Optional[str],
    time_since_bot_msg: float,
) -> Optional[str]:
    """Determine if and why the bot should respond.

    Returns:
        Trigger type string ("mentioned", "reply", "random") or None.
    """
    message = update.message
    if not message or not message.text:
        return None

    text = message.text.lower()

    # 1. Direct @mention
    if bot_username and f"@{bot_username.lower()}" in text:
        return "mentioned"

    # 2. Reply to bot's message
    if (
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.is_bot
    ):
        return "reply"

    # 3. Keyword triggers (configurable bot names)
    bot_triggers = {"bot", "doppelganger"}
    if any(trigger in text for trigger in bot_triggers):
        return "mentioned"

    # 4. Random chance
    if random.random() < RANDOM_REPLY_CHANCE:
        return "random"

    # 5. Question when bot has been quiet (30+ min)
    if "?" in text and time_since_bot_msg > 30 and random.random() < 0.3:
        return "random"

    return None


def resolve_user_name(update: Update) -> str:
    """Extract the best display name for a user."""
    user = update.message.from_user
    if user.first_name:
        return user.first_name
    if user.username:
        return user.username
    return f"User_{user.id}"


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Process an incoming group message.

    This is the main message handler — it logs the message,
    updates profiles, checks triggers, and generates responses.
    """
    message = update.message
    if not message or not message.text:
        return

    # Skip bot messages
    if message.from_user.is_bot:
        return

    # Retrieve shared state
    tracker: ConversationTracker = context.bot_data["tracker"]
    profile_manager: ProfileManager = context.bot_data["profile_manager"]
    bot_username: Optional[str] = context.bot_data.get("bot_username")

    user_id = message.from_user.id
    user_name = resolve_user_name(update)
    text = message.text

    logger.debug(f"Message from {user_name} ({user_id}): {text[:80]}")

    # Log the message
    reply_to_id = None
    if message.reply_to_message:
        reply_to_id = message.reply_to_message.message_id

    await tracker.log_message(
        user_id=user_id,
        user_name=user_name,
        message_text=text,
        reply_to_message_id=reply_to_id,
    )

    # Update personality profile
    recent_context = tracker.get_recent_messages(20)
    await profile_manager.process_message(
        user_id=user_id,
        user_name=user_name,
        message_text=text,
        context_messages=recent_context,
    )

    # Check if bot should respond
    time_since_bot = tracker.get_time_since_bot_message()
    trigger = determine_trigger(update, bot_username, time_since_bot)

    if not trigger:
        return

    logger.info(f"Triggered ({trigger}) by {user_name}")

    # Anti-spam: don't respond if bot just spoke (within 5 min for random)
    if trigger == "random" and time_since_bot < 5:
        logger.debug("Skipping random trigger — bot spoke recently")
        return

    # Typing indicator
    try:
        await context.bot.send_chat_action(
            chat_id=GROUP_CHAT_ID,
            action="typing",
        )
    except Exception:
        pass  # Non-critical

    # Natural delay (1-3 seconds)
    await asyncio.sleep(random.uniform(1.0, 3.0))

    # Build context and generate response
    profiles_summary = profile_manager.get_profiles_summary()
    recent_messages = tracker.get_recent_messages(30)

    try:
        response = await generate_response(
            profiles_summary=profiles_summary,
            recent_messages=recent_messages,
            trigger_type=trigger,
            target_user=user_name,
        )
    except Exception:
        logger.exception("AI response generation failed")
        return

    if not response:
        logger.warning("AI returned empty response")
        return

    # Send with retry
    for attempt in range(3):
        try:
            await message.reply_text(response)
            break
        except Exception as exc:
            logger.warning(f"Send attempt {attempt + 1}/3 failed: {exc}")
            if attempt < 2:
                await asyncio.sleep(2)
            else:
                logger.error("Failed to send message after 3 attempts")
                return

    # Log bot's own message
    await tracker.log_message(
        user_id=0,
        user_name="Bot",
        message_text=response,
        is_bot=True,
    )

    logger.info(f"[{trigger}] → {user_name}: {response[:100]}")
