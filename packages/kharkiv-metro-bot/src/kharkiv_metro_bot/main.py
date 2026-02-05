"""Telegram bot entry point."""

import asyncio
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from kharkiv_metro_bot.analytics import is_analytics_enabled, track_user
from kharkiv_metro_bot.handlers import (
    register_admin_handlers,
    register_common_handlers,
    register_route_handlers,
    register_schedule_handlers,
    register_stations_handlers,
)
from kharkiv_metro_bot.handlers.common import set_bot_commands
from kharkiv_metro_bot.middleware.i18n_middleware import I18nMiddleware

# Load .env from current working directory
load_dotenv()


# Analytics middleware
class AnalyticsMiddleware:
    """Middleware to track all user interactions."""

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
        if is_analytics_enabled() and hasattr(event, "from_user") and event.from_user:
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

    # Show analytics status
    if is_analytics_enabled():
        print("Analytics: Enabled")
    else:
        print("Analytics: Disabled")

    bot = Bot(token=get_token())
    dp = Dispatcher(storage=MemoryStorage())

    # Add middleware
    dp.message.middleware(I18nMiddleware())
    dp.callback_query.middleware(I18nMiddleware())
    if is_analytics_enabled():
        dp.message.middleware(AnalyticsMiddleware())
        dp.callback_query.middleware(AnalyticsMiddleware())

    register_handlers(dp)
    await set_bot_commands(bot)

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
