"""Generate sample schedule data for testing."""
from __future__ import annotations

import random

from ..core.models import DayType, ScheduleEntry, StationSchedule, create_stations
from ..data.database import MetroDatabase


def generate_schedule_for_station(
    station_id: str,
    direction_id: str,
    day_type: DayType,
    base_frequency: int = 10,
) -> StationSchedule:
    """Generate realistic schedule for a station.
    
    Args:
        station_id: Station ID
        direction_id: Direction (terminal station) ID
        day_type: Weekday or weekend
        base_frequency: Base frequency in minutes (default 10)
    """
    entries = []

    # Different frequencies for different times of day
    # Format: (start_hour, end_hour, frequency_minutes)
    if day_type == DayType.WEEKDAY:
        time_periods = [
            (5, 7, 10),      # Early morning: every 10 min
            (7, 10, 5),      # Morning rush: every 5 min
            (10, 16, 7),     # Day: every 7 min
            (16, 19, 5),     # Evening rush: every 5 min
            (19, 22, 8),     # Evening: every 8 min
        ]
    else:  # Weekend
        time_periods = [
            (5, 10, 12),     # Morning: every 12 min
            (10, 22, 10),    # Day: every 10 min
        ]

    for start_hour, end_hour, freq in time_periods:
        for hour in range(start_hour, end_hour):
            # Generate departures for this hour
            minute = 0
            while minute < 60:
                # Add some randomness to make it realistic
                actual_minute = minute + random.randint(-1, 1)
                if 0 <= actual_minute < 60:
                    entries.append(ScheduleEntry(hour=hour, minutes=actual_minute))
                minute += freq

    # Sort entries
    entries.sort(key=lambda e: (e.hour, e.minutes))

    return StationSchedule(
        station_id=station_id,
        direction_station_id=direction_id,
        day_type=day_type,
        entries=entries,
    )


def generate_all_schedules(db: MetroDatabase) -> None:
    """Generate schedules for all stations and save to database."""
    stations = create_stations()

    # Group stations by line
    from ..core.models import Line

    line_stations = {
        Line.KHOLODNOHIRSKO_ZAVODSKA: [],
        Line.SALTIVSKA: [],
        Line.OLEKSIIVSKA: [],
    }

    for station_id, station in stations.items():
        line_stations[station.line].append(station)

    # Sort by order
    for line in line_stations:
        line_stations[line].sort(key=lambda s: s.order)

    total_schedules = 0

    for line, stations_list in line_stations.items():
        if len(stations_list) < 2:
            continue

        # Terminal stations for this line
        terminal1 = stations_list[0]
        terminal2 = stations_list[-1]

        print(f"Generating schedules for {line.display_name_ua}...")

        for station in stations_list:
            # Skip terminal stations (they don't have departures in one direction)
            if station.id != terminal2.id:
                # Schedule towards terminal2
                for day_type in [DayType.WEEKDAY, DayType.WEEKEND]:
                    schedule = generate_schedule_for_station(
                        station.id,
                        terminal2.id,
                        day_type,
                    )
                    db.save_schedule(schedule)
                    total_schedules += 1

            if station.id != terminal1.id:
                # Schedule towards terminal1
                for day_type in [DayType.WEEKDAY, DayType.WEEKEND]:
                    schedule = generate_schedule_for_station(
                        station.id,
                        terminal1.id,
                        day_type,
                    )
                    db.save_schedule(schedule)
                    total_schedules += 1

    print(f"Generated {total_schedules} schedules")


def main():
    """Main entry point."""
    db = MetroDatabase()
    generate_all_schedules(db)
    print("Done!")


if __name__ == "__main__":
    main()
