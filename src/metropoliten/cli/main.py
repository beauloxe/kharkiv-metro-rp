"""CLI interface for metro route planner."""

from __future__ import annotations

import json
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table

from ..core.models import DayType, Line
from ..core.router import MetroRouter


def _get_line_color_rich(line: Line) -> str:
    """Get rich color markup for a metro line."""
    color_map = {
        "red": "[red]",
        "blue": "[blue]",
        "green": "[green]",
    }
    return color_map.get(line.color, "[white]")


from ..data.database import MetroDatabase
from ..data.initializer import init_database

console = Console()


@click.group()
@click.option(
    "--db-path",
    default="data/metro.db",
    help="Path to database file",
    type=click.Path(),
)
@click.pass_context
def cli(ctx: click.Context, db_path: str) -> None:
    """Kharkiv Metro Route Planner CLI."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path


@cli.command()
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
def init(output: str) -> None:
    """Initialize database with station data."""
    try:
        db = init_database()

        if output == "json":
            click.echo(json.dumps({"status": "ok", "message": "Database initialized"}))
        else:
            console.print("[green]✓[/green] Database initialized successfully")
    except Exception as e:
        if output == "json":
            click.echo(json.dumps({"status": "error", "message": str(e)}))
        else:
            console.print(f"[red]✗[/red] Error: {e}")
        raise click.Exit(1)


@cli.command()
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
    type=click.Choice(["weekday", "weekend"]),
    help="Day type (overrides date)",
    default=None,
)
@click.option(
    "--num-options",
    "-n",
    type=int,
    default=1,
    help="Number of route options",
)
@click.option(
    "--lang",
    "-l",
    type=click.Choice(["ua", "en"]),
    default="ua",
    help="Language for station names",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["full", "simple", "json"]),
    default="full",
    help="Output format (full=detailed table, simple=compact inline, json=JSON)",
)
@click.pass_context
def route(
    ctx: click.Context,
    from_station: str,
    to_station: str,
    time: str | None,
    date: str | None,
    day_type: str | None,
    num_options: int,
    lang: str,
    format: str,
) -> None:
    """Find route between two stations."""
    try:
        router = MetroRouter(db=MetroDatabase(ctx.obj["db_path"]))

        # Find stations
        from_st = router.find_station_by_name(from_station, lang)
        to_st = router.find_station_by_name(to_station, lang)

        if not from_st:
            click.echo(f"Station not found: {from_station}", err=True)
            raise click.Exit(1)

        if not to_st:
            click.echo(f"Station not found: {to_station}", err=True)
            raise click.Exit(1)

        # Parse departure time
        if time:
            hour, minute = map(int, time.split(":"))
        else:
            now = datetime.now()
            hour, minute = now.hour, now.minute

        if date:
            year, month, day = map(int, date.split("-"))
            departure_time = datetime(year, month, day, hour, minute)
        else:
            departure_time = datetime.now().replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )

        # Override day type if specified
        if day_type:
            dt = DayType.WEEKDAY if day_type == "weekday" else DayType.WEEKEND
        else:
            dt = None

        # Find routes
        if num_options > 1:
            routes = router.find_multiple_routes(from_st.id, to_st.id, departure_time, num_options)
        else:
            route = router.find_route(from_st.id, to_st.id, departure_time, dt)
            routes = [route] if route else []

        if not routes:
            click.echo("No route found", err=True)
            raise click.Exit(1)

        # Output
        if format == "json":
            result = {
                "from": getattr(from_st, f"name_{lang}"),
                "to": getattr(to_st, f"name_{lang}"),
                "routes": [r.to_dict(lang) for r in routes],
            }
            click.echo(json.dumps(result, indent=2, ensure_ascii=False))
        elif format == "simple":
            for i, route_obj in enumerate(routes, 1):
                if num_options > 1:
                    console.print(f"\n[bold cyan]Option {i}:[/bold cyan]")
                _display_route_simple(route_obj, lang, console)
        else:
            for i, route_obj in enumerate(routes, 1):
                if num_options > 1:
                    console.print(f"\n[bold cyan]Option {i}:[/bold cyan]")

                _display_route_table(route_obj, lang, console)

    except Exception as e:
        if format == "json":
            click.echo(json.dumps({"status": "error", "message": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise click.Exit(1)


def _display_route_table(route, lang: str, console: Console) -> None:
    """Display route in table format."""
    name_attr = f"name_{lang}"

    # Summary
    total_time = route.total_duration_minutes
    transfers = route.num_transfers

    console.print(
        f"[bold]Total time:[/bold] {total_time} min | [bold]Transfers:[/bold] {transfers}"
    )

    if route.departure_time and route.arrival_time:
        dep = route.departure_time.strftime("%H:%M")
        arr = route.arrival_time.strftime("%H:%M")
        console.print(f"[bold]Departure:[/bold] {dep} | [bold]Arrival:[/bold] {arr}")

    # Table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("From")
    table.add_column("To")
    table.add_column("Type")
    table.add_column("Time")

    for segment in route.segments:
        from_name = getattr(segment.from_station, name_attr)
        to_name = getattr(segment.to_station, name_attr)

        if segment.is_transfer:
            seg_type = "[yellow]Transfer[/yellow]"
            time_str = f"{segment.duration_minutes} min"
        else:
            line = segment.from_station.line
            line_name = getattr(line, f"display_name_{lang}")
            color = line.color
            seg_type = f"[{color}]{line_name}[/{color}]"

            if segment.departure_time and segment.arrival_time:
                dep = segment.departure_time.strftime("%H:%M")
                arr = segment.arrival_time.strftime("%H:%M")
                time_str = f"{dep} → {arr} ({segment.duration_minutes} min)"
            else:
                time_str = f"{segment.duration_minutes} min"

        table.add_row(from_name, to_name, seg_type, time_str)

    console.print(table)


def _display_route_simple(route, lang: str, console: Console) -> None:
    """Display route in compact inline format."""
    name_attr = f"name_{lang}"

    # Build the path showing all stations
    path_parts = []

    # Track which stations we've already added to avoid duplicates
    added_stations = set()

    # Always add the first station
    if route.segments:
        first_station = route.segments[0].from_station
        first_name = getattr(first_station, name_attr)
        path_parts.append(first_name)
        added_stations.add(first_name)

    # Add all stations along the route
    for segment in route.segments:
        to_name = getattr(segment.to_station, name_attr)

        if segment.is_transfer:
            # At transfer, add the transfer destination station with its line color
            transfer_line = segment.to_station.line
            transfer_color = transfer_line.color
            path_parts.append(f"[{transfer_color}]{to_name}[/{transfer_color}]")
            added_stations.add(to_name)
        else:
            # For train segments, add the destination station if not already added
            if to_name not in added_stations:
                path_parts.append(to_name)
                added_stations.add(to_name)

    # Create the path string
    path_str = " → ".join(path_parts)

    # Summary info
    total_time = route.total_duration_minutes
    transfers = route.num_transfers

    if route.departure_time and route.arrival_time:
        dep = route.departure_time.strftime("%H:%M")
        arr = route.arrival_time.strftime("%H:%M")
        time_str = f"{dep} → {arr} ({total_time} min)"
    else:
        time_str = f"{total_time} min"

    transfers_str = (
        f"{transfers} пересадка"
        if transfers == 1
        else f"{transfers} пересадки"
        if transfers > 0
        else "без пересадок"
    )

    console.print(f"{path_str}")
    console.print(f"[dim]{time_str} | {transfers_str}[/dim]")


@cli.command()
@click.argument("station")
@click.option(
    "--direction",
    "-d",
    help="Direction (terminal station name)",
    default=None,
)
@click.option(
    "--day-type",
    type=click.Choice(["weekday", "weekend"]),
    help="Day type",
    default=None,
)
@click.option(
    "--lang",
    "-l",
    type=click.Choice(["ua", "en"]),
    default="ua",
    help="Language",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
@click.pass_context
def schedule(
    ctx: click.Context,
    station: str,
    direction: str | None,
    day_type: str | None,
    lang: str,
    output: str,
) -> None:
    """Show schedule for a station."""
    try:
        router = MetroRouter(db=MetroDatabase(ctx.obj["db_path"]))

        # Find station
        st = router.find_station_by_name(station, lang)
        if not st:
            click.echo(f"Station not found: {station}", err=True)
            raise click.Exit(1)

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
            raise click.Exit(1)

        # Output
        if output == "json":
            result = {
                "station": getattr(st, f"name_{lang}"),
                "schedules": [
                    {
                        "direction": router.stations.get(sch.direction_station_id, st).name_ua,
                        "entries": [
                            {"hour": e.hour, "minutes": e.minutes}
                            for e in sch.entries[:20]  # Limit entries
                        ],
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

                    # Group by hour
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
        raise click.Exit(1)


@cli.command()
@click.option(
    "--line",
    "-l",
    type=click.Choice(["kholodnohirsko_zavodska", "saltivska", "oleksiivska"]),
    help="Filter by line",
    default=None,
)
@click.option(
    "--lang",
    type=click.Choice(["ua", "en"]),
    default="ua",
    help="Language",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
@click.pass_context
def stations(
    ctx: click.Context,
    line: str | None,
    lang: str,
    output: str,
) -> None:
    """List all stations."""
    try:
        db = MetroDatabase(ctx.obj["db_path"])
        name_attr = f"name_{lang}"

        if line:
            stations_data = db.get_stations_by_line(line)
        else:
            stations_data = db.get_all_stations()

        if output == "json":
            result = [
                {
                    "id": s["id"],
                    "name": s[name_attr],
                    "line": Line(s["line"]).display_name_ua
                    if lang == "ua"
                    else Line(s["line"]).display_name_en,
                }
                for s in stations_data
            ]
            click.echo(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Line")
            table.add_column("Station")

            for s in stations_data:
                line_name = (
                    Line(s["line"]).display_name_ua
                    if lang == "ua"
                    else Line(s["line"]).display_name_en
                )
                table.add_row(line_name, s[name_attr])

            console.print(table)

    except Exception as e:
        if output == "json":
            click.echo(json.dumps({"status": "error", "message": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise click.Exit(1)


@cli.command()
@click.pass_context
def update(ctx: click.Context) -> None:
    """Update schedules from website (scraper)."""
    console.print("[yellow]Note:[/yellow] Web scraping is not fully implemented yet.")
    console.print("Please populate the database manually or use sample data.")


if __name__ == "__main__":
    cli()
