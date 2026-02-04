"""Core data models for Kharkiv metro."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from enum import Enum


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
        names = {
            Line.KHOLODNOHIRSKO_ZAVODSKA: "Холодногірсько-заводська",
            Line.SALTIVSKA: "Салтівська",
            Line.OLEKSIIVSKA: "Олексіївська",
        }
        return names[self]

    @property
    def display_name_en(self) -> str:
        names = {
            Line.KHOLODNOHIRSKO_ZAVODSKA: "Kholodnohirsko-Zavodska",
            Line.SALTIVSKA: "Saltivska",
            Line.OLEKSIIVSKA: "Oleksiivska",
        }
        return names[self]

    @property
    def color(self) -> str:
        colors = {
            Line.KHOLODNOHIRSKO_ZAVODSKA: "red",
            Line.SALTIVSKA: "blue",
            Line.OLEKSIIVSKA: "green",
        }
        return colors[self]


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

    def to_datetime(self, base_date: dt.datetime) -> dt.datetime:
        # Preserve timezone from base_date
        return base_date.replace(hour=self.hour, minute=self.minutes, second=0, microsecond=0)

    def __lt__(self, other: ScheduleEntry) -> bool:
        if self.hour != other.hour:
            return self.hour < other.hour
        return self.minutes < other.minutes

    def __le__(self, other: ScheduleEntry) -> bool:
        if self.hour != other.hour:
            return self.hour < other.hour
        return self.minutes <= other.minutes


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
        return sorted(future)[:limit]

    def get_departures_between(self, start_time: dt.time, end_time: dt.time) -> list[ScheduleEntry]:
        """Get departures between two times."""
        return [e for e in self.entries if start_time <= e.time <= end_time]


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


# Define metro network structure
# Line 1: Kholodnohirsko-Zavodska (Red)
LINE_1_STATIONS = [
    ("kholodna_hora", "Холодна гора", "Kholodna Hora"),
    ("vokzalna", "Вокзальна", "Vokzalna"),
    ("tsentralnyi_rynok", "Центральний ринок", "Tsentralnyi Rynok"),
    ("maidan_konstytutsii", "Майдан Конституції", "Maidan Konstytutsii"),
    ("levada", "Левада", "Levada"),
    ("sportyvna", "Спортивна", "Sportyvna"),
    ("zavodska", "Заводська", "Zavodska"),
    ("turboatom", "Турбоатом", "Turboatom"),
    ("palats_sportu", "Палац спорту", "Palats Sportu"),
    ("armiiska", "Армійська", "Armiiska"),
    ("maselskoho", "Ім. О.С. Масельського", "Im. O.S. Maselskoho"),
    ("traktornyi_zavod", "Тракторний завод", "Traktornyi Zavod"),
    ("industrialna", "Індустріальна", "Industrialna"),
]

# Line 2: Saltivska (Blue)
LINE_2_STATIONS = [
    ("istorychnyi_muzei", "Історичний музей", "Istorychnyi Muzei"),
    ("university", "Університет", "Universytet"),
    ("yaroslava_mudroho", "Ярослава Мудрого", "Yaroslava Mudroho"),
    ("kyivska", "Київська", "Kyivska"),
    ("barabashova", "Академіка Барабашова", "Akademika Barabashova"),
    ("pavlova", "Академіка Павлова", "Akademika Pavlova"),
    ("studentska", "Студентська", "Studentska"),
    ("saltivska", "Салтівська", "Saltivska"),
]

# Line 3: Oleksiivska (Green)
LINE_3_STATIONS = [
    ("metrobudivnykiv", "Метробудівників", "Metrobudivnykiv"),
    ("zakhysnykiv_ukrainy", "Захисників України", "Zakhysnykiv Ukrainy"),
    ("beketova", "Архітектора Бекетова", "Arkhitektora Beketova"),
    ("derzhprom", "Держпром", "Derzhprom"),
    ("naukova", "Наукова", "Naukova"),
    ("botanichnyi_sad", "Ботанічний сад", "Botanichnyi Sad"),
    ("23_serpnia", "23 Серпня", "23 Serpnia"),
    ("oleksiivska", "Олексіївська", "Oleksiivska"),
    ("peremoha", "Перемога", "Peremoha"),
]

# Transfer stations (station_id -> transfer_to_station_id)
TRANSFERS = {
    "maidan_konstytutsii": "istorychnyi_muzei",
    "istorychnyi_muzei": "maidan_konstytutsii",
    "sportyvna": "metrobudivnykiv",
    "metrobudivnykiv": "sportyvna",
    "university": "derzhprom",
    "derzhprom": "university",
}

# Alias station names -> actual station names (for backward compatibility)
ALIAS_STATION_NAMES = {
    # Ukrainian old names
    "героїв праці": "Салтівська",
    "проспект гагаріна": "Левада",
    "пушкінська": "Ярослава Мудрого",
    "завод імені малишева": "Заводська",
    "південний вокзал": "Вокзальна",
    # Aliases
    "23": "23 Серпня",
    "барабашова": "Академіка Барабашова",
    "бекетова": "Архітектора Бекетова",
    "ботсад": "Ботанічний сад",
    "гагаріна": "Левада",
    "масельського": "Ім. О.С. Масельського",
    "павлова": "Академіка Павлова",
    "палац": "Палац спорту",
    "хтз": "Тракторний завод",
    # TODO: add English old names
}


class MetroClosedError(Exception):
    """Raised when trying to plan a route when metro is closed."""

    def __init__(self, message: str | None = None) -> None:
        if message is None:
            message = "Метро закрите та/або на останній потяг неможливо встигнути"
        super().__init__(message)


def create_stations() -> dict[str, Station]:
    """Create all stations with their metadata."""
    stations = {}

    for order, (sid, name_ua, name_en) in enumerate(LINE_1_STATIONS, 1):
        transfer = TRANSFERS.get(sid)
        stations[sid] = Station(
            id=sid,
            name_ua=name_ua,
            name_en=name_en,
            line=Line.KHOLODNOHIRSKO_ZAVODSKA,
            order=order,
            transfer_to=transfer,
        )

    for order, (sid, name_ua, name_en) in enumerate(LINE_2_STATIONS, 1):
        transfer = TRANSFERS.get(sid)
        stations[sid] = Station(
            id=sid,
            name_ua=name_ua,
            name_en=name_en,
            line=Line.SALTIVSKA,
            order=order,
            transfer_to=transfer,
        )

    for order, (sid, name_ua, name_en) in enumerate(LINE_3_STATIONS, 1):
        transfer = TRANSFERS.get(sid)
        stations[sid] = Station(
            id=sid,
            name_ua=name_ua,
            name_en=name_en,
            line=Line.OLEKSIIVSKA,
            order=order,
            transfer_to=transfer,
        )

    return stations
