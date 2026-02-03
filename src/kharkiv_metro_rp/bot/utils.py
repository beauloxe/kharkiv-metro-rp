"""Utility functions for the Telegram bot."""

import hashlib
import os
from datetime import datetime
from pathlib import Path

from kharkiv_metro_rp.config import Config
from kharkiv_metro_rp.core.models import DayType, Route
from kharkiv_metro_rp.core.router import MetroRouter
from kharkiv_metro_rp.data.database import MetroDatabase
from kharkiv_metro_rp.data.initializer import init_database

from .constants import LINE_COLOR_EMOJI, LINE_NAME_EMOJI, LINE_ORDER, TIMEZONE


def now() -> datetime:
    """Get current time in configured timezone."""
    return datetime.now(TIMEZONE)


def get_db_path() -> str:
    """Get database path from environment or Config."""
    # Environment variable takes priority (useful for Railway, Docker, etc.)
    db_path = os.getenv("DB_PATH")
    if db_path:
        # Ensure parent directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return db_path

    # Fallback to Config default
    config = Config()
    config.ensure_dirs()
    return config.get_db_path()


def get_router() -> MetroRouter:
    """Get MetroRouter instance."""
    db_path = get_db_path()

    # Auto-initialize database if it doesn't exist
    if not Path(db_path).exists():
        init_database(db_path)

    db = MetroDatabase(db_path)
    return MetroRouter(db=db)


def get_stations_by_line(router: MetroRouter, line_name: str) -> list[str]:
    """Get list of station names for a given line."""
    stations = []
    for st in router.stations.values():
        if st.line.display_name_ua == line_name:
            stations.append(st.name_ua)
    return stations


def get_stations_by_line_except(router: MetroRouter, line_name: str, exclude_station: str) -> list[str]:
    """Get list of station names for a given line, excluding one station."""
    stations = []
    for st in router.stations.values():
        if st.line.display_name_ua == line_name and st.name_ua != exclude_station:
            stations.append(st.name_ua)
    return stations


def format_route(route: Route) -> str:
    """Format route compactly for Telegram with times on segments."""
    lines = []
    # Header: From → To
    lines.append(f"🚇 {route.segments[0].from_station.name_ua} → {route.segments[-1].to_station.name_ua}")
    # if route.num_transfers > 0:
    #     lines.append(f"🔄 Пересадок: {route.num_transfers}")
    lines.append(f"⏱ {route.total_duration_minutes} хв")
    lines.append("")
    lines.append("📍 Маршрут:")

    i = 0
    while i < len(route.segments):
        segment = route.segments[i]

        if segment.is_transfer:
            # Transfer - show as "next" info
            lines.append("")
            lines.append(
                f"🔄 {segment.from_station.name_ua} → {segment.to_station.name_ua} ({segment.duration_minutes} хв)"
            )
            lines.append("")
            i += 1
        else:
            # Travel segment - find all consecutive segments on same line
            line = segment.from_station.line
            color_emoji = LINE_COLOR_EMOJI.get(line.color, "⚪")

            # Start of this line section
            start_station = segment.from_station
            start_time = segment.departure_time

            # Find end of this line section
            end_station = segment.to_station
            end_time = segment.arrival_time
            total_duration = segment.duration_minutes

            i += 1
            while i < len(route.segments) and not route.segments[i].is_transfer:
                # Continue on same line
                end_station = route.segments[i].to_station
                end_time = route.segments[i].arrival_time
                total_duration += route.segments[i].duration_minutes
                i += 1

            # Format with times
            from_name = start_station.name_ua
            to_name = end_station.name_ua

            if start_time and end_time:
                dep = start_time.strftime("%H:%M")
                arr = end_time.strftime("%H:%M")
                time_str = f"{dep} → {arr}"
            else:
                time_str = f"{total_duration} хв"

            lines.append(f"{color_emoji} {from_name} → {to_name}")
            lines.append(f"• {time_str} ({total_duration} хв)")

    return "\n".join(lines)


def format_schedule(station_name: str, schedules: list, router: MetroRouter) -> str:
    """Format schedule for Telegram."""
    lines = []
    lines.append(f"🚇 {station_name}")
    lines.append(f"📅 {'Будні' if schedules[0].day_type.value == 'weekday' else 'Вихідні'}")
    lines.append("")

    for sch in schedules[:2]:  # Show up to 2 directions
        dir_station = router.stations.get(sch.direction_station_id)
        if dir_station:
            dir_name = dir_station.name_ua
            lines.append(f"➡️ Напрямок: {dir_name}")

            # Group by hour
            by_hour: dict[int, list[int]] = {}
            for entry in sch.entries:
                if entry.hour not in by_hour:
                    by_hour[entry.hour] = []
                by_hour[entry.hour].append(entry.minutes)

            for hour in sorted(by_hour.keys()):
                minutes = ", ".join(f"{m:02d}" for m in sorted(by_hour[hour]))
                lines.append(f"{hour:02d}: {minutes}")

            lines.append("")

    return "\n".join(lines)


def format_stations_list(line_name: str, stations: list[str]) -> str:
    """Format stations list for display."""
    emoji = LINE_NAME_EMOJI.get(line_name, "⚪")
    lines = [f"{emoji} {line_name}:\n"]

    for st_name in stations:
        lines.append(f"• {st_name}")

    return "\n".join(lines)


def get_day_type_from_string(day_type: str) -> DayType:
    """Convert string day type to DayType enum."""
    return DayType.WEEKDAY if day_type == "weekday" else DayType.WEEKEND


def get_current_day_type() -> DayType:
    """Get DayType based on current day in configured timezone."""
    return DayType.WEEKDAY if now().weekday() < 5 else DayType.WEEKEND


def parse_line_selection(text: str) -> str | None:
    """Parse line selection from button text."""
    from .constants import LINE_DISPLAY_TO_INTERNAL

    return LINE_DISPLAY_TO_INTERNAL.get(text)


def parse_day_type_selection(text: str) -> str | None:
    """Parse day type selection from button text."""
    from .constants import DAY_TYPE_DISPLAY_TO_INTERNAL

    return DAY_TYPE_DISPLAY_TO_INTERNAL.get(text)


def build_line_groups(route: Route) -> dict[str, list]:
    """Group route segments by line for reminder buttons."""
    # Get travel segments (excluding transfers)
    travel_segments = [s for s in route.segments if not s.is_transfer]

    # Group segments by line
    line_groups: dict[str, list] = {}
    for seg in travel_segments:
        line_id = seg.from_station.line.color if seg.from_station.line else "unknown"
        if line_id not in line_groups:
            line_groups[line_id] = []
        line_groups[line_id].append(seg)

    return line_groups


def generate_route_key(route: Route) -> str:
    """Generate unique key for route storage (short hash for callback_data limit)."""
    from_st = route.segments[0].from_station
    to_st = route.segments[-1].to_station
    departure_ts = int(route.segments[0].departure_time.timestamp())
    # Use short hash to stay within Telegram's 64-byte callback_data limit
    full_key = f"{from_st.id}:{to_st.id}:{departure_ts}"
    return hashlib.md5(full_key.encode()).hexdigest()[:12]
