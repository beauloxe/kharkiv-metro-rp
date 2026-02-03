"""Route command for metro CLI."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import click
from click.exceptions import Exit

from ..bot.constants import TIMEZONE
from ..config import Config
from ..core.models import DayType
from ..core.router import MetroRouter
from .utils import _display_route_simple, _display_route_table, _get_db, console


@click.command()
@click.argument("from_station")
@click.argument("to_station")
@click.option(
    "--time",
    "-t",
    help="Departure time (HH:MM)",
    default=None,
)
@click.option(
    "--date",
    "-d",
    help="Departure date (YYYY-MM-DD)",
    default=None,
)
@click.option(
    "--day-type",
    "-s",
    type=click.Choice(["weekday", "weekend"]),
    help="Day type (overrides date)",
    default=None,
)
@click.option(
    "--lang",
    "-l",
    type=click.Choice(["ua", "en"]),
    default=None,
    help="Language for station names",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["full", "simple", "json"]),
    default=None,
    help="Output format (full=detailed table, simple=inline, json=JSON)",
)
@click.option(
    "--compact",
    "-c",
    is_flag=True,
    help="Show only key stations (start, transfers, end)",
)
@click.pass_context
def route(
    ctx: click.Context,
    from_station: str,
    to_station: str,
    time: str | None,
    date: str | None,
    day_type: str | None,
    lang: str | None,
    format: str | None,
    compact: bool,
) -> None:
    """Find route between two stations."""
    # Initialize defaults
    fmt = "full"

    try:
        config: Config = ctx.obj["config"]

        # Use config defaults if not specified
        if lang is None:
            lang = config.get("preferences.language", "ua")

        # Check preferences.route.format first, fallback to "full"
        fmt = config.get("preferences.route.format", "full") if format is None else format

        # CLI flag inverts the config setting
        # If config compact=true, --compact shows full version
        # If config compact=false (default), --compact shows compact version
        config_compact = config.get("preferences.route.compact", False)
        compact = (not config_compact) if compact else config_compact

        # Ensure lang is not None
        lang = lang or "ua"
        fmt = fmt or "full"

        router = MetroRouter(db=_get_db(ctx))

        # Find stations
        from_st = router.find_station_by_name(from_station, lang)
        to_st = router.find_station_by_name(to_station, lang)

        if not from_st:
            click.echo(f"Station not found: {from_station}", err=True)
            raise Exit(1)

        if not to_st:
            click.echo(f"Station not found: {to_station}", err=True)
            raise Exit(1)

        # Parse departure time (with configured timezone)
        if time:
            hour, minute = map(int, time.split(":"))
        else:
            now = datetime.now(TIMEZONE)
            hour, minute = now.hour, now.minute

        if date:
            year, month, day = map(int, date.split("-"))
            departure_time = datetime(year, month, day, hour, minute, tzinfo=TIMEZONE)
        else:
            departure_time = datetime.now(TIMEZONE).replace(hour=hour, minute=minute, second=0, microsecond=0)

        # Override day type if specified
        dt = (DayType.WEEKDAY if day_type == "weekday" else DayType.WEEKEND) if day_type else None

        # Find route
        route = router.find_route(from_st.id, to_st.id, departure_time, dt)

        if not route:
            click.echo("No route found", err=True)
            raise Exit(1)

        # Output
        if fmt == "json":
            result = {
                "from": getattr(from_st, f"name_{lang}"),
                "to": getattr(to_st, f"name_{lang}"),
                "route": route.to_dict(lang),
            }
            click.echo(json.dumps(result, indent=2, ensure_ascii=False))
        elif fmt == "simple":
            _display_route_simple(route, lang, console, compact=compact)
        else:
            _display_route_table(route, lang, console, compact=compact)

    except Exception as e:
        if fmt == "json":
            click.echo(json.dumps({"status": "error", "message": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise Exit(1)
