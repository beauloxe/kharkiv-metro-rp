"""Stations handlers for the Telegram bot."""

from aiogram import Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from ..constants import LINE_DISPLAY_TO_INTERNAL, ButtonText
from ..keyboards import get_lines_keyboard, get_main_keyboard
from ..states import StationsStates
from ..utils import format_stations_list, get_router, get_stations_by_line


async def cmd_stations(message: types.Message, state: FSMContext):
    """Handle /stations command."""
    await state.set_state(StationsStates.waiting_for_line)
    await message.answer(
        "📋 Оберіть лінію метро:",
        reply_markup=get_lines_keyboard(),
    )


async def process_line_selection(message: types.Message, state: FSMContext):
    """Process line selection and show stations."""
    selected_line = LINE_DISPLAY_TO_INTERNAL.get(message.text)
    if not selected_line:
        await message.answer(
            "❌ Невідома лінія. Оберіть з клавіатури.",
            reply_markup=get_lines_keyboard(),
        )
        return

    try:
        router = get_router()
        stations = get_stations_by_line(router, selected_line)

        result = format_stations_list(selected_line, stations)
        await message.answer(result, reply_markup=get_main_keyboard())

    except Exception as e:
        await message.answer(f"❌ Помилка: {e}", reply_markup=get_main_keyboard())

    await state.clear()


async def back_from_stations_line(message: types.Message, state: FSMContext):
    """Go back from stations line - return to main menu."""
    await state.clear()
    await message.answer("🏠 Головне меню", reply_markup=get_main_keyboard())


async def cancel_stations(message: types.Message, state: FSMContext):
    """Cancel stations lookup."""
    await state.clear()
    await message.answer("❌ Перегляд станцій скасовано", reply_markup=get_main_keyboard())


def register_stations_handlers(dp: Dispatcher):
    """Register stations handlers."""
    # Command handlers
    dp.message.register(cmd_stations, Command("stations"))

    # State handlers
    dp.message.register(back_from_stations_line, StationsStates.waiting_for_line, F.text == ButtonText.BACK)
    dp.message.register(cancel_stations, StationsStates.waiting_for_line, F.text == ButtonText.CANCEL)
    dp.message.register(process_line_selection, StationsStates.waiting_for_line)
