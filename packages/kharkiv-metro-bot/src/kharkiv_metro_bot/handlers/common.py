"""Common handlers for the Telegram bot (start, menu, catch-all)."""

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import BotCommand
from kharkiv_metro_core import Language, get_text

from ..constants import CommandText
from ..keyboards import get_language_keyboard, get_lines_keyboard, get_main_keyboard
from ..user_data import get_user_language, set_user_language


async def cmd_start(message: types.Message, lang: Language = "ua"):
    """Handle /start command."""
    await message.answer(
        get_text("start_message", lang),
        reply_markup=get_main_keyboard(lang),
    )


async def cmd_about(message: types.Message, lang: Language = "ua"):
    """Handle /about command."""
    about_text = get_text("about_message", lang)
    await message.answer(
        about_text, parse_mode="HTML", reply_markup=get_main_keyboard(lang), disable_web_page_preview=True
    )


async def cmd_language(message: types.Message, state: FSMContext):
    """Handle /lang command - show language selection."""
    await state.set_state("waiting_for_language")
    await message.answer(
        "🌐 Оберіть мову / Select language:",
        reply_markup=get_language_keyboard(),
    )


async def process_language_selection(message: types.Message, state: FSMContext):
    """Process language selection."""
    user_id = message.from_user.id

    if message.text == "🇺🇦 Українська":
        set_user_language(user_id, "ua")
        await message.answer(
            "✅ Мову змінено на Українську",
            reply_markup=get_main_keyboard("ua"),
        )
    elif message.text == "🇬🇧 English":
        set_user_language(user_id, "en")
        await message.answer(
            "✅ Language changed to English",
            reply_markup=get_main_keyboard("en"),
        )
    else:
        # Get current language for error message
        lang = get_user_language(user_id)
        await message.answer(
            get_text("error_unknown_choice", lang),
            reply_markup=get_language_keyboard(),
        )
        return

    await state.clear()


async def menu_route(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Handle route button from menu."""
    # Lazy import to avoid circular dependencies
    from .route import cmd_route

    await cmd_route(message, state, lang)


async def menu_schedule(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Handle schedule button from menu."""
    from ..states import ScheduleStates

    await state.set_state(ScheduleStates.waiting_for_line)
    msg = await message.answer(
        get_text("select_line", lang),
        reply_markup=get_lines_keyboard(lang),
    )
    await state.update_data(active_message_id=msg.message_id)


async def menu_stations(message: types.Message, state: FSMContext, lang: Language = "ua"):
    """Handle stations button from menu."""
    from .stations import cmd_stations

    await cmd_stations(message, state, lang)


async def catch_all_handler(message: types.Message, lang: Language = "ua"):
    """Handle any unhandled messages when NOT in a state."""
    await message.answer(
        get_text("start_message", lang),
        reply_markup=get_main_keyboard(lang),
    )


# Valid button texts that should NOT trigger reset
def get_valid_buttons() -> list[str]:
    """Get list of valid button texts that should not trigger session reset."""
    return [
        # Menu buttons
        get_text("route", "ua"),
        get_text("route", "en"),
        get_text("schedule", "ua"),
        get_text("schedule", "en"),
        get_text("stations", "ua"),
        get_text("stations", "en"),
        # Navigation buttons
        get_text("back", "ua"),
        get_text("back", "en"),
        get_text("cancel", "ua"),
        get_text("cancel", "en"),
        # Language selection
        "🇺🇦 Українська",
        "🇬🇧 English",
    ]


async def set_bot_commands(bot: Bot):
    """Set bot commands menu."""
    commands = [
        BotCommand(command="start", description=CommandText.START),
        BotCommand(command="about", description=CommandText.ABOUT),
        BotCommand(command="lang", description="Змінити мову / Change language"),
    ]
    await bot.set_my_commands(commands)


def register_common_handlers(dp: Dispatcher):
    """Register common handlers."""
    # Command handlers - work in any state
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_about, Command("about"))
    dp.message.register(cmd_language, Command("lang"))

    # Language selection handler
    dp.message.register(process_language_selection, F.text.in_(["🇺🇦 Українська", "🇬🇧 English"]))

    # Menu button handlers - only work when NOT in any state (main menu)
    # Use i18n to check button text in both languages
    dp.message.register(menu_route, StateFilter(None), F.text.in_([get_text("route", "ua"), get_text("route", "en")]))
    dp.message.register(
        menu_schedule, StateFilter(None), F.text.in_([get_text("schedule", "ua"), get_text("schedule", "en")])
    )
    dp.message.register(
        menu_stations, StateFilter(None), F.text.in_([get_text("stations", "ua"), get_text("stations", "en")])
    )

    # Catch-all handler when NOT in a state (for unknown text)
    dp.message.register(catch_all_handler, StateFilter(None))
