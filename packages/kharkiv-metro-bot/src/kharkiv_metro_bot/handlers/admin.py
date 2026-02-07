"""Admin handlers for user data and bot management."""

from aiogram import Dispatcher, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from kharkiv_metro_core import get_text as tr

from ..user_data import get_admin_id, get_user_data_db, is_user_data_enabled


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    admin_id = get_admin_id()
    return admin_id is not None and user_id == admin_id


async def cmd_stats(message: types.Message, state: FSMContext):
    """Get analytics statistics (admin only)."""
    await state.clear()
    if not is_admin(message.from_user.id):
        from ..keyboards import get_main_keyboard

        await message.answer(
            tr("start_message", "ua"),
            reply_markup=get_main_keyboard("ua"),
        )
        return

    if not is_user_data_enabled():
        await message.answer(tr("user_data_disabled"))
        return

    db = get_user_data_db()
    if db is None:
        await message.answer(tr("error_route_expired"))
        return

    stats = db.get_stats()

    feature_lines = []
    for feature, count in stats["feature_usage"].items():
        feature_lines.append(f"  • {feature}: {count}")

    feature_text = "\n".join(feature_lines) if feature_lines else tr("stats_no_data", "ua")

    lang = "ua"
    response = (
        f"{tr('stats_title', lang)}\n\n"
        f"{tr('stats_users', lang)}\n"
        f"{tr('stats_users_total', lang, count=stats['total_users'])}\n"
        f"{tr('stats_users_active_today', lang, count=stats['active_today'])}\n"
        f"{tr('stats_users_active_week', lang, count=stats['active_this_week'])}\n\n"
        f"{tr('stats_features', lang)}\n"
        f"{feature_text}"
    )

    await message.answer(response, parse_mode="HTML")


def register_admin_handlers(dp: Dispatcher):
    """Register admin handlers."""
    dp.message.register(cmd_stats, Command("stats"), StateFilter("*"))
