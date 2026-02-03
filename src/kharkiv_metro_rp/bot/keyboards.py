"""Keyboard builders for the Telegram bot."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from kharkiv_metro_rp.core.router import MetroRouter

from .constants import (
    LINE_DISPLAY_TO_INTERNAL,
    LINE_INTERNAL_TO_DISPLAY,
    LINE_ORDER,
    ButtonText,
)


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Create main menu keyboard."""
    keyboard = [
        [KeyboardButton(text=ButtonText.ROUTE), KeyboardButton(text=ButtonText.SCHEDULE)],
        [KeyboardButton(text=ButtonText.STATIONS)],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_lines_keyboard(include_back: bool = True) -> ReplyKeyboardMarkup:
    """Create keyboard with line selection."""
    keyboard = [
        [KeyboardButton(text="🔴 Холодногірсько-Заводська")],
        [KeyboardButton(text="🔵 Салтівська")],
        [KeyboardButton(text="🟢 Олексіївська")],
    ]
    if include_back:
        keyboard.append([KeyboardButton(text=ButtonText.BACK), KeyboardButton(text=ButtonText.CANCEL)])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def get_day_type_keyboard(include_cancel: bool = True) -> ReplyKeyboardMarkup:
    """Create keyboard for day type selection."""
    keyboard = [
        [KeyboardButton(text=ButtonText.WEEKDAYS)],
        [KeyboardButton(text=ButtonText.WEEKENDS)],
    ]
    if include_cancel:
        keyboard.append([KeyboardButton(text=ButtonText.BACK), KeyboardButton(text=ButtonText.CANCEL)])
    else:
        keyboard.append([KeyboardButton(text=ButtonText.BACK)])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def get_time_choice_keyboard() -> ReplyKeyboardMarkup:
    """Create keyboard for time choice."""
    keyboard = [
        [KeyboardButton(text=ButtonText.CURRENT_TIME)],
        [KeyboardButton(text=ButtonText.CUSTOM_TIME)],
        [KeyboardButton(text=ButtonText.BACK), KeyboardButton(text=ButtonText.CANCEL)],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Create keyboard with back and cancel buttons only."""
    keyboard = [[KeyboardButton(text=ButtonText.BACK), KeyboardButton(text=ButtonText.CANCEL)]]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def get_stations_keyboard(
    stations: list[str],
    include_back: bool = True,
) -> ReplyKeyboardMarkup:
    """Create keyboard with stations list (2 per row)."""
    keyboard = []
    for i in range(0, len(stations), 2):
        row = [KeyboardButton(text=st) for st in stations[i : i + 2]]
        keyboard.append(row)

    if include_back:
        keyboard.append([KeyboardButton(text=ButtonText.BACK), KeyboardButton(text=ButtonText.CANCEL)])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def get_stations_keyboard_by_line(
    router: MetroRouter,
    exclude_station: str | None = None,
) -> ReplyKeyboardMarkup:
    """Create reply keyboard with stations grouped by line."""
    # Group stations by line
    lines_stations: dict[str, list[str]] = {line: [] for line in LINE_ORDER}

    for st in router.stations.values():
        line_name = st.line.display_name_ua
        if line_name in lines_stations and (exclude_station is None or st.name_ua != exclude_station):
            lines_stations[line_name].append(st.name_ua)

    # Build keyboard: stations grouped by line (2 per row)
    keyboard = []
    for line_name in LINE_ORDER:
        stations = lines_stations[line_name]
        for i in range(0, len(stations), 2):
            row = [KeyboardButton(text=st) for st in stations[i : i + 2]]
            keyboard.append(row)

    keyboard.append([KeyboardButton(text=ButtonText.BACK), KeyboardButton(text=ButtonText.CANCEL)])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)


def build_reminder_keyboard(
    route_key: str,
    line_groups: dict[str, list],
    clicked_idx: int | None = None,
    remind_time: str | None = None,
) -> InlineKeyboardMarkup:
    """Build inline keyboard with reminder buttons."""
    buttons = []
    line_ids = list(line_groups.keys())

    for idx, (line_id, segments) in enumerate(line_groups.items()):
        if clicked_idx is not None and idx == clicked_idx:
            # This is the clicked button - show as set
            time_display = remind_time or "✅"
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"❌ Скасувати нагадування на {time_display}",
                        callback_data=f"remind_cancel|{route_key}|{idx}",
                    )
                ]
            )
        else:
            # Create button for this line group
            if len(segments) >= 1:
                last_seg = segments[-1]
                remind_ts = int(last_seg.departure_time.timestamp()) if last_seg.departure_time else 0
                btn_text = f"⏰ Вихід на {last_seg.to_station.name_ua}"
            else:
                remind_ts = 0
                btn_text = "⏰ Вихід"

            buttons.append(
                [
                    InlineKeyboardButton(
                        text=btn_text,
                        callback_data=f"remind|{route_key}|{idx}|{remind_ts}",
                    )
                ]
            )

    return InlineKeyboardMarkup(inline_keyboard=buttons)
