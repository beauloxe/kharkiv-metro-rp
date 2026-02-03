"""Init command for metro CLI."""

from __future__ import annotations

import json

import click
from click.exceptions import Exit

from ..bot.constants import DB_PATH
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
        # Use centralized DB_PATH constant
        db = init_database(DB_PATH)
        path_msg = DB_PATH

        if output == "json":
            click.echo(json.dumps({"status": "ok", "path": path_msg}))
        else:
            console.print(f"[green]✓[/green] Database initialized at: {path_msg}")
    except Exception as e:
        if output == "json":
            click.echo(json.dumps({"status": "error", "message": str(e)}))
        else:
            console.print(f"[red]✗[/red] Error: {e}")
        raise Exit(1)
