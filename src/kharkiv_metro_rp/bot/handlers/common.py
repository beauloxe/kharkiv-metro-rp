"""Common handlers for the Telegram bot (start, menu, catch-all)."""

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand

from ..constants import ButtonText, CommandText
from ..keyboards import get_main_keyboard


async def cmd_start(message: types.Message):
    """Handle /start command."""
    await message.answer(
        "🚇 Бот для планування маршрутів Харківського метро\n\nОберіть дію:",
        reply_markup=get_main_keyboard(),
    )


async def menu_route(message: types.Message, state: FSMContext):
    """Handle route button from menu."""
    from .route import cmd_route

    await cmd_route(message, state)


async def menu_schedule(message: types.Message, state: FSMContext):
    """Handle schedule button from menu."""
    from ..keyboards import get_lines_keyboard
    from ..states import ScheduleStates

    # Start interactive schedule flow directly
    await state.set_state(ScheduleStates.waiting_for_line)
    await message.answer(
        "📅 Оберіть лінію метро:",
        reply_markup=get_lines_keyboard(),
    )


async def menu_stations(message: types.Message, state: FSMContext):
    """Handle stations button from menu."""
    from .stations import cmd_stations

    await cmd_stations(message, state)


async def catch_all_handler(message: types.Message, state: FSMContext):
    """Handle any unhandled messages when NOT in a state - show main menu."""
    # This handler only runs when StateFilter(None) matches (no active state)
    await message.answer(
        "🚇 Бот для планування маршрутів Харківського метро\n\nОберіть дію:",
        reply_markup=get_main_keyboard(),
    )


async def reset_state_handler(message: types.Message, state: FSMContext):
    """Handle any unhandled messages when IN a state - reset to main menu."""
    # This handler runs when user is in some state but message wasn't handled by state handlers
    await state.clear()
    await message.answer(
        "🤖 Сеанс відновлено\n\nСхоже, сесія закінчилась.\nПовертаємось до головного меню:",
        reply_markup=get_main_keyboard(),
    )


async def set_bot_commands(bot: Bot):
    """Set bot commands menu."""
    commands = [
        BotCommand(command="start", description=CommandText.START),
        BotCommand(command="route", description=CommandText.ROUTE),
        BotCommand(command="schedule", description=CommandText.SCHEDULE),
        BotCommand(command="stations", description=CommandText.STATIONS),
    ]
    await bot.set_my_commands(commands)


def register_common_handlers(dp: Dispatcher):
    """Register common handlers."""
    # Command handlers - work in any state
    dp.message.register(cmd_start, Command("start"))

    # Menu button handlers - only work when NOT in any state (main menu)
    dp.message.register(menu_route, StateFilter(None), F.text == ButtonText.ROUTE)
    dp.message.register(menu_schedule, StateFilter(None), F.text == ButtonText.SCHEDULE)
    dp.message.register(menu_stations, StateFilter(None), F.text == ButtonText.STATIONS)

    # Catch-all handler when NOT in a state (for unknown text)
    dp.message.register(catch_all_handler, StateFilter(None))

    # Reset handler when IN any state (catches unhandled messages during workflows)
    # ~StateFilter(None) means "any state except None" = "any active state"
    dp.message.register(reset_state_handler, ~StateFilter(None))
