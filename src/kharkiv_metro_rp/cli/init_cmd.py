"""Init command for metro CLI."""

from __future__ import annotations

import json

import click
from click.exceptions import Exit

from ..config import Config
from ..data.initializer import init_database
from .utils import console


@click.command()
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "table"]),
    default="table",
    help="Output format",
)
@click.pass_context
def init(ctx: click.Context, output: str) -> None:
    """Initialize database with station data."""
    try:
        config: Config = ctx.obj["config"]
        db_path = config.get_db_path()
        db = init_database(db_path)

        if output == "json":
            click.echo(json.dumps({"status": "ok", "path": db_path}))
        else:
            console.print(f"[green]✓[/green] Database initialized at: {db_path}")
    except Exception as e:
        if output == "json":
            click.echo(json.dumps({"status": "error", "message": str(e)}))
        else:
            console.print(f"[red]✗[/red] Error: {e}")
        raise Exit(1)
