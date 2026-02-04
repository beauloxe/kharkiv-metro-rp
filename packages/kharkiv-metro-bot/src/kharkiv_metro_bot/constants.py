"""Constants for the Telegram bot."""

from typing import Final

from kharkiv_metro_core import Config

# Get config values
_config = Config()
TIMEZONE = Config.TIMEZONE
LINE_ORDER = Config.LINE_ORDER
DB_PATH = _config.get_db_path()

# Line mappings
LINE_DISPLAY_TO_INTERNAL: Final[dict[str, str]] = {
    "🔴 Холодногірсько-Заводська": "Холодногірсько-заводська",
    "🔵 Салтівська": "Салтівська",
    "🟢 Олексіївська": "Олексіївська",
}

LINE_INTERNAL_TO_DISPLAY: Final[dict[str, str]] = {
    "Холодногірсько-заводська": "🔴 Холодногірсько-Заводська",
    "Салтівська": "🔵 Салтівська",
    "Олексіївська": "🟢 Олексіївська",
}

# Emoji mappings
LINE_COLOR_EMOJI: Final[dict[str, str]] = {
    "red": "🔴",
    "blue": "🔵",
    "green": "🟢",
}

LINE_NAME_EMOJI: Final[dict[str, str]] = {
    "Холодногірсько-заводська": "🔴",
    "Салтівська": "🔵",
    "Олексіївська": "🟢",
}

# Day type mappings
DAY_TYPE_DISPLAY_TO_INTERNAL: Final[dict[str, str]] = {
    "📅 Будні": "weekday",
    "🎉 Вихідні": "weekend",
}

DAY_TYPE_INTERNAL_TO_DISPLAY: Final[dict[str, str]] = {
    "weekday": "📅 Будні",
    "weekend": "🎉 Вихідні",
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
