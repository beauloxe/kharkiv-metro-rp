"""Initialize database with station data."""

from __future__ import annotations

from ..core.models import DayType, create_stations
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


def init_schedules(db: MetroDatabase) -> None:
    """Initialize database with schedules by scraping."""
    try:
        from .scraper import scrape_all_schedules

        print("Scraping weekday schedules...")
        weekday_schedules = scrape_all_schedules(DayType.WEEKDAY)
        for schedule in weekday_schedules:
            db.save_schedule(schedule)
        print(f"Saved {len(weekday_schedules)} weekday schedules")

        print("Scraping weekend schedules...")
        weekend_schedules = scrape_all_schedules(DayType.WEEKEND)
        for schedule in weekend_schedules:
            db.save_schedule(schedule)
        print(f"Saved {len(weekend_schedules)} weekend schedules")

    except Exception as e:
        print(f"Warning: Could not scrape schedules: {e}")
        print("Schedules will need to be loaded manually")


def init_database(db_path: str = "data/metro.db") -> MetroDatabase:
    """Initialize database with all static data."""
    db = MetroDatabase(db_path)
    init_stations(db)
    init_schedules(db)
    return db
