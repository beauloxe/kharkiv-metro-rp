"""Kharkiv Metro Core Library."""

from .config import Config
from .database import MetroDatabase
from .graph import MetroGraph, get_metro_graph
from .i18n import (
    DAY_TYPE_DISPLAY_TO_INTERNAL,
    DEFAULT_LANGUAGE,
    LINE_DISPLAY_TO_INTERNAL,
    TRANSLATIONS,
    Language,
    get_line_display_by_internal,
    get_line_display_name,
    get_line_short_name,
    get_text,
    parse_day_type_display,
    parse_line_display_name,
)
from .initializer import init_database, init_schedules, init_stations
from .models import (
    ALIAS_STATION_NAMES,
    TRANSFERS,
    DayType,
    Line,
    MetroClosedError,
    Route,
    RouteSegment,
    ScheduleEntry,
    Station,
    StationSchedule,
    create_stations,
)
from .router import MetroRouter

# Lazy import for MetroScraper to avoid loading aiohttp/bs4 on startup
# These are heavy dependencies only needed for scraping operations
_MetroScraper = None


def __getattr__(name):
    """Lazy load MetroScraper to avoid importing heavy dependencies on startup."""
    global _MetroScraper
    if name == "MetroScraper":
        if _MetroScraper is None:
            from .scraper import MetroScraper as _MS

            _MetroScraper = _MS
        return _MetroScraper
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Config
    "Config",
    # Models
    "DayType",
    "Line",
    "Station",
    "ScheduleEntry",
    "StationSchedule",
    "RouteSegment",
    "Route",
    "MetroClosedError",
    "TRANSFERS",
    "ALIAS_STATION_NAMES",
    "create_stations",
    # Graph
    "MetroGraph",
    "get_metro_graph",
    # Database
    "MetroDatabase",
    # Router
    "MetroRouter",
    # Scraper (lazy loaded)
    "MetroScraper",
    # Initializer
    "init_database",
    "init_stations",
    "init_schedules",
    # i18n
    "Language",
    "DEFAULT_LANGUAGE",
    "TRANSLATIONS",
    "get_text",
    "get_line_display_name",
    "get_line_short_name",
    "get_line_display_by_internal",
    "parse_line_display_name",
    "parse_day_type_display",
    "DAY_TYPE_DISPLAY_TO_INTERNAL",
    "LINE_DISPLAY_TO_INTERNAL",
]
