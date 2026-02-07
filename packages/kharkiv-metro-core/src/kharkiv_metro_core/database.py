"""SQLite database for metro schedules."""

from __future__ import annotations

import datetime as dt
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

from .models import DayType, ScheduleEntry, StationSchedule


class MetroDatabase:
    """SQLite database for metro data."""

    def __init__(self, db_path: str = "data/metro.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper setup."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Stations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stations (
                    id TEXT PRIMARY KEY,
                    name_ua TEXT NOT NULL,
                    name_en TEXT NOT NULL,
                    line TEXT NOT NULL,
                    station_order INTEGER NOT NULL,
                    transfer_to TEXT
                )
            """)

            # Schedules table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    station_id TEXT NOT NULL,
                    direction_station_id TEXT NOT NULL,
                    day_type TEXT NOT NULL,
                    hour INTEGER NOT NULL,
                    minutes INTEGER NOT NULL,
                    FOREIGN KEY (station_id) REFERENCES stations(id),
                    FOREIGN KEY (direction_station_id) REFERENCES stations(id)
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_schedules_station
                ON schedules(station_id, direction_station_id, day_type)
            """)

            conn.commit()

    @staticmethod
    def _rows_to_entries(rows: list[sqlite3.Row]) -> list[ScheduleEntry]:
        return [ScheduleEntry(hour=r["hour"], minutes=r["minutes"]) for r in rows]

    @staticmethod
    def _schedule_key(schedule: StationSchedule) -> tuple[str, str, str]:
        return schedule.station_id, schedule.direction_station_id, schedule.day_type.value

    def _delete_schedule(self, cursor, schedule: StationSchedule) -> None:
        cursor.execute(
            """
            DELETE FROM schedules
            WHERE station_id = ? AND direction_station_id = ? AND day_type = ?
        """,
            self._schedule_key(schedule),
        )

    def _insert_schedule_entries(self, cursor, schedule: StationSchedule) -> int:
        if not schedule.entries:
            return 0

        cursor.executemany(
            """
            INSERT INTO schedules
            (station_id, direction_station_id, day_type, hour, minutes)
            VALUES (?, ?, ?, ?, ?)
        """,
            [
                (
                    schedule.station_id,
                    schedule.direction_station_id,
                    schedule.day_type.value,
                    entry.hour,
                    entry.minutes,
                )
                for entry in schedule.entries
            ],
        )
        return len(schedule.entries)

    def save_stations(self, stations: list[dict]) -> None:
        """Save stations to database using batch insert."""
        if not stations:
            return

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Batch insert for better performance (Pattern 16)
            cursor.executemany(
                """
                INSERT OR REPLACE INTO stations
                (id, name_ua, name_en, line, station_order, transfer_to)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                [
                    (
                        station["id"],
                        station["name_ua"],
                        station["name_en"],
                        station["line"],
                        station["order"],
                        station.get("transfer_to"),
                    )
                    for station in stations
                ],
            )

            conn.commit()

    def save_schedule(self, schedule: StationSchedule) -> None:
        """Save schedule entries to database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            self._delete_schedule(cursor, schedule)
            self._insert_schedule_entries(cursor, schedule)
            conn.commit()

    def save_schedules(self, schedules: list[StationSchedule]) -> int:
        """Save multiple schedules to database using single transaction."""
        if not schedules:
            return 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            count = 0

            for schedule in schedules:
                self._delete_schedule(cursor, schedule)
                count += self._insert_schedule_entries(cursor, schedule)

            conn.commit()
            return count

    def get_station_schedule(
        self,
        station_id: str,
        direction_station_id: str,
        day_type: DayType,
    ) -> StationSchedule | None:
        """Get schedule for a station."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT hour, minutes FROM schedules
                WHERE station_id = ? AND direction_station_id = ? AND day_type = ?
                ORDER BY hour, minutes
            """,
                (station_id, direction_station_id, day_type.value),
            )

            rows = cursor.fetchall()
            if not rows:
                return None

            entries = self._rows_to_entries(rows)

            return StationSchedule(
                station_id=station_id,
                direction_station_id=direction_station_id,
                day_type=day_type,
                entries=entries,
            )

    def get_next_departures(
        self,
        station_id: str,
        direction_station_id: str,
        day_type: DayType,
        after_time: dt.time,
        limit: int = 3,
    ) -> list[ScheduleEntry]:
        """Get next departures after given time."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT hour, minutes FROM schedules
                WHERE station_id = ? AND direction_station_id = ? AND day_type = ?
                AND (hour > ? OR (hour = ? AND minutes >= ?))
                ORDER BY hour, minutes
                LIMIT ?
            """,
                (
                    station_id,
                    direction_station_id,
                    day_type.value,
                    after_time.hour,
                    after_time.hour,
                    after_time.minute,
                    limit,
                ),
            )

            rows = cursor.fetchall()
            return self._rows_to_entries(rows)

    def get_all_schedules_for_station(self, station_id: str, day_type: DayType) -> list[StationSchedule]:
        """Get all schedules (all directions) for a station using single query."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Single query with all data - avoids N+1 problem (Pattern 16)
            cursor.execute(
                """
                SELECT direction_station_id, hour, minutes
                FROM schedules
                WHERE station_id = ? AND day_type = ?
                ORDER BY direction_station_id, hour, minutes
            """,
                (station_id, day_type.value),
            )

            # Group entries by direction
            direction_entries: dict[str, list[ScheduleEntry]] = defaultdict(list)

            for row in cursor.fetchall():
                direction = row["direction_station_id"]
                direction_entries[direction].append(ScheduleEntry(hour=row["hour"], minutes=row["minutes"]))

            # Build StationSchedule objects
            return [
                StationSchedule(
                    station_id=station_id,
                    direction_station_id=direction,
                    day_type=day_type,
                    entries=entries,
                )
                for direction, entries in direction_entries.items()
            ]

    def has_schedules(self) -> bool:
        """Check if schedules table has any data."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM schedules")
            count = cursor.fetchone()[0]
            return count > 0

    def get_station(self, station_id: str) -> dict | None:
        """Get station by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM stations WHERE id = ?
            """,
                (station_id,),
            )

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_all_stations(self) -> list[dict]:
        """Get all stations."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM stations ORDER BY line, station_order
            """)

            return [dict(row) for row in cursor.fetchall()]

    def get_last_departure_time(self, day_type: DayType) -> dt.time | None:
        """Get the last departure time across all stations for a given day type."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT MAX(hour) as max_hour, MAX(minutes) as max_minutes
                FROM schedules
                WHERE day_type = ?
                AND hour = (SELECT MAX(hour) FROM schedules WHERE day_type = ?)
            """,
                (day_type.value, day_type.value),
            )

            row = cursor.fetchone()
            if row and row["max_hour"] is not None:
                return dt.time(row["max_hour"], row["max_minutes"])
            return None

    def get_first_departure_time(self, day_type: DayType) -> dt.time | None:
        """Get the first departure time across all stations for a given day type."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT MIN(hour) as min_hour, MIN(minutes) as min_minutes
                FROM schedules
                WHERE day_type = ?
                AND hour = (SELECT MIN(hour) FROM schedules WHERE day_type = ?)
            """,
                (day_type.value, day_type.value),
            )

            row = cursor.fetchone()
            if row and row["min_hour"] is not None:
                return dt.time(row["min_hour"], row["min_minutes"])
            return None

    def is_metro_open(
        self,
        day_type: DayType,
        check_time: dt.time,
        early_planning_minutes: int = 90,
    ) -> tuple[bool, dt.time | None, dt.time | None]:
        """Check if metro is open at given time.

        Metro is considered open for planning:
        - During operating hours (first_departure to last_departure)
        - Up to early_planning_minutes before first departure (allows early planning)

        Returns:
            Tuple of (is_open, last_departure_time, first_departure_time or None)
        """
        last_departure = self.get_last_departure_time(day_type)
        first_departure = self.get_first_departure_time(day_type)

        if last_departure is None or first_departure is None:
            return True, None, None  # No schedules, assume always open

        # Calculate earliest planning time
        first_dt = dt.datetime.combine(dt.datetime.today(), first_departure)
        earliest_planning_dt = first_dt - dt.timedelta(minutes=early_planning_minutes)
        earliest_planning = dt.time(earliest_planning_dt.hour, earliest_planning_dt.minute)

        # Check if current time is within operating hours or early planning window
        if earliest_planning <= check_time <= last_departure:
            return True, last_departure, first_departure

        # Metro is closed (after last departure or too early before first departure)
        return False, last_departure, first_departure

    def get_stations_by_line(self, line: str) -> list[dict]:
        """Get stations by line."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM stations WHERE line = ? ORDER BY station_order
            """,
                (line,),
            )

            return [dict(row) for row in cursor.fetchall()]
