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
        cli_override: str | None = ctx.obj.get("db_path")
        
        if cli_override:
            # Custom path
            db = init_database(cli_override)
            path_msg = cli_override
        else:
            # XDG path
            config.ensure_dirs()
            config.create_default()
            db_path = config.get_db_path()
            db = init_database(db_path)
            path_msg = db_path
        
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
