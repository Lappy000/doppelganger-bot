"""
Telegram Bot handlers and commands for Doppelganger Bot.

Implements all user-facing commands and the silent message learning pipeline.
"""

import logging
from datetime import datetime
from typing import Optional

from telegram import Update, User
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import AppConfig
from .generator import ResponseGenerator
from .personality import PersonalityEngine
from .storage import ProfileStorage

logger = logging.getLogger(__name__)


class DoppelgangerBot:
    """Main bot class that ties everything together."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.storage = ProfileStorage(config.bot.data_dir)
        self.personality_engine = PersonalityEngine(self.storage, config.bot)
        self.generator = ResponseGenerator(config.llm, self.personality_engine)
        self._opted_out: set[int] = set()
        self._app: Optional[Application] = None

    def run(self) -> None:
        """Start the bot."""
        errors = self.config.validate()
        if errors:
            for err in errors:
                logger.error(f"Config error: {err}")
            raise SystemExit(1)

        self._app = (
            Application.builder()
            .token(self.config.bot.telegram_token)
            .build()
        )

        # Register handlers
        self._register_handlers(self._app)

        logger.info("🎭 Doppelganger Bot starting...")
        self._app.run_polling(allowed_updates=Update.ALL_TYPES)

    def _register_handlers(self, app: Application) -> None:
        """Register all command and message handlers."""
        # Commands
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("help", self._cmd_help))
        app.add_handler(CommandHandler("profile", self._cmd_profile))
        app.add_handler(CommandHandler("impersonate", self._cmd_impersonate))
        app.add_handler(CommandHandler("roast", self._cmd_roast))
        app.add_handler(CommandHandler("stats", self._cmd_stats))
        app.add_handler(CommandHandler("optout", self._cmd_optout))
        app.add_handler(CommandHandler("optin", self._cmd_optin))
        app.add_handler(CommandHandler("forget", self._cmd_forget))

        # Silent message learning (must be last - catches all text messages)
        app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
                self._handle_message,
            )
        )

    # =========================================================================
    # COMMAND HANDLERS
    # =========================================================================

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        await update.message.reply_text(
            "🎭 *Doppelganger Bot*\n\n"
            "I silently learn everyone's writing style in this group. "
            "Once I've seen enough messages, I can impersonate anyone or roast them in their own style!\n\n"
            "Commands:\n"
            "• /profile @user — See learned personality traits\n"
            "• /impersonate @user [topic] — Generate a message as them\n"
            "• /roast @user — Roast them in their own style\n"
            "• /stats — Group statistics\n"
            "• /optout — Stop learning from your messages\n"
            "• /forget — Delete all your data\n\n"
            "⚠️ I never store messages — only extracted style features.",
            parse_mode="Markdown",
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        await update.message.reply_text(
            "🎭 *Doppelganger Bot Commands*\n\n"
            "*/profile* `@username`\n"
            "  Show the learned personality profile of a user\n\n"
            "*/impersonate* `@username` `[topic]`\n"
            "  Generate a message mimicking that user's style\n"
            "  Optional: add a topic for them to talk about\n\n"
            "*/roast* `@username`\n"
            "  Generate a roast written in their own style\n\n"
            "*/stats*\n"
            "  Show group learning statistics\n\n"
            "*/optout*\n"
            "  Stop the bot from learning your writing style\n\n"
            "*/optin*\n"
            "  Resume learning (if previously opted out)\n\n"
            "*/forget*\n"
            "  Permanently delete all your personality data\n\n"
            "_Privacy: No messages are stored. Only statistical features "
            "(word frequencies, emoji patterns, etc.) are kept._",
            parse_mode="Markdown",
        )

    async def _cmd_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /profile command - show a user's learned personality."""
        chat_id = update.effective_chat.id
        target_user = self._resolve_target_user(update, context)

        if target_user is None:
            await update.message.reply_text(
                "Usage: /profile @username\n"
                "Or reply to someone's message with /profile"
            )
            return

        # Force flush any buffered data
        self.personality_engine.force_flush(
            target_user.id, chat_id, target_user.username or "", target_user.full_name
        )

        profile = self.storage.load_profile(target_user.id, chat_id)
        if profile is None or profile.total_messages_analyzed < 5:
            await update.message.reply_text(
                f"🤷 I don't have enough data on {target_user.full_name} yet. "
                f"I need at least {self.config.bot.min_messages_for_profile} messages to build a profile."
            )
            return

        summary = profile.get_summary()
        await update.message.reply_text(summary)

    async def _cmd_impersonate(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /impersonate command - generate a message as another user."""
        chat_id = update.effective_chat.id
        target_user = self._resolve_target_user(update, context)

        if target_user is None:
            await update.message.reply_text(
                "Usage: /impersonate @username [topic]\n"
                "Example: /impersonate @john what he thinks about pineapple on pizza"
            )
            return

        # Extract topic from remaining args
        topic = None
        if context.args and len(context.args) > 1:
            # First arg is the username, rest is the topic
            topic = " ".join(context.args[1:])

        # Check if profile has enough data
        profile = self.storage.load_profile(target_user.id, chat_id)
        if profile is None or profile.total_messages_analyzed < self.config.bot.min_messages_for_profile:
            await update.message.reply_text(
                f"🤷 Not enough data on {target_user.full_name} yet. "
                f"Need {self.config.bot.min_messages_for_profile} messages, "
                f"have {profile.total_messages_analyzed if profile else 0}."
            )
            return

        # Send typing indicator
        await update.effective_chat.send_action("typing")

        # Generate impersonation
        response = await self.generator.generate_impersonation(
            target_user.id, chat_id, topic=topic
        )

        if response:
            await update.message.reply_text(
                f"🎭 *{target_user.full_name} would say:*\n\n{response}",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text("😵 Failed to generate impersonation. Try again later.")

    async def _cmd_roast(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /roast command - roast a user in their own style."""
        chat_id = update.effective_chat.id
        target_user = self._resolve_target_user(update, context)

        if target_user is None:
            await update.message.reply_text(
                "Usage: /roast @username\nOr reply to someone's message with /roast"
            )
            return

        profile = self.storage.load_profile(target_user.id, chat_id)
        if profile is None or profile.total_messages_analyzed < self.config.bot.min_messages_for_profile:
            await update.message.reply_text(
                f"🤷 Need more data on {target_user.full_name} to roast them properly. "
                f"({profile.total_messages_analyzed if profile else 0}/{self.config.bot.min_messages_for_profile} messages)"
            )
            return

        await update.effective_chat.send_action("typing")

        response = await self.generator.generate_roast(target_user.id, chat_id)
        if response:
            await update.message.reply_text(
                f"🔥 *Self-roast by {target_user.full_name}:*\n\n{response}",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text("😵 Roast generation failed. The heat was too much.")

    async def _cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stats command - show group statistics."""
        chat_id = update.effective_chat.id
        stats = self.storage.get_chat_stats(chat_id)

        if stats["total_users"] == 0:
            await update.message.reply_text("📊 No data collected yet. I'm still learning!")
            return

        lines = [
            "📊 *Group Statistics*\n",
            f"👥 Profiles built: {stats['total_users']}",
            f"💬 Total messages analyzed: {stats['total_messages']}",
            "",
            "🏆 *Most Active (by messages learned):*",
        ]

        for i, (name, count) in enumerate(stats.get("top_users", [])[:5], 1):
            medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i - 1]
            lines.append(f"  {medal} {name}: {count} msgs")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def _cmd_optout(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /optout command - stop learning from a user."""
        user_id = update.effective_user.id
        self._opted_out.add(user_id)
        await update.message.reply_text(
            "✅ Opted out. I will no longer learn from your messages.\n"
            "Your existing profile data is preserved. Use /forget to delete it."
        )

    async def _cmd_optin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /optin command - resume learning."""
        user_id = update.effective_user.id
        self._opted_out.discard(user_id)
        await update.message.reply_text("✅ Opted back in. I'll continue learning your style.")

    async def _cmd_forget(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /forget command - delete all user data."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        deleted = self.storage.delete_profile(user_id, chat_id)
        self._opted_out.add(user_id)  # Also opt them out

        if deleted:
            await update.message.reply_text(
                "🗑️ All your personality data for this chat has been deleted.\n"
                "You've also been opted out. Use /optin to allow learning again."
            )
        else:
            await update.message.reply_text("ℹ️ No data found to delete. You've been opted out.")

    # =========================================================================
    # MESSAGE LEARNING
    # =========================================================================

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Silently process all group messages for learning."""
        if not update.message or not update.message.text:
            return

        user = update.effective_user
        if not user or user.is_bot:
            return

        # Respect opt-outs
        if user.id in self._opted_out:
            return

        text = update.message.text
        chat_id = update.effective_chat.id
        is_reply = update.message.reply_to_message is not None
        timestamp = update.message.date or datetime.now()

        # Process the message (non-blocking personality update)
        self.personality_engine.process_message(
            text=text,
            user_id=user.id,
            chat_id=chat_id,
            username=user.username or "",
            display_name=user.full_name,
            timestamp=timestamp,
            is_reply=is_reply,
        )

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def _resolve_target_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[User]:
        """Resolve the target user from a command (by @mention or reply)."""
        # Check if replying to a message
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            return update.message.reply_to_message.from_user

        # Check for @username in args
        if context.args:
            # The entities in the message might contain the user
            if update.message.entities:
                for entity in update.message.entities:
                    if entity.type == "text_mention" and entity.user:
                        return entity.user
                    if entity.type == "mention":
                        # We have a @username but need to find the user object
                        # Unfortunately, Telegram doesn't give us the full User object from @mentions
                        # We'll look for them in our stored profiles
                        username = context.args[0].lstrip("@")
                        return self._find_user_by_username(username, update.effective_chat.id)

            # Try first arg as username
            if context.args[0].startswith("@"):
                username = context.args[0].lstrip("@")
                return self._find_user_by_username(username, update.effective_chat.id)

        return None

    def _find_user_by_username(self, username: str, chat_id: int) -> Optional[User]:
        """Find a user by username from stored profiles."""
        profiles = self.storage.list_profiles(chat_id)
        for profile in profiles:
            if profile.username.lower() == username.lower():
                # Create a minimal User object for our purposes
                return _create_pseudo_user(profile.user_id, profile.username, profile.display_name)
        return None


class _PseudoUser:
    """Minimal user object for when we only have profile data."""

    def __init__(self, user_id: int, username: str, full_name: str):
        self.id = user_id
        self.username = username
        self.full_name = full_name
        self.is_bot = False


def _create_pseudo_user(user_id: int, username: str, display_name: str):
    """Create a pseudo user object from stored profile data."""
    return _PseudoUser(user_id, username, display_name)


def main():
    """Entry point for the bot."""
    import sys
    from dotenv import load_dotenv

    load_dotenv()

    # Configure logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )

    config = AppConfig.from_env()
    errors = config.validate()
    if errors:
        for err in errors:
            print(f"❌ {err}", file=sys.stderr)
        print("\nCopy .env.example to .env and fill in your tokens.", file=sys.stderr)
        sys.exit(1)

    bot = DoppelgangerBot(config)
    bot.run()


if __name__ == "__main__":
    main()
