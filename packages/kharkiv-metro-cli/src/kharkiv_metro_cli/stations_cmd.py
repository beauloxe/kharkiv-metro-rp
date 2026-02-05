"""Stations command for metro CLI."""

from __future__ import annotations

import json

import click
from click.exceptions import Exit
from kharkiv_metro_core import Config, Line
from kharkiv_metro_core import get_text as tr
from rich.table import Table

from .utils import console, ensure_db


@click.command()
@click.option(
    "--line",
    "-l",
    type=click.Choice(["kholodnohirsko_zavodska", "saltivska", "oleksiivska", "k", "s", "o"]),
    help="Filter by line",
)
@click.option("--lang", type=click.Choice(["ua", "en"]), help="Language")
@click.option("--output", "-o", type=click.Choice(["json", "table"]), help="Output format")
@click.pass_context
def stations(ctx: click.Context, line: str | None, lang: str | None, output: str | None) -> None:
    """List all stations."""
    config: Config = ctx.obj["config"]
    lang = lang or config.get("preferences.language", "ua")
    fmt = output or config.get("preferences.output_format", "table")

    try:
        db_path = str(ctx.obj.get("db_path") or config.get_db_path())
        db = ensure_db(db_path)

        name_attr = f"name_{lang}"

        # Map short aliases to full line names
        line_map = {"k": "kholodnohirsko_zavodska", "s": "saltivska", "o": "oleksiivska"}
        if line:
            line = line_map.get(line, line)
            stations_data = db.get_stations_by_line(line)
        else:
            stations_data = db.get_all_stations()

        if fmt == "json":
            _output_json(stations_data, name_attr, lang)
        else:
            _output_table(stations_data, name_attr, lang)

    except Exception as e:
        if fmt == "json":
            click.echo(json.dumps({"status": "error", "message": str(e)}))
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise Exit(1)


def _output_json(stations_data: list, name_attr: str, lang: str) -> None:
    """Output stations in JSON format."""
    result = [
        {
            "id": s["id"],
            "name": s[name_attr],
            "line": Line(s["line"]).display_name_ua if lang == "ua" else Line(s["line"]).display_name_en,
        }
        for s in stations_data
    ]
    click.echo(json.dumps(result, indent=2, ensure_ascii=False))


def _output_table(stations_data: list, name_attr: str, lang: str) -> None:
    """Output stations as table."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column(tr("Line", lang))
    table.add_column(tr("Station", lang))

    for s in stations_data:
        line_name = Line(s["line"]).display_name_ua if lang == "ua" else Line(s["line"]).display_name_en
        table.add_row(line_name, s[name_attr])

    console.print(table)
