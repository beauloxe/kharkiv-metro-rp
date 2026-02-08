"""Init command for metro CLI."""

from __future__ import annotations

import json

import click
from click.exceptions import Exit
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
def init(ctx: click.Context, output: str) -> None:
    """Initialize database with station data."""

    def _run() -> None:
        db_path = get_db_path(ctx)
        init_or_get_db(db_path)

        if output == "json":
            click.echo(json.dumps({"status": "ok", "path": db_path}))
        else:
            console.print(f"[green]✓[/green] Database initialized at: {db_path}")

    run_with_error_handling(_run, output)
