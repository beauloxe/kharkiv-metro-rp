"""Route handlers for the Telegram bot."""

import asyncio
import re
from datetime import datetime

from aiogram import Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from kharkiv_metro_core import DayType, MetroClosedError

from ..constants import LINE_INTERNAL_TO_DISPLAY
from ..i18n import Language, get_text, LINE_DISPLAY_TO_INTERNAL, DAY_TYPE_DISPLAY_TO_INTERNAL
from ..keyboards import (
    build_reminder_keyboard,
    get_day_type_keyboard,
    get_lines_keyboard,
    get_main_keyboard,
    get_stations_keyboard,
    get_time_choice_keyboard,
)
from ..states import RouteStates
from ..utils import (
    build_line_groups,
    format_route,
    generate_route_key,
    get_router,
    get_stations_by_line,
    get_stations_by_line_except,
    now,
)

# Store pending reminders for callback reminder system
pending_reminders: dict[int, dict] = {}

# Store active routes for reminder callback lookup (callback_data limited to 64 bytes)
_active_routes: dict[str, tuple] = {}


async def cmd_route(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Start route conversation."""
    await state.set_state(RouteStates.waiting_for_from_line)
    
    # Get valid lines for current language
    from ..i18n import get_line_display_name
    valid_lines = [
        get_line_display_name("kholodnohirsko_zavodska", lang),
        get_line_display_name("saltivska", lang),
        get_line_display_name("oleksiivska", lang),
    ]
    
    msg = await message.answer(
        get_text("from_station_prompt", lang),
        reply_markup=get_lines_keyboard(lang),
    )
    await state.update_data(active_message_id=msg.message_id, valid_lines=valid_lines)


# ===== From Line Handlers =====


async def process_from_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process line selection for 'from' station."""
    # Convert display name directly to internal using combined mapping
    selected_line = LINE_DISPLAY_TO_INTERNAL.get(message.text)
    
    if not selected_line:
        await message.answer(
            get_text("error_unknown_line", lang),
            reply_markup=get_lines_keyboard(lang),
        )
        return

    await state.update_data(from_line=selected_line)
    await state.set_state(RouteStates.waiting_for_from_station)

    router = get_router()
    stations = get_stations_by_line(router, selected_line, lang)
    
    # Store valid stations for next step
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
            # If edit fails, send new message
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


async def back_from_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from from_line - return to main menu."""
    await state.clear()
    await message.answer(get_text("main_menu", lang), reply_markup=get_main_keyboard(lang))


async def cancel_from_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Cancel route building from from_line."""
    await state.clear()
    await message.answer(get_text("error_cancelled", lang), reply_markup=get_main_keyboard(lang))


# ===== From Station Handlers =====


async def process_from_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process from station - now ask for to_line."""
    # Validate station selection
    data = await state.get_data()
    valid_stations: list[str] = data.get("valid_stations", [])
    
    if message.text not in valid_stations:
        await message.answer(
            get_text("error_unknown_choice", lang),
            reply_markup=get_stations_keyboard(valid_stations, lang),
        )
        return
    
    await state.update_data(from_station=message.text)
    await state.set_state(RouteStates.waiting_for_to_line)
    
    # Re-use valid_lines from before (lines are same)
    valid_lines = data.get("valid_lines", [])
    active_msg_id = data.get("active_message_id")
    
    if active_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=active_msg_id,
                text=get_text("to_station_prompt", lang),
                reply_markup=get_lines_keyboard(lang),
            )
        except Exception:
            msg = await message.answer(
                get_text("to_station_prompt", lang),
                reply_markup=get_lines_keyboard(lang),
            )
            await state.update_data(active_message_id=msg.message_id)
    else:
        msg = await message.answer(
            get_text("to_station_prompt", lang),
            reply_markup=get_lines_keyboard(lang),
        )
        await state.update_data(active_message_id=msg.message_id)


async def back_from_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from from_station - return to from_line selection."""
    await state.set_state(RouteStates.waiting_for_from_line)
    
    data = await state.get_data()
    from_line = data.get("from_line")
    active_msg_id = data.get("active_message_id")
    
    router = get_router()
    stations = get_stations_by_line(router, from_line, lang)
    
    if active_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=active_msg_id,
                text=get_text("from_station_prompt", lang),
                reply_markup=get_stations_keyboard(stations, lang),
            )
        except Exception:
            msg = await message.answer(
                get_text("from_station_prompt", lang),
                reply_markup=get_stations_keyboard(stations, lang),
            )
            await state.update_data(active_message_id=msg.message_id)
    else:
        msg = await message.answer(
            get_text("from_station_prompt", lang),
            reply_markup=get_stations_keyboard(stations, lang),
        )
        await state.update_data(active_message_id=msg.message_id)


async def cancel_from_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Cancel route building from from_station."""
    await state.clear()
    await message.answer(get_text("error_cancelled", lang), reply_markup=get_main_keyboard(lang))


# ===== To Line Handlers =====


async def process_to_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process line selection for 'to' station."""
    # Get valid lines from state
    data = await state.get_data()
    valid_lines: list[str] = data.get("valid_lines", [])
    
    if message.text not in valid_lines:
        await message.answer(
            get_text("error_unknown_line", lang),
            reply_markup=get_lines_keyboard(lang),
        )
        return

    # Find internal line name by display name
    selected_line = LINE_DISPLAY_TO_INTERNAL.get(message.text)
    if not selected_line:
        await message.answer(
            get_text("error_unknown_line", lang),
            reply_markup=get_lines_keyboard(lang),
        )
        return

    await state.update_data(to_line=selected_line)
    await state.set_state(RouteStates.waiting_for_to_station)

    # Get stations on this line, excluding from_station
    data = await state.get_data()
    from_station = data.get("from_station", "")
    active_msg_id = data.get("active_message_id")

    router = get_router()
    stations = get_stations_by_line_except(router, selected_line, from_station, lang)
    
    # Store valid stations for next step
    await state.update_data(valid_stations=stations)

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


async def back_to_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from to_line - return to from_station selection."""
    data = await state.get_data()
    from_line = data.get("from_line", "Холодногірсько-заводська" if lang == "ua" else "Kholodnohirsko-Zavodska")
    active_msg_id = data.get("active_message_id")

    router = get_router()
    stations = get_stations_by_line(router, from_line, lang)

    await state.set_state(RouteStates.waiting_for_from_station)

    if active_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=active_msg_id,
                text=get_text("select_station_line", lang, line=LINE_INTERNAL_TO_DISPLAY.get(from_line, from_line)),
                reply_markup=get_stations_keyboard(stations, lang),
            )
        except Exception:
            msg = await message.answer(
                get_text("select_station_line", lang, line=LINE_INTERNAL_TO_DISPLAY.get(from_line, from_line)),
                reply_markup=get_stations_keyboard(stations, lang),
            )
            await state.update_data(active_message_id=msg.message_id)
    else:
        msg = await message.answer(
            get_text("select_station_line", lang, line=LINE_INTERNAL_TO_DISPLAY.get(from_line, from_line)),
            reply_markup=get_stations_keyboard(stations, lang),
        )
        await state.update_data(active_message_id=msg.message_id)


async def cancel_to_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Cancel route building from to_line."""
    await state.clear()
    await message.answer(get_text("error_cancelled", lang), reply_markup=get_main_keyboard(lang))


# ===== To Station Handlers =====


async def process_to_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process to station and ask for time choice."""
    await state.update_data(to_station=message.text)
    await state.set_state(RouteStates.waiting_for_time_choice)
    
    data = await state.get_data()
    active_msg_id = data.get("active_message_id")
    
    if active_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=active_msg_id,
                text=get_text("time_prompt", lang),
                reply_markup=get_time_choice_keyboard(lang),
            )
        except Exception:
            msg = await message.answer(
                get_text("time_prompt", lang),
                reply_markup=get_time_choice_keyboard(lang),
            )
            await state.update_data(active_message_id=msg.message_id)
    else:
        msg = await message.answer(
            get_text("time_prompt", lang),
            reply_markup=get_time_choice_keyboard(lang),
        )
        await state.update_data(active_message_id=msg.message_id)


async def back_to_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from to_station - return to to_line selection."""
    await state.set_state(RouteStates.waiting_for_to_line)
    
    data = await state.get_data()
    to_line = data.get("to_line", "Холодногірсько-заводська" if lang == "ua" else "Kholodnohirsko-Zavodska")
    from_station = data.get("from_station", "")
    active_msg_id = data.get("active_message_id")

    router = get_router()
    stations = get_stations_by_line_except(router, to_line, from_station, lang)

    if active_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=active_msg_id,
                text=get_text("select_station_line", lang, line=LINE_INTERNAL_TO_DISPLAY.get(to_line, to_line)),
                reply_markup=get_stations_keyboard(stations, lang),
            )
        except Exception:
            msg = await message.answer(
                get_text("select_station_line", lang, line=LINE_INTERNAL_TO_DISPLAY.get(to_line, to_line)),
                reply_markup=get_stations_keyboard(stations, lang),
            )
            await state.update_data(active_message_id=msg.message_id)
    else:
        msg = await message.answer(
            get_text("select_station_line", lang, line=LINE_INTERNAL_TO_DISPLAY.get(to_line, to_line)),
            reply_markup=get_stations_keyboard(stations, lang),
        )
        await state.update_data(active_message_id=msg.message_id)


async def cancel_to_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Cancel route building from to_station."""
    await state.clear()
    await message.answer(get_text("error_cancelled", lang), reply_markup=get_main_keyboard(lang))


# ===== Time Choice Handlers =====


async def process_time_choice(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process time choice selection."""
    if message.text == get_text("current_time", lang):
        # Use current time and day type
        await process_current_time(message, state, lang)
    elif message.text == get_text("time_minus_20", lang):
        await process_offset_time(message, state, -20, lang)
    elif message.text == get_text("time_minus_10", lang):
        await process_offset_time(message, state, -10, lang)
    elif message.text == get_text("time_plus_10", lang):
        await process_offset_time(message, state, 10, lang)
    elif message.text == get_text("time_plus_20", lang):
        await process_offset_time(message, state, 20, lang)
    elif message.text == get_text("custom_time", lang):
        # Ask for day type first, then custom time
        await state.set_state(RouteStates.waiting_for_day_type)
        data = await state.get_data()
        active_msg_id = data.get("active_message_id")
        
        # Store valid day types for validation
        valid_day_types = [
            get_text("weekdays", lang),
            get_text("weekends", lang),
        ]
        
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
    else:
        await message.answer(
            get_text("error_unknown_choice", lang),
            reply_markup=get_time_choice_keyboard(lang),
        )


async def back_from_time_choice(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from time_choice - return to to_station selection."""
    data = await state.get_data()
    to_line = data.get("to_line", "Холодногірсько-заводська" if lang == "ua" else "Kholodnohirsko-Zavodska")
    from_station = data.get("from_station", "")
    active_msg_id = data.get("active_message_id")

    router = get_router()
    stations = get_stations_by_line_except(router, to_line, from_station, lang)

    await state.set_state(RouteStates.waiting_for_to_station)

    if active_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=active_msg_id,
                text=get_text("select_station_line", lang, line=LINE_INTERNAL_TO_DISPLAY.get(to_line, to_line)),
                reply_markup=get_stations_keyboard(stations, lang),
            )
        except Exception:
            msg = await message.answer(
                get_text("select_station_line", lang, line=LINE_INTERNAL_TO_DISPLAY.get(to_line, to_line)),
                reply_markup=get_stations_keyboard(stations, lang),
            )
            await state.update_data(active_message_id=msg.message_id)
    else:
        msg = await message.answer(
            get_text("select_station_line", lang, line=LINE_INTERNAL_TO_DISPLAY.get(to_line, to_line)),
            reply_markup=get_stations_keyboard(stations, lang),
        )
        await state.update_data(active_message_id=msg.message_id)


async def cancel_from_time_choice(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Cancel route building from time_choice."""
    await state.clear()
    await message.answer(get_text("error_cancelled", lang), reply_markup=get_main_keyboard(lang))


# ===== Day Type (for custom time) Handlers =====


async def process_day_type_route(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process day type selection for custom time."""
    # Get valid day types from state
    data = await state.get_data()
    valid_day_types: list[str] = data.get("valid_day_types", [])
    
    if message.text not in valid_day_types:
        await message.answer(
            get_text("error_unknown_choice", lang),
            reply_markup=get_day_type_keyboard(lang),
        )
        return
    
    selected_day = DAY_TYPE_DISPLAY_TO_INTERNAL.get(message.text)

    await state.update_data(day_type=selected_day)
    await state.set_state(RouteStates.waiting_for_custom_time)
    
    data = await state.get_data()
    active_msg_id = data.get("active_message_id")
    
    if active_msg_id:
        try:
            # Remove keyboard for custom time input
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=active_msg_id,
                text=get_text("custom_time_prompt", lang),
                reply_markup=None,
            )
        except Exception:
            await message.answer(get_text("custom_time_prompt", lang))
    else:
        await message.answer(get_text("custom_time_prompt", lang))


async def back_from_day_type_route(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from day_type - return to time_choice selection."""
    await state.set_state(RouteStates.waiting_for_time_choice)
    
    data = await state.get_data()
    active_msg_id = data.get("active_message_id")
    
    if active_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=active_msg_id,
                text=get_text("time_prompt", lang),
                reply_markup=get_time_choice_keyboard(lang),
            )
        except Exception:
            msg = await message.answer(
                get_text("time_prompt", lang),
                reply_markup=get_time_choice_keyboard(lang),
            )
            await state.update_data(active_message_id=msg.message_id)
    else:
        msg = await message.answer(
            get_text("time_prompt", lang),
            reply_markup=get_time_choice_keyboard(lang),
        )
        await state.update_data(active_message_id=msg.message_id)


async def cancel_from_day_type_route(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Cancel route building from day_type."""
    await state.clear()
    await message.answer(get_text("error_cancelled", lang), reply_markup=get_main_keyboard(lang))


# ===== Custom Time Handlers =====


async def process_custom_time(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process custom time input."""
    time_input = message.text.strip()

    # Validate time format HH:MM
    if not re.match(r"^\d{1,2}:\d{2}$", time_input):
        await message.answer(
            get_text("error_invalid_time_format", lang),
        )
        return

    try:
        hour, minute = map(int, time_input.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Invalid time")

        data = await state.get_data()
        from_station_name = data.get("from_station")
        to_station_name = data.get("to_station")
        day_type_str = data.get("day_type", "weekday")

        # Create datetime with custom time in configured timezone
        base_time = now()
        departure_time = base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

        await _build_and_send_route(
            message,
            state,
            from_station_name,
            to_station_name,
            departure_time,
            day_type_str,
            lang,
        )

    except ValueError:
        await message.answer(
            get_text("error_invalid_time", lang),
        )
        return
    except Exception as e:
        await message.answer(get_text("error_generic", lang, error=str(e)), reply_markup=get_main_keyboard(lang))
        await state.clear()


async def back_from_custom_time(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from custom_time - return to day_type selection."""
    await state.set_state(RouteStates.waiting_for_day_type)
    
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
        except Exception:
            msg = await message.answer(
                get_text("day_type_prompt", lang),
                reply_markup=get_day_type_keyboard(lang),
            )
            await state.update_data(active_message_id=msg.message_id)
    else:
        msg = await message.answer(
            get_text("day_type_prompt", lang),
            reply_markup=get_day_type_keyboard(lang),
        )
        await state.update_data(active_message_id=msg.message_id)


# ===== Route Building Logic =====


async def process_current_time(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process current time selection."""
    data = await state.get_data()
    from_station_name = data.get("from_station")
    to_station_name = data.get("to_station")
    day_type_str = "weekday" if now().weekday() < 5 else "weekend"

    departure_time = now()

    await _build_and_send_route(
        message,
        state,
        from_station_name,
        to_station_name,
        departure_time,
        day_type_str,
        lang,
    )


async def process_offset_time(message: types.Message, state: FSMContext, offset_minutes: int, lang: Language = "ua"):
    """Process time with offset (+/- minutes) from current time."""
    from datetime import timedelta

    data = await state.get_data()
    from_station_name = data.get("from_station")
    to_station_name = data.get("to_station")
    day_type_str = "weekday" if now().weekday() < 5 else "weekend"

    departure_time = now() + timedelta(minutes=offset_minutes)

    await _build_and_send_route(
        message,
        state,
        from_station_name,
        to_station_name,
        departure_time,
        day_type_str,
        lang,
    )


async def _build_and_send_route(
    message: types.Message,
    state: FSMContext,
    from_station_name: str,
    to_station_name: str,
    departure_time: datetime,
    day_type_str: str,
    lang: Language = "ua",
):
    """Build route and send result with reminder buttons."""
    try:
        router = get_router()
        from_st = router.find_station_by_name(from_station_name, lang)
        to_st = router.find_station_by_name(to_station_name, lang)

        if not from_st:
            await message.answer(
                get_text("error_station_not_found", lang, station=from_station_name),
                reply_markup=get_main_keyboard(lang),
            )
            await state.clear()
            return

        if not to_st:
            await message.answer(
                get_text("error_station_not_found", lang, station=to_station_name),
                reply_markup=get_main_keyboard(lang),
            )
            await state.clear()
            return

        dt = DayType.WEEKDAY if day_type_str == "weekday" else DayType.WEEKEND
        try:
            route = router.find_route(from_st.id, to_st.id, departure_time, dt)
        except MetroClosedError:
            await message.answer(
                get_text("error_metro_closed", lang),
                reply_markup=get_main_keyboard(lang),
            )
            await state.clear()
            return

        if not route:
            await message.answer(get_text("error_route_not_found", lang), reply_markup=get_main_keyboard(lang))
            await state.clear()
            return

        result = format_route(route, lang)

        # Build line groups for reminder buttons
        line_groups = build_line_groups(route)

        # Store route for callback lookup
        route_key = generate_route_key(route)
        _active_routes[route_key] = (route, line_groups)

        # Build reminder keyboard only if there's at least one line with 2+ stations
        has_long_line = any(len(segments) > 1 for segments in line_groups.values())
        reminder_kb = build_reminder_keyboard(route_key, line_groups, lang) if has_long_line else None

        if reminder_kb and reminder_kb.inline_keyboard:
            await message.answer(result, reply_markup=reminder_kb)
        else:
            await message.answer(result)

        await message.answer(get_text("main_menu", lang), reply_markup=get_main_keyboard(lang))

    except Exception as e:
        await message.answer(get_text("error_generic", lang, error=str(e)), reply_markup=get_main_keyboard(lang))

    await state.clear()


# ===== Reminder Callback Handler =====


async def process_reminder(callback: types.CallbackQuery, lang: Language = "ua"):
    """Process reminder request - schedules for arrival at previous station."""
    # Parse callback data: remind|{route_key}|{index}|{arrival_ts}
    parts = callback.data.split("|")

    # Handle old format (for backward compatibility with old buttons)
    if len(parts) == 5 and ":" in parts[1]:
        await callback.answer(get_text("outdated_button", lang))
        return

    route_key = parts[1] if len(parts) > 1 else ""
    try:
        segment_idx = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        await callback.answer(get_text("error_invalid_data", lang))
        return
    arrival_ts = int(parts[3]) if len(parts) > 3 else 0

    # Get route and line_groups from active routes
    route_data = _active_routes.get(route_key)
    if not route_data:
        await callback.answer(get_text("error_route_expired", lang))
        return
    route, line_groups = route_data

    # segment_idx is index in line_groups (line_idx from creation)
    line_ids = list(line_groups.keys())
    if segment_idx < 0 or segment_idx >= len(line_ids):
        await callback.answer(get_text("error_invalid_line", lang))
        return

    line_id = line_ids[segment_idx]
    segments = line_groups[line_id]

    # Get the target segment (second-to-last if multiple, or the only one)
    target_segment = segments[-2] if len(segments) >= 2 else segments[0]

    from_st = route.segments[0].from_station
    to_st = route.segments[-1].to_station
    prev_st = target_segment.from_station  # Remind at from_station to exit at to_station

    # Store reminder for trigger command
    user_id = callback.from_user.id
    pending_reminders[user_id] = {
        "from_st": from_st,
        "to_st": to_st,
        "prev_st": prev_st,
        "arrival_ts": arrival_ts,
    }

    # Calculate wait time until departure from station before last (when to remind)
    current_time = now()
    # Use departure time from the last segment's from_station (second-to-last station of the line)
    remind_time = segments[-1].departure_time if len(segments) >= 1 else None

    if remind_time:
        wait_seconds = (remind_time - current_time).total_seconds()
        remind_time_str = remind_time.strftime("%H:%M")
    else:
        wait_seconds = 0
        remind_time_str = None

    # Rebuild keyboard with updated button text for clicked button
    new_kb = build_reminder_keyboard(route_key, line_groups, lang, clicked_idx=segment_idx, remind_time=remind_time_str)

    await callback.message.edit_reply_markup(reply_markup=new_kb)
    await callback.answer(get_text("reminder_set", lang))

    if wait_seconds > 0:
        # Wait until arrival time
        await asyncio.sleep(wait_seconds)

        # Send reminder if still pending
        if user_id in pending_reminders:
            del pending_reminders[user_id]
            # Get the last station of this line group (where user needs to exit)
            last_station = segments[-1].to_station
            name_attr = "name_ua" if lang == "ua" else "name_en"
            await callback.message.answer(get_text("reminder_exit_prepare", lang, station=getattr(last_station, name_attr)))


async def cancel_reminder(callback: types.CallbackQuery, lang: Language = "ua"):
    """Cancel reminder."""
    # Parse callback data: remind_cancel|{route_key}|{idx}
    parts = callback.data.split("|")

    route_key = parts[1] if len(parts) > 1 else ""
    try:
        int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        await callback.answer(get_text("error_invalid_data", lang))
        return

    # Get route and line_groups from active routes
    route_data = _active_routes.get(route_key)
    if not route_data:
        await callback.answer(get_text("error_route_expired", lang))
        return
    route, line_groups = route_data

    # Remove reminder from pending
    user_id = callback.from_user.id
    if user_id in pending_reminders:
        del pending_reminders[user_id]

    # Rebuild keyboard - revert to original button
    new_kb = build_reminder_keyboard(route_key, line_groups, lang)

    await callback.message.edit_reply_markup(reply_markup=new_kb)
    await callback.answer(get_text("reminder_cancelled", lang))


# ===== Registration =====


def register_route_handlers(dp: Dispatcher):
    """Register route handlers."""
    # Command handlers
    dp.message.register(cmd_route, Command("route"))

    # From line state handlers
    dp.message.register(back_from_line, RouteStates.waiting_for_from_line, F.text == get_text("back", "ua"))
    dp.message.register(back_from_line, RouteStates.waiting_for_from_line, F.text == get_text("back", "en"))
    dp.message.register(cancel_from_line, RouteStates.waiting_for_from_line, F.text == get_text("cancel", "ua"))
    dp.message.register(cancel_from_line, RouteStates.waiting_for_from_line, F.text == get_text("cancel", "en"))
    dp.message.register(process_from_line, RouteStates.waiting_for_from_line)

    # From station state handlers
    dp.message.register(back_from_station, RouteStates.waiting_for_from_station, F.text == get_text("back", "ua"))
    dp.message.register(back_from_station, RouteStates.waiting_for_from_station, F.text == get_text("back", "en"))
    dp.message.register(cancel_from_station, RouteStates.waiting_for_from_station, F.text == get_text("cancel", "ua"))
    dp.message.register(cancel_from_station, RouteStates.waiting_for_from_station, F.text == get_text("cancel", "en"))
    dp.message.register(process_from_station, RouteStates.waiting_for_from_station)

    # To line state handlers
    dp.message.register(back_to_line, RouteStates.waiting_for_to_line, F.text == get_text("back", "ua"))
    dp.message.register(back_to_line, RouteStates.waiting_for_to_line, F.text == get_text("back", "en"))
    dp.message.register(cancel_to_line, RouteStates.waiting_for_to_line, F.text == get_text("cancel", "ua"))
    dp.message.register(cancel_to_line, RouteStates.waiting_for_to_line, F.text == get_text("cancel", "en"))
    dp.message.register(process_to_line, RouteStates.waiting_for_to_line)

    # To station state handlers
    dp.message.register(back_to_station, RouteStates.waiting_for_to_station, F.text == get_text("back", "ua"))
    dp.message.register(back_to_station, RouteStates.waiting_for_to_station, F.text == get_text("back", "en"))
    dp.message.register(cancel_to_station, RouteStates.waiting_for_to_station, F.text == get_text("cancel", "ua"))
    dp.message.register(cancel_to_station, RouteStates.waiting_for_to_station, F.text == get_text("cancel", "en"))
    dp.message.register(process_to_station, RouteStates.waiting_for_to_station)

    # Time choice state handlers
    dp.message.register(back_from_time_choice, RouteStates.waiting_for_time_choice, F.text == get_text("back", "ua"))
    dp.message.register(back_from_time_choice, RouteStates.waiting_for_time_choice, F.text == get_text("back", "en"))
    dp.message.register(cancel_from_time_choice, RouteStates.waiting_for_time_choice, F.text == get_text("cancel", "ua"))
    dp.message.register(cancel_from_time_choice, RouteStates.waiting_for_time_choice, F.text == get_text("cancel", "en"))
    dp.message.register(process_time_choice, RouteStates.waiting_for_time_choice)

    # Day type state handlers
    dp.message.register(back_from_day_type_route, RouteStates.waiting_for_day_type, F.text == get_text("back", "ua"))
    dp.message.register(back_from_day_type_route, RouteStates.waiting_for_day_type, F.text == get_text("back", "en"))
    dp.message.register(cancel_from_day_type_route, RouteStates.waiting_for_day_type, F.text == get_text("cancel", "ua"))
    dp.message.register(cancel_from_day_type_route, RouteStates.waiting_for_day_type, F.text == get_text("cancel", "en"))
    dp.message.register(process_day_type_route, RouteStates.waiting_for_day_type)

    # Custom time state handlers
    dp.message.register(back_from_custom_time, RouteStates.waiting_for_custom_time, F.text == get_text("back", "ua"))
    dp.message.register(back_from_custom_time, RouteStates.waiting_for_custom_time, F.text == get_text("back", "en"))
    dp.message.register(process_custom_time, RouteStates.waiting_for_custom_time)

    # Callback query handler for reminders
    dp.callback_query.register(process_reminder, F.data.startswith("remind|"))
    dp.callback_query.register(cancel_reminder, F.data.startswith("remind_cancel|"))
