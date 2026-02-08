"""Schedule handlers for the Telegram bot."""

from aiogram import Dispatcher, F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext

from kharkiv_metro_core import (
    DayType,
    Language,
    get_line_display_name,
    get_text,
    parse_day_type_display,
    parse_line_display_name,
)

from ..keyboards import (
    get_day_type_keyboard,
    get_lines_keyboard,
    get_main_keyboard,
    get_stations_keyboard,
)
from ..states import ScheduleStates
from ..utils import (
    format_schedule,
    get_back_texts,
    get_cancel_texts,
    get_current_day_type,
    get_router,
    get_stations_by_line,
    get_valid_lines,
    update_message,
)

# Create routers for schedule handlers
command_router = Router()
router = Router()
router.message.filter(~F.text.startswith("/"))

BACK_TEXTS = get_back_texts()
CANCEL_TEXTS = get_cancel_texts()
BACK_OR_CANCEL_TEXTS = BACK_TEXTS + CANCEL_TEXTS


@command_router.message(Command("schedule"), StateFilter("*"))
async def cmd_schedule(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Handle /schedule command."""
    await state.clear()
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await state.set_state(ScheduleStates.waiting_for_line)

        valid_lines = get_valid_lines(lang)

        msg = await message.answer(
            get_text("select_line", lang),
            reply_markup=get_lines_keyboard(lang),
        )
        await state.update_data(active_message_id=msg.message_id, valid_lines=valid_lines)
        return

    station_name = args[1]

    try:
        router = get_router()
        st = router.find_station_by_name(station_name, lang)
        if not st:
            await message.answer(
                get_text("error_station_not_found", lang, station=station_name),
                reply_markup=get_main_keyboard(lang),
            )
            return

        dt = get_current_day_type()
        schedules = router.get_station_schedule(st.id, None, dt)

        if not schedules:
            await message.answer(
                get_text("schedule_not_found", lang, default="❌ Розклад не знайдено"),
                reply_markup=get_main_keyboard(lang),
            )
            return

        result = format_schedule(getattr(st, f"name_{lang}"), schedules, router, lang)
        await message.answer(result, reply_markup=get_main_keyboard(lang))

    except Exception as e:
        await message.answer(
            get_text("error_generic", lang, error=str(e)),
            reply_markup=get_main_keyboard(lang),
        )

    await state.clear()


@router.message(ScheduleStates.waiting_for_line, ~F.text.in_(BACK_OR_CANCEL_TEXTS))
async def process_schedule_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process line selection for schedule."""
    selected_line = parse_line_display_name(message.text, lang)

    if not selected_line:
        await message.answer(
            get_text("error_unknown_line", lang),
            reply_markup=get_lines_keyboard(lang),
        )
        return

    await state.update_data(schedule_line=selected_line)
    await state.set_state(ScheduleStates.waiting_for_station)

    router = get_router()
    stations = get_stations_by_line(router, selected_line, lang)

    # Store valid stations for validation
    await state.update_data(valid_stations=stations)

    line_display = get_line_display_name(selected_line, lang)

    await update_message(
        message,
        state,
        get_text("select_station_line", lang, line=line_display),
        get_stations_keyboard(stations, lang),
    )


@router.message(ScheduleStates.waiting_for_line, F.text.in_(BACK_TEXTS))
async def back_from_schedule_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from schedule line - return to main menu."""
    await state.clear()
    await message.answer(get_text("main_menu", lang), reply_markup=get_main_keyboard(lang))


@router.message(ScheduleStates.waiting_for_line, F.text.in_(CANCEL_TEXTS))
async def cancel_from_schedule_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Cancel schedule lookup from line."""
    await state.clear()
    await message.answer(
        get_text("schedule_cancelled", lang, default="❌ Перегляд розкладу скасовано"),
        reply_markup=get_main_keyboard(lang),
    )


@router.message(ScheduleStates.waiting_for_station, ~F.text.in_(BACK_OR_CANCEL_TEXTS))
async def process_schedule_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process station selection for schedule."""
    # Validate station selection
    data = await state.get_data()
    valid_stations: list[str] = data.get("valid_stations", [])

    if message.text not in valid_stations:
        await message.answer(
            get_text("error_unknown_choice", lang),
            reply_markup=get_stations_keyboard(valid_stations, lang),
        )
        return

    await state.update_data(schedule_station=message.text)
    await state.set_state(ScheduleStates.waiting_for_day_type)

    valid_day_types = [
        get_text("weekdays", lang),
        get_text("weekends", lang),
    ]

    await state.update_data(valid_day_types=valid_day_types)

    await update_message(
        message,
        state,
        get_text("day_type_prompt", lang),
        get_day_type_keyboard(lang),
    )


@router.message(ScheduleStates.waiting_for_station, F.text.in_(BACK_TEXTS))
async def back_from_schedule_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from schedule station - return to line selection."""
    await state.set_state(ScheduleStates.waiting_for_line)

    await update_message(
        message,
        state,
        get_text("select_line", lang),
        get_lines_keyboard(lang),
    )


@router.message(ScheduleStates.waiting_for_station, F.text.in_(CANCEL_TEXTS))
async def cancel_from_schedule_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Cancel schedule lookup from station."""
    await state.clear()
    await message.answer(
        get_text("schedule_cancelled", lang, default="❌ Перегляд розкладу скасовано"),
        reply_markup=get_main_keyboard(lang),
    )


@router.message(ScheduleStates.waiting_for_day_type, ~F.text.in_(BACK_OR_CANCEL_TEXTS))
async def process_day_type(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process day type selection and show schedule."""
    selected_day = parse_day_type_display(message.text, lang)

    if not selected_day:
        await message.answer(
            get_text("error_unknown_choice", lang),
            reply_markup=get_day_type_keyboard(lang),
        )
        return

    data = await state.get_data()
    station_name = data.get("schedule_station", "")

    try:
        router = get_router()
        st = router.find_station_by_name(station_name, lang)
        if not st:
            await message.answer(
                get_text("error_station_not_found", lang, station=station_name),
                reply_markup=get_main_keyboard(lang),
            )
            await state.clear()
            return

        dt = DayType.WEEKDAY if selected_day == "weekday" else DayType.WEEKEND
        schedules = router.get_station_schedule(st.id, None, dt)

        if not schedules:
            await message.answer(
                get_text("schedule_not_found", lang, default="❌ Розклад не знайдено"),
                reply_markup=get_main_keyboard(lang),
            )
            await state.clear()
            return

        result = format_schedule(getattr(st, f"name_{lang}"), schedules, router, lang)
        await message.answer(result, reply_markup=get_main_keyboard(lang))

    except Exception as e:
        await message.answer(
            get_text("error_generic", lang, error=str(e)),
            reply_markup=get_main_keyboard(lang),
        )

    await state.clear()


@router.message(ScheduleStates.waiting_for_day_type, F.text.in_(BACK_TEXTS))
async def back_from_day_type(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from day type - return to station selection."""
    data = await state.get_data()
    schedule_line = data.get("schedule_line")
    if not schedule_line:
        await state.set_state(ScheduleStates.waiting_for_line)
        await update_message(
            message,
            state,
            get_text("select_line", lang),
            get_lines_keyboard(lang),
        )
        return

    router = get_router()
    stations = get_stations_by_line(router, schedule_line, lang)
    line_display = get_line_display_name(schedule_line, lang)

    await state.set_state(ScheduleStates.waiting_for_station)

    await update_message(
        message,
        state,
        get_text("select_station_line", lang, line=line_display),
        get_stations_keyboard(stations, lang),
    )


@router.message(ScheduleStates.waiting_for_day_type, F.text.in_(CANCEL_TEXTS))
async def cancel_from_day_type(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Cancel schedule lookup from day_type."""
    await state.clear()
    await message.answer(
        get_text("schedule_cancelled", lang, default="❌ Перегляд розкладу скасовано"),
        reply_markup=get_main_keyboard(lang),
    )


def register_schedule_handlers(dp: Dispatcher):
    """Register schedule handlers."""
    dp.include_router(command_router)
    dp.include_router(router)
