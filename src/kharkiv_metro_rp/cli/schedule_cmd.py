"""Schedule command for metro CLI."""

from __future__ import annotations

import json
from datetime import datetime

import click
from click.exceptions import Exit

from ..config import Config
from ..core.models import DayType
from ..core.router import MetroRouter
from .utils import _get_db, console


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
    ctx: click.Context,
    station: str,
    direction: str | None,
    day_type: str | None,
    lang: str | None,
    output: str | None,
) -> None:
    """Show schedule for a station."""
    try:
        config: Config = ctx.obj["config"]

        # Use config defaults if not specified
        if lang is None:
            lang = config.get("preferences.language", "ua")
        if output is None:
            output = config.get("preferences.output_format", "table")

        # Ensure lang is not None
        lang = lang or "ua"

        router = MetroRouter(db=_get_db(ctx))

        # Find station
        st = router.find_station_by_name(station, lang)
        if not st:
            click.echo(f"Station not found: {station}", err=True)
            raise Exit(1)

        # Determine day type
        if day_type:
            dt = DayType.WEEKDAY if day_type == "weekday" else DayType.WEEKEND
        else:
            dt = DayType.WEEKDAY if datetime.now().weekday() < 5 else DayType.WEEKEND

        # Find direction if specified
        direction_id = None
        if direction:
            dir_st = router.find_station_by_name(direction, lang)
            if dir_st:
                direction_id = dir_st.id

        # Get schedules
        schedules = router.get_station_schedule(st.id, direction_id, dt)

        if not schedules:
            click.echo("No schedule found", err=True)
            raise Exit(1)

        # Output
        if output == "json":
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
        else:
            console.print(f"\n[bold cyan]{getattr(st, f'name_{lang}')}[/bold cyan]")
            console.print(f"Line: {getattr(st.line, f'display_name_{lang}')}")

            name_attr = f"name_{lang}"
            for sch in schedules:
                dir_st = router.stations.get(sch.direction_station_id)
                if dir_st:
                    dir_name = getattr(dir_st, name_attr)
                    console.print(f"\n[yellow]Direction: {dir_name}[/yellow]")

                    by_hour = {}
                    for entry in sch.entries:
                        if entry.hour not in by_hour:
                            by_hour[entry.hour] = []
                        by_hour[entry.hour].append(entry.minutes)

                    for hour in sorted(by_hour.keys()):
                        minutes_str = ", ".join(f"{m:02d}" for m in sorted(by_hour[hour]))
                        console.print(f"  {hour:2d}: {minutes_str}")

    except Exception as e:
        if output == "json":
            click.echo(json.dumps({"status": "error", "message": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise Exit(1)
