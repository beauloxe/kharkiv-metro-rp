"""Route handlers for the Telegram bot."""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Callable

from aiogram import Dispatcher, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from kharkiv_metro_core import (
    DAY_TYPE_DISPLAY_TO_INTERNAL,
    LINE_DISPLAY_TO_INTERNAL,
    DayType,
    Language,
    MetroClosedError,
    get_line_display_name,
    get_text,
)

from ..keyboards import (
    build_reminder_keyboard,
    get_day_type_keyboard,
    get_lines_keyboard,
    get_main_keyboard,
    get_stations_keyboard,
    get_time_choice_keyboard,
)
from ..states import RouteStates
from ..user_data import (
    clear_user_reminders,
    deactivate_user_reminder,
    get_all_active_reminders,
    save_user_reminder,
)
from ..utils import (
    build_line_groups,
    format_route,
    generate_route_key,
    get_router,
    get_stations_by_line,
    get_stations_by_line_except,
    now,
)

# Store pending reminders and active routes
pending_reminders: dict[int, dict] = {}
_active_routes: dict[str, tuple] = {}

# Create router for route handlers
router = Router()

BACK_TEXTS = (get_text("back", "ua"), get_text("back", "en"))
CANCEL_TEXTS = (get_text("cancel", "ua"), get_text("cancel", "en"))
BACK_OR_CANCEL_TEXTS = BACK_TEXTS + CANCEL_TEXTS


# ===== Helper Functions =====


async def update_message(
    message: types.Message,
    state: FSMContext,
    text: str,
    keyboard,
) -> None:
    """Update existing message or send new one."""
    data = await state.get_data()
    msg_id = data.get("active_message_id")

    if msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text=text,
                reply_markup=keyboard,
            )
            return
        except Exception:
            pass

    msg = await message.answer(text, reply_markup=keyboard)
    await state.update_data(active_message_id=msg.message_id)


def get_valid_lines(lang: Language) -> list[str]:
    """Get list of valid line display names."""
    return [
        get_line_display_name("kholodnohirsko_zavodska", lang),
        get_line_display_name("saltivska", lang),
        get_line_display_name("oleksiivska", lang),
    ]


def parse_time(time_str: str) -> datetime | None:
    """Parse time string in HH:MM format."""
    match = re.match(r"^(\d{1,2}):(\d{2})$", time_str.strip())
    if not match:
        return None

    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    return now().replace(hour=hour, minute=minute, second=0, microsecond=0)


async def restore_pending_reminders(bot) -> None:
    """Restore active reminders from database."""
    metro_router = get_router()
    for reminder in get_all_active_reminders():
        user_id = reminder.get("user_id")
        station_id = reminder.get("station_id")
        remind_at_raw = reminder.get("remind_at")
        lang = reminder.get("lang", "ua")
        reminder_id = reminder.get("id")

        if user_id is None or station_id is None or remind_at_raw is None:
            continue

        station = metro_router.stations.get(station_id)
        if not station:
            if reminder_id:
                deactivate_user_reminder(reminder_id)
            continue

        remind_at = datetime.fromisoformat(remind_at_raw)
        delay = (remind_at - now()).total_seconds()
        if delay <= 0:
            if reminder_id:
                deactivate_user_reminder(reminder_id)
            continue

        if user_id in pending_reminders:
            continue

        task = asyncio.create_task(_send_reminder(bot, user_id, station, lang, delay, reminder_id=reminder_id))
        pending_reminders[user_id] = {"task": task, "time": remind_at, "reminder_id": reminder_id}


# ===== Main Entry Point =====


@router.message(Command("route"))
async def cmd_route(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Start route conversation."""
    await state.set_state(RouteStates.waiting_for_from_line)

    valid_lines = get_valid_lines(lang)
    msg = await message.answer(
        get_text("from_station_prompt", lang),
        reply_markup=get_lines_keyboard(lang),
    )
    await state.update_data(active_message_id=msg.message_id, valid_lines=valid_lines)


# ===== Generic Handlers =====


async def handle_line_selection(
    message: types.Message,
    state: FSMContext,
    lang: Language,
    next_state: str,
    prompt_key: str,
    storage_key: str,
) -> bool:
    """Handle line selection with validation."""
    selected = LINE_DISPLAY_TO_INTERNAL.get(message.text)

    if not selected:
        await message.answer(
            get_text("error_unknown_line", lang),
            reply_markup=get_lines_keyboard(lang),
        )
        return False

    await state.update_data(**{storage_key: selected})
    await state.set_state(next_state)

    metro_router = get_router()
    stations = get_stations_by_line(metro_router, selected, lang)
    await state.update_data(valid_stations=stations)

    await update_message(
        message,
        state,
        get_text(prompt_key, lang, line=message.text),
        get_stations_keyboard(stations, lang),
    )
    return True


async def handle_station_selection(
    message: types.Message,
    state: FSMContext,
    lang: Language,
    next_state: str,
    prompt_key: str,
    keyboard_func: Callable,
) -> bool:
    """Handle station selection with validation."""
    data = await state.get_data()
    valid_stations: list = data.get("valid_stations", [])

    if message.text not in valid_stations:
        await message.answer(
            get_text("error_unknown_choice", lang),
            reply_markup=get_stations_keyboard(valid_stations, lang),
        )
        return False

    await state.update_data(station=message.text)
    await state.set_state(next_state)

    await update_message(
        message,
        state,
        get_text(prompt_key, lang),
        keyboard_func(lang),
    )
    return True


async def handle_back(
    message: types.Message,
    state: FSMContext,
    lang: Language,
    target_state: str,
    text: str,
    keyboard,
) -> None:
    """Generic back handler."""
    await state.set_state(target_state)
    await update_message(message, state, text, keyboard)


async def handle_cancel(message: types.Message, state: FSMContext, lang: Language) -> None:
    """Generic cancel handler."""
    await state.clear()
    await message.answer(get_text("error_cancelled", lang), reply_markup=get_main_keyboard(lang))


# ===== Specific Handlers =====


@router.message(
    RouteStates.waiting_for_from_line,
    ~F.text.in_(CANCEL_TEXTS),
)
async def process_from_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process line selection for 'from' station."""
    await handle_line_selection(
        message,
        state,
        lang,
        RouteStates.waiting_for_from_station,
        "select_station_line",
        "from_line",
    )


@router.message(
    RouteStates.waiting_for_from_station,
    ~F.text.in_(BACK_OR_CANCEL_TEXTS),
)
async def process_from_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process 'from' station and ask for 'to' line."""
    if not await handle_station_selection(
        message,
        state,
        lang,
        RouteStates.waiting_for_to_line,
        "to_station_prompt",
        get_lines_keyboard,
    ):
        return

    await state.update_data(from_station=message.text, valid_lines=get_valid_lines(lang))


@router.message(
    RouteStates.waiting_for_to_line,
    ~F.text.in_(BACK_OR_CANCEL_TEXTS),
)
async def process_to_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process line selection for 'to' station."""
    selected = LINE_DISPLAY_TO_INTERNAL.get(message.text)
    if not selected:
        await message.answer(
            get_text("error_unknown_line", lang),
            reply_markup=get_lines_keyboard(lang),
        )
        return

    data = await state.get_data()
    from_station = data.get("from_station")

    await state.update_data(to_line=selected)
    await state.set_state(RouteStates.waiting_for_to_station)

    metro_router = get_router()
    stations = get_stations_by_line_except(metro_router, selected, from_station, lang)
    await state.update_data(valid_stations=stations)

    await update_message(
        message,
        state,
        get_text("select_station_line", lang, line=message.text),
        get_stations_keyboard(stations, lang),
    )


@router.message(
    RouteStates.waiting_for_to_station,
    ~F.text.in_(BACK_OR_CANCEL_TEXTS),
)
async def process_to_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process 'to' station and ask for time choice."""
    data = await state.get_data()
    valid_stations: list = data.get("valid_stations", [])

    if message.text not in valid_stations:
        await message.answer(
            get_text("error_unknown_choice", lang),
            reply_markup=get_stations_keyboard(valid_stations, lang),
        )
        return

    await state.update_data(to_station=message.text)
    await state.set_state(RouteStates.waiting_for_time_choice)

    await update_message(
        message,
        state,
        get_text("time_prompt", lang),
        get_time_choice_keyboard(lang),
    )


@router.message(
    RouteStates.waiting_for_time_choice,
    ~F.text.in_(BACK_OR_CANCEL_TEXTS),
)
async def process_time_choice(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process time choice selection."""
    text = message.text

    if text == get_text("current_time", lang):
        await process_current_time(message, state, lang)
    elif text in (
        get_text("time_minus_20", lang),
        get_text("time_minus_10", lang),
        get_text("time_plus_10", lang),
        get_text("time_plus_20", lang),
    ):
        await process_offset_time(message, state, lang)
    elif text == get_text("custom_time", lang):
        await state.set_state(RouteStates.waiting_for_day_type)
        await state.update_data(valid_day_types=[get_text("weekdays", lang), get_text("weekends", lang)])

        await update_message(
            message,
            state,
            get_text("day_type_prompt", lang),
            get_day_type_keyboard(lang),
        )
    else:
        await message.answer(get_text("error_unknown_choice", lang))


@router.message(
    RouteStates.waiting_for_day_type,
    ~F.text.in_(BACK_OR_CANCEL_TEXTS),
)
async def process_day_type_route(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process day type and ask for custom time."""
    data = await state.get_data()
    valid_day_types: list = data.get("valid_day_types", [])

    if message.text not in valid_day_types:
        await message.answer(get_text("error_unknown_choice", lang), reply_markup=get_day_type_keyboard(lang))
        return

    selected = DAY_TYPE_DISPLAY_TO_INTERNAL.get(message.text)
    await state.update_data(day_type=selected)
    await state.set_state(RouteStates.waiting_for_custom_time)

    await update_message(
        message,
        state,
        get_text("custom_time_prompt", lang),
        None,  # No keyboard for text input
    )


@router.message(
    RouteStates.waiting_for_custom_time,
    ~F.text.in_(BACK_TEXTS),
)
async def process_custom_time(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process custom time input."""
    parsed = parse_time(message.text)
    if not parsed:
        await message.answer(get_text("error_invalid_time_format", lang))
        return

    await _build_and_send_route(message, state, lang, parsed)


async def process_current_time(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process current time selection."""
    await _build_and_send_route(message, state, lang, now())


async def process_offset_time(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Process time offset selection."""
    offsets = {
        get_text("time_minus_20", lang): -20,
        get_text("time_minus_10", lang): -10,
        get_text("time_plus_10", lang): 10,
        get_text("time_plus_20", lang): 20,
    }
    offset = offsets.get(message.text, 0)
    await _build_and_send_route(message, state, lang, now() + timedelta(minutes=offset))


# ===== Back Handlers =====


@router.message(RouteStates.waiting_for_from_station, F.text.in_(BACK_TEXTS))
async def back_from_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from station selection to line selection."""
    data = await state.get_data()
    from_line = data.get("from_line", "Холодногірсько-заводська")

    await handle_back(
        message,
        state,
        lang,
        RouteStates.waiting_for_from_line,
        get_text("from_station_prompt", lang),
        get_lines_keyboard(lang),
    )


@router.message(RouteStates.waiting_for_to_line, F.text.in_(BACK_TEXTS))
async def back_from_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from to_line to from_station."""
    data = await state.get_data()
    from_line = data.get("from_line", "Холодногірсько-заводська")

    metro_router = get_router()
    stations = get_stations_by_line(metro_router, from_line, lang)

    await handle_back(
        message,
        state,
        lang,
        RouteStates.waiting_for_from_station,
        get_text("select_station_line", lang, line=from_line),
        get_stations_keyboard(stations, lang),
    )


@router.message(RouteStates.waiting_for_to_station, F.text.in_(BACK_TEXTS))
async def back_to_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from to_station to to_line."""
    await handle_back(
        message,
        state,
        lang,
        RouteStates.waiting_for_to_line,
        get_text("to_station_prompt", lang),
        get_lines_keyboard(lang),
    )


@router.message(RouteStates.waiting_for_time_choice, F.text.in_(BACK_TEXTS))
async def back_from_time_choice(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from time_choice to to_station."""
    data = await state.get_data()
    to_line = data.get("to_line", "Холодногірсько-заводська")
    from_station = data.get("from_station", "")

    metro_router = get_router()
    stations = get_stations_by_line_except(metro_router, to_line, from_station, lang)

    # Convert internal line name to display name with emoji
    from kharkiv_metro_core import get_line_display_by_internal

    line_display = get_line_display_by_internal(to_line, lang)

    await handle_back(
        message,
        state,
        lang,
        RouteStates.waiting_for_to_station,
        get_text("select_station_line", lang, line=line_display),
        get_stations_keyboard(stations, lang),
    )


@router.message(RouteStates.waiting_for_day_type, F.text.in_(BACK_TEXTS))
async def back_from_day_type_route(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from day_type to time_choice."""
    await handle_back(
        message,
        state,
        lang,
        RouteStates.waiting_for_time_choice,
        get_text("time_prompt", lang),
        get_time_choice_keyboard(lang),
    )


@router.message(RouteStates.waiting_for_custom_time, F.text.in_(BACK_TEXTS))
async def back_from_custom_time(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Go back from custom_time to day_type."""
    await handle_back(
        message,
        state,
        lang,
        RouteStates.waiting_for_day_type,
        get_text("day_type_prompt", lang),
        get_day_type_keyboard(lang),
    )


# ===== Cancel Handlers =====


@router.message(RouteStates.waiting_for_from_line, F.text.in_(CANCEL_TEXTS))
async def cancel_from_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    await handle_cancel(message, state, lang)


@router.message(RouteStates.waiting_for_from_station, F.text.in_(CANCEL_TEXTS))
async def cancel_from_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    await handle_cancel(message, state, lang)


@router.message(RouteStates.waiting_for_to_line, F.text.in_(CANCEL_TEXTS))
async def cancel_to_line(message: types.Message, state: FSMContext, lang: Language = "ua"):
    await handle_cancel(message, state, lang)


@router.message(RouteStates.waiting_for_to_station, F.text.in_(CANCEL_TEXTS))
async def cancel_to_station(message: types.Message, state: FSMContext, lang: Language = "ua"):
    await handle_cancel(message, state, lang)


@router.message(RouteStates.waiting_for_time_choice, F.text.in_(CANCEL_TEXTS))
async def cancel_from_time_choice(message: types.Message, state: FSMContext, lang: Language = "ua"):
    await handle_cancel(message, state, lang)


@router.message(RouteStates.waiting_for_day_type, F.text.in_(CANCEL_TEXTS))
async def cancel_from_day_type_route(message: types.Message, state: FSMContext, lang: Language = "ua"):
    await handle_cancel(message, state, lang)


# ===== Route Building =====


async def _build_and_send_route(
    message: types.Message,
    state: FSMContext,
    lang: Language,
    departure_time: datetime,
) -> None:
    """Build route and send result."""
    data = await state.get_data()

    from_station_name = data.get("from_station")
    to_station_name = data.get("to_station")
    day_type_str = data.get("day_type")

    day_type = DayType.WEEKDAY if day_type_str == "weekday" else DayType.WEEKEND if day_type_str else None

    metro_router = get_router()

    from_st = metro_router.find_station_by_name(from_station_name, lang)
    to_st = metro_router.find_station_by_name(to_station_name, lang)

    if not from_st or not to_st:
        await message.answer(get_text("error_station_not_found", lang, station=from_station_name or to_station_name))
        await state.clear()
        return

    try:
        route = metro_router.find_route(from_st.id, to_st.id, departure_time, day_type)
    except MetroClosedError:
        await message.answer(get_text("error_metro_closed", lang), reply_markup=get_main_keyboard(lang))
        await state.clear()
        return
    except Exception as e:
        await message.answer(get_text("error_generic", lang, error=str(e)), reply_markup=get_main_keyboard(lang))
        await state.clear()
        return

    if not route:
        await message.answer(get_text("error_route_not_found", lang), reply_markup=get_main_keyboard(lang))
        await state.clear()
        return

    # Format and send route
    route_text = format_route(route, lang)
    line_groups = build_line_groups(route)

    # Store route for reminder callbacks
    route_key = generate_route_key(route)
    _active_routes[route_key] = (route, line_groups)

    keyboard = build_reminder_keyboard(route_key, line_groups, lang) if len(route.segments) > 1 else None

    await message.answer(route_text, reply_markup=get_main_keyboard(lang))

    if keyboard:
        await message.answer(get_text("navigation_hint", lang), reply_markup=keyboard)

    await state.clear()


# ===== Reminder Handlers =====


@router.callback_query(F.data.startswith("remind|"))
async def process_reminder(callback: types.CallbackQuery, lang: Language = "ua"):
    """Set up a reminder for station exit."""
    try:
        _, route_key, group_idx, remind_ts = callback.data.split("|")
        group_idx = int(group_idx)
        remind_ts = int(remind_ts)
    except ValueError:
        await callback.answer(get_text("error_invalid_data", lang))
        return

    route_data = _active_routes.get(route_key)
    if not route_data:
        await callback.answer(get_text("error_route_expired", lang))
        return

    route, line_groups = route_data
    segments = list(line_groups.values())[group_idx] if group_idx < len(line_groups) else None

    if not segments:
        await callback.answer(get_text("error_invalid_line", lang))
        return

    # Calculate reminder time (1 station before last)
    exit_segment = segments[-1]
    remind_time = exit_segment.departure_time

    if remind_time <= now():
        await callback.answer(get_text("error_metro_closed", lang))
        return

    user_id = callback.from_user.id

    clear_user_reminders(user_id)

    # Cancel existing reminder
    if user_id in pending_reminders:
        pending_reminders[user_id]["task"].cancel()

    reminder_id = save_user_reminder(
        user_id,
        route_key,
        exit_segment.to_station.id,
        remind_time,
        lang,
    )

    # Create new reminder task
    delay = (remind_time - now()).total_seconds()
    task = asyncio.create_task(_send_reminder(callback.bot, user_id, exit_segment.to_station, lang, delay, reminder_id))

    pending_reminders[user_id] = {"task": task, "time": remind_time, "reminder_id": reminder_id}

    # Update keyboard
    keyboard = build_reminder_keyboard(
        route_key, line_groups, lang, clicked_idx=group_idx, remind_time=remind_time.strftime("%H:%M")
    )
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer(get_text("reminder_set", lang))


async def _send_reminder(bot, user_id: int, station, lang: Language, delay: float, reminder_id: int | None = None):
    """Send reminder after delay."""
    await asyncio.sleep(delay)

    if user_id not in pending_reminders:
        return

    name_attr = "name_ua" if lang == "ua" else "name_en"
    await bot.send_message(user_id, get_text("reminder_exit_prepare", lang, station=getattr(station, name_attr)))

    if reminder_id:
        deactivate_user_reminder(reminder_id)

    pending_reminders.pop(user_id, None)


@router.callback_query(F.data.startswith("remind_cancel|"))
async def cancel_reminder(callback: types.CallbackQuery, lang: Language = "ua"):
    """Cancel active reminder."""
    user_id = callback.from_user.id

    reminder_id = None
    if user_id in pending_reminders:
        pending_reminders[user_id]["task"].cancel()
        reminder_id = pending_reminders[user_id].get("reminder_id")
        pending_reminders.pop(user_id, None)

    if reminder_id:
        deactivate_user_reminder(reminder_id)
    else:
        clear_user_reminders(user_id)

    # Reset keyboard
    try:
        _, route_key, group_idx = callback.data.split("|")
        route_data = _active_routes.get(route_key)
        if route_data:
            _, line_groups = route_data
            keyboard = build_reminder_keyboard(route_key, line_groups, lang)
            await callback.message.edit_reply_markup(reply_markup=keyboard)
    except ValueError:
        pass

    await callback.answer(get_text("reminder_cancelled", lang))


# ===== Registration =====


def register_route_handlers(dp: Dispatcher) -> None:
    """Register route handlers."""
    dp.include_router(router)
