"""Utility functions for the Telegram bot."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from aiogram import types
from aiogram.fsm.context import FSMContext
from kharkiv_metro_core import (
    Config,
    DayType,
    Language,
    MetroDatabase,
    MetroRouter,
    Route,
    get_line_display_name,
    get_text,
    init_database,
    init_schedules,
    load_metro_data,
)
from kharkiv_metro_core import (
    now as core_now,
)

if TYPE_CHECKING:
    pass


def now() -> datetime:
    """Get current time in configured timezone."""
    return core_now()


def get_db_path() -> str:
    """Get database path."""
    config = Config()
    db_path = config.get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return db_path


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
        db = MetroDatabase.shared(db_path)

    return MetroRouter(db=db)


def _normalize_line_key(line_key: str | None) -> str | None:
    """Normalize line key or internal name to line key."""
    if not line_key:
        return None
    line_meta = load_metro_data().line_meta
    if line_key in line_meta:
        return line_key
    for key, meta in line_meta.items():
        if meta.get("name_ua") == line_key:
            return key
    return None


def get_valid_lines(lang: Language = "ua") -> list[str]:
    """Get list of valid line display names."""
    return [get_line_display_name(line_key, lang) for line_key in load_metro_data().line_order]


async def update_message(
    message: types.Message,
    state: FSMContext,
    text: str,
    keyboard,
) -> None:
    """Update existing message or send new one."""
    data = await state.get_data()
    msg_id = data.get("active_message_id")

    if isinstance(keyboard, types.ReplyKeyboardMarkup):
        msg = await message.answer(text, reply_markup=keyboard)
        await state.update_data(active_message_id=msg.message_id)
        return

    if msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text=text,
                reply_markup=keyboard,
            )
            return
        except Exception:
            pass

    msg = await message.answer(text, reply_markup=keyboard)
    await state.update_data(active_message_id=msg.message_id)


def get_back_texts() -> tuple[str, str]:
    """Get back button texts for both languages."""
    return (get_text("back", "ua"), get_text("back", "en"))


def get_cancel_texts() -> tuple[str, str]:
    """Get cancel button texts for both languages."""
    return (get_text("cancel", "ua"), get_text("cancel", "en"))


def get_stations_by_line(router: MetroRouter, line_key: str, lang: Language = "ua") -> list[str]:
    """Get station names for a given line.

    Args:
        router: MetroRouter instance
        line_key: Internal line key (e.g., "kholodnohirsko_zavodska")
        lang: Language code

    Returns:
        List of station names in the requested language
    """
    normalized_key = _normalize_line_key(line_key)
    if not normalized_key:
        return []
    name_attr = f"name_{lang}"
    return [getattr(st, name_attr) for st in router.stations.values() if st.line.value == normalized_key]


def get_stations_by_line_except(
    router: MetroRouter, line_key: str, exclude_station: str, lang: Language = "ua"
) -> list[str]:
    """Get station names for a line, excluding one station.

    Args:
        router: MetroRouter instance
        line_key: Internal line key (e.g., "kholodnohirsko_zavodska")
        exclude_station: Station name to exclude
        lang: Language code

    Returns:
        List of station names in the requested language
    """
    normalized_key = _normalize_line_key(line_key)
    if not normalized_key:
        return []
    name_attr = f"name_{lang}"
    return [
        getattr(st, name_attr)
        for st in router.stations.values()
        if st.line.value == normalized_key and getattr(st, name_attr) != exclude_station
    ]


def _format_minutes(duration: int, min_text: str, approximate: bool = False) -> str:
    prefix = "~" if approximate and duration == 2 else ""
    return f"{prefix}{duration} {min_text}"


def format_route(route: Route, lang: Language = "ua") -> str:
    """Format route for Telegram."""
    from kharkiv_metro_core import get_text

    from .constants import LINE_COLOR_EMOJI

    if not route.segments:
        return ""

    name_attr = f"name_{lang}"
    min_text = get_text("min", lang)

    header_duration = (
        _format_minutes(route.total_duration_minutes, min_text, approximate=True)
        if route.departure_time is None or route.arrival_time is None
        else f"{route.total_duration_minutes} {min_text}"
    )

    lines = [
        f"🚇 {getattr(route.segments[0].from_station, name_attr)} → {getattr(route.segments[-1].to_station, name_attr)}",
        f"⏱ {header_duration}",
        "",
        f"{get_text('route', lang)}:",
    ]

    for group in route.to_line_groups():
        if group["is_transfer"]:
            lines.append("")
            lines.append(
                f"🔄 {getattr(group['from'], name_attr)} → {getattr(group['to'], name_attr)} "
                f"(<{_format_minutes(group['duration_minutes'], min_text, approximate=not group['computed_delta'])})"
            )
            lines.append("")
            continue

        line = group["line"]
        color_emoji = LINE_COLOR_EMOJI.get(line.color, "⚪")
        start_time = group.get("departure_time")
        end_time = group.get("arrival_time")
        has_times = start_time and end_time
        time_str = (
            f"{start_time.strftime('%H:%M')} → {end_time.strftime('%H:%M')}"
            if has_times
            else _format_minutes(group["duration_minutes"], min_text, approximate=True)
        )
        duration_str = (
            f"{group['duration_minutes']} {min_text}"
            if has_times
            else _format_minutes(group["duration_minutes"], min_text, approximate=True)
        )

        lines.append(f"{color_emoji} {getattr(group['from'], name_attr)} → {getattr(group['to'], name_attr)}")
        lines.append(f"• {time_str} ({duration_str})")

    return "\n".join(lines)


def format_schedule(station_name: str, schedules: list, router: MetroRouter, lang: Language = "ua") -> str:
    """Format schedule for Telegram."""
    from kharkiv_metro_core import get_text

    name_attr = f"name_{lang}"
    day_type_text = get_text("weekday" if schedules[0].day_type.value == "weekday" else "weekend", lang)

    lines = [f"🚇 {station_name}", f"📅 {day_type_text}", ""]

    # Deduplicate schedules by actual destination station name
    seen_directions = set()
    unique_schedules = []
    for sch in schedules:
        dir_station = router.stations.get(sch.direction_station_id)
        if not dir_station:
            continue
        # Use station name as unique key (handles duplicate IDs for same station)
        direction_key = getattr(dir_station, name_attr)
        if direction_key not in seen_directions:
            seen_directions.add(direction_key)
            unique_schedules.append((sch, dir_station))

    for sch, dir_station in unique_schedules[:2]:  # Up to 2 unique directions
        direction_text = get_text("direction", lang)
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
    line_key = _normalize_line_key(line_name) or line_name
    display_name = get_line_display_name(line_key, lang)
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
