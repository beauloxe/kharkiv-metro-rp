"""CLI interface for metro route planner."""

from __future__ import annotations

from pathlib import Path

import click

from ..config import Config
from .config_cmd import config_cmd
from .init_cmd import init
from .route_cmd import route
from .schedule_cmd import schedule
from .scrape_cmd import scrape
from .stations_cmd import stations


@click.group()
@click.option(
    "--config",
    "config_path",
    help="Path to config file (default: XDG config directory)",
    type=click.Path(),
    default=None,
)
@click.option(
    "--db-path",
    help="Path to database file (overrides config)",
    type=click.Path(),
    default=None,
)
@click.pass_context
def cli(ctx: click.Context, config_path: str | None, db_path: str | None) -> None:
    """Kharkiv Metro Route Planner CLI."""
    ctx.ensure_object(dict)

    # Initialize config
    if config_path:
        # Custom config path - create minimal config
        config = Config()
        config.config_file = Path(config_path)
        config._load()
    else:
        config = Config()

    ctx.obj["config"] = config
    ctx.obj["db_path"] = db_path  # CLI override


# Register all commands
cli.add_command(init)
cli.add_command(route)
cli.add_command(schedule)
cli.add_command(stations)
cli.add_command(scrape)
cli.add_command(config_cmd, name="config")


if __name__ == "__main__":
    cli()
