"""
Bot application bootstrap and lifecycle management.

Handles Telegram bot initialization, handler registration,
and the main polling loop.
"""

import asyncio
import sys
from typing import Optional

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.request import HTTPXRequest

from doppelganger.config import (
    TELEGRAM_BOT_TOKEN,
    GROUP_CHAT_ID,
    BOT_NAME,
    setup_logging,
    validate_config,
)
from doppelganger.handlers.messages import handle_message
from doppelganger.handlers.commands import (
    cmd_profile,
    cmd_stats,
    cmd_roast,
    cmd_impersonate,
    cmd_forget,
    cmd_chatid,
)
from doppelganger.storage.tracker import ConversationTracker
from doppelganger.profiles.manager import ProfileManager
from doppelganger.scheduler.background import BotScheduler

logger = setup_logging()

# Global state (initialized in post_init)
bot_username: Optional[str] = None
tracker: Optional[ConversationTracker] = None
profile_manager: Optional[ProfileManager] = None


async def post_init(application) -> None:
    """Execute after bot initialization — set up components."""
    global bot_username, tracker, profile_manager

    # Discover bot identity
    bot_info = await application.bot.get_me()
    bot_username = bot_info.username
    logger.info(f"Bot started: @{bot_username} ({BOT_NAME})")
    logger.info(f"Target group: {GROUP_CHAT_ID}")

    # Initialize storage
    tracker = ConversationTracker()
    await tracker.initialize()

    # Initialize profile manager
    profile_manager = ProfileManager()

    # Store shared state in bot_data for handler access
    application.bot_data["tracker"] = tracker
    application.bot_data["profile_manager"] = profile_manager
    application.bot_data["bot_username"] = bot_username

    # Launch background scheduler
    scheduler = BotScheduler(
        bot=application.bot,
        tracker=tracker,
        profile_manager=profile_manager,
    )
    asyncio.create_task(scheduler.run())
    logger.info("Background scheduler started")


def main() -> None:
    """Main entry point — configure and run the bot."""
    # Validate configuration
    errors = validate_config()
    if errors:
        for err in errors:
            logger.error(f"Config error: {err}")
        logger.error("Fix the above errors in your .env file and try again.")
        sys.exit(1)

    logger.info(f"Starting {BOT_NAME}...")

    # Build application with resilient HTTP settings
    request = HTTPXRequest(
        connect_timeout=20.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=10.0,
    )

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .request(request)
        .post_init(post_init)
        .build()
    )

    # Register command handlers
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("roast", cmd_roast))
    app.add_handler(CommandHandler("impersonate", cmd_impersonate))
    app.add_handler(CommandHandler("forget", cmd_forget))
    app.add_handler(CommandHandler("clear", cmd_forget))  # Alias
    app.add_handler(CommandHandler("chatid", cmd_chatid))

    # Register message handler for the target group
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Chat(GROUP_CHAT_ID),
        handle_message,
    ))

    logger.info("Polling for updates...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
