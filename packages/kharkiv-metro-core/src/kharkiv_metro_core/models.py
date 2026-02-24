"""Core data models for Kharkiv metro."""

from __future__ import annotations

import datetime as dt
import math
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

    def iter_line_groups(self) -> list[tuple[list[RouteSegment], bool]]:
        """Group segments by line, marking transfers."""
        groups: list[tuple[list[RouteSegment], bool]] = []
        segment_index = 0
        while segment_index < len(self.segments):
            segment = self.segments[segment_index]
            if segment.is_transfer:
                groups.append(([segment], True))
                segment_index += 1
                continue

            line_segments = [segment]
            segment_index += 1
            while segment_index < len(self.segments) and not self.segments[segment_index].is_transfer:
                line_segments.append(self.segments[segment_index])
                segment_index += 1
            groups.append((line_segments, False))
        return groups

    def build_path(self, lang: str = "ua", compact: bool = False, transfer_marker: str = "⇌") -> str:
        """Build route path string."""
        if not self.segments:
            return ""

        name_attr = f"name_{lang}"
        if compact:
            first = self.segments[0].from_station
            path = [getattr(first, name_attr)]
            for seg in self.segments:
                if seg.is_transfer:
                    path.append(
                        f"{getattr(seg.from_station, name_attr)} {transfer_marker} {getattr(seg.to_station, name_attr)}"
                    )
            last = self.segments[-1]
            if not last.is_transfer:
                path.append(getattr(last.to_station, name_attr))
            return " → ".join(path)

        seen = {getattr(self.segments[0].from_station, name_attr)}
        path_parts = [getattr(self.segments[0].from_station, name_attr)]
        for seg in self.segments:
            to_name = getattr(seg.to_station, name_attr)
            if to_name in seen:
                continue
            if seg.is_transfer:
                path_parts.append(f"{transfer_marker} {to_name}")
            else:
                path_parts.append(to_name)
            seen.add(to_name)
        return " → ".join(path_parts)

    def summarize_times(self, lang: str, min_text: str, approximate: bool = False) -> str:
        """Summarize total duration and transfers."""
        transfers_text = format_transfers(self.num_transfers, lang)
        if self.departure_time and self.arrival_time:
            dep = self.departure_time.strftime("%H:%M")
            arr = self.arrival_time.strftime("%H:%M")
            return f"{dep} → {arr} | {_format_minutes(self.total_duration_minutes, min_text, approximate)}, {transfers_text}"
        return f"{_format_minutes(self.total_duration_minutes, min_text, approximate)}, {transfers_text}"

    def to_line_groups(self) -> list[dict]:
        """Build compact line-group summaries."""
        groups: list[dict] = []
        segment_index = 0
        while segment_index < len(self.segments):
            segment = self.segments[segment_index]
            if segment.is_transfer:
                transfer_minutes, computed_delta = _compute_transfer_minutes(segment, self.segments, segment_index)
                groups.append(
                    {
                        "from": segment.from_station,
                        "to": segment.to_station,
                        "is_transfer": True,
                        "duration_minutes": transfer_minutes,
                        "computed_delta": computed_delta,
                    }
                )
                segment_index += 1
                continue

            start = segment
            end = segment
            total_duration = segment.duration_minutes
            segment_index += 1

            while segment_index < len(self.segments) and not self.segments[segment_index].is_transfer:
                end = self.segments[segment_index]
                total_duration += end.duration_minutes
                segment_index += 1

            groups.append(
                {
                    "from": start.from_station,
                    "to": end.to_station,
                    "is_transfer": False,
                    "duration_minutes": total_duration,
                    "departure_time": start.departure_time,
                    "arrival_time": end.arrival_time,
                    "line": start.from_station.line,
                }
            )
        return groups

    def format_plain_text(self, lang: str, min_text: str, compact: bool = False) -> str:
        """Format route as simple plain text."""
        if not self.segments:
            return ""

        path = self.build_path(lang=lang, compact=compact)
        if self.departure_time and self.arrival_time:
            time_str = f"{self.departure_time.strftime('%H:%M')} → {self.arrival_time.strftime('%H:%M')}"
        else:
            time_str = _format_minutes(self.total_duration_minutes, min_text, approximate=True)

        transfers_text = format_transfers(self.num_transfers, lang)
        return f"{path}\n{time_str} | {transfers_text}"


def _format_minutes(duration: int, min_text: str, approximate: bool = False) -> str:
    prefix = "~" if approximate and duration == 2 else ""
    return f"{prefix}{duration} {min_text}"


def format_transfers(count: int, lang: str) -> str:
    """Format transfer count using translations."""
    from .i18n import get_text

    if count == 0:
        return get_text("no_transfers", lang)
    key = f"transfers_{'one' if count == 1 else 'many'}"
    text = get_text(key, lang)
    return text.format(count=count)


def _compute_transfer_minutes(seg: RouteSegment, all_segments: list[RouteSegment], index: int) -> tuple[int, bool]:
    transfer_minutes = seg.duration_minutes
    computed_delta = False

    prev_seg = all_segments[index - 1] if index > 0 else None
    arrival_time = prev_seg.arrival_time if prev_seg and prev_seg.arrival_time else seg.arrival_time
    next_seg = all_segments[index + 1] if index + 1 < len(all_segments) else None
    if arrival_time and next_seg and next_seg.departure_time:
        delta_seconds = (next_seg.departure_time - arrival_time).total_seconds()
        if delta_seconds >= 0:
            transfer_minutes = max(transfer_minutes, math.ceil(delta_seconds / 60))
            computed_delta = True
    return transfer_minutes, computed_delta


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
