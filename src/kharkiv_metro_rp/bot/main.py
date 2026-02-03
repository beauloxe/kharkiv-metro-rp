"""Telegram bot entry point."""

import asyncio
import os
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kharkiv_metro_rp.bot.handlers import (
    register_common_handlers,
    register_route_handlers,
    register_schedule_handlers,
    register_stations_handlers,
)
from kharkiv_metro_rp.bot.handlers.common import set_bot_commands

# Load .env from project root
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN not found in .env file")

# Initialize bot and dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def register_handlers():
    """Register all handlers."""
    # Register specific handlers first (they have state filters)
    register_route_handlers(dp)
    register_schedule_handlers(dp)
    register_stations_handlers(dp)
    # Register common handlers last (includes catch-all)
    register_common_handlers(dp)


def main():
    """Run the bot."""
    print("Starting bot...")

    async def on_startup():
        register_handlers()
        await set_bot_commands(bot)
        await dp.start_polling(bot)

    asyncio.run(on_startup())


if __name__ == "__main__":
    main()
