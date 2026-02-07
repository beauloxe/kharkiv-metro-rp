"""Shared timezone-aware time helpers."""

from __future__ import annotations

import datetime as dt

from .config import Config


def now() -> dt.datetime:
    """Return current time in configured timezone."""
    return dt.datetime.now(Config.TIMEZONE)
