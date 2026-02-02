"""Telegram bot entry point."""

import asyncio
import os
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kharkiv_metro_rp.config import Config
from kharkiv_metro_rp.core.router import MetroRouter
from kharkiv_metro_rp.data.database import MetroDatabase
from kharkiv_metro_rp.data.initializer import init_database

# Load .env from project root
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN not found in .env file")

# Initialize bot and dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def get_db_path() -> str:
    """Get database path using Config."""
    config = Config()
    config.ensure_dirs()
    return config.get_db_path()


class RouteStates(StatesGroup):
    """States for route command."""

    waiting_for_from_line = State()
    waiting_for_from_station = State()
    waiting_for_to_line = State()
    waiting_for_to_station = State()
    waiting_for_day_type = State()
    waiting_for_time_choice = State()
    waiting_for_custom_time = State()


class ScheduleStates(StatesGroup):
    """States for schedule command."""

    waiting_for_line = State()
    waiting_for_station = State()
    waiting_for_day_type = State()


class StationsStates(StatesGroup):
    """States for stations command."""

    waiting_for_line = State()


def get_router() -> MetroRouter:
    """Get MetroRouter instance."""
    db_path = get_db_path()

    # Auto-initialize database if it doesn't exist
    if not Path(db_path).exists():
        init_database(db_path)

    db = MetroDatabase(db_path)
    router = MetroRouter(db=db)
    return router


def format_route(route) -> str:
    """Format route compactly for Telegram with times on segments."""
    lines = []
    # Header: From → To
    lines.append(f"🚇 {route.segments[0].from_station.name_ua} → {route.segments[-1].to_station.name_ua}")
    lines.append(f"⏱ {route.total_duration_minutes} хв")
    lines.append("")

    # Group consecutive segments by line for compact view
    i = 0
    while i < len(route.segments):
        segment = route.segments[i]

        if segment.is_transfer:
            # Transfer - single line
            lines.append(
                f"🔄 {segment.from_station.name_ua} → {segment.to_station.name_ua} ({segment.duration_minutes} хв)\n"
            )
            i += 1
        else:
            # Travel segment - find all consecutive segments on same line
            line = segment.from_station.line
            color_emoji = {"red": "🔴", "blue": "🔵", "green": "🟢"}.get(line.color, "⚪")
            line_name = line.display_name_ua

            # Start of this line section
            start_station = segment.from_station
            start_time = segment.departure_time

            # Find end of this line section
            end_station = segment.to_station
            end_time = segment.arrival_time
            total_duration = segment.duration_minutes

            i += 1
            while i < len(route.segments) and not route.segments[i].is_transfer:
                # Continue on same line
                end_station = route.segments[i].to_station
                end_time = route.segments[i].arrival_time
                total_duration += route.segments[i].duration_minutes
                i += 1

            # Format with times
            from_name = start_station.name_ua
            to_name = end_station.name_ua

            if start_time and end_time:
                dep = start_time.strftime("%H:%M")
                arr = end_time.strftime("%H:%M")
                time_str = f"{dep} → {arr}"
            else:
                time_str = f"{total_duration} хв"

            lines.append(f"{color_emoji} {from_name} → {to_name}")
            lines.append(f"• {time_str} ({total_duration} хв)\n")

    return "\n".join(lines)


def format_schedule(station_name: str, schedules: list, router: MetroRouter) -> str:
    """Format schedule for Telegram."""
    lines = []
    lines.append(f"🚇 {station_name}")
    lines.append(f"📅 {'Будні' if schedules[0].day_type.value == 'weekday' else 'Вихідні'}")
    lines.append("")

    for sch in schedules[:2]:  # Show up to 2 directions
        dir_station = router.stations.get(sch.direction_station_id)
        if dir_station:
            dir_name = dir_station.name_ua
            lines.append(f"➡️ Напрямок: {dir_name}")

            # Group by hour
            by_hour = {}
            for entry in sch.entries:
                if entry.hour not in by_hour:
                    by_hour[entry.hour] = []
                by_hour[entry.hour].append(entry.minutes)

            for hour in sorted(by_hour.keys()):
                minutes = ", ".join(f"{m:02d}" for m in sorted(by_hour[hour]))
                lines.append(f"{hour:02d}: {minutes}")

            lines.append("")

    return "\n".join(lines)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Handle /start command."""
    await message.answer(
        "🚇 Бот для планування маршрутів Харківського метро\n\nОберіть дію:",
        reply_markup=get_main_keyboard(),
    )


@dp.message(F.text == "🚇 Маршрут")
async def menu_route(message: types.Message, state: FSMContext):
    """Handle route button from menu."""
    await cmd_route(message, state)


def get_day_type_keyboard() -> types.ReplyKeyboardMarkup:
    """Create keyboard for day type selection."""
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    keyboard = [
        [KeyboardButton(text="📅 Будні")],
        [KeyboardButton(text="🎉 Вихідні")],
        [KeyboardButton(text="🔙 Назад"), KeyboardButton(text="❌ Скасувати")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


@dp.message(F.text == "📅 Розклад")
async def menu_schedule(message: types.Message, state: FSMContext):
    """Handle schedule button from menu."""
    await state.set_state(ScheduleStates.waiting_for_line)
    await message.answer(
        "📅 Оберіть лінію метро:",
        reply_markup=get_lines_keyboard(),
    )


@dp.message(ScheduleStates.waiting_for_line, F.text == "🔙 Назад")
async def back_from_schedule_line(message: types.Message, state: FSMContext):
    """Go back from schedule line - return to main menu."""
    await state.clear()
    await message.answer("🏠 Головне меню", reply_markup=get_main_keyboard())


@dp.message(ScheduleStates.waiting_for_line, F.text == "❌ Скасувати")
async def cancel_from_schedule_line(message: types.Message, state: FSMContext):
    """Cancel schedule lookup from line."""
    await state.clear()
    await message.answer("❌ Перегляд розкладу скасовано", reply_markup=get_main_keyboard())


@dp.message(ScheduleStates.waiting_for_line)
async def process_schedule_line(message: types.Message, state: FSMContext):
    """Process line selection for schedule."""
    line_map = {
        "🔴 Холодногірсько-Заводська": "Холодногірсько-заводська",
        "🔵 Салтівська": "Салтівська",
        "🟢 Олексіївська": "Олексіївська",
    }

    selected_line = line_map.get(message.text)
    if not selected_line:
        await message.answer(
            "❌ Невідома лінія. Оберіть з клавіатури.",
            reply_markup=get_lines_keyboard(),
        )
        return

    await state.update_data(schedule_line=selected_line)
    await state.set_state(ScheduleStates.waiting_for_station)

    router = get_router()
    stations = []
    for st in router.stations.values():
        if st.line.display_name_ua == selected_line:
            stations.append(st.name_ua)

    stations.sort()

    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    keyboard = []
    for i in range(0, len(stations), 2):
        row = [KeyboardButton(text=st) for st in stations[i : i + 2]]
        keyboard.append(row)
    keyboard.append([KeyboardButton(text="🔙 Назад"), KeyboardButton(text="❌ Скасувати")])

    await message.answer(
        f"📍 Оберіть станцію на лінії {message.text}:",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True),
    )


@dp.message(ScheduleStates.waiting_for_station, F.text == "❌ Скасувати")
async def cancel_from_schedule_station(message: types.Message, state: FSMContext):
    """Cancel schedule lookup from station."""
    await state.clear()
    await message.answer("❌ Перегляд розкладу скасовано", reply_markup=get_main_keyboard())


@dp.message(ScheduleStates.waiting_for_station, F.text == "🔙 Назад")
async def back_from_schedule_station(message: types.Message, state: FSMContext):
    """Go back from schedule station - return to line selection."""
    await state.set_state(ScheduleStates.waiting_for_line)
    await message.answer(
        "📅 Оберіть лінію метро:",
        reply_markup=get_lines_keyboard(),
    )


@dp.message(ScheduleStates.waiting_for_station)
async def process_schedule_station(message: types.Message, state: FSMContext):
    """Process station selection for schedule."""
    await state.update_data(schedule_station=message.text)
    await state.set_state(ScheduleStates.waiting_for_day_type)
    await message.answer(
        "📅 Оберіть тип дня:",
        reply_markup=get_day_type_keyboard(),
    )


@dp.message(ScheduleStates.waiting_for_day_type, F.text == "❌ Скасувати")
async def cancel_from_day_type(message: types.Message, state: FSMContext):
    """Cancel schedule lookup from day_type."""
    await state.clear()
    await message.answer("❌ Перегляд розкладу скасовано", reply_markup=get_main_keyboard())


@dp.message(ScheduleStates.waiting_for_day_type, F.text == "🔙 Назад")
async def back_from_day_type(message: types.Message, state: FSMContext):
    """Go back from day type - return to station selection."""
    data = await state.get_data()
    schedule_line = data.get("schedule_line", "Холодногірсько-заводська")

    router = get_router()
    stations = []
    for st in router.stations.values():
        if st.line.display_name_ua == schedule_line:
            stations.append(st.name_ua)

    stations.sort()

    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    keyboard = []
    for i in range(0, len(stations), 2):
        row = [KeyboardButton(text=st) for st in stations[i : i + 2]]
        keyboard.append(row)
    keyboard.append([KeyboardButton(text="🔙 Назад"), KeyboardButton(text="❌ Скасувати")])

    await state.set_state(ScheduleStates.waiting_for_station)

    line_display_map = {
        "Холодногірсько-заводська": "🔴 Холодногірсько-Заводська",
        "Салтівська": "🔵 Салтівська",
        "Олексіївська": "🟢 Олексіївська",
    }

    await message.answer(
        f"📍 Оберіть станцію на лінії {line_display_map.get(schedule_line, schedule_line)}:",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True),
    )


@dp.message(ScheduleStates.waiting_for_day_type)
async def process_day_type(message: types.Message, state: FSMContext):
    """Process day type selection and show schedule."""
    day_type_map = {
        "📅 Будні": "weekday",
        "🎉 Вихідні": "weekend",
    }

    selected_day = day_type_map.get(message.text)
    if not selected_day:
        await message.answer(
            "❌ Невідомий вибір. Оберіть з клавіатури.",
            reply_markup=get_day_type_keyboard(),
        )
        return

    data = await state.get_data()
    station_name = data.get("schedule_station", "")

    try:
        router = get_router()
        from kharkiv_metro_rp.core.models import DayType

        st = router.find_station_by_name(station_name, "ua")
        if not st:
            await message.answer(
                f"❌ Станцію не знайдено: {station_name}",
                reply_markup=get_main_keyboard(),
            )
            await state.clear()
            return

        dt = DayType.WEEKDAY if selected_day == "weekday" else DayType.WEEKEND
        schedules = router.get_station_schedule(st.id, None, dt)

        if not schedules:
            await message.answer(
                "❌ Розклад не знайдено",
                reply_markup=get_main_keyboard(),
            )
            await state.clear()
            return

        result = format_schedule(st.name_ua, schedules, router)
        await message.answer(result, reply_markup=get_main_keyboard())

    except Exception as e:
        await message.answer(f"❌ Помилка: {e}", reply_markup=get_main_keyboard())

    await state.clear()


@dp.message(F.text == "📋 Станції")
async def menu_stations(message: types.Message, state: FSMContext):
    """Handle stations button from menu."""
    await state.set_state(StationsStates.waiting_for_line)
    await message.answer(
        "📋 Оберіть лінію метро:",
        reply_markup=get_lines_keyboard(),
    )


@dp.message(StationsStates.waiting_for_line, F.text == "🔙 Назад")
async def back_from_stations_line(message: types.Message, state: FSMContext):
    """Go back from stations line - return to main menu."""
    await state.clear()
    await message.answer("🏠 Головне меню", reply_markup=get_main_keyboard())


@dp.message(StationsStates.waiting_for_line, F.text == "❌ Скасувати")
async def cancel_stations(message: types.Message, state: FSMContext):
    """Cancel stations lookup."""
    await state.clear()
    await message.answer("❌ Перегляд станцій скасовано", reply_markup=get_main_keyboard())


@dp.message(StationsStates.waiting_for_line)
async def process_line_selection(message: types.Message, state: FSMContext):
    """Process line selection and show stations."""

    line_map = {
        "🔴 Холодногірсько-Заводська": "Холодногірсько-заводська",
        "🔵 Салтівська": "Салтівська",
        "🟢 Олексіївська": "Олексіївська",
    }

    selected_line = line_map.get(message.text)
    if not selected_line:
        await message.answer(
            "❌ Невідома лінія. Оберіть з клавіатури.",
            reply_markup=get_lines_keyboard(),
        )
        return

    try:
        router = get_router()
        stations = []
        for station in router.stations.values():
            if station.line.display_name_ua == selected_line:
                stations.append(station.name_ua)

        color_emoji = {"Холодногірсько-заводська": "🔴", "Салтівська": "🔵", "Олексіївська": "🟢"}
        emoji = color_emoji.get(selected_line, "⚪")

        lines = [f"{emoji} {selected_line}:\n"]
        for st_name in stations:
            lines.append(f"  • {st_name}")

        result = "\n".join(lines)
        await message.answer(result, reply_markup=get_main_keyboard())

    except Exception as e:
        await message.answer(f"❌ Помилка: {e}", reply_markup=get_main_keyboard())

    await state.clear()


def get_main_keyboard() -> types.ReplyKeyboardMarkup:
    """Create main menu keyboard."""
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    keyboard = [
        [KeyboardButton(text="🚇 Маршрут"), KeyboardButton(text="📅 Розклад")],
        [KeyboardButton(text="📋 Станції")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_stations_keyboard_by_line(router: MetroRouter, exclude_station: str | None = None) -> types.ReplyKeyboardMarkup:
    """Create reply keyboard with stations grouped by line."""
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    # Get all stations and sort by line order (must match database format)
    line_order = ["Холодногірсько-заводська", "Салтівська", "Олексіївська"]

    # Group stations by line using line_id to ensure correct grouping
    lines_stations: dict[str, list[str]] = {line: [] for line in line_order}

    for st in router.stations.values():
        line_name = st.line.display_name_ua
        if line_name in lines_stations and (exclude_station is None or st.name_ua != exclude_station):
            lines_stations[line_name].append(st.name_ua)

    # Build keyboard: stations grouped by line (2 per row)
    keyboard = []

    for line_name in line_order:
        stations = lines_stations[line_name]
        # Sort stations to have consistent order
        stations.sort()
        for i in range(0, len(stations), 2):
            row = [KeyboardButton(text=st) for st in stations[i : i + 2]]
            keyboard.append(row)

    keyboard.append([KeyboardButton(text="🔙 Назад"), KeyboardButton(text="❌ Скасувати")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def get_cancel_keyboard() -> types.ReplyKeyboardMarkup:
    """Create keyboard with back button only."""
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    keyboard = [[KeyboardButton(text="🔙 Назад"), KeyboardButton(text="❌ Скасувати")]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def get_lines_keyboard() -> types.ReplyKeyboardMarkup:
    """Create keyboard with line selection."""
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    keyboard = [
        [KeyboardButton(text="🔴 Холодногірсько-Заводська")],
        [KeyboardButton(text="🔵 Салтівська")],
        [KeyboardButton(text="🟢 Олексіївська")],
        [KeyboardButton(text="🔙 Назад"), KeyboardButton(text="❌ Скасувати")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


@dp.message(Command("route"))
async def cmd_route(message: types.Message, state: FSMContext):
    """Start route conversation."""
    await state.set_state(RouteStates.waiting_for_from_line)
    await message.answer(
        "📍 Звідки їдемо? Спочатку оберіть лінію:",
        reply_markup=get_lines_keyboard(),
    )


@dp.message(RouteStates.waiting_for_from_line, F.text == "❌ Скасувати")
async def cancel_from_line(message: types.Message, state: FSMContext):
    """Cancel route building from from_line."""
    await state.clear()
    await message.answer("❌ Побудову маршруту скасовано", reply_markup=get_main_keyboard())


@dp.message(RouteStates.waiting_for_from_line, F.text == "🔙 Назад")
async def back_from_line(message: types.Message, state: FSMContext):
    """Go back from from_line - return to main menu."""
    await state.clear()
    await message.answer("🏠 Головне меню", reply_markup=get_main_keyboard())


@dp.message(RouteStates.waiting_for_from_line)
async def process_from_line(message: types.Message, state: FSMContext):
    """Process line selection for 'from' station."""
    line_map = {
        "🔴 Холодногірсько-Заводська": "Холодногірсько-заводська",
        "🔵 Салтівська": "Салтівська",
        "🟢 Олексіївська": "Олексіївська",
    }

    selected_line = line_map.get(message.text)
    if not selected_line:
        await message.answer(
            "❌ Невідома лінія. Оберіть з клавіатури.",
            reply_markup=get_lines_keyboard(),
        )
        return

    await state.update_data(from_line=selected_line)
    await state.set_state(RouteStates.waiting_for_from_station)

    router = get_router()
    stations = []
    for st in router.stations.values():
        if st.line.display_name_ua == selected_line:
            stations.append(st.name_ua)

    stations.sort()

    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    keyboard = []
    for i in range(0, len(stations), 2):
        row = [KeyboardButton(text=st) for st in stations[i : i + 2]]
        keyboard.append(row)
    keyboard.append([KeyboardButton(text="🔙 Назад"), KeyboardButton(text="❌ Скасувати")])

    await message.answer(
        f"📍 Оберіть станцію на лінії {message.text}:",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True),
    )


@dp.message(RouteStates.waiting_for_from_station, F.text == "❌ Скасувати")
async def cancel_from_station(message: types.Message, state: FSMContext):
    """Cancel route building from from_station."""
    await state.clear()
    await message.answer("❌ Побудову маршруту скасовано", reply_markup=get_main_keyboard())


@dp.message(RouteStates.waiting_for_from_station, F.text == "🔙 Назад")
async def back_from_station(message: types.Message, state: FSMContext):
    """Go back from from_station - return to from_line selection."""
    await state.set_state(RouteStates.waiting_for_from_line)
    await message.answer(
        "📍 Звідки їдемо? Спочатку оберіть лінію:",
        reply_markup=get_lines_keyboard(),
    )


@dp.message(RouteStates.waiting_for_from_station)
async def process_from_station(message: types.Message, state: FSMContext):
    """Process from station - now ask for to_line."""
    await state.update_data(from_station=message.text)
    await state.set_state(RouteStates.waiting_for_to_line)
    await message.answer(
        "📍 Куди їдемо? Спочатку оберіть лінію:",
        reply_markup=get_lines_keyboard(),
    )


@dp.message(RouteStates.waiting_for_to_line, F.text == "❌ Скасувати")
async def cancel_to_line(message: types.Message, state: FSMContext):
    """Cancel route building from to_line."""
    await state.clear()
    await message.answer("❌ Побудову маршруту скасовано", reply_markup=get_main_keyboard())


@dp.message(RouteStates.waiting_for_to_line, F.text == "🔙 Назад")
async def back_to_line(message: types.Message, state: FSMContext):
    """Go back from to_line - return to from_station selection."""
    data = await state.get_data()
    from_line = data.get("from_line", "Холодногірсько-заводська")

    router = get_router()
    stations = []
    for st in router.stations.values():
        if st.line.display_name_ua == from_line:
            stations.append(st.name_ua)
    stations.sort()

    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    keyboard = []
    for i in range(0, len(stations), 2):
        row = [KeyboardButton(text=st) for st in stations[i : i + 2]]
        keyboard.append(row)
    keyboard.append([KeyboardButton(text="🔙 Назад"), KeyboardButton(text="❌ Скасувати")])

    await state.set_state(RouteStates.waiting_for_from_station)

    line_display_map = {
        "Холодногірсько-заводська": "🔴 Холодногірсько-Заводська",
        "Салтівська": "🔵 Салтівська",
        "Олексіївська": "🟢 Олексіївська",
    }

    await message.answer(
        f"📍 Оберіть станцію на лінії {line_display_map.get(from_line, from_line)}:",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True),
    )


@dp.message(RouteStates.waiting_for_to_line)
async def process_to_line(message: types.Message, state: FSMContext):
    """Process line selection for 'to' station."""
    line_map = {
        "🔴 Холодногірсько-Заводська": "Холодногірсько-заводська",
        "🔵 Салтівська": "Салтівська",
        "🟢 Олексіївська": "Олексіївська",
    }

    selected_line = line_map.get(message.text)
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
    stations = []
    for st in router.stations.values():
        if st.line.display_name_ua == selected_line and st.name_ua != from_station:
            stations.append(st.name_ua)

    stations.sort()

    # Build keyboard with stations on selected line
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    keyboard = []
    for i in range(0, len(stations), 2):
        row = [KeyboardButton(text=st) for st in stations[i : i + 2]]
        keyboard.append(row)
    keyboard.append([KeyboardButton(text="🔙 Назад"), KeyboardButton(text="❌ Скасувати")])

    await message.answer(
        f"📍 Оберіть станцію на лінії {message.text}:",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True),
    )


@dp.message(RouteStates.waiting_for_to_station, F.text == "❌ Скасувати")
async def cancel_to_station(message: types.Message, state: FSMContext):
    """Cancel route building from to_station."""
    await state.clear()
    await message.answer("❌ Побудову маршруту скасовано", reply_markup=get_main_keyboard())


@dp.message(RouteStates.waiting_for_to_station, F.text == "🔙 Назад")
async def back_to_station(message: types.Message, state: FSMContext):
    """Go back from to_station - return to to_line selection."""
    await state.set_state(RouteStates.waiting_for_to_line)
    await message.answer(
        "📍 Куди їдемо? Спочатку оберіть лінію:",
        reply_markup=get_lines_keyboard(),
    )


def get_day_type_keyboard() -> types.ReplyKeyboardMarkup:
    """Create keyboard for day type selection."""
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    keyboard = [
        [KeyboardButton(text="📅 Будні")],
        [KeyboardButton(text="🎉 Вихідні")],
        [KeyboardButton(text="🔙 Назад")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def get_time_choice_keyboard() -> types.ReplyKeyboardMarkup:
    """Create keyboard for time choice."""
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    keyboard = [
        [KeyboardButton(text="🕐 Поточний час")],
        [KeyboardButton(text="⌚ Свій час")],
        [KeyboardButton(text="🔙 Назад"), KeyboardButton(text="❌ Скасувати")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


@dp.message(RouteStates.waiting_for_to_station)
async def process_to_station(message: types.Message, state: FSMContext):
    """Process to station and ask for time choice."""
    await state.update_data(to_station=message.text)
    await state.set_state(RouteStates.waiting_for_time_choice)
    await message.answer("⏰ Який час?", reply_markup=get_time_choice_keyboard())


@dp.message(RouteStates.waiting_for_time_choice, F.text == "❌ Скасувати")
async def cancel_from_time_choice(message: types.Message, state: FSMContext):
    """Cancel route building from time_choice."""
    await state.clear()
    await message.answer("❌ Побудову маршруту скасовано", reply_markup=get_main_keyboard())


@dp.message(RouteStates.waiting_for_time_choice, F.text == "🔙 Назад")
async def back_from_time_choice(message: types.Message, state: FSMContext):
    """Go back from time_choice - return to to_station selection."""
    data = await state.get_data()
    to_line = data.get("to_line", "Холодногірсько-заводська")
    from_station = data.get("from_station", "")

    router = get_router()
    stations = []
    for st in router.stations.values():
        if st.line.display_name_ua == to_line and st.name_ua != from_station:
            stations.append(st.name_ua)
    stations.sort()

    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    keyboard = []
    for i in range(0, len(stations), 2):
        row = [KeyboardButton(text=st) for st in stations[i : i + 2]]
        keyboard.append(row)
    keyboard.append([KeyboardButton(text="🔙 Назад")])

    await state.set_state(RouteStates.waiting_for_to_station)

    line_display_map = {
        "Холодногірсько-заводська": "🔴 Холодногірсько-Заводська",
        "Салтівська": "🔵 Салтівська",
        "Олексіївська": "🟢 Олексіївська",
    }

    await message.answer(
        f"📍 Оберіть станцію на лінії {line_display_map.get(to_line, to_line)}:",
        reply_markup=ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True),
    )


@dp.message(RouteStates.waiting_for_time_choice)
async def process_time_choice(message: types.Message, state: FSMContext):
    """Process time choice selection."""
    if message.text == "🕐 Поточний час":
        # Use current time and day type
        await process_current_time(message, state)
    elif message.text == "⌚ Свій час":
        # Ask for day type first, then custom time
        await state.set_state(RouteStates.waiting_for_day_type)
        await message.answer("📅 Оберіть тип дня:", reply_markup=get_day_type_keyboard())
    else:
        await message.answer(
            "❌ Невідомий вибір. Оберіть з клавіатури.",
            reply_markup=get_time_choice_keyboard(),
        )


@dp.message(RouteStates.waiting_for_day_type, F.text == "❌ Скасувати")
async def cancel_from_day_type_route(message: types.Message, state: FSMContext):
    """Cancel route building from day_type."""
    await state.clear()
    await message.answer("❌ Побудову маршруту скасовано", reply_markup=get_main_keyboard())


@dp.message(RouteStates.waiting_for_day_type, F.text == "🔙 Назад")
async def back_from_day_type_route(message: types.Message, state: FSMContext):
    """Go back from day_type - return to time_choice selection."""
    await state.set_state(RouteStates.waiting_for_time_choice)
    await message.answer("⏰ Який час?", reply_markup=get_time_choice_keyboard())


@dp.message(RouteStates.waiting_for_day_type)
async def process_day_type_route(message: types.Message, state: FSMContext):
    """Process day type selection for custom time."""
    day_type_map = {
        "📅 Будні": "weekday",
        "🎉 Вихідні": "weekend",
    }

    selected_day = day_type_map.get(message.text)
    if not selected_day:
        await message.answer(
            "❌ Невідомий вибір. Оберіть з клавіатури.",
            reply_markup=get_day_type_keyboard(),
        )
        return

    await state.update_data(day_type=selected_day)
    await state.set_state(RouteStates.waiting_for_custom_time)
    await message.answer("⌚ Введіть час у форматі ГГ:ХХ (наприклад: 14:30)", reply_markup=types.ReplyKeyboardRemove())


async def process_current_time(message: types.Message, state: FSMContext):
    """Process current time selection."""
    from datetime import datetime

    data = await state.get_data()
    from_station = data.get("from_station")
    to_station = data.get("to_station")
    # For current time, determine day type from today
    day_type = "weekday" if datetime.now().weekday() < 5 else "weekend"

    try:
        router = get_router()
        from_st = router.find_station_by_name(from_station, "ua")
        to_st = router.find_station_by_name(to_station, "ua")

        if not from_st:
            await message.answer(
                f"❌ Станцію не знайдено: {from_station}\nСпробуйте ще раз через /route",
                reply_markup=get_main_keyboard(),
            )
            await state.clear()
            return

        if not to_st:
            await message.answer(
                f"❌ Станцію не знайдено: {to_station}\nСпробуйте ще раз через /route", reply_markup=get_main_keyboard()
            )
            await state.clear()
            return

        from kharkiv_metro_rp.core.models import DayType

        dt = DayType.WEEKDAY if day_type == "weekday" else DayType.WEEKEND
        departure_time = datetime.now()
        route = router.find_route(from_st.id, to_st.id, departure_time, dt)

        if not route:
            await message.answer("❌ Маршрут не знайдено\nСпробуйте інші станції.", reply_markup=get_main_keyboard())
            await state.clear()
            return

        result = format_route(route)
        await message.answer(result, reply_markup=get_main_keyboard())

    except Exception as e:
        await message.answer(f"❌ Помилка: {e}\nСпробуйте ще раз через /route", reply_markup=get_main_keyboard())

    await state.clear()


@dp.message(RouteStates.waiting_for_custom_time, F.text == "🔙 Назад")
async def back_from_custom_time(message: types.Message, state: FSMContext):
    """Go back from custom_time - return to day_type selection."""
    await state.set_state(RouteStates.waiting_for_day_type)
    await message.answer("📅 Оберіть тип дня:", reply_markup=get_day_type_keyboard())


@dp.message(RouteStates.waiting_for_custom_time)
async def process_custom_time(message: types.Message, state: FSMContext):
    """Process custom time input."""
    import re
    from datetime import datetime

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
        from_station = data.get("from_station")
        to_station = data.get("to_station")
        day_type = data.get("day_type", "weekday")

        # Create datetime with custom time
        now = datetime.now()
        departure_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        router = get_router()
        from_st = router.find_station_by_name(from_station, "ua")
        to_st = router.find_station_by_name(to_station, "ua")

        if not from_st:
            await message.answer(
                f"❌ Станцію не знайдено: {from_station}\nСпробуйте ще раз через /route",
                reply_markup=get_main_keyboard(),
            )
            await state.clear()
            return

        if not to_st:
            await message.answer(
                f"❌ Станцію не знайдено: {to_station}\nСпробуйте ще раз через /route", reply_markup=get_main_keyboard()
            )
            await state.clear()
            return

        from kharkiv_metro_rp.core.models import DayType

        dt = DayType.WEEKDAY if day_type == "weekday" else DayType.WEEKEND
        route = router.find_route(from_st.id, to_st.id, departure_time, dt)

        if not route:
            await message.answer("❌ Маршрут не знайдено\nСпробуйте інші станції.", reply_markup=get_main_keyboard())
            await state.clear()
            return

        result = format_route(route)
        await message.answer(result, reply_markup=get_main_keyboard())

    except ValueError:
        await message.answer(
            "❌ Неправильний час. Введіть годину (0-23) та хвилини (0-59).\nНаприклад: 14:30",
            reply_markup=types.ReplyKeyboardRemove(),
        )
        return
    except Exception as e:
        await message.answer(f"❌ Помилка: {e}\nСпробуйте ще раз через /route", reply_markup=get_main_keyboard())

    await state.clear()


@dp.message(Command("schedule"))
async def cmd_schedule(message: types.Message, state: FSMContext):
    """Handle /schedule command."""
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await state.set_state(ScheduleStates.waiting_for_line)
        await message.answer(
            "📅 Оберіть лінію метро:",
            reply_markup=get_lines_keyboard(),
        )
        return

    station_name = args[1]

    try:
        router = get_router()
        from datetime import datetime

        from kharkiv_metro_rp.core.models import DayType

        st = router.find_station_by_name(station_name, "ua")
        if not st:
            await message.answer(f"❌ Станцію не знайдено: {station_name}", reply_markup=get_main_keyboard())
            return

        dt = DayType.WEEKDAY if datetime.now().weekday() < 5 else DayType.WEEKEND
        schedules = router.get_station_schedule(st.id, None, dt)

        if not schedules:
            await message.answer("❌ Розклад не знайдено", reply_markup=get_main_keyboard())
            return

        result = format_schedule(st.name_ua, schedules, router)
        await message.answer(result, reply_markup=get_main_keyboard())

    except Exception as e:
        await message.answer(f"❌ Помилка: {e}", reply_markup=get_main_keyboard())


@dp.message(Command("stations"))
async def cmd_stations(message: types.Message, state: FSMContext):
    """Handle /stations command."""
    await state.set_state(StationsStates.waiting_for_line)
    await message.answer(
        "📋 Оберіть лінію метро:",
        reply_markup=get_lines_keyboard(),
    )


def main():
    """Run the bot."""
    print("Starting bot...")
    asyncio.run(dp.start_polling(bot))


if __name__ == "__main__":
    main()
