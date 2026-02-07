"""Admin handlers for user data and bot management."""

from aiogram import Dispatcher, types
from aiogram.filters import Command

from ..user_data import get_admin_id, get_user_data_db, is_user_data_enabled


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    admin_id = get_admin_id()
    return admin_id is not None and user_id == admin_id


async def cmd_stats(message: types.Message):
    """Get analytics statistics (admin only)."""
    if not is_admin(message.from_user.id):
        # Treat as unknown command for non-admins
        from ..keyboards import get_main_keyboard

        await message.answer(
            "🚇 Бот для планування маршрутів Харківського метро\n\nОберіть дію:",
            reply_markup=get_main_keyboard(),
        )
        return

    if not is_user_data_enabled():
        await message.answer("📊 User data is currently disabled.")
        return

    db = get_user_data_db()
    if db is None:
        await message.answer("❌ User data database not initialized.")
        return

    stats = db.get_stats()

    # Format feature usage
    feature_lines = []
    for feature, count in stats["feature_usage"].items():
        feature_lines.append(f"  • {feature}: {count}")

    feature_text = "\n".join(feature_lines) if feature_lines else "  No data yet"

    response = (
        f"📊 <b>Bot Statistics</b>\n\n"
        f"<b>Users:</b>\n"
        f"  • Total unique: {stats['total_users']}\n"
        f"  • Active today: {stats['active_today']}\n"
        f"  • Active this week: {stats['active_this_week']}\n\n"
        f"<b>Feature Usage:</b>\n"
        f"{feature_text}"
    )

    await message.answer(response, parse_mode="HTML")


def register_admin_handlers(dp: Dispatcher):
    """Register admin handlers."""
    dp.message.register(cmd_stats, Command("stats"))
