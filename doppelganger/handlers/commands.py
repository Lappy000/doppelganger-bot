"""
Command handlers for bot slash commands.

Provides user-facing commands for profile inspection,
roasting, impersonation, and admin operations.
"""

import logging
from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from doppelganger.config import GROUP_CHAT_ID
from doppelganger.ai.engine import generate_response, generate_impersonation
from doppelganger.storage.tracker import ConversationTracker
from doppelganger.profiles.manager import ProfileManager

logger = logging.getLogger("doppelganger.handlers.commands")


async def cmd_profile(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show a user's learned personality profile.

    Usage:
        /profile — shows your own profile
        /profile <name> — shows someone else's profile
    """
    try:
        profile_manager: ProfileManager = context.bot_data["profile_manager"]

        # Determine target user
        if context.args:
            target_name = " ".join(context.args)
            profile = profile_manager.find_profile_by_name(target_name)
            if not profile:
                await update.message.reply_text(
                    f"No profile found for '{target_name}'"
                )
                return
        else:
            user_id = update.message.from_user.id
            profile = profile_manager.get_profile(user_id)

        # Format profile display
        lines = [f"🎭 Profile: {profile['name']}\n"]

        if profile["personality_traits"]:
            traits = ", ".join(profile["personality_traits"][:6])
            lines.append(f"Personality: {traits}")

        if profile["interests"]:
            interests = ", ".join(profile["interests"][:6])
            lines.append(f"Interests: {interests}")

        if profile["dislikes"]:
            dislikes = ", ".join(profile["dislikes"][:4])
            lines.append(f"Dislikes: {dislikes}")

        if profile["humor_style"]:
            lines.append(f"Humor: {profile['humor_style']}")

        if profile["speech_patterns"]:
            patterns = ", ".join(profile["speech_patterns"][:4])
            lines.append(f"Speech: {patterns}")

        if profile["roast_material"]:
            lines.append(f"Roast material: {len(profile['roast_material'])} items")

        lines.append(f"Messages tracked: {profile['message_count']}")
        lines.append(f"Quotes saved: {len(profile['recent_quotes'])}")

        await update.message.reply_text("\n".join(lines))

    except Exception:
        logger.exception("Error in /profile command")


async def cmd_stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Display group activity leaderboard.

    Usage: /stats
    """
    try:
        profile_manager: ProfileManager = context.bot_data["profile_manager"]
        profiles = profile_manager.get_all_profiles()

        if not profiles:
            await update.message.reply_text("No profiles yet — start chatting!")
            return

        # Sort by message count
        sorted_profiles = sorted(
            profiles.values(),
            key=lambda p: p["message_count"],
            reverse=True,
        )

        lines = ["📊 Group Activity:\n"]
        medals = ["🥇", "🥈", "🥉"]

        for i, profile in enumerate(sorted_profiles[:10], 1):
            medal = medals[i - 1] if i <= 3 else f"{i}."
            lines.append(
                f"{medal} {profile['name']}: {profile['message_count']} messages"
            )

        await update.message.reply_text("\n".join(lines))

    except Exception:
        logger.exception("Error in /stats command")


async def cmd_roast(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Generate a personalized roast for a group member.

    Usage: /roast <name>
    """
    try:
        if not context.args:
            await update.message.reply_text(
                "Who should I roast? Usage: /roast <name>"
            )
            return

        target_name = " ".join(context.args)
        profile_manager: ProfileManager = context.bot_data["profile_manager"]
        tracker: ConversationTracker = context.bot_data["tracker"]

        # Find target profile
        target_profile = profile_manager.find_profile_by_name(target_name)
        if not target_profile:
            await update.message.reply_text(f"Don't know anyone named '{target_name}'")
            return

        # Generate roast
        profiles_summary = profile_manager.get_profiles_summary()
        recent = tracker.get_recent_messages(20)

        response = await generate_response(
            profiles_summary=profiles_summary,
            recent_messages=recent,
            trigger_type="roast",
            target_user=target_profile["name"],
        )

        if response:
            await update.message.reply_text(response)
            await tracker.log_message(
                user_id=0,
                user_name="Bot",
                message_text=response,
                is_bot=True,
            )
        else:
            await update.message.reply_text("Couldn't think of anything. They're too boring.")

    except Exception:
        logger.exception("Error in /roast command")


async def cmd_impersonate(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Generate a message as if written by a specific user.

    Usage: /impersonate <name>
    """
    try:
        if not context.args:
            await update.message.reply_text(
                "Who should I impersonate? Usage: /impersonate <name>"
            )
            return

        target_name = " ".join(context.args)
        profile_manager: ProfileManager = context.bot_data["profile_manager"]
        tracker: ConversationTracker = context.bot_data["tracker"]

        target_profile = profile_manager.find_profile_by_name(target_name)
        if not target_profile:
            await update.message.reply_text(
                f"Don't know '{target_name}' well enough to impersonate them."
            )
            return

        recent = tracker.get_recent_messages(20)
        response = await generate_impersonation(
            profile=target_profile,
            recent_messages=recent,
        )

        if response:
            await update.message.reply_text(f"[{target_profile['name']}]: {response}")
        else:
            await update.message.reply_text("Couldn't channel their energy right now.")

    except Exception:
        logger.exception("Error in /impersonate command")


async def cmd_forget(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Clear conversation history (preserves personality profiles).

    Usage: /forget or /clear
    """
    try:
        if update.message.chat.id != GROUP_CHAT_ID:
            return

        tracker: ConversationTracker = context.bot_data["tracker"]
        await tracker.clear_history()

        await update.message.reply_text(
            "✅ Conversation history cleared.\n"
            "Personality profiles are preserved."
        )
        logger.info("Conversation history cleared by user command")

    except Exception:
        logger.exception("Error in /forget command")


async def cmd_chatid(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Display the current chat ID (useful for initial setup).

    Usage: /chatid
    """
    try:
        chat_id = update.message.chat.id
        chat_type = update.message.chat.type
        chat_title = update.message.chat.title or "Private"

        await update.message.reply_text(
            f"📍 Chat Info:\n"
            f"  ID: {chat_id}\n"
            f"  Type: {chat_type}\n"
            f"  Title: {chat_title}\n\n"
            f"Add this to your .env:\n"
            f"GROUP_CHAT_ID={chat_id}"
        )
    except Exception:
        logger.exception("Error in /chatid command")
