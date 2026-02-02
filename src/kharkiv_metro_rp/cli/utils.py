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
        console.print(f"[cyan]ℹ First run detected[/cyan]")
        console.print(f"[dim]Config:[/dim] {config.config_path}")
        console.print(f"[dim]Database:[/dim] {db_path}\n")

        db = init_database(db_path)

        console.print(f"[green]✓[/green] Initialized {db_path}")
        console.print(f"[yellow]ℹ[/yellow] Run 'metro scrape' to populate schedules\n")
    else:
        db = MetroDatabase(db_path)

    return db


def _get_db(ctx: click.Context) -> MetroDatabase:
    """Get database instance, auto-initialize if needed."""
    config: Config = ctx.obj["config"]
    cli_override: str | None = ctx.obj.get("db_path")

    if cli_override:
        # CLI override - use specified path
        if not _check_db_exists(cli_override):
            console.print(f"[red]✗[/red] Database not found at: {cli_override}")
            console.print("[yellow]Run:[/yellow] metro init --db-path " + cli_override)
            raise Exit(1)
        return MetroDatabase(cli_override)

    # Use XDG paths with auto-initialization
    return _auto_init_xdg(config)


def _display_route_table(route: Route, lang: str, console: Console) -> None:
    """Display route in table format."""
    name_attr = f"name_{lang}"

    # Summary
    total_time = route.total_duration_minutes
    transfers = route.num_transfers

    console.print(
        f"[bold]{_('Total time', lang)}:[/bold] {total_time} {_('min', lang)} | [bold]{_('Transfers', lang)}:[/bold] {transfers}"
    )

    if route.departure_time and route.arrival_time:
        dep = route.departure_time.strftime("%H:%M")
        arr = route.arrival_time.strftime("%H:%M")
        console.print(f"[bold]{_('Departure', lang)}:[/bold] {dep} | [bold]{_('Arrival', lang)}:[/bold] {arr}")

    # Table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column(_("From", lang))
    table.add_column(_("To", lang))
    table.add_column(_("Line", lang))
    table.add_column(_("Time", lang))

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
                time_str = f"{dep} → {arr} ({segment.duration_minutes} {_('min', lang)})"
            else:
                time_str = f"{segment.duration_minutes} {_('min', lang)}"

        table.add_row(from_name, to_name, seg_type, time_str)

    console.print(table)


def _display_route_simple(route: Route, lang: str, console: Console) -> None:
    """Display route in compact inline format."""
    name_attr = f"name_{lang}"

    # Build the path showing all stations
    path_parts = []
    added_stations = set()

    if route.segments:
        first_station = route.segments[0].from_station
        first_name = getattr(first_station, name_attr)
        path_parts.append(first_name)
        added_stations.add(first_name)

    for segment in route.segments:
        to_name = getattr(segment.to_station, name_attr)

        if segment.is_transfer:
            transfer_line = segment.to_station.line
            transfer_color = transfer_line.color
            path_parts.append(f"[{transfer_color}]{to_name}[/{transfer_color}]")
            added_stations.add(to_name)
        else:
            if to_name not in added_stations:
                path_parts.append(to_name)
                added_stations.add(to_name)

    path_str = " → ".join(path_parts)
    total_time = route.total_duration_minutes
    transfers = route.num_transfers

    if route.departure_time and route.arrival_time:
        dep = route.departure_time.strftime("%H:%M")
        arr = route.arrival_time.strftime("%H:%M")
        time_str = f"{dep} → {arr} ({total_time} {_('min', lang)})"
    else:
        time_str = f"{total_time} {_('min', lang)}"

    transfers_str = _plural_transfers(transfers, lang)

    console.print(f"{path_str}")
    console.print(f"[dim]{time_str} | {transfers_str}[/dim]")
