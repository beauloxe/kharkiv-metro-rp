"""Core data models for Kharkiv metro."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum

from .data_loader import load_metro_data


class DayType(Enum):
    """Type of day for schedule."""

    WEEKDAY = "weekday"
    WEEKEND = "weekend"


class Line(Enum):
    """Metro lines in Kharkiv."""

    KHOLODNOHIRSKO_ZAVODSKA = "kholodnohirsko_zavodska"
    SALTIVSKA = "saltivska"
    OLEKSIIVSKA = "oleksiivska"

    @property
    def display_name_ua(self) -> str:
        metro_data = load_metro_data()
        return metro_data.line_meta[self.value]["name_ua"]

    @property
    def display_name_en(self) -> str:
        metro_data = load_metro_data()
        return metro_data.line_meta[self.value]["name_en"]

    @property
    def color(self) -> str:
        metro_data = load_metro_data()
        return metro_data.line_meta[self.value]["color"]


@dataclass(slots=True)
class Station:
    """Metro station."""

    id: str
    name_ua: str
    name_en: str
    line: Line
    order: int
    transfer_to: str | None = None

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Station):
            return NotImplemented
        return self.id == other.id


@dataclass(slots=True)
class ScheduleEntry:
    """Single schedule entry (departure time)."""

    hour: int
    minutes: int

    @property
    def time(self) -> dt.time:
        return dt.datetime.strptime(f"{self.hour:02d}:{self.minutes:02d}", "%H:%M").time()


@dataclass(slots=True)
class StationSchedule:
    """Schedule for a station in a specific direction."""

    station_id: str
    direction_station_id: str
    day_type: DayType
    entries: list[ScheduleEntry] = field(default_factory=list)

    def get_next_departures(self, after_time: dt.time, limit: int = 3) -> list[ScheduleEntry]:
        """Get next departures at or after given time."""
        future = [e for e in self.entries if e.time >= after_time]
        return list(sorted(future, key=lambda entry: (entry.hour, entry.minutes)))[:limit]


@dataclass(slots=True)
class RouteSegment:
    """Single segment of a route."""

    from_station: Station
    to_station: Station
    departure_time: dt.datetime | None
    arrival_time: dt.datetime | None
    is_transfer: bool = False
    duration_minutes: int = 0

    @property
    def line(self) -> Line | None:
        if self.is_transfer:
            return None
        return self.from_station.line


@dataclass(slots=True)
class Route:
    """Complete route from start to end."""

    segments: list[RouteSegment] = field(default_factory=list)
    total_duration_minutes: int = 0
    num_transfers: int = 0
    departure_time: dt.datetime | None = None
    arrival_time: dt.datetime | None = None

    @property
    def stations(self) -> list[Station]:
        """Get all stations in the route."""
        if not self.segments:
            return []
        result = [self.segments[0].from_station]
        for seg in self.segments:
            result.append(seg.to_station)
        return result

    def to_dict(self, lang: str = "ua") -> dict:
        """Convert route to dictionary."""
        name_attr = f"name_{lang}"
        line_attr = f"display_name_{lang}"

        def station_dict(station: Station) -> dict:
            return {
                "id": station.id,
                "name": getattr(station, name_attr),
                "line": getattr(station.line, line_attr),
            }

        def segment_dict(seg: RouteSegment) -> dict:
            return {
                "from_station": station_dict(seg.from_station),
                "to_station": station_dict(seg.to_station),
                "departure_time": seg.departure_time.isoformat() if seg.departure_time else None,
                "arrival_time": seg.arrival_time.isoformat() if seg.arrival_time else None,
                "is_transfer": seg.is_transfer,
                "duration_minutes": seg.duration_minutes,
            }

        return {
            "total_duration_minutes": self.total_duration_minutes,
            "num_transfers": self.num_transfers,
            "departure_time": self.departure_time.isoformat() if self.departure_time else None,
            "arrival_time": self.arrival_time.isoformat() if self.arrival_time else None,
            "segments": [segment_dict(seg) for seg in self.segments],
        }


class MetroClosedError(Exception):
    """Raised when trying to plan a route when metro is closed."""

    def __init__(self, message: str | None = None) -> None:
        if message is None:
            message = "Метро закрите та/або на останній потяг неможливо встигнути"
        super().__init__(message)


def create_stations() -> dict[str, Station]:
    """Create all stations with their metadata."""
    metro_data = load_metro_data()
    stations: dict[str, Station] = {}

    line_mapping = {
        "kholodnohirsko_zavodska": Line.KHOLODNOHIRSKO_ZAVODSKA,
        "saltivska": Line.SALTIVSKA,
        "oleksiivska": Line.OLEKSIIVSKA,
    }

    for line_key in metro_data.line_order:
        line_enum = line_mapping[line_key]
        for order, station in enumerate(metro_data.stations_by_line.get(line_key, []), 1):
            transfer = metro_data.transfers.get(station.id)
            stations[station.id] = Station(
                id=station.id,
                name_ua=station.name_ua,
                name_en=station.name_en,
                line=line_enum,
                order=order,
                transfer_to=transfer,
            )

    return stations
