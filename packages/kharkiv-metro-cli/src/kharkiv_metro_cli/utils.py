"""CLI utilities."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

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
    from kharkiv_metro_core import get_text

    if count == 0:
        return get_text("no_transfers", lang)
    # Get pluralized form from core translations
    key = f"transfers_{'one' if count == 1 else 'many'}"
    text = get_text(key, lang)
    return text.format(count=count)


def get_db_path(ctx: click.Context) -> str:
    """Get database path from context or config."""
    if ctx.obj.get("db_path"):
        return ctx.obj["db_path"]
    config: Config = ctx.obj["config"]
    return config.get_db_path()


def ensure_db(db_path: str) -> MetroDatabase:
    """Ensure database exists and return it."""
    if not os.path.exists(db_path):
        console.print(f"[red]✗[/red] Database not found at: {db_path}")
        console.print("[yellow]Run:[/yellow] metro init")
        raise Exit(1)
    return MetroDatabase(db_path)


def init_db_if_needed(config: Config) -> MetroDatabase:
    """Initialize database if it doesn't exist."""
    db_path = config.get_db_path()
    if not os.path.exists(db_path):
        console.print("[cyan]ℹ First run detected[/cyan]")
        console.print(f"[dim]Database:[/dim] {db_path}\n")
        db = init_database(db_path)
        console.print(f"[green]✓[/green] Initialized {db_path}")
        console.print("[yellow]ℹ[/yellow] Run 'metro scrape' to populate schedules\n")
        return db
    return MetroDatabase(db_path)


def display_route_table(route: Route, lang: str, compact: bool = False) -> None:
    """Display route as table."""
    total = route.total_duration_minutes
    transfers = format_transfers(route.num_transfers, lang)

    # Time header
    if route.departure_time and route.arrival_time:
        dep = route.departure_time.strftime("%H:%M")
        arr = route.arrival_time.strftime("%H:%M")
        time_str = f"{dep} → {arr} | {total} {_('min', lang)}, {transfers}"
    else:
        time_str = f"{total} {_('min', lang)}, {transfers}"
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
        for seg in route.segments:
            from_name = getattr(seg.from_station, name_attr)
            to_name = getattr(seg.to_station, name_attr)

            if seg.is_transfer:
                line_str = f"[yellow]{_('Transfer', lang)}[/yellow]"
                time_str = f"{seg.duration_minutes} {_('min', lang)}"
            else:
                line = seg.from_station.line
                line_name = getattr(line, f"display_name_{lang}")
                line_str = f"[{line.color}]{line_name}[/{line.color}]"
                if seg.departure_time and seg.arrival_time:
                    dep = seg.departure_time.strftime("%H:%M")
                    arr = seg.arrival_time.strftime("%H:%M")
                    time_str = f"{dep} → {arr} | {seg.duration_minutes} {_('min', lang)}"
                else:
                    time_str = f"{seg.duration_minutes} {_('min', lang)}"

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
    i = 0
    while i < len(route.segments):
        seg = route.segments[i]

        if seg.is_transfer:
            i += 1
            continue

        # Start of line segment
        start_time = seg.departure_time
        end_time = seg.arrival_time

        # Find end of this line section
        i += 1
        while i < len(route.segments) and not route.segments[i].is_transfer:
            end_time = route.segments[i].arrival_time
            i += 1

        if start_time and end_time:
            dep = start_time.strftime("%H:%M")
            arr = end_time.strftime("%H:%M")
            time_parts.append(f"{dep} → {arr}")

    if time_parts:
        time_str = "; ".join(time_parts) + f" | {total} {_('min', lang)}, {transfers}"
    else:
        time_str = f"{total} {_('min', lang)}, {transfers}"

    console.print(f"[dim]{time_str}[/dim]")
    console.print(path_str)


def _group_segments(route: Route, lang: str) -> list[dict]:
    """Group segments by line for compact view."""
    result = []
    name_attr = f"name_{lang}"
    i = 0

    while i < len(route.segments):
        seg = route.segments[i]

        if seg.is_transfer:
            result.append(
                {
                    "from": getattr(seg.from_station, name_attr),
                    "to": getattr(seg.to_station, name_attr),
                    "line": f"[yellow]{_('Transfer', lang)}[/yellow]",
                    "time": f"{seg.duration_minutes} {_('min', lang)}",
                }
            )
            i += 1
        else:
            # Group consecutive segments on same line
            line = seg.from_station.line
            line_name = getattr(line, f"display_name_{lang}")
            start_station = seg.from_station
            start_time = seg.departure_time
            end_station = seg.to_station
            end_time = seg.arrival_time
            total_time = seg.duration_minutes

            i += 1
            while i < len(route.segments) and not route.segments[i].is_transfer:
                end_station = route.segments[i].to_station
                end_time = route.segments[i].arrival_time
                total_time += route.segments[i].duration_minutes
                i += 1

            time_str = (
                f"{start_time.strftime('%H:%M')} → {end_time.strftime('%H:%M')} | {total_time} {_('min', lang)}"
                if start_time and end_time
                else f"{total_time} {_('min', lang)}"
            )

            result.append(
                {
                    "from": getattr(start_station, name_attr),
                    "to": getattr(end_station, name_attr),
                    "line": f"[{line.color}]{line_name}[/{line.color}]",
                    "time": time_str,
                }
            )

    return result


def _build_compact_path(route: Route, name_attr: str) -> str:
    """Build compact path string."""
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
