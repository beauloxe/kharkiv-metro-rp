"""Schedule handlers for the Telegram bot."""

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
    get_day_type_keyboard,
    get_lines_keyboard,
    get_main_keyboard,
    get_stations_keyboard,
)
from ..states import ScheduleStates
from ..utils import (
    format_schedule,
    get_current_day_type,
    get_day_type_from_string,
    get_router,
    get_stations_by_line,
)


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
        st = router.find_station_by_name(station_name, "ua")
        if not st:
            await message.answer(f"❌ Станцію не знайдено: {station_name}", reply_markup=get_main_keyboard())
            return

        dt = get_current_day_type()
        schedules = router.get_station_schedule(st.id, None, dt)

        if not schedules:
            await message.answer("❌ Розклад не знайдено", reply_markup=get_main_keyboard())
            return

        result = format_schedule(st.name_ua, schedules, router)
        await message.answer(result, reply_markup=get_main_keyboard())

    except Exception as e:
        await message.answer(f"❌ Помилка: {e}", reply_markup=get_main_keyboard())


async def process_schedule_line(message: types.Message, state: FSMContext):
    """Process line selection for schedule."""
    selected_line = LINE_DISPLAY_TO_INTERNAL.get(message.text)
    if not selected_line:
        await message.answer(
            "❌ Невідома лінія. Оберіть з клавіатури.",
            reply_markup=get_lines_keyboard(),
        )
        return

    await state.update_data(schedule_line=selected_line)
    await state.set_state(ScheduleStates.waiting_for_station)

    router = get_router()
    stations = get_stations_by_line(router, selected_line)

    await message.answer(
        f"📍 Оберіть станцію на лінії {message.text}:",
        reply_markup=get_stations_keyboard(stations),
    )


async def back_from_schedule_line(message: types.Message, state: FSMContext):
    """Go back from schedule line - return to main menu."""
    await state.clear()
    await message.answer("🏠 Головне меню", reply_markup=get_main_keyboard())


async def cancel_from_schedule_line(message: types.Message, state: FSMContext):
    """Cancel schedule lookup from line."""
    await state.clear()
    await message.answer("❌ Перегляд розкладу скасовано", reply_markup=get_main_keyboard())


async def process_schedule_station(message: types.Message, state: FSMContext):
    """Process station selection for schedule."""
    await state.update_data(schedule_station=message.text)
    await state.set_state(ScheduleStates.waiting_for_day_type)
    await message.answer(
        "📅 Оберіть тип дня:",
        reply_markup=get_day_type_keyboard(),
    )


async def back_from_schedule_station(message: types.Message, state: FSMContext):
    """Go back from schedule station - return to line selection."""
    await state.set_state(ScheduleStates.waiting_for_line)
    await message.answer(
        "📅 Оберіть лінію метро:",
        reply_markup=get_lines_keyboard(),
    )


async def cancel_from_schedule_station(message: types.Message, state: FSMContext):
    """Cancel schedule lookup from station."""
    await state.clear()
    await message.answer("❌ Перегляд розкладу скасовано", reply_markup=get_main_keyboard())


async def process_day_type(message: types.Message, state: FSMContext):
    """Process day type selection and show schedule."""
    selected_day = DAY_TYPE_DISPLAY_TO_INTERNAL.get(message.text)
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
        st = router.find_station_by_name(station_name, "ua")
        if not st:
            await message.answer(
                f"❌ Станцію не знайдено: {station_name}",
                reply_markup=get_main_keyboard(),
            )
            await state.clear()
            return

        dt = get_day_type_from_string(selected_day)
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


async def back_from_day_type(message: types.Message, state: FSMContext):
    """Go back from day type - return to station selection."""
    data = await state.get_data()
    schedule_line = data.get("schedule_line", "Холодногірсько-заводська")

    router = get_router()
    stations = get_stations_by_line(router, schedule_line)

    await state.set_state(ScheduleStates.waiting_for_station)

    await message.answer(
        f"📍 Оберіть станцію на лінії {LINE_INTERNAL_TO_DISPLAY.get(schedule_line, schedule_line)}:",
        reply_markup=get_stations_keyboard(stations),
    )


async def cancel_from_day_type(message: types.Message, state: FSMContext):
    """Cancel schedule lookup from day_type."""
    await state.clear()
    await message.answer("❌ Перегляд розкладу скасовано", reply_markup=get_main_keyboard())


def register_schedule_handlers(dp: Dispatcher):
    """Register schedule handlers."""
    # Command handlers
    dp.message.register(cmd_schedule, Command("schedule"))

    # Line selection state handlers
    dp.message.register(back_from_schedule_line, ScheduleStates.waiting_for_line, F.text == ButtonText.BACK)
    dp.message.register(cancel_from_schedule_line, ScheduleStates.waiting_for_line, F.text == ButtonText.CANCEL)
    dp.message.register(process_schedule_line, ScheduleStates.waiting_for_line)

    # Station selection state handlers
    dp.message.register(cancel_from_schedule_station, ScheduleStates.waiting_for_station, F.text == ButtonText.CANCEL)
    dp.message.register(back_from_schedule_station, ScheduleStates.waiting_for_station, F.text == ButtonText.BACK)
    dp.message.register(process_schedule_station, ScheduleStates.waiting_for_station)

    # Day type selection state handlers
    dp.message.register(cancel_from_day_type, ScheduleStates.waiting_for_day_type, F.text == ButtonText.CANCEL)
    dp.message.register(back_from_day_type, ScheduleStates.waiting_for_day_type, F.text == ButtonText.BACK)
    dp.message.register(process_day_type, ScheduleStates.waiting_for_day_type)
