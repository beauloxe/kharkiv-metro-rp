"""Constants for the Telegram bot."""

from typing import Final

from kharkiv_metro_core import Config, get_line_display_by_internal, load_metro_data

# Get config values
_config = Config()
TIMEZONE = Config.TIMEZONE
DB_PATH = _config.get_db_path()
LINE_ORDER = [
    get_line_display_by_internal(line_key, "ua")
    for line_key in load_metro_data().line_order
]

# Line mappings
_metro_data = load_metro_data()
LINE_INTERNAL_TO_DISPLAY: Final[dict[str, str]] = {
    meta["name_ua"]: get_line_display_by_internal(meta["name_ua"], "ua")
    for meta in _metro_data.line_meta.values()
}

# Emoji mappings
LINE_COLOR_EMOJI: Final[dict[str, str]] = {
    meta["color"]: meta["emoji"]
    for meta in _metro_data.line_meta.values()
}

LINE_NAME_EMOJI: Final[dict[str, str]] = {
    meta["name_ua"]: meta["emoji"]
    for meta in _metro_data.line_meta.values()
}

# Day type mappings
DAY_TYPE_DISPLAY_TO_INTERNAL: Final[dict[str, str]] = {
    f"{meta['emoji']} {meta['name_ua']}": key
    for key, meta in _metro_data.day_types.items()
}

DAY_TYPE_INTERNAL_TO_DISPLAY: Final[dict[str, str]] = {
    key: f"{meta['emoji']} {meta['name_ua']}" for key, meta in _metro_data.day_types.items()
}


# Keyboard button texts
class ButtonText:
    """Button text constants."""

    BACK = "🔙 Назад"
    CANCEL = "❌ Скасувати"
    ROUTE = "🚇 Маршрут"
    SCHEDULE = "📅 Розклад"
    STATIONS = "📋 Станції"
    WEEKDAYS = "📅 Будні"
    WEEKENDS = "🎉 Вихідні"
    CURRENT_TIME = "🕐 Поточний час"
    TIME_MINUS_20 = "⏪ -20 хв"
    TIME_MINUS_10 = "◀ -10 хв"
    TIME_PLUS_10 = "▶ +10 хв"
    TIME_PLUS_20 = "⏩ +20 хв"
    CUSTOM_TIME = "⌚ Свій час"


# Command texts
class CommandText:
    """Command description constants."""

    START = "Запустити бота"
    ROUTE = "Побудувати маршрут"
    SCHEDULE = "Розклад станції"
    STATIONS = "Список станцій"
    ABOUT = "Про бота"
