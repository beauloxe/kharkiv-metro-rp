"""Telegram bot entry point."""

import asyncio
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
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
from kharkiv_metro_bot.user_data import is_user_data_enabled, track_user

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


async def main() -> None:
    """Run the bot."""
    print("Starting bot...")

    # Show user data status
    if is_user_data_enabled():
        print("User data: Enabled")
    else:
        print("User data: Disabled")

    bot = Bot(token=get_token())
    dp = Dispatcher(storage=MemoryStorage())

    # Add middleware
    dp.message.middleware(I18nMiddleware())
    dp.callback_query.middleware(I18nMiddleware())
    if is_user_data_enabled():
        dp.message.middleware(UserDataMiddleware())
        dp.callback_query.middleware(UserDataMiddleware())

    register_handlers(dp)
    await set_bot_commands(bot)
    await restore_pending_reminders(bot)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


def main_sync() -> None:
    """Synchronous entry point for the bot."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main_sync()
