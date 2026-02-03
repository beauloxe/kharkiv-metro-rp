"""Initialize database with station data."""

from __future__ import annotations

from ..core.models import create_stations
from .database import MetroDatabase


def init_stations(db: MetroDatabase) -> None:
    """Initialize database with station data."""
    stations = create_stations()

    station_data = []
    for station in stations.values():
        station_data.append(
            {
                "id": station.id,
                "name_ua": station.name_ua,
                "name_en": station.name_en,
                "line": station.line.value,
                "order": station.order,
                "transfer_to": station.transfer_to,
            }
        )

    db.save_stations(station_data)
    print(f"Initialized {len(station_data)} stations")


def init_database(db_path: str = "data/metro.db") -> MetroDatabase:
    """Initialize database with all static data."""
    db = MetroDatabase(db_path)
    init_stations(db)
    return db
