"""Keyboard builders for the Telegram bot with i18n support."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from kharkiv_metro_core import Language, MetroRouter, get_line_display_name, get_text, load_metro_data

from .constants import LINE_ORDER

# Navigation button texts
NAV_BACK_TEXT = "back"
NAV_CANCEL_TEXT = "cancel"


def get_main_keyboard(lang: Language = "ua") -> ReplyKeyboardMarkup:
    """Create main menu keyboard."""
    keyboard = [
        [KeyboardButton(text=get_text("route", lang)), KeyboardButton(text=get_text("schedule", lang))],
        [KeyboardButton(text=get_text("stations", lang))],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def _add_nav_buttons(keyboard: list, lang: Language) -> list:
    """Add back and cancel buttons to keyboard."""
    keyboard.append([KeyboardButton(text=get_text("back", lang)), KeyboardButton(text=get_text("cancel", lang))])
    return keyboard


def get_lines_keyboard(lang: Language = "ua") -> ReplyKeyboardMarkup:
    """Create keyboard with line selection and navigation."""
    keyboard = [
        [KeyboardButton(text=get_line_display_name(line_key, lang))]
        for line_key in load_metro_data().line_order
    ]
    keyboard = _add_nav_buttons(keyboard, lang)
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def get_day_type_keyboard(lang: Language = "ua") -> ReplyKeyboardMarkup:
    """Create keyboard for day type selection with navigation."""
    keyboard = [
        [KeyboardButton(text=get_text("weekdays", lang))],
        [KeyboardButton(text=get_text("weekends", lang))],
    ]
    keyboard = _add_nav_buttons(keyboard, lang)
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def get_time_choice_keyboard(lang: Language = "ua") -> ReplyKeyboardMarkup:
    """Create keyboard for time choice with navigation."""
    keyboard = [
        [KeyboardButton(text=get_text("time_minus_20", lang)), KeyboardButton(text=get_text("time_minus_10", lang))],
        [KeyboardButton(text=get_text("current_time", lang))],
        [KeyboardButton(text=get_text("time_plus_10", lang)), KeyboardButton(text=get_text("time_plus_20", lang))],
        [KeyboardButton(text=get_text("custom_time", lang))],
    ]
    keyboard = _add_nav_buttons(keyboard, lang)
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def get_stations_keyboard(
    stations: list[str],
    lang: Language = "ua",
) -> ReplyKeyboardMarkup:
    """Create keyboard with stations list (2 per row) and navigation."""
    keyboard = []
    for i in range(0, len(stations), 2):
        row = [KeyboardButton(text=st) for st in stations[i : i + 2]]
        keyboard.append(row)

    keyboard = _add_nav_buttons(keyboard, lang)
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def _get_station_internal_name(router: MetroRouter, display_name: str) -> str | None:
    """Get internal (Ukrainian) station name from display name.

    Args:
        router: MetroRouter instance
        display_name: Station name in any language

    Returns:
        Internal Ukrainian name or None if not found
    """
    for st in router.stations.values():
        if st.name_ua == display_name or st.name_en == display_name:
            return st.name_ua
    return None


def get_stations_keyboard_by_line(
    router: MetroRouter,
    lang: Language = "ua",
    exclude_station: str | None = None,
) -> ReplyKeyboardMarkup:
    """Create reply keyboard with stations grouped by line and navigation."""
    # Convert exclude_station to internal name if provided
    exclude_internal = None
    if exclude_station:
        exclude_internal = _get_station_internal_name(router, exclude_station)

    # Group stations by line using internal names as keys
    lines_stations: dict[str, list[str]] = {line: [] for line in LINE_ORDER}

    for st in router.stations.values():
        # Use internal (Ukrainian) line name as key
        internal_line_name = st.line.display_name_ua
        if internal_line_name in lines_stations:
            # Check exclusion using internal name
            if exclude_internal is None or st.name_ua != exclude_internal:
                lines_stations[internal_line_name].append(getattr(st, f"name_{lang}"))

    # Build keyboard: stations grouped by line (2 per row)
    keyboard = []
    for line_name in LINE_ORDER:
        stations = lines_stations[line_name]
        for i in range(0, len(stations), 2):
            row = [KeyboardButton(text=st) for st in stations[i : i + 2]]
            keyboard.append(row)

    keyboard = _add_nav_buttons(keyboard, lang)
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def build_reminder_keyboard(
    route_key: str,
    line_groups: dict[str, list],
    lang: Language = "ua",
    clicked_idx: int | None = None,
    remind_time: str | None = None,
) -> InlineKeyboardMarkup:
    """Build inline keyboard with reminder buttons."""
    buttons = []

    for idx, (_line_id, segments) in enumerate(line_groups.items()):
        # Skip short trips (1 station) - no reminder needed
        if len(segments) <= 1:
            continue
        if clicked_idx is not None and idx == clicked_idx:
            # This is the clicked button - show as set
            time_display = remind_time or get_text("reminder_set_short", lang)
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=get_text("reminder_cancel_button", lang, time=time_display),
                        callback_data=f"remind_cancel|{route_key}|{idx}",
                    )
                ]
            )
        else:
            # Create button for this line group
            if len(segments) >= 1:
                last_seg = segments[-1]
                remind_ts = int(last_seg.departure_time.timestamp()) if last_seg.departure_time else 0
                station_name = getattr(last_seg.to_station, f"name_{lang}")
                btn_text = get_text("reminder_button", lang, station=station_name)
            else:
                remind_ts = 0
                btn_text = get_text("reminder_button_default", lang)

            buttons.append(
                [
                    InlineKeyboardButton(
                        text=btn_text,
                        callback_data=f"remind|{route_key}|{idx}|{remind_ts}",
                    )
                ]
            )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_language_keyboard() -> ReplyKeyboardMarkup:
    """Create keyboard for language selection."""
    keyboard = [
        [KeyboardButton(text="🇺🇦 Українська")],
        [KeyboardButton(text="🇬🇧 English")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)
