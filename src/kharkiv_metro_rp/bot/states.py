"""Finite State Machine states for the bot."""

from aiogram.fsm.state import State, StatesGroup


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
