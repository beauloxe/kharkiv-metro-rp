"""Scrape command for metro CLI."""

from __future__ import annotations

import json

import click
from click.exceptions import Exit

from ..bot.constants import DB_PATH
from ..data.database import MetroDatabase
from ..data.initializer import init_database, init_stations
from .utils import _check_db_exists, console


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
    from ..data.scraper import MetroScraper

    try:
        # Use centralized DB_PATH constant
        if init_db:
            db = init_database(DB_PATH)
        else:
            if not _check_db_exists(DB_PATH):
                console.print(f"[red]✗[/red] Database not found at: {DB_PATH}")
                console.print("[yellow]Run:[/yellow] metro scrape --init-db")
                raise Exit(1)
            db = MetroDatabase(DB_PATH)

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
