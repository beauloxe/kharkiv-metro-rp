"""Stations handlers for the Telegram bot."""

from aiogram import Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from kharkiv_metro_core import LINE_DISPLAY_TO_INTERNAL, Language, get_text

from ..keyboards import get_lines_keyboard, get_main_keyboard
from ..states import StationsStates
from ..utils import format_stations_list, get_router, get_stations_by_line


async def cmd_stations(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Handle /stations command."""
    await state.set_state(StationsStates.waiting_for_line)

    # Get valid lines for current language
    from kharkiv_metro_core import get_line_display_name

    valid_lines = [
        get_line_display_name("kholodnohirsko_zavodska", lang),
        get_line_display_name("saltivska", lang),
        get_line_display_name("oleksiivska", lang),
    ]

    msg = await message.answer(
        get_text("select_line", lang),
        reply_markup=get_lines_keyboard(lang),
    )
    await state.update_data(active_message_id=msg.message_id, valid_lines=valid_lines)


async def process_line_selection(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process line selection and show stations."""
    # Convert display name directly to internal using combined mapping
    selected_line = LINE_DISPLAY_TO_INTERNAL.get(message.text)

    if not selected_line:
        await message.answer(
            get_text("error_unknown_line", lang),
            reply_markup=get_lines_keyboard(lang),
        )
        return

    try:
        router = get_router()
        stations = get_stations_by_line(router, selected_line, lang)

        result = format_stations_list(selected_line, stations, lang)
        await message.answer(result, reply_markup=get_main_keyboard(lang))

    except Exception as e:
        await message.answer(
            get_text("error_generic", lang, error=str(e)),
            reply_markup=get_main_keyboard(lang),
        )

    await state.clear()


async def back_from_stations_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from stations line - return to main menu."""
    await state.clear()
    await message.answer(get_text("main_menu", lang), reply_markup=get_main_keyboard(lang))


async def cancel_stations(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Cancel stations lookup."""
    await state.clear()
    await message.answer(
        get_text("stations_cancelled", lang, default="❌ Перегляд станцій скасовано"),
        reply_markup=get_main_keyboard(lang),
    )


def register_stations_handlers(dp: Dispatcher):
    """Register stations handlers."""
    dp.message.register(cmd_stations, Command("stations"))
    dp.message.register(back_from_stations_line, StationsStates.waiting_for_line, F.text == get_text("back", "ua"))
    dp.message.register(back_from_stations_line, StationsStates.waiting_for_line, F.text == get_text("back", "en"))
    dp.message.register(cancel_stations, StationsStates.waiting_for_line, F.text == get_text("cancel", "ua"))
    dp.message.register(cancel_stations, StationsStates.waiting_for_line, F.text == get_text("cancel", "en"))
    dp.message.register(process_line_selection, StationsStates.waiting_for_line)
