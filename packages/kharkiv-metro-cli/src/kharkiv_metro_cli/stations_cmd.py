"""Stations command for metro CLI."""

from __future__ import annotations

import click

from .utils import (
    format_station_rows,
    get_db,
    get_lang,
    get_output_format,
    output_stations_json,
    output_stations_table,
    run_with_error_handling,
)


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
    lang = get_lang(ctx, lang)
    fmt = get_output_format(ctx, output, "preferences.output_format", "table")

    def _run() -> None:
        db = get_db(ctx)
        name_attr = f"name_{lang}"
        line_filter = line

        # Map short aliases to full line names
        line_map = {"k": "kholodnohirsko_zavodska", "s": "saltivska", "o": "oleksiivska"}
        if line_filter:
            line_filter = line_map.get(line_filter, line_filter)
            stations_data = db.get_stations_by_line(line_filter)
        else:
            stations_data = db.get_all_stations()

        rows = format_station_rows(stations_data, name_attr, lang)
        if fmt == "json":
            output_stations_json(rows, stations_data, lang)
        else:
            output_stations_table(rows, lang)

    run_with_error_handling(_run)
