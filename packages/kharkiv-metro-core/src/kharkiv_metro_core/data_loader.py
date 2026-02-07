"""Load metro metadata from packaged TOML."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from functools import lru_cache


@dataclass(frozen=True)
class StationRecord:
    """Raw station record loaded from data file."""

    id: str
    name_ua: str
    name_en: str


@dataclass(frozen=True)
class MetroData:
    """Normalized metro data from TOML."""

    line_order: list[str]
    stations_by_line: dict[str, list[StationRecord]]
    transfers: dict[str, str]
    aliases: dict[str, str]
    line_meta: dict[str, dict[str, str]]
    day_types: dict[str, dict[str, str]]
    scraper: dict[str, Any]


def _load_raw_data() -> dict[str, Any]:
    data_path = files("kharkiv_metro_core.data").joinpath("metro.toml")
    with data_path.open("rb") as handle:
        import tomllib

        return tomllib.load(handle)


@lru_cache(maxsize=1)
def load_metro_data() -> MetroData:
    """Load and normalize metro data from TOML."""
    raw = _load_raw_data()
    lines = raw.get("lines", {})
    line_order = list(lines.get("order", []))
    stations_by_line: dict[str, list[StationRecord]] = {}

    for line_key, line_data in lines.items():
        if line_key == "order":
            continue
        stations: list[StationRecord] = []
        for station in line_data.get("stations", []):
            stations.append(
                StationRecord(
                    id=station["id"],
                    name_ua=station["name_ua"],
                    name_en=station["name_en"],
                )
            )
        stations_by_line[line_key] = stations

    return MetroData(
        line_order=line_order,
        stations_by_line=stations_by_line,
        transfers=dict(raw.get("transfers", {})),
        aliases=dict(raw.get("aliases", {})),
        line_meta=dict(raw.get("line_meta", {})),
        day_types=dict(raw.get("day_types", {})),
        scraper=dict(raw.get("scraper", {})),
    )
