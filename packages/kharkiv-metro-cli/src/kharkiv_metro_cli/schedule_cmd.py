"""Schedule command for metro CLI."""

from __future__ import annotations

import json
from datetime import time
from typing import TYPE_CHECKING

import click
from click.exceptions import Exit
from kharkiv_metro_core import Config, DayType, MetroDatabase, MetroRouter, now
from kharkiv_metro_core import get_text as tr
from rich.table import Table

from .utils import console

if TYPE_CHECKING:
    from click.core import Context


@click.command()
@click.argument("station")
@click.option(
    "--direction",
    "-d",
    help="Direction (terminal station name)",
    default=None,
)
@click.option(
    "--day-type",
    "-s",
    type=click.Choice(["weekday", "weekend"]),
    help="Day type",
    default=None,
)
@click.option(
    "--lang",
    "-l",
    type=click.Choice(["ua", "en"]),
    default=None,
    help="Language",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "table"]),
    default=None,
    help="Output format",
)
@click.pass_context
def schedule(
    ctx: Context,
    station: str,
    direction: str | None,
    day_type: str | None,
    lang: str | None,
    output: str | None,
) -> None:
    """Show schedule for a station."""
    fmt = output or "table"

    try:
        config: Config = ctx.obj["config"]
        lang = lang or config.get("preferences.language", "ua")

        # Get database and router
        db_path = str(ctx.obj.get("db_path") or config.get_db_path())
        db = MetroDatabase(db_path)
        router = MetroRouter(db=db)

        # Find station
        st = router.find_station_by_name(station, lang)
        if not st:
            click.echo(f"Station not found: {station}", err=True)
            raise Exit(1)

        # Determine day type
        day_type_enum = (
            DayType.WEEKDAY
            if day_type == "weekday"
            else DayType.WEEKEND
            if day_type
            else (DayType.WEEKDAY if now().weekday() < 5 else DayType.WEEKEND)
        )

        # Find direction if specified
        direction_id = None
        if direction:
            dir_st = router.find_station_by_name(direction, lang)
            if dir_st:
                direction_id = dir_st.id

        # Get operating hours
        first_departure = db.get_first_departure_time(day_type_enum)
        last_departure = db.get_last_departure_time(day_type_enum)

        # Check if metro is open
        check_time = now().time()
        is_open, _, _ = db.is_metro_open(day_type_enum, check_time)

        # Get schedules
        schedules = router.get_station_schedule(st.id, direction_id, day_type_enum)
        if not schedules:
            click.echo("No schedule found", err=True)
            raise Exit(1)

        # Output
        if fmt == "json":
            _output_json(st, schedules, router, lang)
        else:
            _output_table(st, schedules, router, lang, first_departure, last_departure, is_open)

    except Exception as e:
        if fmt == "json":
            click.echo(json.dumps({"status": "error", "message": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise Exit(1)


def _output_json(st, schedules, router, lang: str) -> None:
    """Output schedule in JSON format."""
    result = {
        "station": getattr(st, f"name_{lang}"),
        "schedules": [
            {
                "direction": router.stations.get(sch.direction_station_id, st).name_ua,
                "entries": [{"hour": e.hour, "minutes": e.minutes} for e in sch.entries[:20]],
            }
            for sch in schedules
        ],
    }
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))


def _output_table(
    st,
    schedules,
    router,
    lang: str,
    first_departure: time | None,
    last_departure: time | None,
    is_open: bool,
) -> None:
    """Output schedule in table format."""
    name_attr = f"name_{lang}"

    # Show station name and line
    line_name = getattr(st.line, f"display_name_{lang}")
    console.print(
        f"[dim]{tr('Station', lang)}:[/dim] {getattr(st, name_attr)} ({line_name} {tr('Line', lang).lower()})"
    )

    # Collect schedule data
    schedule_data = []
    all_hours = set()

    for sch in schedules:
        dir_st = router.stations.get(sch.direction_station_id)
        if not dir_st:
            continue

        dir_name = getattr(dir_st, name_attr)
        entries_by_hour: dict[int, list[int]] = {}

        for entry in sch.entries:
            if entry.hour not in entries_by_hour:
                entries_by_hour[entry.hour] = []
            entries_by_hour[entry.hour].append(entry.minutes)
            all_hours.add(entry.hour)

        schedule_data.append((dir_name, entries_by_hour))

    if not schedule_data:
        console.print("[yellow]No schedule data available[/yellow]")
        return

    # Display table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column(tr("Hour", lang))

    for dir_name, _ in schedule_data:
        table.add_column(dir_name)

    for hour in sorted(all_hours):
        row = [f"{hour:02d}"]
        for _, entries_by_hour in schedule_data:
            minutes_list = entries_by_hour.get(hour, [])
            if minutes_list:
                minutes_str = ", ".join(f"{m:02d}" for m in sorted(minutes_list))
                row.append(minutes_str)
            else:
                row.append("")
        table.add_row(*row)

    console.print(table)
