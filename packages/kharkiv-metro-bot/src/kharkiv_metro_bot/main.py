"""Telegram bot entry point."""

import asyncio
import logging
import os
import sys
from datetime import timedelta

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from kharkiv_metro_bot.handlers import (
    register_admin_handlers,
    register_common_handlers,
    register_route_handlers,
    register_schedule_handlers,
    register_stations_handlers,
)
from kharkiv_metro_bot.handlers.common import set_bot_commands
from kharkiv_metro_bot.handlers.route import restore_pending_reminders
from kharkiv_metro_bot.middleware.i18n_middleware import I18nMiddleware
from kharkiv_metro_bot.user_data import cleanup_expired_reminders, is_user_data_enabled, track_user

from .storage import SqliteStorage

logger = logging.getLogger(__name__)

# Load .env from current working directory
load_dotenv()


# User data middleware
class UserDataMiddleware:
    """Middleware to track user interactions."""

    def __init__(self):
        self.feature_map = {
            "/start": "start",
            "/about": "about",
            "/route": "route",
            "/schedule": "schedule",
            "/stations": "stations",
            "/stats": "admin_stats",
        }

    async def __call__(self, handler, event, data):
        if is_user_data_enabled() and hasattr(event, "from_user") and event.from_user:
            # Determine feature from message text or callback
            feature = "interaction"
            if hasattr(event, "text") and event.text:
                text = event.text.split()[0]  # Get command without args
                feature = self.feature_map.get(text, "message")
            elif hasattr(event, "data") and event.data:
                feature = "callback"

            await track_user(event.from_user.id, feature)

        return await handler(event, data)


def get_token() -> str:
    """Get bot token from environment."""
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN not found in environment")
        raise ValueError("BOT_TOKEN not found in .env file")
    return token


def register_handlers(dp: Dispatcher) -> None:
    """Register all handlers in correct order."""
    # Register admin handlers first
    register_admin_handlers(dp)
    # Register specific handlers (they have state filters)
    register_route_handlers(dp)
    register_schedule_handlers(dp)
    register_stations_handlers(dp)
    # Register common handlers last (includes catch-all)
    register_common_handlers(dp)


async def _cleanup_expired_reminders_task() -> None:
    while True:
        await asyncio.sleep(3600)
        try:
            cleaned = cleanup_expired_reminders()
            if cleaned:
                logger.info("Deactivated %s expired reminders", cleaned)
        except Exception as exc:
            logger.exception("Failed to cleanup reminders: %s", exc)


async def main() -> None:
    """Run the bot."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logger.info("Starting bot...")

    # Show user data status
    if is_user_data_enabled():
        logger.info("User data: Enabled")
    else:
        logger.warning("User data: Disabled")

    bot = Bot(token=get_token())
    storage = SqliteStorage.from_user_data_db()
    removed = storage.cleanup_stale_states(timedelta(hours=12))
    if removed:
        logger.info("Removed %s stale sessions", removed)
    dp = Dispatcher(storage=storage)

    # Add middleware
    dp.message.middleware(I18nMiddleware())
    dp.callback_query.middleware(I18nMiddleware())
    if is_user_data_enabled():
        dp.message.middleware(UserDataMiddleware())
        dp.callback_query.middleware(UserDataMiddleware())

    register_handlers(dp)
    await set_bot_commands(bot)
    await restore_pending_reminders(bot)

    cleanup_task = asyncio.create_task(_cleanup_expired_reminders_task())

    try:
        await dp.start_polling(bot)
    finally:
        cleanup_task.cancel()
        await bot.session.close()


def main_sync() -> None:
    """Synchronous entry point for the bot."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main_sync()
