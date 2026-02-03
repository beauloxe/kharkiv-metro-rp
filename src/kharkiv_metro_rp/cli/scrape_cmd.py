"""Scrape command for metro CLI."""

from __future__ import annotations

import json
import os

import click
from click.exceptions import Exit

from ..config import Config
from ..data.database import MetroDatabase
from ..data.initializer import init_stations
from .utils import _check_db_exists, _get_db, console


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
        config: Config = ctx.obj["config"]
        cli_override: str | None = ctx.obj.get("db_path")

        # Check environment variable if no CLI override
        if not cli_override:
            cli_override = os.getenv("DB_PATH")

        if cli_override:
            # Custom path
            if init_db:
                from ..data.initializer import init_database

                db = init_database(cli_override)
            else:
                if not _check_db_exists(cli_override):
                    console.print(f"[red]✗[/red] Database not found at: {cli_override}")
                    console.print("[yellow]Run:[/yellow] metro scrape --init-db --db-path " + cli_override)
                    raise Exit(1)
                db = MetroDatabase(cli_override)
        else:
            # XDG path
            if init_db:
                config.ensure_dirs()
                config.create_default()
            db = _get_db(ctx)

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
