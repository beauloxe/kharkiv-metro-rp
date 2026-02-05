"""Utility functions for the Telegram bot."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from kharkiv_metro_core import Config, DayType, MetroDatabase, MetroRouter, Route, init_database, init_schedules
from .i18n import Language

if TYPE_CHECKING:
    pass


def now() -> datetime:
    """Get current time in configured timezone."""
    return datetime.now(Config.TIMEZONE)


def get_db_path() -> str:
    """Get database path."""
    config = Config()
    db_path = config.get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return db_path


def get_analytics_db_path() -> str:
    """Get analytics database path."""
    config = Config()
    analytics_path = config.get_analytics_db_path()
    Path(analytics_path).parent.mkdir(parents=True, exist_ok=True)
    return analytics_path


def get_router() -> MetroRouter:
    """Get MetroRouter instance."""
    db_path = get_db_path()

    if not Path(db_path).exists():
        db = init_database(db_path)
        try:
            init_schedules(db)
        except Exception:
            pass  # Schedules can be added later
    else:
        db = MetroDatabase(db_path)

    return MetroRouter(db=db)


def get_stations_by_line(router: MetroRouter, line_name: str, lang: Language = "ua") -> list[str]:
    """Get station names for a given line.
    
    Args:
        router: MetroRouter instance
        line_name: Internal line name (e.g., "Холодногірсько-заводська")
        lang: Language code
        
    Returns:
        List of station names in the requested language
    """
    name_attr = "name_ua" if lang == "ua" else "name_en"
    # Always compare with display_name_ua since line_name is internal (Ukrainian)
    return [
        getattr(st, name_attr)
        for st in router.stations.values()
        if st.line.display_name_ua == line_name
    ]


def get_stations_by_line_except(
    router: MetroRouter, line_name: str, exclude_station: str, lang: Language = "ua"
) -> list[str]:
    """Get station names for a line, excluding one station.
    
    Args:
        router: MetroRouter instance
        line_name: Internal line name (e.g., "Холодногірсько-заводська")
        exclude_station: Station name to exclude
        lang: Language code
        
    Returns:
        List of station names in the requested language
    """
    name_attr = "name_ua" if lang == "ua" else "name_en"
    # Always compare with display_name_ua since line_name is internal (Ukrainian)
    return [
        getattr(st, name_attr)
        for st in router.stations.values()
        if st.line.display_name_ua == line_name and getattr(st, name_attr) != exclude_station
    ]


def format_route(route: Route, lang: Language = "ua") -> str:
    """Format route for Telegram."""
    from .constants import LINE_COLOR_EMOJI
    from .i18n import get_text

    name_attr = "name_ua" if lang == "ua" else "name_en"
    min_text = "хв" if lang == "ua" else "min"

    lines = [
        f"🚇 {getattr(route.segments[0].from_station, name_attr)} → {getattr(route.segments[-1].to_station, name_attr)}",
        f"⏱ {route.total_duration_minutes} {min_text}",
        "",
        f"📍 {get_text('route', lang)}:",
    ]

    i = 0
    while i < len(route.segments):
        seg = route.segments[i]

        if seg.is_transfer:
            lines.append("")
            lines.append(f"🔄 {getattr(seg.from_station, name_attr)} → {getattr(seg.to_station, name_attr)} ({seg.duration_minutes} {min_text})")
            lines.append("")
            i += 1
        else:
            # Group consecutive segments on same line
            start_station = seg.from_station
            start_time = seg.departure_time
            end_station = seg.to_station
            end_time = seg.arrival_time
            total_duration = seg.duration_minutes
            line = seg.from_station.line

            i += 1
            while i < len(route.segments) and not route.segments[i].is_transfer:
                end_station = route.segments[i].to_station
                end_time = route.segments[i].arrival_time
                total_duration += route.segments[i].duration_minutes
                i += 1

            color_emoji = LINE_COLOR_EMOJI.get(line.color, "⚪")
            time_str = (
                f"{start_time.strftime('%H:%M')} → {end_time.strftime('%H:%M')}"
                if start_time and end_time
                else f"{total_duration} {min_text}"
            )

            lines.append(f"{color_emoji} {getattr(start_station, name_attr)} → {getattr(end_station, name_attr)}")
            lines.append(f"• {time_str} ({total_duration} {min_text})")

    return "\n".join(lines)


def format_schedule(station_name: str, schedules: list, router: MetroRouter, lang: Language = "ua") -> str:
    """Format schedule for Telegram."""
    from .i18n import get_text

    name_attr = "name_ua" if lang == "ua" else "name_en"
    day_type_text = get_text("weekday" if schedules[0].day_type.value == "weekday" else "weekend", lang)

    lines = [f"🚇 {station_name}", f"📅 {day_type_text}", ""]

    for sch in schedules[:2]:  # Up to 2 directions
        dir_station = router.stations.get(sch.direction_station_id)
        if not dir_station:
            continue

        direction_text = get_text("cmd_schedule", lang) if lang == "en" else "Напрямок"
        lines.append(f"➡️ {direction_text}: {getattr(dir_station, name_attr)}")

        # Group by hour
        by_hour: dict[int, list[int]] = {}
        for entry in sch.entries:
            by_hour.setdefault(entry.hour, []).append(entry.minutes)

        for hour in sorted(by_hour.keys()):
            minutes = ", ".join(f"{m:02d}" for m in sorted(by_hour[hour]))
            lines.append(f"{hour:02d}: {minutes}")

        lines.append("")

    return "\n".join(lines)


def format_stations_list(line_name: str, stations: list[str], lang: Language = "ua") -> str:
    """Format stations list."""
    from .i18n import get_line_display_by_internal
    
    # line_name is internal (Ukrainian), translate to display name
    display_name = get_line_display_by_internal(line_name, lang)
    header = f"{display_name}:\n"
    body = "\n".join(f"• {name}" for name in stations)
    return header + body


def get_current_day_type() -> DayType:
    """Get current day type."""
    return DayType.WEEKDAY if now().weekday() < 5 else DayType.WEEKEND


def build_line_groups(route: Route) -> dict[str, list]:
    """Group route segments by line."""
    groups: dict[str, list] = {}
    for seg in route.segments:
        if seg.is_transfer:
            continue
        line_id = seg.from_station.line.color if seg.from_station.line else "unknown"
        groups.setdefault(line_id, []).append(seg)
    return groups


def generate_route_key(route: Route) -> str:
    """Generate unique key for route."""
    from_st = route.segments[0].from_station
    to_st = route.segments[-1].to_station
    departure_ts = int(route.segments[0].departure_time.timestamp())
    full_key = f"{from_st.id}:{to_st.id}:{departure_ts}"
    return hashlib.md5(full_key.encode()).hexdigest()[:12]
