"""Scrape command for metro CLI."""

from __future__ import annotations

import json

import click
from click.exceptions import Exit
from kharkiv_metro_core import Config, init_database

from .utils import console, ensure_db


@click.command()
@click.option(
    "--init-db",
    is_flag=True,
    help="Initialize database with stations before scraping",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
@click.pass_context
def scrape(ctx: click.Context, init_db: bool, output: str) -> None:
    """Scrape and update schedules from metro.kharkiv.ua."""
    from kharkiv_metro_core import MetroScraper

    try:
        config: Config = ctx.obj["config"]
        db_path = config.get_db_path()

        # Use config database path
        if init_db:
            db = init_database(db_path)
        else:
            db = ensure_db(db_path)

        if output == "table":
            console.print("[cyan]Scraping schedules from metro.kharkiv.ua...[/cyan]")
            console.print("[dim]This may take 5-10 minutes...[/dim]\n")

        scraper = MetroScraper()
        all_schedules_dict = scraper.scrape_all_schedules()

        all_schedules = []
        for station_schedules in all_schedules_dict.values():
            all_schedules.extend(station_schedules)

        count = db.save_schedules(all_schedules)
        unique_stations = len(all_schedules_dict)

        if output == "json":
            click.echo(
                json.dumps(
                    {
                        "status": "ok",
                        "schedules_saved": count,
                        "stations": unique_stations,
                    }
                )
            )
        else:
            console.print(f"[green]✓[/green] Saved [bold]{count}[/bold] schedules from {unique_stations} stations")

    except Exception as e:
        if output == "json":
            click.echo(json.dumps({"status": "error", "message": str(e)}))
        else:
            console.print(f"[red]✗[/red] Error: {e}")
        raise Exit(1)
