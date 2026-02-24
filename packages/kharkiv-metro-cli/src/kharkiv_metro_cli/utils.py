"""CLI utilities."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Callable

import click
from click.exceptions import Exit
from kharkiv_metro_core import Config, MetroDatabase, init_database
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from kharkiv_metro_core import Route

console = Console()


def _(key: str, lang: str = "ua") -> str:
    """Get translation from core i18n."""
    from kharkiv_metro_core import get_text

    return get_text(key, lang)


def format_transfers(count: int, lang: str = "ua") -> str:
    """Format transfer count."""
    from kharkiv_metro_core import format_transfers as core_format_transfers

    return core_format_transfers(count, lang)


def get_config(ctx: click.Context) -> Config:
    """Get Config instance from context."""
    return ctx.obj["config"]


def get_db_path(ctx: click.Context) -> str:
    """Get database path from context or config."""
    if ctx.obj.get("db_path"):
        return ctx.obj["db_path"]
    return get_config(ctx).get_db_path()


def ensure_db(db_path: str) -> MetroDatabase:
    """Ensure database exists and return it."""
    if not os.path.exists(db_path):
        console.print(f"[red]✗[/red] Database not found at: {db_path}")
        console.print("[yellow]Run:[/yellow] metro init")
        raise Exit(1)
    return MetroDatabase.shared(db_path)


def init_or_get_db(db_path: str) -> MetroDatabase:
    """Initialize database if needed and return it."""
    if not os.path.exists(db_path):
        return init_database(db_path)
    return MetroDatabase.shared(db_path)


def get_db(ctx: click.Context) -> MetroDatabase:
    """Get database instance or fail if missing."""
    return ensure_db(get_db_path(ctx))


def get_lang(ctx: click.Context, value: str | None) -> str:
    """Get language from option or config."""
    return value or get_config(ctx).get("preferences.language", "ua")


def get_output_format(ctx: click.Context, value: str | None, key: str, default: str) -> str:
    """Get output format from option or config key."""
    return value or get_config(ctx).get(key, default)


def parse_day_type(value: str | None):
    """Parse day type option into enum."""
    from kharkiv_metro_core import DayType

    if not value:
        return None
    return DayType.WEEKDAY if value == "weekday" else DayType.WEEKEND


def find_station_or_exit(router, name: str, lang: str):
    """Find station or exit with error message."""
    station = router.find_station_by_name(name, lang)
    if not station:
        click.echo(f"Station not found: {name}", err=True)
        raise Exit(1)
    return station


def run_with_error_handling(func: Callable[[], None], output: str | None = None) -> None:
    """Run command handler with consistent error handling."""
    try:
        func()
    except Exception as e:
        if output == "json":
            click.echo(json.dumps({"status": "error", "message": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise Exit(1)


def _format_minutes(duration: int, lang: str, approximate: bool = False) -> str:
    prefix = "~" if approximate and duration == 2 else ""
    return f"{prefix}{duration} {_('min', lang)}"


def display_route_table(route: Route, lang: str, compact: bool = False) -> None:
    """Display route as table."""
    total = route.total_duration_minutes
    transfers = format_transfers(route.num_transfers, lang)

    # Time header
    if route.departure_time and route.arrival_time:
        dep = route.departure_time.strftime("%H:%M")
        arr = route.arrival_time.strftime("%H:%M")
        time_str = f"{dep} → {arr} | {_format_minutes(total, lang)}, {transfers}"
    else:
        time_str = f"{_format_minutes(total, lang, approximate=True)}, {transfers}"
    console.print(f"[dim]{time_str}[/dim]")

    # Build table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column(_("From", lang))
    table.add_column(_("To", lang))
    table.add_column(_("Line", lang))
    table.add_column(_("Time", lang))

    if compact:
        segments = _group_segments(route, lang)
        for seg in segments:
            from_name = seg["from"]
            to_name = seg["to"]
            line_str = seg["line"]
            time_str = seg["time"]
            table.add_row(from_name, to_name, line_str, time_str)
    else:
        name_attr = f"name_{lang}"
        for group in route.to_line_groups():
            from_name = getattr(group["from"], name_attr)
            to_name = getattr(group["to"], name_attr)

            if group["is_transfer"]:
                line_str = f"[yellow]{_('Transfer', lang)}[/yellow]"
                time_str = (
                    f"<{_format_minutes(group['duration_minutes'], lang, approximate=not group['computed_delta'])}"
                )
            else:
                line = group["line"]
                line_name = getattr(line, f"display_name_{lang}")
                line_str = f"[{line.color}]{line_name}[/{line.color}]"
                start_time = group.get("departure_time")
                end_time = group.get("arrival_time")
                if start_time and end_time:
                    dep = start_time.strftime("%H:%M")
                    arr = end_time.strftime("%H:%M")
                    time_str = f"{dep} → {arr} | {_format_minutes(group['duration_minutes'], lang)}"
                else:
                    time_str = _format_minutes(group["duration_minutes"], lang, approximate=True)

            table.add_row(from_name, to_name, line_str, time_str)

    console.print(table)


def display_route_simple(route: Route, lang: str, compact: bool = False) -> None:
    """Display route inline."""
    if not route.segments:
        return

    name_attr = f"name_{lang}"

    # Build path string
    path_str = _build_compact_path(route, name_attr) if compact else _build_full_path(route, name_attr)

    # Time info
    total = route.total_duration_minutes
    transfers = format_transfers(route.num_transfers, lang)

    # Group time by line segments (between transfers)
    time_parts = []
    has_times = True

    for group in route.to_line_groups():
        if group["is_transfer"]:
            continue

        start_time = group.get("departure_time")
        end_time = group.get("arrival_time")
        if not start_time or not end_time:
            has_times = False
            continue

        dep = start_time.strftime("%H:%M")
        arr = end_time.strftime("%H:%M")
        time_parts.append(f"{dep} → {arr}")

    if time_parts:
        time_str = "; ".join(time_parts) + f" | {_format_minutes(total, lang, approximate=not has_times)}, {transfers}"
    else:
        time_str = f"{_format_minutes(total, lang, approximate=True)}, {transfers}"

    console.print(f"[dim]{time_str}[/dim]")
    console.print(path_str)


def format_station_rows(stations_data: list[dict], name_attr: str, lang: str) -> list[tuple[str, str]]:
    """Prepare station rows with line names."""
    from kharkiv_metro_core import Line

    rows = []
    for station in stations_data:
        line_enum = Line(station["line"])
        line_name = line_enum.display_name_ua if lang == "ua" else line_enum.display_name_en
        rows.append((line_name, station[name_attr]))
    return rows


def output_stations_table(rows: list[tuple[str, str]], lang: str) -> None:
    """Output stations in table format."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column(_("Line", lang))
    table.add_column(_("Station", lang))
    for line_name, station_name in rows:
        table.add_row(line_name, station_name)
    console.print(table)


def output_stations_json(rows: list[tuple[str, str]], stations_data: list[dict], lang: str) -> None:
    """Output stations in JSON format."""
    result = [
        {
            "id": station["id"],
            "name": station[f"name_{lang}"],
            "line": line_name,
        }
        for station, (line_name, _station_name) in zip(stations_data, rows, strict=False)
    ]
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))


def _group_segments(route: Route, lang: str) -> list[dict]:
    """Group segments by line for compact view."""
    result = []
    name_attr = f"name_{lang}"

    for group in route.to_line_groups():
        if group["is_transfer"]:
            result.append(
                {
                    "from": getattr(group["from"], name_attr),
                    "to": getattr(group["to"], name_attr),
                    "line": f"[yellow]{_('Transfer', lang)}[/yellow]",
                    "time": f"<{_format_minutes(group['duration_minutes'], lang, approximate=not group['computed_delta'])}",
                }
            )
            continue

        line = group["line"]
        line_name = getattr(line, f"display_name_{lang}")
        start_time = group.get("departure_time")
        end_time = group.get("arrival_time")
        has_times = start_time and end_time
        time_str = (
            f"{start_time.strftime('%H:%M')} → {end_time.strftime('%H:%M')} | {_format_minutes(group['duration_minutes'], lang)}"
            if has_times
            else _format_minutes(group["duration_minutes"], lang, approximate=True)
        )

        result.append(
            {
                "from": getattr(group["from"], name_attr),
                "to": getattr(group["to"], name_attr),
                "line": f"[{line.color}]{line_name}[/{line.color}]",
                "time": time_str,
            }
        )

    return result


def _build_compact_path(route: Route, name_attr: str) -> str:
    """Build compact path string."""
    if not route.segments:
        return ""

    first = route.segments[0].from_station
    path = f"[{first.line.color}]{getattr(first, name_attr)}[/{first.line.color}]"

    for seg in route.segments:
        if seg.is_transfer:
            from_name = getattr(seg.from_station, name_attr)
            to_name = getattr(seg.to_station, name_attr)
            to_color = seg.to_station.line.color
            path += f" → {from_name} ⇌ [{to_color}]{to_name}[/{to_color}]"

    last = route.segments[-1]
    if not last.is_transfer:
        path += f" → {getattr(last.to_station, name_attr)}"

    return path


def _build_full_path(route: Route, name_attr: str) -> str:
    """Build full path string."""
    if not route.segments:
        return ""

    first = route.segments[0].from_station
    path = f"[{first.line.color}]{getattr(first, name_attr)}[/{first.line.color}]"

    seen = {getattr(first, name_attr)}

    for seg in route.segments:
        to_name = getattr(seg.to_station, name_attr)
        if to_name in seen:
            continue

        if seg.is_transfer:
            color = seg.to_station.line.color
            path += f" ⇌ [{color}]{to_name}[/{color}]"
        else:
            path += f" → {to_name}"

        seen.add(to_name)

    return path
