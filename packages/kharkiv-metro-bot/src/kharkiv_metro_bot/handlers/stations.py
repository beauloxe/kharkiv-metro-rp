"""Stations handlers for the Telegram bot."""

from aiogram import Dispatcher, F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from kharkiv_metro_core import (
    Language,
    get_text,
    parse_line_display_name,
)

from ..keyboards import get_lines_keyboard, get_main_keyboard
from ..states import StationsStates
from ..utils import (
    format_stations_list,
    get_back_texts,
    get_cancel_texts,
    get_router,
    get_stations_by_line,
    get_valid_lines,
)

# Create routers for stations handlers
command_router = Router()
router = Router()
router.message.filter(~F.text.startswith("/"))

BACK_TEXTS = get_back_texts()
CANCEL_TEXTS = get_cancel_texts()
BACK_OR_CANCEL_TEXTS = BACK_TEXTS + CANCEL_TEXTS


@command_router.message(Command("stations"), StateFilter("*"))
async def cmd_stations(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Handle /stations command."""
    await state.clear()
    await state.set_state(StationsStates.waiting_for_line)

    valid_lines = get_valid_lines(lang)

    msg = await message.answer(
        get_text("select_line", lang),
        reply_markup=get_lines_keyboard(lang),
    )
    await state.update_data(active_message_id=msg.message_id, valid_lines=valid_lines)


@router.message(StationsStates.waiting_for_line, ~F.text.in_(BACK_OR_CANCEL_TEXTS))
async def process_line_selection(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process line selection and show stations."""
    selected_line = parse_line_display_name(message.text, lang)

    if not selected_line:
        await message.answer(
            get_text("error_unknown_line", lang),
            reply_markup=get_lines_keyboard(lang),
        )
        return

    router = get_router()
    stations = get_stations_by_line(router, selected_line, lang)

    result = format_stations_list(selected_line, stations, lang)
    await message.answer(result, reply_markup=get_main_keyboard(lang))
    await state.clear()


@router.message(StationsStates.waiting_for_line, F.text.in_(BACK_TEXTS))
async def back_from_stations_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from stations line - return to main menu."""
    await state.clear()
    await message.answer(get_text("main_menu", lang), reply_markup=get_main_keyboard(lang))


@router.message(StationsStates.waiting_for_line, F.text.in_(CANCEL_TEXTS))
async def cancel_stations(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Cancel stations lookup."""
    await state.clear()
    await message.answer(
        get_text("stations_cancelled", lang, default="❌ Перегляд станцій скасовано"),
        reply_markup=get_main_keyboard(lang),
    )


def register_stations_handlers(dp: Dispatcher):
    """Register stations handlers."""
    dp.include_router(command_router)
    dp.include_router(router)
