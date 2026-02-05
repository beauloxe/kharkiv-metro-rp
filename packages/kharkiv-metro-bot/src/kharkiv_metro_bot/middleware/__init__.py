"""Middleware for handling user language."""

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from ..i18n import DEFAULT_LANGUAGE, Language, get_text as _get_text
from ..analytics import get_user_language


class I18nMiddleware(BaseMiddleware):
    """Middleware to inject i18n functions into handler data."""

    async def __call__(self, handler, event, data):
        """Add language and get_text function to handler data."""
        # Get user_id from event
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None

        # Get user language
        if user_id:
            lang = get_user_language(user_id)
        else:
            lang = DEFAULT_LANGUAGE

        # Add to data
        data["lang"] = lang
        data["get_text"] = lambda key, **kwargs: _get_text(key, lang, **kwargs)

        return await handler(event, data)


def get_text(key: str, lang: Language, **kwargs) -> str:
    """Get translated text.
    
    This is a convenience function that wraps i18n.get_text
    to be used with the lang parameter from middleware.
    """
    return _get_text(key, lang, **kwargs)
