"""Stations command for metro CLI."""
from __future__ import annotations

import json

import click
from click.exceptions import Exit
from rich.table import Table

from ..config import Config
from ..core.models import Line
from .utils import _get_db, console


@click.command()
@click.option(
    "--line",
    "-l",
    type=click.Choice(["kholodnohirsko_zavodska", "saltivska", "oleksiivska", "k", "s", "o"]),
    help="Filter by line (k=kholodnohirsko_zavodska, s=saltivska, o=oleksiivska)",
    default=None,
)
@click.option(
    "--lang",
    type=click.Choice(["ua", "en"]),
    default=None,
    help="Language",
)
@click.option(
    "--output",
    "-o",
    type=click.Choice(["json", "table"]),
    default=None,
    help="Output format",
)
@click.pass_context
def stations(
    ctx: click.Context,
    line: str | None,
    lang: str | None,
    output: str | None,
) -> None:
    """List all stations."""
    try:
        config: Config = ctx.obj["config"]
        
        # Use config defaults if not specified
        if lang is None:
            lang = config.get("preferences.language", "ua")
        if output is None:
            output = config.get("preferences.output_format", "table")
        
        db = _get_db(ctx)
        name_attr = f"name_{lang}"

        line_map = {
            "k": "kholodnohirsko_zavodska",
            "s": "saltivska",
            "o": "oleksiivska",
        }
        if line:
            line = line_map.get(line, line)
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
        raise Exit(1)
