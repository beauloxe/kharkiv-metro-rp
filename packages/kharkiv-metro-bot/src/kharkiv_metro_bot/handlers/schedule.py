"""Schedule handlers for the Telegram bot."""

from aiogram import Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from kharkiv_metro_core import DAY_TYPE_DISPLAY_TO_INTERNAL, LINE_DISPLAY_TO_INTERNAL, DayType, Language, get_text

from ..constants import LINE_INTERNAL_TO_DISPLAY
from ..keyboards import (
    get_day_type_keyboard,
    get_lines_keyboard,
    get_main_keyboard,
    get_stations_keyboard,
)
from ..states import ScheduleStates
from ..utils import (
    format_schedule,
    get_current_day_type,
    get_router,
    get_stations_by_line,
)


async def cmd_schedule(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Handle /schedule command."""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await state.set_state(ScheduleStates.waiting_for_line)

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

        result = format_schedule(st.name_ua if lang == "ua" else st.name_en, schedules, router, lang)
        await message.answer(result, reply_markup=get_main_keyboard(lang))

    except Exception as e:
        await message.answer(
            get_text("error_generic", lang, error=str(e)),
            reply_markup=get_main_keyboard(lang),
        )


async def process_schedule_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process line selection for schedule."""
    # Convert display name directly to internal using combined mapping
    selected_line = LINE_DISPLAY_TO_INTERNAL.get(message.text)

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

    data = await state.get_data()
    active_msg_id = data.get("active_message_id")

    if active_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=active_msg_id,
                text=get_text("select_station_line", lang, line=message.text),
                reply_markup=get_stations_keyboard(stations, lang),
            )
        except Exception:
            msg = await message.answer(
                get_text("select_station_line", lang, line=message.text),
                reply_markup=get_stations_keyboard(stations, lang),
            )
            await state.update_data(active_message_id=msg.message_id)
    else:
        msg = await message.answer(
            get_text("select_station_line", lang, line=message.text),
            reply_markup=get_stations_keyboard(stations, lang),
        )
        await state.update_data(active_message_id=msg.message_id)


async def back_from_schedule_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from schedule line - return to main menu."""
    await state.clear()
    await message.answer(get_text("main_menu", lang), reply_markup=get_main_keyboard(lang))


async def cancel_from_schedule_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Cancel schedule lookup from line."""
    await state.clear()
    await message.answer(
        get_text("schedule_cancelled", lang, default="❌ Перегляд розкладу скасовано"),
        reply_markup=get_main_keyboard(lang),
    )


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

    # Store valid day types for validation
    valid_day_types = [
        get_text("weekdays", lang),
        get_text("weekends", lang),
    ]

    data = await state.get_data()
    active_msg_id = data.get("active_message_id")

    if active_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=active_msg_id,
                text=get_text("day_type_prompt", lang),
                reply_markup=get_day_type_keyboard(lang),
            )
            await state.update_data(valid_day_types=valid_day_types)
        except Exception:
            msg = await message.answer(
                get_text("day_type_prompt", lang),
                reply_markup=get_day_type_keyboard(lang),
            )
            await state.update_data(active_message_id=msg.message_id, valid_day_types=valid_day_types)
    else:
        msg = await message.answer(
            get_text("day_type_prompt", lang),
            reply_markup=get_day_type_keyboard(lang),
        )
        await state.update_data(active_message_id=msg.message_id, valid_day_types=valid_day_types)


async def back_from_schedule_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from schedule station - return to line selection."""
    await state.set_state(ScheduleStates.waiting_for_line)

    data = await state.get_data()
    schedule_line = data.get("schedule_line", "Холодногірсько-заводська" if lang == "ua" else "Kholodnohirsko-Zavodska")
    active_msg_id = data.get("active_message_id")

    router = get_router()
    stations = get_stations_by_line(router, schedule_line, lang)

    if active_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=active_msg_id,
                text=get_text(
                    "select_station_line", lang, line=LINE_INTERNAL_TO_DISPLAY.get(schedule_line, schedule_line)
                ),
                reply_markup=get_stations_keyboard(stations, lang),
            )
        except Exception:
            msg = await message.answer(
                get_text("select_station_line", lang, line=LINE_INTERNAL_TO_DISPLAY.get(schedule_line, schedule_line)),
                reply_markup=get_stations_keyboard(stations, lang),
            )
            await state.update_data(active_message_id=msg.message_id)
    else:
        msg = await message.answer(
            get_text("select_station_line", lang, line=LINE_INTERNAL_TO_DISPLAY.get(schedule_line, schedule_line)),
            reply_markup=get_stations_keyboard(stations, lang),
        )
        await state.update_data(active_message_id=msg.message_id)


async def cancel_from_schedule_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Cancel schedule lookup from station."""
    await state.clear()
    await message.answer(
        get_text("schedule_cancelled", lang, default="❌ Перегляд розкладу скасовано"),
        reply_markup=get_main_keyboard(lang),
    )


async def process_day_type(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process day type selection and show schedule."""
    # Convert display name directly to internal using combined mapping
    selected_day = DAY_TYPE_DISPLAY_TO_INTERNAL.get(message.text)

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

        result = format_schedule(st.name_ua if lang == "ua" else st.name_en, schedules, router, lang)
        await message.answer(result, reply_markup=get_main_keyboard(lang))

    except Exception as e:
        await message.answer(
            get_text("error_generic", lang, error=str(e)),
            reply_markup=get_main_keyboard(lang),
        )

    await state.clear()


async def back_from_day_type(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from day type - return to station selection."""
    data = await state.get_data()
    schedule_line = data.get("schedule_line", "Холодногірсько-заводська" if lang == "ua" else "Kholodnohirsko-Zavodska")
    active_msg_id = data.get("active_message_id")

    router = get_router()
    stations = get_stations_by_line(router, schedule_line, lang)

    await state.set_state(ScheduleStates.waiting_for_station)

    if active_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=active_msg_id,
                text=get_text(
                    "select_station_line", lang, line=LINE_INTERNAL_TO_DISPLAY.get(schedule_line, schedule_line)
                ),
                reply_markup=get_stations_keyboard(stations, lang),
            )
        except Exception:
            msg = await message.answer(
                get_text("select_station_line", lang, line=LINE_INTERNAL_TO_DISPLAY.get(schedule_line, schedule_line)),
                reply_markup=get_stations_keyboard(stations, lang),
            )
            await state.update_data(active_message_id=msg.message_id)
    else:
        msg = await message.answer(
            get_text("select_station_line", lang, line=LINE_INTERNAL_TO_DISPLAY.get(schedule_line, schedule_line)),
            reply_markup=get_stations_keyboard(stations, lang),
        )
        await state.update_data(active_message_id=msg.message_id)


async def cancel_from_day_type(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Cancel schedule lookup from day_type."""
    await state.clear()
    await message.answer(
        get_text("schedule_cancelled", lang, default="❌ Перегляд розкладу скасовано"),
        reply_markup=get_main_keyboard(lang),
    )


def register_schedule_handlers(dp: Dispatcher):
    """Register schedule handlers."""
    # Command handlers
    dp.message.register(cmd_schedule, Command("schedule"))

    # Line selection state handlers
    dp.message.register(back_from_schedule_line, ScheduleStates.waiting_for_line, F.text == get_text("back", "ua"))
    dp.message.register(back_from_schedule_line, ScheduleStates.waiting_for_line, F.text == get_text("back", "en"))
    dp.message.register(cancel_from_schedule_line, ScheduleStates.waiting_for_line, F.text == get_text("cancel", "ua"))
    dp.message.register(cancel_from_schedule_line, ScheduleStates.waiting_for_line, F.text == get_text("cancel", "en"))
    dp.message.register(process_schedule_line, ScheduleStates.waiting_for_line)

    # Station selection state handlers
    dp.message.register(
        back_from_schedule_station, ScheduleStates.waiting_for_station, F.text == get_text("back", "ua")
    )
    dp.message.register(
        back_from_schedule_station, ScheduleStates.waiting_for_station, F.text == get_text("back", "en")
    )
    dp.message.register(
        cancel_from_schedule_station, ScheduleStates.waiting_for_station, F.text == get_text("cancel", "ua")
    )
    dp.message.register(
        cancel_from_schedule_station, ScheduleStates.waiting_for_station, F.text == get_text("cancel", "en")
    )
    dp.message.register(process_schedule_station, ScheduleStates.waiting_for_station)

    # Day type selection state handlers
    dp.message.register(back_from_day_type, ScheduleStates.waiting_for_day_type, F.text == get_text("back", "ua"))
    dp.message.register(back_from_day_type, ScheduleStates.waiting_for_day_type, F.text == get_text("back", "en"))
    dp.message.register(cancel_from_day_type, ScheduleStates.waiting_for_day_type, F.text == get_text("cancel", "ua"))
    dp.message.register(cancel_from_day_type, ScheduleStates.waiting_for_day_type, F.text == get_text("cancel", "en"))
    dp.message.register(process_day_type, ScheduleStates.waiting_for_day_type)
