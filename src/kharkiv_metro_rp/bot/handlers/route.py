"""Route handlers for the Telegram bot."""

import asyncio
import re
from datetime import datetime

from aiogram import Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from kharkiv_metro_rp.core.models import DayType

from ..constants import (
    DAY_TYPE_DISPLAY_TO_INTERNAL,
    LINE_DISPLAY_TO_INTERNAL,
    LINE_INTERNAL_TO_DISPLAY,
    ButtonText,
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
from ..utils import (
    build_line_groups,
    format_route,
    generate_route_key,
    get_current_day_type,
    get_day_type_from_string,
    get_router,
    get_stations_by_line,
    get_stations_by_line_except,
)

# Store pending reminders for callback reminder system
pending_reminders: dict[int, dict] = {}

# Store active routes for reminder callback lookup (callback_data limited to 64 bytes)
_active_routes: dict[str, tuple] = {}


async def cmd_route(message: types.Message, state: FSMContext):
    """Start route conversation."""
    await state.set_state(RouteStates.waiting_for_from_line)
    await message.answer(
        "📍 Звідки їдемо? Спочатку оберіть лінію:",
        reply_markup=get_lines_keyboard(),
    )


# ===== From Line Handlers =====


async def process_from_line(message: types.Message, state: FSMContext):
    """Process line selection for 'from' station."""
    selected_line = LINE_DISPLAY_TO_INTERNAL.get(message.text)
    if not selected_line:
        await message.answer(
            "❌ Невідома лінія. Оберіть з клавіатури.",
            reply_markup=get_lines_keyboard(),
        )
        return

    await state.update_data(from_line=selected_line)
    await state.set_state(RouteStates.waiting_for_from_station)

    router = get_router()
    stations = get_stations_by_line(router, selected_line)

    await message.answer(
        f"📍 Оберіть станцію на лінії {message.text}:",
        reply_markup=get_stations_keyboard(stations),
    )


async def back_from_line(message: types.Message, state: FSMContext):
    """Go back from from_line - return to main menu."""
    await state.clear()
    await message.answer("🏠 Головне меню", reply_markup=get_main_keyboard())


async def cancel_from_line(message: types.Message, state: FSMContext):
    """Cancel route building from from_line."""
    await state.clear()
    await message.answer("❌ Побудову маршруту скасовано", reply_markup=get_main_keyboard())


# ===== From Station Handlers =====


async def process_from_station(message: types.Message, state: FSMContext):
    """Process from station - now ask for to_line."""
    await state.update_data(from_station=message.text)
    await state.set_state(RouteStates.waiting_for_to_line)
    await message.answer(
        "📍 Куди їдемо? Спочатку оберіть лінію:",
        reply_markup=get_lines_keyboard(),
    )


async def back_from_station(message: types.Message, state: FSMContext):
    """Go back from from_station - return to from_line selection."""
    await state.set_state(RouteStates.waiting_for_from_line)
    await message.answer(
        "📍 Звідки їдемо? Спочатку оберіть лінію:",
        reply_markup=get_lines_keyboard(),
    )


async def cancel_from_station(message: types.Message, state: FSMContext):
    """Cancel route building from from_station."""
    await state.clear()
    await message.answer("❌ Побудову маршруту скасовано", reply_markup=get_main_keyboard())


# ===== To Line Handlers =====


async def process_to_line(message: types.Message, state: FSMContext):
    """Process line selection for 'to' station."""
    selected_line = LINE_DISPLAY_TO_INTERNAL.get(message.text)
    if not selected_line:
        await message.answer(
            "❌ Невідома лінія. Оберіть з клавіатури.",
            reply_markup=get_lines_keyboard(),
        )
        return

    await state.update_data(to_line=selected_line)
    await state.set_state(RouteStates.waiting_for_to_station)

    # Get stations on this line, excluding from_station
    data = await state.get_data()
    from_station = data.get("from_station", "")

    router = get_router()
    stations = get_stations_by_line_except(router, selected_line, from_station)

    await message.answer(
        f"📍 Оберіть станцію на лінії {message.text}:",
        reply_markup=get_stations_keyboard(stations),
    )


async def back_to_line(message: types.Message, state: FSMContext):
    """Go back from to_line - return to from_station selection."""
    data = await state.get_data()
    from_line = data.get("from_line", "Холодногірсько-заводська")

    router = get_router()
    stations = get_stations_by_line(router, from_line)

    await state.set_state(RouteStates.waiting_for_from_station)

    await message.answer(
        f"📍 Оберіть станцію на лінії {LINE_INTERNAL_TO_DISPLAY.get(from_line, from_line)}:",
        reply_markup=get_stations_keyboard(stations),
    )


async def cancel_to_line(message: types.Message, state: FSMContext):
    """Cancel route building from to_line."""
    await state.clear()
    await message.answer("❌ Побудову маршруту скасовано", reply_markup=get_main_keyboard())


# ===== To Station Handlers =====


async def process_to_station(message: types.Message, state: FSMContext):
    """Process to station and ask for time choice."""
    await state.update_data(to_station=message.text)
    await state.set_state(RouteStates.waiting_for_time_choice)
    await message.answer("⏰ Який час?", reply_markup=get_time_choice_keyboard())


async def back_to_station(message: types.Message, state: FSMContext):
    """Go back from to_station - return to to_line selection."""
    await state.set_state(RouteStates.waiting_for_to_line)
    await message.answer(
        "📍 Куди їдемо? Спочатку оберіть лінію:",
        reply_markup=get_lines_keyboard(),
    )


async def cancel_to_station(message: types.Message, state: FSMContext):
    """Cancel route building from to_station."""
    await state.clear()
    await message.answer("❌ Побудову маршруту скасовано", reply_markup=get_main_keyboard())


# ===== Time Choice Handlers =====


async def process_time_choice(message: types.Message, state: FSMContext):
    """Process time choice selection."""
    if message.text == ButtonText.CURRENT_TIME:
        # Use current time and day type
        await process_current_time(message, state)
    elif message.text == ButtonText.TIME_MINUS_20:
        await process_offset_time(message, state, -20)
    elif message.text == ButtonText.TIME_MINUS_10:
        await process_offset_time(message, state, -10)
    elif message.text == ButtonText.TIME_PLUS_10:
        await process_offset_time(message, state, 10)
    elif message.text == ButtonText.TIME_PLUS_20:
        await process_offset_time(message, state, 20)
    elif message.text == ButtonText.CUSTOM_TIME:
        # Ask for day type first, then custom time
        await state.set_state(RouteStates.waiting_for_day_type)
        await message.answer("📅 Оберіть тип дня:", reply_markup=get_day_type_keyboard(include_cancel=True))
    else:
        await message.answer(
            "❌ Невідомий вибір. Оберіть з клавіатури.",
            reply_markup=get_time_choice_keyboard(),
        )


async def back_from_time_choice(message: types.Message, state: FSMContext):
    """Go back from time_choice - return to to_station selection."""
    data = await state.get_data()
    to_line = data.get("to_line", "Холодногірсько-заводська")
    from_station = data.get("from_station", "")

    router = get_router()
    stations = get_stations_by_line_except(router, to_line, from_station)

    await state.set_state(RouteStates.waiting_for_to_station)

    await message.answer(
        f"📍 Оберіть станцію на лінії {LINE_INTERNAL_TO_DISPLAY.get(to_line, to_line)}:",
        reply_markup=get_stations_keyboard(stations),
    )


async def cancel_from_time_choice(message: types.Message, state: FSMContext):
    """Cancel route building from time_choice."""
    await state.clear()
    await message.answer("❌ Побудову маршруту скасовано", reply_markup=get_main_keyboard())


# ===== Day Type (for custom time) Handlers =====


async def process_day_type_route(message: types.Message, state: FSMContext):
    """Process day type selection for custom time."""
    selected_day = DAY_TYPE_DISPLAY_TO_INTERNAL.get(message.text)
    if not selected_day:
        await message.answer(
            "❌ Невідомий вибір. Оберіть з клавіатури.",
            reply_markup=get_day_type_keyboard(include_cancel=True),
        )
        return

    await state.update_data(day_type=selected_day)
    await state.set_state(RouteStates.waiting_for_custom_time)
    await message.answer(
        "⌚ Введіть час у форматі ГГ:ХХ (наприклад: 14:30)",
        reply_markup=types.ReplyKeyboardRemove(),
    )


async def back_from_day_type_route(message: types.Message, state: FSMContext):
    """Go back from day_type - return to time_choice selection."""
    await state.set_state(RouteStates.waiting_for_time_choice)
    await message.answer("⏰ Який час?", reply_markup=get_time_choice_keyboard())


async def cancel_from_day_type_route(message: types.Message, state: FSMContext):
    """Cancel route building from day_type."""
    await state.clear()
    await message.answer("❌ Побудову маршруту скасовано", reply_markup=get_main_keyboard())


# ===== Custom Time Handlers =====


async def process_custom_time(message: types.Message, state: FSMContext):
    """Process custom time input."""
    time_input = message.text.strip()

    # Validate time format HH:MM
    if not re.match(r"^\d{1,2}:\d{2}$", time_input):
        await message.answer(
            "❌ Неправильний формат часу. Введіть у форматі ГГ:ХХ (наприклад: 14:30)",
            reply_markup=types.ReplyKeyboardRemove(),
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

        # Create datetime with custom time
        now = datetime.now()
        departure_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        await _build_and_send_route(
            message,
            state,
            from_station_name,
            to_station_name,
            departure_time,
            day_type_str,
        )

    except ValueError:
        await message.answer(
            "❌ Неправильний час. Введіть годину (0-23) та хвилини (0-59).\nНаприклад: 14:30",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return
    except Exception as e:
        await message.answer(f"❌ Помилка: {e}\nСпробуйте ще раз через /route", reply_markup=get_main_keyboard())
        await state.clear()


async def back_from_custom_time(message: types.Message, state: FSMContext):
    """Go back from custom_time - return to day_type selection."""
    await state.set_state(RouteStates.waiting_for_day_type)
    await message.answer("📅 Оберіть тип дня:", reply_markup=get_day_type_keyboard(include_cancel=True))


# ===== Route Building Logic =====


async def process_current_time(message: types.Message, state: FSMContext):
    """Process current time selection."""
    data = await state.get_data()
    from_station_name = data.get("from_station")
    to_station_name = data.get("to_station")
    day_type_str = "weekday" if datetime.now().weekday() < 5 else "weekend"

    departure_time = datetime.now()

    await _build_and_send_route(
        message,
        state,
        from_station_name,
        to_station_name,
        departure_time,
        day_type_str,
    )


async def process_offset_time(message: types.Message, state: FSMContext, offset_minutes: int):
    """Process time with offset (+/- minutes) from current time."""
    from datetime import timedelta

    data = await state.get_data()
    from_station_name = data.get("from_station")
    to_station_name = data.get("to_station")
    day_type_str = "weekday" if datetime.now().weekday() < 5 else "weekend"

    departure_time = datetime.now() + timedelta(minutes=offset_minutes)

    await _build_and_send_route(
        message,
        state,
        from_station_name,
        to_station_name,
        departure_time,
        day_type_str,
    )


async def _build_and_send_route(
    message: types.Message,
    state: FSMContext,
    from_station_name: str,
    to_station_name: str,
    departure_time: datetime,
    day_type_str: str,
):
    """Build route and send result with reminder buttons."""
    try:
        router = get_router()
        from_st = router.find_station_by_name(from_station_name, "ua")
        to_st = router.find_station_by_name(to_station_name, "ua")

        if not from_st:
            await message.answer(
                f"❌ Станцію не знайдено: {from_station_name}\nСпробуйте ще раз через /route",
                reply_markup=get_main_keyboard(),
            )
            await state.clear()
            return

        if not to_st:
            await message.answer(
                f"❌ Станцію не знайдено: {to_station_name}\nСпробуйте ще раз через /route",
                reply_markup=get_main_keyboard(),
            )
            await state.clear()
            return

        dt = get_day_type_from_string(day_type_str)
        route = router.find_route(from_st.id, to_st.id, departure_time, dt)

        if not route:
            await message.answer("❌ Маршрут не знайдено\nСпробуйте інші станції.", reply_markup=get_main_keyboard())
            await state.clear()
            return

        result = format_route(route)

        # Build line groups for reminder buttons
        line_groups = build_line_groups(route)

        # Store route for callback lookup
        route_key = generate_route_key(route)
        _active_routes[route_key] = (route, line_groups)

        # Build reminder keyboard only if there's at least one line with 2+ stations
        has_long_line = any(len(segments) > 1 for segments in line_groups.values())
        if has_long_line:
            reminder_kb = build_reminder_keyboard(route_key, line_groups)
        else:
            reminder_kb = None

        if reminder_kb and reminder_kb.inline_keyboard:
            await message.answer(result, reply_markup=reminder_kb)
        else:
            await message.answer(result)

        await message.answer("🏠 Головне меню", reply_markup=get_main_keyboard())

    except Exception as e:
        await message.answer(f"❌ Помилка: {e}\nСпробуйте ще раз через /route", reply_markup=get_main_keyboard())

    await state.clear()


# ===== Reminder Callback Handler =====


async def process_reminder(callback: types.CallbackQuery):
    """Process reminder request - schedules for arrival at previous station."""
    # Parse callback data: remind|{route_key}|{index}|{arrival_ts}
    parts = callback.data.split("|")

    # Handle old format (for backward compatibility with old buttons)
    if len(parts) == 5 and ":" in parts[1]:
        await callback.answer("❌ Ця кнопка застаріла. Будь ласка, побудуйте маршрут знову.")
        return

    route_key = parts[1] if len(parts) > 1 else ""
    try:
        segment_idx = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        await callback.answer("❌ Помилка: неправильний формат даних")
        return
    arrival_ts = int(parts[3]) if len(parts) > 3 else 0

    # Get route and line_groups from active routes
    route_data = _active_routes.get(route_key)
    if not route_data:
        await callback.answer("❌ Помилка: маршрут не знайдено або застарів")
        return
    route, line_groups = route_data

    # segment_idx is index in line_groups (line_idx from creation)
    line_ids = list(line_groups.keys())
    if segment_idx < 0 or segment_idx >= len(line_ids):
        await callback.answer("❌ Помилка: неправильний індекс лінії")
        return

    line_id = line_ids[segment_idx]
    segments = line_groups[line_id]

    # Get the target segment (second-to-last if multiple, or the only one)
    if len(segments) >= 2:
        target_segment = segments[-2]  # Second-to-last segment
    else:
        target_segment = segments[0]

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
    now = datetime.now()
    # Use departure time from the last segment's from_station (second-to-last station of the line)
    if len(segments) >= 1:
        remind_time = segments[-1].departure_time
    else:
        remind_time = None

    if remind_time:
        wait_seconds = (remind_time - now).total_seconds()
        remind_time_str = remind_time.strftime("%H:%M")
    else:
        wait_seconds = 0
        remind_time_str = None

    # Rebuild keyboard with updated button text for clicked button
    new_kb = build_reminder_keyboard(route_key, line_groups, clicked_idx=segment_idx, remind_time=remind_time_str)

    await callback.message.edit_reply_markup(reply_markup=new_kb)
    await callback.answer("✅ Нагадування встановлено!")

    if wait_seconds > 0:
        # Wait until arrival time
        await asyncio.sleep(wait_seconds)

        # Send reminder if still pending
        if user_id in pending_reminders:
            del pending_reminders[user_id]
            # Get the last station of this line group (where user needs to exit)
            last_station = segments[-1].to_station
            await callback.message.answer(f"⏰ Готуйтесь виходити на наступній станції: {last_station.name_ua}")


async def cancel_reminder(callback: types.CallbackQuery):
    """Cancel reminder."""
    # Parse callback data: remind_cancel|{route_key}|{idx}
    parts = callback.data.split("|")

    route_key = parts[1] if len(parts) > 1 else ""
    try:
        segment_idx = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        await callback.answer("❌ Помилка: неправильний формат даних")
        return

    # Get route and line_groups from active routes
    route_data = _active_routes.get(route_key)
    if not route_data:
        await callback.answer("❌ Помилка: маршрут не знайдено або він застарів")
        return
    route, line_groups = route_data

    # Remove reminder from pending
    user_id = callback.from_user.id
    if user_id in pending_reminders:
        del pending_reminders[user_id]

    # Rebuild keyboard - revert to original button
    new_kb = build_reminder_keyboard(route_key, line_groups)

    await callback.message.edit_reply_markup(reply_markup=new_kb)
    await callback.answer("❌ Нагадування скасовано!")


# ===== Trigger Command =====


# ===== Registration =====


def register_route_handlers(dp: Dispatcher):
    """Register route handlers."""
    # Command handlers
    dp.message.register(cmd_route, Command("route"))

    # From line state handlers
    dp.message.register(back_from_line, RouteStates.waiting_for_from_line, F.text == ButtonText.BACK)
    dp.message.register(cancel_from_line, RouteStates.waiting_for_from_line, F.text == ButtonText.CANCEL)
    dp.message.register(process_from_line, RouteStates.waiting_for_from_line)

    # From station state handlers
    dp.message.register(back_from_station, RouteStates.waiting_for_from_station, F.text == ButtonText.BACK)
    dp.message.register(cancel_from_station, RouteStates.waiting_for_from_station, F.text == ButtonText.CANCEL)
    dp.message.register(process_from_station, RouteStates.waiting_for_from_station)

    # To line state handlers
    dp.message.register(back_to_line, RouteStates.waiting_for_to_line, F.text == ButtonText.BACK)
    dp.message.register(cancel_to_line, RouteStates.waiting_for_to_line, F.text == ButtonText.CANCEL)
    dp.message.register(process_to_line, RouteStates.waiting_for_to_line)

    # To station state handlers
    dp.message.register(back_to_station, RouteStates.waiting_for_to_station, F.text == ButtonText.BACK)
    dp.message.register(cancel_to_station, RouteStates.waiting_for_to_station, F.text == ButtonText.CANCEL)
    dp.message.register(process_to_station, RouteStates.waiting_for_to_station)

    # Time choice state handlers
    dp.message.register(back_from_time_choice, RouteStates.waiting_for_time_choice, F.text == ButtonText.BACK)
    dp.message.register(cancel_from_time_choice, RouteStates.waiting_for_time_choice, F.text == ButtonText.CANCEL)
    dp.message.register(process_time_choice, RouteStates.waiting_for_time_choice)

    # Day type state handlers
    dp.message.register(back_from_day_type_route, RouteStates.waiting_for_day_type, F.text == ButtonText.BACK)
    dp.message.register(cancel_from_day_type_route, RouteStates.waiting_for_day_type, F.text == ButtonText.CANCEL)
    dp.message.register(process_day_type_route, RouteStates.waiting_for_day_type)

    # Custom time state handlers
    dp.message.register(back_from_custom_time, RouteStates.waiting_for_custom_time, F.text == ButtonText.BACK)
    dp.message.register(process_custom_time, RouteStates.waiting_for_custom_time)

    # Callback query handler for reminders
    dp.callback_query.register(process_reminder, F.data.startswith("remind|"))
    dp.callback_query.register(cancel_reminder, F.data.startswith("remind_cancel|"))
