"""Telegram bot entry point."""

import asyncio
import os
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from kharkiv_metro_bot.handlers import (
    register_common_handlers,
    register_route_handlers,
    register_schedule_handlers,
    register_stations_handlers,
)
from kharkiv_metro_bot.handlers.common import set_bot_commands

# Load .env from current working directory
load_dotenv()


def get_token() -> str:
    """Get bot token from environment."""
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN not found in .env file")
    return token


def register_handlers(dp: Dispatcher) -> None:
    """Register all handlers in correct order."""
    # Register specific handlers first (they have state filters)
    register_route_handlers(dp)
    register_schedule_handlers(dp)
    register_stations_handlers(dp)
    # Register common handlers last (includes catch-all)
    register_common_handlers(dp)


async def main() -> None:
    """Run the bot."""
    print("Starting bot...")

    bot = Bot(token=get_token())
    dp = Dispatcher(storage=MemoryStorage())

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
