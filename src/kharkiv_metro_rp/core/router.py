"""Router for finding optimal metro routes."""

from __future__ import annotations

from datetime import datetime, timedelta

from ..bot.constants import DB_PATH, TIMEZONE
from ..data.database import MetroDatabase
from .graph import MetroGraph
from .models import (
    DayType,
    Line,
    Route,
    RouteSegment,
    Station,
    StationSchedule,
)


class MetroRouter:
    """Router for finding metro routes with schedule-based timing."""

    def __init__(
        self,
        db: MetroDatabase | None = None,
        graph: MetroGraph | None = None,
    ) -> None:
        self.db = db or MetroDatabase(DB_PATH)
        self.graph = graph or MetroGraph()
        self.stations = self.graph.stations

    def find_route(
        self,
        from_station_id: str,
        to_station_id: str,
        departure_time: datetime,
        day_type: DayType | None = None,
    ) -> Route | None:
        """Find optimal route with schedule-based timing."""
        if day_type is None:
            day_type = self._get_day_type(departure_time)

        # Find shortest path using graph
        path_result = self.graph.find_shortest_path(from_station_id, to_station_id)
        if not path_result:
            return None

        path, _ = path_result

        # Build route with schedule-based timing
        return self._build_route_with_schedule(path, departure_time, day_type)

    def find_multiple_routes(
        self,
        from_station_id: str,
        to_station_id: str,
        departure_time: datetime,
        num_options: int = 3,
    ) -> list[Route]:
        """Find multiple route options."""
        day_type = self._get_day_type(departure_time)
        routes = []

        # Find primary route
        primary = self.find_route(from_station_id, to_station_id, departure_time, day_type)
        if primary:
            routes.append(primary)

        # Find alternative routes by trying different departure times
        current_time = departure_time
        for i in range(1, num_options * 2):
            if len(routes) >= num_options:
                break

            # Try 10 minutes later
            current_time = current_time + timedelta(minutes=10)
            alt_route = self.find_route(from_station_id, to_station_id, current_time, day_type)

            if alt_route and not self._routes_similar(routes[-1], alt_route):
                routes.append(alt_route)

        return routes[:num_options]

    def _build_route_with_schedule(
        self,
        path: list[str],
        start_time: datetime,
        day_type: DayType,
    ) -> Route:
        """Build route with schedule-based timing."""
        segments: list[RouteSegment] = []
        num_transfers = 0

        current_time: datetime = start_time
        current_line: Line | None = None
        direction: str | None = None

        for i in range(len(path) - 1):
            from_id = path[i]
            to_id = path[i + 1]

            from_station = self.stations[from_id]
            to_station = self.stations[to_id]

            # Check if this is a transfer
            is_transfer = from_station.transfer_to == to_id

            if is_transfer:
                # Transfer segment
                duration = 3
                segment = RouteSegment(
                    from_station=from_station,
                    to_station=to_station,
                    departure_time=current_time,
                    arrival_time=current_time + timedelta(minutes=duration),
                    is_transfer=True,
                    duration_minutes=duration,
                )
                num_transfers += 1
                segments.append(segment)
                if segment.arrival_time is not None:
                    current_time = segment.arrival_time
                current_line = None  # Reset line after transfer
                direction = None  # Reset direction after transfer

            else:
                # Train segment
                # Ensure direction is set
                if current_line is None or from_station.line != current_line:
                    current_line = from_station.line
                    direction = self._find_terminal_in_path(path, i, current_line)

                    # Get exact departure time from schedule at the start of line
                    next_departures = self.db.get_next_departures(
                        from_id,
                        direction,
                        day_type,
                        current_time.time(),
                        limit=1,
                    )

                    if next_departures:
                        departure = next_departures[0]
                        departure_dt = datetime.combine(current_time.date(), departure.time)
                        if departure_dt < current_time:
                            departure_dt += timedelta(days=1)
                        current_time = departure_dt

                # Calculate travel time based on arrival at next station
                # Try to find when a train arrives at the next station heading same direction
                arrival_time: datetime | None = None
                if direction:
                    arrival_time = self._calculate_arrival_time(to_id, direction, day_type, current_time)

                if arrival_time:
                    travel_time = int((arrival_time - current_time).total_seconds() / 60)
                else:
                    # Fallback to default 2 minutes if no schedule found
                    travel_time = 2
                    arrival_time = current_time + timedelta(minutes=travel_time)

                segment = RouteSegment(
                    from_station=from_station,
                    to_station=to_station,
                    departure_time=current_time,
                    arrival_time=arrival_time,
                    is_transfer=False,
                    duration_minutes=travel_time,
                )
                segments.append(segment)
                current_time = arrival_time

        # Calculate total duration
        if segments and segments[0].departure_time and segments[-1].arrival_time:
            total_duration = int((segments[-1].arrival_time - segments[0].departure_time).total_seconds() / 60)
            departure = segments[0].departure_time
            arrival = segments[-1].arrival_time
        else:
            total_duration = sum(s.duration_minutes for s in segments)
            departure = None
            arrival = None

        return Route(
            segments=segments,
            total_duration_minutes=total_duration,
            num_transfers=num_transfers,
            departure_time=departure,
            arrival_time=arrival,
        )

    def _calculate_arrival_time(
        self,
        station_id: str,
        direction: str,
        day_type: DayType,
        after_time: datetime,
    ) -> datetime | None:
        """Calculate arrival time at station based on schedule.

        Looks up when a train arrives at the given station heading in the specified direction.
        Returns None if no schedule is available.
        """
        # Look up arrivals at the next station heading to the same terminal
        arrivals = self.db.get_next_departures(
            station_id,
            direction,
            day_type,
            after_time.time(),
            limit=1,
        )

        if arrivals:
            arrival = arrivals[0]
            # Preserve timezone from after_time
            arrival_dt = after_time.replace(hour=arrival.time.hour, minute=arrival.time.minute, second=0, microsecond=0)
            if arrival_dt < after_time:
                arrival_dt += timedelta(days=1)
            return arrival_dt

        return None

    def _find_terminal_in_path(self, path: list[str], start_idx: int, line: Line) -> str:
        """Find terminal station in path for given line starting from index."""
        # Find all stations on this line in the path
        line_stations = []
        for i in range(start_idx, len(path)):
            if self.stations[path[i]].line == line:
                line_stations.append(path[i])
            else:
                break

        if len(line_stations) >= 2:
            first_order = self.stations[line_stations[0]].order
            last_order = self.stations[line_stations[-1]].order

            # Find terminal stations for this line (first and last on the line)
            line_stations_all = [sid for sid, station in self.stations.items() if station.line == line]
            min_order = min(self.stations[sid].order for sid in line_stations_all)
            max_order = max(self.stations[sid].order for sid in line_stations_all)
            first_terminal = next(sid for sid in line_stations_all if self.stations[sid].order == min_order)
            last_terminal = next(sid for sid in line_stations_all if self.stations[sid].order == max_order)

            if last_order > first_order:
                return last_terminal  # Going forward - return last terminal
            else:
                return first_terminal  # Going backward - return first terminal

        return path[start_idx]

    def _get_day_type(self, dt: datetime) -> DayType:
        """Determine if date is weekday or weekend."""
        if dt.weekday() >= 5:
            return DayType.WEEKEND
        return DayType.WEEKDAY

    def _routes_similar(self, route1: Route, route2: Route) -> bool:
        """Check if two routes are similar."""
        if len(route1.segments) != len(route2.segments):
            return False

        for s1, s2 in zip(route1.segments, route2.segments):
            if s1.from_station.id != s2.from_station.id:
                return False
            if s1.to_station.id != s2.to_station.id:
                return False

        if route1.departure_time and route2.departure_time:
            diff = abs((route1.departure_time - route2.departure_time).total_seconds())
            if diff < 300:
                return True

        return False

    def get_station_schedule(
        self,
        station_id: str,
        direction_id: str | None = None,
        day_type: DayType | None = None,
    ) -> list[StationSchedule]:
        """Get schedule for a station."""
        if day_type is None:
            day_type = self._get_day_type(datetime.now(TIMEZONE))

        if direction_id:
            schedule = self.db.get_station_schedule(station_id, direction_id, day_type)
            return [schedule] if schedule else []
        else:
            return self.db.get_all_schedules_for_station(station_id, day_type)

    def find_station_by_name(self, name: str, lang: str = "ua") -> Station | None:
        """Find station by name."""
        return self.graph.find_station_by_name(name, lang)
