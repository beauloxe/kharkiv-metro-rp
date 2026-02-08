"""Scrape command for metro CLI."""

from __future__ import annotations

import json

import click
from .utils import console, get_db_path, init_or_get_db, run_with_error_handling


@click.command()
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
@click.pass_context
def scrape(ctx: click.Context, output: str) -> None:
    """Scrape and update schedules from metro.kharkiv.ua."""
    from kharkiv_metro_core import MetroScraper

    def _run() -> None:
        db_path = get_db_path(ctx)
        db = init_or_get_db(db_path)

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

    run_with_error_handling(_run, output)
