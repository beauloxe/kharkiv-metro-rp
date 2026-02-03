"""CLI utilities."""

from __future__ import annotations

import os
import sqlite3
from typing import TYPE_CHECKING

import click
from click.exceptions import Exit
from rich.console import Console
from rich.table import Table

from ..config import Config
from ..core.models import Line
from ..data.database import MetroDatabase
from ..data.initializer import init_database

if TYPE_CHECKING:
    from ..core.router import Route

console = Console()

# Translation dictionary
TRANSLATIONS = {
    "ua": {
        "From": "Звідки",
        "To": "Куди",
        "Type": "Тип",
        "Time": "Час",
        "Total time": "Загальний час",
        "Transfers": "Пересадки",
        "Departure": "Відправлення",
        "Arrival": "Прибуття",
        "Transfer": "Пересадка",
        "Line": "Лінія",
        "Direction": "Напрямок",
        "{count} transfer": "{count} пересадка",
        "{count} transfers": "{count} пересадки",
        "no transfers": "без пересадок",
        "min": "хв",
        "Station": "Станція",
        "Minutes": "Хвилини",
        "Hour": "Година",
    },
    "en": {
        "From": "From",
        "To": "To",
        "Type": "Type",
        "Time": "Time",
        "Total time": "Total time",
        "Transfers": "Transfers",
        "Departure": "Departure",
        "Arrival": "Arrival",
        "Transfer": "Transfer",
        "Line": "Line",
        "Direction": "Direction",
        "{count} transfer": "{count} transfer",
        "{count} transfers": "{count} transfers",
        "no transfers": "no transfers",
        "min": "min",
        "Station": "Station",
        "Minutes": "Minutes",
        "Hour": "Hour",
    },
}


def _(key: str, lang: str = "ua") -> str:
    """Get translation for a key."""
    return TRANSLATIONS.get(lang, TRANSLATIONS["ua"]).get(key, key)


def _plural_transfers(count: int, lang: str = "ua") -> str:
    """Get localized transfer count string."""
    if lang == "ua":
        if count == 0:
            return _("no transfers", lang)
        elif count == 1:
            return _("{count} transfer", lang).format(count=count)
        else:
            return _("{count} transfers", lang).format(count=count)
    else:  # English
        if count == 0:
            return _("no transfers", lang)
        elif count == 1:
            return _("{count} transfer", lang).format(count=count)
        else:
            return _("{count} transfers", lang).format(count=count)


def _get_line_color_rich(line: Line) -> str:
    """Get rich color markup for a metro line."""
    color_map = {
        "red": "[red]",
        "blue": "[blue]",
        "green": "[green]",
    }
    return color_map.get(line.color, "[white]")


def _check_db_exists(db_path: str) -> bool:
    """Check if database file exists and has data."""
    if not os.path.exists(db_path):
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM stations")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def _auto_init_xdg(config: Config) -> MetroDatabase:
    """Auto-initialize XDG directories and database."""
    config.ensure_dirs()
    config.create_default()

    db_path = config.get_db_path()

    if not _check_db_exists(db_path):
        console.print("[cyan]ℹ First run detected[/cyan]")
        console.print(f"[dim]Config:[/dim] {config.config_path}")
        console.print(f"[dim]Database:[/dim] {db_path}\n")

        db = init_database(db_path)

        console.print(f"[green]✓[/green] Initialized {db_path}")
        console.print("[yellow]ℹ[/yellow] Run 'metro scrape' to populate schedules\n")
    else:
        db = MetroDatabase(db_path)

    return db


def _get_db(ctx: click.Context) -> MetroDatabase:
    """Get database instance, auto-initialize if needed."""
    config: Config = ctx.obj["config"]
    cli_override: str | None = ctx.obj.get("db_path")

    # Check environment variable if no CLI override
    if not cli_override:
        cli_override = os.getenv("DB_PATH")

    if cli_override:
        # CLI override or env var - use specified path
        if not _check_db_exists(cli_override):
            console.print(f"[red]✗[/red] Database not found at: {cli_override}")
            console.print("[yellow]Run:[/yellow] metro init --db-path " + cli_override)
            raise Exit(1)
        return MetroDatabase(cli_override)

    # Use XDG paths with auto-initialization
    return _auto_init_xdg(config)


def _display_route_table(route: Route, lang: str, console: Console, compact: bool = False) -> None:
    """Display route in table format."""
    name_attr = f"name_{lang}"

    total_time = route.total_duration_minutes
    transfers = route.num_transfers
    transfers_str = _plural_transfers(transfers, lang)

    # Show departure → arrival | total time, transfers
    if route.departure_time and route.arrival_time:
        dep = route.departure_time.strftime("%H:%M")
        arr = route.arrival_time.strftime("%H:%M")
        time_str = f"{dep} → {arr} | {total_time} {_('min', lang)}, {transfers_str}"
    else:
        time_str = f"{total_time} {_('min', lang)}, {transfers_str}"

    console.print(f"[dim]{time_str}[/dim]")

    # Table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column(_("From", lang))
    table.add_column(_("To", lang))
    table.add_column(_("Line", lang))
    table.add_column(_("Time", lang))

    if compact:
        # Group segments by line, showing only start/end for each line section
        i = 0
        while i < len(route.segments):
            segment = route.segments[i]

            if segment.is_transfer:
                # Transfer segment - show individually
                from_name = getattr(segment.from_station, name_attr)
                to_name = getattr(segment.to_station, name_attr)
                seg_type = f"[yellow]{_('Transfer', lang)}[/yellow]"
                time_str = f"{segment.duration_minutes} {_('min', lang)}"
                table.add_row(from_name, to_name, seg_type, time_str)
                i += 1
            else:
                # Train segment - find all consecutive segments on same line
                line = segment.from_station.line
                line_name = getattr(line, f"display_name_{lang}")
                color = line.color
                seg_type = f"[{color}]{line_name}[/{color}]"

                # Start of this line section
                start_station = segment.from_station
                start_time = segment.departure_time

                # Find end of this line section
                end_station = segment.to_station
                end_time = segment.arrival_time
                total_segment_time = segment.duration_minutes

                i += 1
                while i < len(route.segments) and not route.segments[i].is_transfer:
                    # Continue on same line
                    end_station = route.segments[i].to_station
                    end_time = route.segments[i].arrival_time
                    total_segment_time += route.segments[i].duration_minutes
                    i += 1

                from_name = getattr(start_station, name_attr)
                to_name = getattr(end_station, name_attr)

                if start_time and end_time:
                    dep = start_time.strftime("%H:%M")
                    arr = end_time.strftime("%H:%M")
                    time_str = f"{dep} → {arr} | {total_segment_time} {_('min', lang)}"
                else:
                    time_str = f"{total_segment_time} {_('min', lang)}"

                table.add_row(from_name, to_name, seg_type, time_str)
    else:
        # Full mode - show every segment
        for segment in route.segments:
            from_name = getattr(segment.from_station, name_attr)
            to_name = getattr(segment.to_station, name_attr)

            if segment.is_transfer:
                seg_type = f"[yellow]{_('Transfer', lang)}[/yellow]"
                time_str = f"{segment.duration_minutes} {_('min', lang)}"
            else:
                line = segment.from_station.line
                line_name = getattr(line, f"display_name_{lang}")
                color = line.color
                seg_type = f"[{color}]{line_name}[/{color}]"

                if segment.departure_time and segment.arrival_time:
                    dep = segment.departure_time.strftime("%H:%M")
                    arr = segment.arrival_time.strftime("%H:%M")
                    time_str = f"{dep} → {arr} | {segment.duration_minutes} {_('min', lang)}"
                else:
                    time_str = f"{segment.duration_minutes} {_('min', lang)}"

            table.add_row(from_name, to_name, seg_type, time_str)

    console.print(table)


def _display_route_simple(route: Route, lang: str, console: Console, compact: bool = False) -> None:
    """Display route in inline format."""
    name_attr = f"name_{lang}"

    # Build the path showing stations
    path_parts = []

    if not route.segments:
        return

    if compact:
        # Compact mode - build path string incrementally with transfer indicators
        first_station = route.segments[0].from_station
        first_name = getattr(first_station, name_attr)
        first_color = first_station.line.color
        path_str = f"[{first_color}]{first_name}[/{first_color}]"

        for segment in route.segments:
            if segment.is_transfer:
                # Transfer segment: from_station is where we exit, to_station is where we enter new line
                from_name = getattr(segment.from_station, name_attr)
                to_name = getattr(segment.to_station, name_attr)
                to_color = segment.to_station.line.color

                path_str += f" → {from_name} ⇌ [{to_color}]{to_name}[/{to_color}]"

        # End station (if not already added as transfer)
        last_segment = route.segments[-1]
        last_station = last_segment.to_station
        last_name = getattr(last_station, name_attr)

        if not last_segment.is_transfer:
            path_str += f" → {last_name}"
    else:
        # Full mode - all stations with transfer indicators
        added_stations = set()

        first_station = route.segments[0].from_station
        first_name = getattr(first_station, name_attr)
        first_color = first_station.line.color
        path_str = f"[{first_color}]{first_name}[/{first_color}]"
        added_stations.add(first_name)

        for segment in route.segments:
            to_name = getattr(segment.to_station, name_attr)

            if to_name in added_stations:
                continue

            if segment.is_transfer:
                # Transfer - use double arrow and color the station
                transfer_line = segment.to_station.line
                transfer_color = transfer_line.color
                path_str += f" ⇌ [{transfer_color}]{to_name}[/{transfer_color}]"
            else:
                # Same line - use single arrow, plain text
                path_str += f" → {to_name}"

            added_stations.add(to_name)

    total_time = route.total_duration_minutes
    transfers = route.num_transfers
    transfers_str = _plural_transfers(transfers, lang)

    # Build time info for each line segment (segmented for simple mode)
    time_parts = []
    current_line_start_time = None
    current_line_end_time = None

    for segment in route.segments:
        if segment.is_transfer:
            # End of line section - add its time
            if current_line_start_time and current_line_end_time:
                dep = current_line_start_time.strftime("%H:%M")
                arr = current_line_end_time.strftime("%H:%M")
                time_parts.append(f"{dep} → {arr}")
            current_line_start_time = None
            current_line_end_time = None
        else:
            # Train segment
            if current_line_start_time is None and segment.departure_time:
                current_line_start_time = segment.departure_time
            if segment.arrival_time:
                current_line_end_time = segment.arrival_time

    # Don't forget last line section
    if current_line_start_time and current_line_end_time:
        dep = current_line_start_time.strftime("%H:%M")
        arr = current_line_end_time.strftime("%H:%M")
        time_parts.append(f"{dep} → {arr}")

    if time_parts:
        time_str = "; ".join(time_parts) + f" | {total_time} {_('min', lang)}, {transfers_str}"
    else:
        time_str = f"{total_time} {_('min', lang)}, {transfers_str}"

    console.print(f"[dim]{time_str}[/dim]")
    console.print(f"{path_str}")
