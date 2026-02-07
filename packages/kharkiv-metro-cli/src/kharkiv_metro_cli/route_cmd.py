"""Route command for metro CLI."""

from __future__ import annotations

import json
from datetime import datetime

import click
from click.exceptions import Exit
from kharkiv_metro_core import Config, DayType, MetroClosedError, MetroDatabase, MetroRouter, now

from .utils import console, display_route_simple, display_route_table


@click.command()
@click.argument("from_station")
@click.argument("to_station")
@click.option("--time", "-t", help="Departure time (HH:MM)")
@click.option("--date", "-d", help="Departure date (YYYY-MM-DD)")
@click.option("--day-type", "-s", type=click.Choice(["weekday", "weekend"]), help="Day type (overrides date)")
@click.option("--lang", "-l", type=click.Choice(["ua", "en"]), help="Language for station names")
@click.option("--format", "-f", type=click.Choice(["full", "simple", "json"]), help="Output format")
@click.option("--compact", "-c", is_flag=True, help="Show only key stations (start, transfers, end)")
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
    config: Config = ctx.obj["config"]
    lang = lang or config.get("preferences.language", "ua")
    fmt = format or config.get("preferences.route.format", "full")

    # Handle compact flag logic
    config_compact = config.get("preferences.route.compact", False)
    show_compact = (not config_compact) if compact else config_compact

    try:
        # Get database
        db_path = str(ctx.obj.get("db_path") or config.get_db_path())
        db = MetroDatabase(db_path)
        router = MetroRouter(db=db)

        # Find stations
        from_st = router.find_station_by_name(from_station, lang)
        to_st = router.find_station_by_name(to_station, lang)

        if not from_st:
            click.echo(f"Station not found: {from_station}", err=True)
            raise Exit(1)
        if not to_st:
            click.echo(f"Station not found: {to_station}", err=True)
            raise Exit(1)

        # Parse departure time
        if time:
            hour, minute = map(int, time.split(":"))
        else:
            current_time = now()
            hour, minute = current_time.hour, current_time.minute

        if date:
            year, month, day = map(int, date.split("-"))
            departure_time = datetime(year, month, day, hour, minute, tzinfo=Config.TIMEZONE)
        else:
            departure_time = now().replace(hour=hour, minute=minute, second=0, microsecond=0)

        # Determine day type
        day_type_enum = None
        if day_type:
            day_type_enum = DayType.WEEKDAY if day_type == "weekday" else DayType.WEEKEND

        # Find route
        try:
            route_result = router.find_route(from_st.id, to_st.id, departure_time, day_type_enum)
        except MetroClosedError:
            error_msg = "Метро закрите та/або на останній потяг неможливо встигнути"
            if fmt == "json":
                click.echo(json.dumps({"status": "error", "message": error_msg}))
            else:
                console.print(f"[red]Error:[/red] {error_msg}")
            raise Exit(1)

        if not route_result:
            click.echo("No route found", err=True)
            raise Exit(1)

        # Output result
        _output_route(route_result, from_st, to_st, lang, fmt, show_compact)

    except Exception as e:
        if fmt == "json":
            click.echo(json.dumps({"status": "error", "message": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise Exit(1)


def _output_route(route, from_st, to_st, lang: str, fmt: str, compact: bool) -> None:
    """Output route in the specified format."""
    if fmt == "json":
        result = {
            "from": getattr(from_st, f"name_{lang}"),
            "to": getattr(to_st, f"name_{lang}"),
            "route": route.to_dict(lang),
        }
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    elif fmt == "simple":
        display_route_simple(route, lang, compact=compact)
    else:
        display_route_table(route, lang, compact=compact)
