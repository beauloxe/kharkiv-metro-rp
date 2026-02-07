"""Internationalization module for Kharkiv Metro."""

from typing import Literal

Language = Literal["ua", "en"]

DEFAULT_LANGUAGE: Language = "ua"

# Translation dictionary
TRANSLATIONS: dict[Language, dict[str, str]] = {
    "ua": {
        # CLI specific
        "From": "Звідки",
        "To": "Куди",
        "Line": "Лінія",
        "Time": "Час",
        "Transfer": "Пересадка",
        "min": "хв",
        "Hour": "Година",
        "Operating hours": "Години роботи",
        "CLOSED": "ЗАКРИТО",
        "Station": "Станція",
        "no_transfers": "без пересадок",
        "transfers_one": "{count} пересадка",
        "transfers_many": "{count} пересадки",
        # Main menu
        "main_menu": "🏠 Головне меню",
        "route": "🚇 Маршрут",
        "schedule": "📅 Розклад",
        "stations": "📋 Станції",
        "language": "🌐 Мова",
        "about": "ℹ️ Про бота",
        # Navigation
        "back": "🔙 Назад",
        "cancel": "❌ Скасувати",
        "next": "Далі ▶️",
        # Route building
        "from_station_prompt": "📍 Звідки їдемо? Спочатку оберіть лінію:",
        "to_station_prompt": "📍 Куди їдемо? Спочатку оберіть лінію:",
        "select_station_line": "📍 Оберіть станцію на лінії {line}:",
        "time_prompt": "⏰ Який час?",
        "day_type_prompt": "📅 Оберіть тип дня:",
        "custom_time_prompt": "⌚ Введіть час у форматі ГГ:ХХ (наприклад: 14:30)",
        # Time options
        "current_time": "🕐 Поточний час",
        "custom_time": "⌚ Свій час",
        "time_minus_20": "⏪ -20 хв",
        "time_minus_10": "◀ -10 хв",
        "time_plus_10": "▶ +10 хв",
        "time_plus_20": "⏩ +20 хв",
        # Day types
        "weekdays": "📅 Будні",
        "weekends": "🎉 Вихідні",
        "weekday": "Будній",
        "weekend": "Вихідний",
        # Errors
        "error_unknown_line": "❌ Невідома лінія. Оберіть з клавіатури.",
        "error_unknown_choice": "❌ Невідомий вибір. Оберіть з клавіатури.",
        "error_invalid_time_format": "❌ Неправильний формат часу. Введіть у форматі ГГ:ХХ (наприклад: 14:30)",
        "error_invalid_time": "❌ Неправильний час. Введіть годину (0-23) та хвилини (0-59).\nНаприклад: 14:30",
        "error_station_not_found": "❌ Станцію не знайдено: {station}\nСпробуйте ще раз через /route",
        "error_route_not_found": "❌ Маршрут не знайдено\nСпробуйте інші станції.",
        "error_metro_closed": "❌ Метро закрите та/або на останній потяг неможливо встигнути\nСпробуйте інший час або день.",
        "error_generic": "❌ Помилка: {error}\nСпробуйте ще раз через /route",
        "error_cancelled": "❌ Побудову маршруту скасовано",
        # Reminders
        "reminder_set": "✅ Нагадування встановлено!",
        "reminder_cancelled": "❌ Нагадування скасовано!",
        "reminder_exit_prepare": "⏰ Готуйтесь виходити на наступній станції: {station}",
        "reminder_button": "⏰ Вихід на {station}",
        "reminder_cancel_button": "❌ Скасувати нагадування на {time}",
        # Outdated
        "outdated_button": "❌ Ця кнопка застаріла. Будь ласка, побудуйте маршрут знову.",
        "error_invalid_data": "❌ Помилка: неправильний формат даних",
        "error_route_expired": "❌ Помилка: маршрут не знайдено або застарів",
        "error_invalid_line": "❌ Помилка: неправильний індекс лінії",
        # Commands
        "cmd_start": "Запустити бота",
        "cmd_route": "Побудувати маршрут",
        "cmd_schedule": "Розклад станції",
        "cmd_stations": "Список станцій",
        "cmd_about": "Про бота",
        "cmd_language": "Змінити мову",
        # Lines (for display)
        "line_red": "🔴 Холодногірсько-Заводська",
        "line_blue": "🔵 Салтівська",
        "line_green": "🟢 Олексіївська",
        "line_red_short": "Холодногірсько-заводська",
        "line_blue_short": "Салтівська",
        "line_green_short": "Олексіївська",
        # Language selection
        "select_language": "🌐 Оберіть мову / Select language:",
        "language_set": "✅ Мову змінено на Українську",
        # Common / Menu
        "start_message": "🚇 Бот для планування маршрутів Харківського метро\n\nОберіть дію:",
        "about_message": (
            "🚇 Цей бот допомагає знаходити оптимальні маршрути та переглядати розклад Харківського метрополітену.\n\n"
            "Основні функції:\n"
            "• Гнучка побудова маршруту з пересадками та часом на поїздку\n"
            "• Нагадування перед виходом за одну станцію\n"
            "• Розклад станцій по буднях та вихідних\n"
            "Джерело даних: https://www.metro.kharkiv.ua/hkrafiky-krukhu-poizdiv/\n\n"
            "⚠️ Цей проєкт не пов'язаний з КП «Харківський метрополітен» і не надає жодних гарантій. "
            "Користуючись цим проєктом, Ви несете відповідальність за планування маршруту."
            '\n\nБільше інформації та код проєкту <a href="https://github.com/beauloxe/kharkiv-metro-rp">за посиланням</a>.'
        ),
        "select_line": "📅 Оберіть лінію метро:",
        "session_restored": "🤖 Сеанс відновлено\n\nСхоже, сесія закінчилась.\nПовертаємось до головного меню:",
        # Schedule
        "schedule_not_found": "❌ Розклад не знайдено",
        "schedule_cancelled": "❌ Перегляд розкладу скасовано",
        "direction": "Напрямок",
        # Stations
        "stations_cancelled": "❌ Перегляд станцій скасовано",
        # Navigation hint
        "navigation_hint": "👇 Оберіть варіант нижче або натисніть кнопку:",
    },
    "en": {
        # CLI specific
        "From": "From",
        "To": "To",
        "Line": "Line",
        "Time": "Time",
        "Transfer": "Transfer",
        "min": "min",
        "Hour": "Hour",
        "Operating hours": "Operating hours",
        "CLOSED": "CLOSED",
        "Station": "Station",
        "no_transfers": "no transfers",
        "transfers_one": "{count} transfer",
        "transfers_many": "{count} transfers",
        # Main menu
        "main_menu": "🏠 Main menu",
        "route": "🚇 Route",
        "schedule": "📅 Schedule",
        "stations": "📋 Stations",
        "language": "🌐 Language",
        "about": "ℹ️ About",
        # Navigation
        "back": "🔙 Back",
        "cancel": "❌ Cancel",
        "next": "Next ▶️",
        # Route building
        "from_station_prompt": "📍 Where are you traveling from? First, select a line:",
        "to_station_prompt": "📍 Where are you going to? First, select a line:",
        "select_station_line": "📍 Select a station on the {line} line:",
        "time_prompt": "⏰ What time?",
        "day_type_prompt": "📅 Select day type:",
        "custom_time_prompt": "⌚ Enter time in HH:MM format (e.g., 14:30)",
        # Time options
        "current_time": "🕐 Current time",
        "custom_time": "⌚ Custom time",
        "time_minus_20": "⏪ -20 min",
        "time_minus_10": "◀ -10 min",
        "time_plus_10": "▶ +10 min",
        "time_plus_20": "⏩ +20 min",
        # Day types
        "weekdays": "📅 Weekdays",
        "weekends": "🎉 Weekends",
        "weekday": "Weekday",
        "weekend": "Weekend",
        # Errors
        "error_unknown_line": "❌ Unknown line. Please select from the keyboard.",
        "error_unknown_choice": "❌ Unknown choice. Please select from the keyboard.",
        "error_invalid_time_format": "❌ Invalid time format. Enter in HH:MM format (e.g., 14:30)",
        "error_invalid_time": "❌ Invalid time. Enter hour (0-23) and minutes (0-59).\nExample: 14:30",
        "error_station_not_found": "❌ Station not found: {station}\nPlease try again via /route",
        "error_route_not_found": "❌ Route not found\nPlease try other stations.",
        "error_metro_closed": "❌ Metro is closed and/or you cannot catch the last train\nPlease try another time or day.",
        "error_generic": "❌ Error: {error}\nPlease try again via /route",
        "error_cancelled": "❌ Route planning cancelled",
        # Reminders
        "reminder_set": "✅ Reminder set!",
        "reminder_cancelled": "❌ Reminder cancelled!",
        "reminder_exit_prepare": "⏰ Get ready to exit at the next station: {station}",
        "reminder_button": "⏰ Exit at {station}",
        "reminder_cancel_button": "❌ Cancel reminder at {time}",
        # Outdated
        "outdated_button": "❌ This button is outdated. Please rebuild your route.",
        "error_invalid_data": "❌ Error: invalid data format",
        "error_route_expired": "❌ Error: route not found or expired",
        "error_invalid_line": "❌ Error: invalid line index",
        # Commands
        "cmd_start": "Start the bot",
        "cmd_route": "Build a route",
        "cmd_schedule": "Station schedule",
        "cmd_stations": "List of stations",
        "cmd_about": "About the bot",
        "cmd_language": "Change language",
        # Lines (for display)
        "line_red": "🔴 Kholodnohirsko-Zavodska",
        "line_blue": "🔵 Saltivska",
        "line_green": "🟢 Oleksiivska",
        "line_red_short": "Kholodnohirsko-Zavodska",
        "line_blue_short": "Saltivska",
        "line_green_short": "Oleksiivska",
        # Language selection
        "select_language": "🌐 Select language / Оберіть мову:",
        "language_set": "✅ Language changed to English",
        # Common / Menu
        "start_message": "🚇 Kharkiv Metro Route Planner Bot\n\nChoose an action:",
        "about_message": (
            "🚇 This bot helps find optimal routes and view schedules for Kharkiv Metro.\n\n"
            "Main features:\n"
            "• Flexible route building with transfers and travel time\n"
            "• Reminders one station before exit\n"
            "• Station schedules for weekdays and weekends\n"
            "Data source: https://www.metro.kharkiv.ua/hkrafiky-krukhu-poizdiv/\n\n"
            "⚠️ This project is not affiliated with KP «Kharkiv Metro» and provides no guarantees. "
            "By using this project, you are responsible for route planning.\n\n"
            'More information and project code <a href="https://github.com/beauloxe/kharkiv-metro-rp">at this link</a>.'
        ),
        "select_line": "📅 Select a metro line:",
        "session_restored": "🤖 Session restored\n\nLooks like the session has expired.\nReturning to main menu:",
        # Schedule
        "schedule_not_found": "❌ Schedule not found",
        "schedule_cancelled": "❌ Schedule lookup cancelled",
        "direction": "Direction",
        # Stations
        "stations_cancelled": "❌ Stations lookup cancelled",
        # Navigation hint
        "navigation_hint": "👇 Select an option below or press a button:",
    },
}

LINE_INTERNAL_NAMES: dict[str, str] = {
    "kholodnohirsko_zavodska": "Холодногірсько-заводська",
    "saltivska": "Салтівська",
    "oleksiivska": "Олексіївська",
}

LINE_DISPLAY_TEXT_KEYS: dict[str, dict[str, str]] = {
    "kholodnohirsko_zavodska": {"full": "line_red", "short": "line_red_short"},
    "saltivska": {"full": "line_blue", "short": "line_blue_short"},
    "oleksiivska": {"full": "line_green", "short": "line_green_short"},
}

INTERNAL_LINE_NAME_TO_KEY: dict[str, str] = {name: key for key, name in LINE_INTERNAL_NAMES.items()}


def get_text(key: str, lang: Language = DEFAULT_LANGUAGE, **kwargs) -> str:
    """Get translated text by key.

    Args:
        key: Translation key
        lang: Language code ('ua' or 'en')
        **kwargs: Format string arguments

    Returns:
        Translated text
    """
    text = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE]).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text


def get_line_display_name(line_key: str, lang: Language = DEFAULT_LANGUAGE) -> str:
    """Get display name for a line.

    Args:
        line_key: Internal line key (e.g., 'kholodnohirsko_zavodska')
        lang: Language code

    Returns:
        Display name with emoji
    """
    mapping = LINE_DISPLAY_TEXT_KEYS.get(line_key)
    if not mapping:
        return line_key
    return get_text(mapping["full"], lang)


def get_line_short_name(line_key: str, lang: Language = DEFAULT_LANGUAGE) -> str:
    """Get short name for a line (without emoji).

    Args:
        line_key: Internal line key
        lang: Language code

    Returns:
        Short display name
    """
    mapping = LINE_DISPLAY_TEXT_KEYS.get(line_key)
    if not mapping:
        return line_key
    return get_text(mapping["short"], lang)


def get_line_display_by_internal(internal_name: str, lang: Language = DEFAULT_LANGUAGE) -> str:
    """Get display name for a line by its internal (Ukrainian) name.

    Args:
        internal_name: Internal line name (e.g., 'Холодногірсько-заводська')
        lang: Language code

    Returns:
        Display name with emoji (e.g., '🔴 Kholodnohirsko-Zavodska')
    """
    line_key = INTERNAL_LINE_NAME_TO_KEY.get(internal_name)
    if not line_key:
        return internal_name
    return get_line_display_name(line_key, lang)


def _build_line_display_to_internal(lang: Language) -> dict[str, str]:
    return {
        get_text(keys["full"], lang): LINE_INTERNAL_NAMES[line_key] for line_key, keys in LINE_DISPLAY_TEXT_KEYS.items()
    }


# Reverse mapping: display name -> internal name
LINE_DISPLAY_TO_INTERNAL_I18N: dict[Language, dict[str, str]] = {
    "ua": _build_line_display_to_internal("ua"),
    "en": _build_line_display_to_internal("en"),
}

# Combined mapping for all languages (for state-based validation)
LINE_DISPLAY_TO_INTERNAL: dict[str, str] = {
    **LINE_DISPLAY_TO_INTERNAL_I18N["ua"],
    **LINE_DISPLAY_TO_INTERNAL_I18N["en"],
}


def parse_line_display_name(display_name: str, lang: Language = DEFAULT_LANGUAGE) -> str | None:
    """Parse display line name to internal name.

    Args:
        display_name: Display name with emoji (e.g., "🔴 Холодногірсько-Заводська")
        lang: Language code

    Returns:
        Internal line name or None if not found
    """
    return LINE_DISPLAY_TO_INTERNAL_I18N.get(lang, {}).get(display_name)


# Day type reverse mapping
DAY_TYPE_DISPLAY_TO_INTERNAL_I18N: dict[Language, dict[str, str]] = {
    "ua": {
        "📅 Будні": "weekday",
        "🎉 Вихідні": "weekend",
    },
    "en": {
        "📅 Weekdays": "weekday",
        "🎉 Weekends": "weekend",
    },
}

# Combined mapping for all languages
DAY_TYPE_DISPLAY_TO_INTERNAL: dict[str, str] = {
    **DAY_TYPE_DISPLAY_TO_INTERNAL_I18N["ua"],
    **DAY_TYPE_DISPLAY_TO_INTERNAL_I18N["en"],
}


def parse_day_type_display(display_name: str, lang: Language = DEFAULT_LANGUAGE) -> str | None:
    """Parse display day type to internal value.

    Args:
        display_name: Display day type (e.g., "📅 Будні")
        lang: Language code

    Returns:
        Internal day type ("weekday" or "weekend") or None
    """
    return DAY_TYPE_DISPLAY_TO_INTERNAL_I18N.get(lang, {}).get(display_name)
