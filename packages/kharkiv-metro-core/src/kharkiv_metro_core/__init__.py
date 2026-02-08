"""Kharkiv Metro Core Library."""

from .config import Config
from .data_loader import load_metro_data
from .database import MetroDatabase
from .graph import MetroGraph, get_metro_graph
from .i18n import (
    DEFAULT_LANGUAGE,
    Language,
    get_day_type_display_to_internal,
    get_line_display_by_internal,
    get_line_display_name,
    get_line_display_to_internal,
    get_line_short_name,
    get_text,
    get_translations,
    parse_day_type_display,
    parse_line_display_name,
)
from .initializer import init_database, init_schedules, init_stations
from .models import (
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
from .time_utils import now

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
    "load_metro_data",
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
    "now",
    # i18n
    "Language",
    "DEFAULT_LANGUAGE",
    "get_translations",
    "get_text",
    "get_line_display_name",
    "get_line_short_name",
    "get_line_display_by_internal",
    "parse_line_display_name",
    "parse_day_type_display",
    "get_day_type_display_to_internal",
    "get_line_display_to_internal",
]
