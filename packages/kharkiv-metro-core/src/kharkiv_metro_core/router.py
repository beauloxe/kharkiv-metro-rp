"""Router for finding optimal metro routes."""

from __future__ import annotations

import datetime as dt

from .config import Config
from .database import MetroDatabase
from .graph import MetroGraph, get_metro_graph
from .models import (
    DayType,
    Line,
    MetroClosedError,
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
        config = Config()
        self.db = db or MetroDatabase.shared(config.get_db_path())
        self.graph = graph or get_metro_graph()
        self._line_terminals: dict[Line, tuple[str, str]] | None = None
        self._next_departure_cache: dict[tuple[str, str, DayType, int, int, int], list] = {}
        self._previous_departure_cache: dict[tuple[str, str, DayType, int, int, int], list] = {}

    @property
    def stations(self) -> dict[str, Station]:
        return self.graph.stations

    def find_route(
        self,
        from_station_id: str,
        to_station_id: str,
        departure_time: dt.datetime,
        day_type: DayType | None = None,
        arrival_by: dt.datetime | None = None,
    ) -> Route | None:
        """Find optimal route with schedule-based timing.

        If arrival_by is provided, compute a route that arrives no later than this time.
        """
        if day_type is None:
            day_type = self._get_day_type(arrival_by or departure_time)

        # Find shortest path using graph
        path_result = self.graph.find_shortest_path(from_station_id, to_station_id)
        if not path_result:
            return None

        path, _ = path_result

        if arrival_by is not None:
            route = self._build_route_arrival_by(path, arrival_by, day_type)
            if route and route.arrival_time and route.arrival_time > arrival_by:
                return None
            if route and route.departure_time:
                is_open, _, _ = self.db.is_metro_open(day_type, route.departure_time.time())
                if not is_open:
                    raise MetroClosedError()
            return route

        # Check if metro is still open at departure time
        is_open, last_departure, first_departure = self.db.is_metro_open(day_type, departure_time.time())
        if not is_open:
            raise MetroClosedError()

        # Build route with schedule-based timing
        route = self._build_route_with_schedule(path, departure_time, day_type)

        # Check if route can be completed before metro closes
        if route and route.arrival_time:
            is_still_open, _, _ = self.db.is_metro_open(day_type, route.arrival_time.time())
            if not is_still_open:
                raise MetroClosedError()

        return route

    def _build_route_with_schedule(
        self,
        path: list[str],
        start_time: dt.datetime,
        day_type: DayType,
    ) -> Route:
        """Build route with schedule-based timing."""
        # Check if metro is open at start time (or within early planning window)
        is_open, last_departure, first_departure = self.db.is_metro_open(day_type, start_time.time())
        if not is_open:
            raise MetroClosedError()

        # Precompute terminal stations for all lines to avoid repeated calculations
        line_terminals = self._get_line_terminals()

        segments: list[RouteSegment] = []
        num_transfers = 0

        current_time: dt.datetime = start_time
        current_line: Line | None = None
        direction: str | None = None

        # Local variables for faster access (Pattern 9)
        stations = self.stations
        db = self.db
        timedelta_minutes = dt.timedelta

        for i in range(len(path) - 1):
            from_id = path[i]
            to_id = path[i + 1]

            from_station = stations[from_id]
            to_station = stations[to_id]

            # Check if this is a transfer
            is_transfer = from_station.transfer_to == to_id

            if is_transfer:
                # Transfer segment
                duration = 3
                arrival = current_time + timedelta_minutes(minutes=duration)
                segment = RouteSegment(
                    from_station=from_station,
                    to_station=to_station,
                    departure_time=current_time,
                    arrival_time=arrival,
                    is_transfer=True,
                    duration_minutes=duration,
                )
                num_transfers += 1
                segments.append(segment)
                current_time = arrival
                current_line = None  # Reset line after transfer
                direction = None  # Reset direction after transfer

            else:
                # Train segment
                # Ensure direction is set
                if current_line is None or from_station.line != current_line:
                    current_line = from_station.line
                    direction = self._find_terminal_in_path_fast(path, i, current_line, line_terminals)

                    # Get exact departure time from schedule at the start of line
                    current_time_only = dt.time(current_time.hour, current_time.minute)
                    next_departures = self._get_next_departures(
                        from_id,
                        direction,
                        day_type,
                        current_time_only,
                        limit=1,
                    )

                    if next_departures:
                        departure = next_departures[0]
                        departure_dt = dt.datetime.combine(current_time.date(), departure.time, current_time.tzinfo)
                        if departure_dt < current_time:
                            departure_dt += timedelta_minutes(days=1)
                        current_time = departure_dt
                    else:
                        # No departures available - metro is closed
                        raise MetroClosedError()

                # Calculate travel time based on arrival at next station
                # Try to find when a train arrives at the next station heading same direction
                arrival_time: dt.datetime | None = None
                if direction:
                    arrival_time = self._calculate_arrival_time(to_id, direction, day_type, current_time)

                if arrival_time:
                    travel_time = int((arrival_time - current_time).total_seconds() / 60)
                else:
                    # Fallback to default 2 minutes if no schedule found
                    travel_time = 2
                    arrival_time = current_time + timedelta_minutes(minutes=travel_time)

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

    def _build_route_arrival_by(
        self,
        path: list[str],
        arrival_by: dt.datetime,
        day_type: DayType,
    ) -> Route:
        """Build route that arrives no later than target time."""
        is_open, _, _ = self.db.is_metro_open(day_type, arrival_by.time())
        if not is_open:
            raise MetroClosedError()

        line_terminals = self._get_line_terminals()
        reverse_segments: list[RouteSegment] = []
        num_transfers = 0

        current_time: dt.datetime = arrival_by
        current_line: Line | None = None
        direction: str | None = None

        stations = self.stations
        timedelta_minutes = dt.timedelta

        for i in range(len(path) - 1, 0, -1):
            from_id = path[i - 1]
            to_id = path[i]

            from_station = stations[from_id]
            to_station = stations[to_id]

            is_transfer = from_station.transfer_to == to_id

            if is_transfer:
                duration = 3
                departure = current_time - timedelta_minutes(minutes=duration)
                segment = RouteSegment(
                    from_station=from_station,
                    to_station=to_station,
                    departure_time=departure,
                    arrival_time=current_time,
                    is_transfer=True,
                    duration_minutes=duration,
                )
                num_transfers += 1
                reverse_segments.append(segment)
                current_time = departure
                current_line = None
                direction = None
                continue

            if current_line is None or from_station.line != current_line:
                current_line = from_station.line
                direction = self._find_terminal_in_path_fast(path, i - 1, current_line, line_terminals)

            departure_time: dt.datetime | None = None
            arrival_time: dt.datetime | None = None

            if direction:
                departure_time, arrival_time = self._find_departure_before(
                    from_id,
                    to_id,
                    direction,
                    day_type,
                    current_time,
                )

            if departure_time and arrival_time:
                travel_time = int((arrival_time - departure_time).total_seconds() / 60)
                if travel_time <= 0:
                    travel_time = 2
                    arrival_time = departure_time + timedelta_minutes(minutes=travel_time)
            else:
                travel_time = 2
                arrival_time = current_time
                departure_time = current_time - timedelta_minutes(minutes=travel_time)

            segment = RouteSegment(
                from_station=from_station,
                to_station=to_station,
                departure_time=departure_time,
                arrival_time=arrival_time,
                is_transfer=False,
                duration_minutes=travel_time,
            )
            reverse_segments.append(segment)
            current_time = departure_time

        segments = list(reversed(reverse_segments))

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

    def _find_departure_before(
        self,
        from_station_id: str,
        to_station_id: str,
        direction: str,
        day_type: DayType,
        arrival_by: dt.datetime,
        limit: int = 5,
    ) -> tuple[dt.datetime | None, dt.datetime | None]:
        """Find latest departure that arrives before target time."""
        previous_departures = self._get_previous_departures(
            from_station_id,
            direction,
            day_type,
            arrival_by.time(),
            limit=limit,
        )

        for departure in previous_departures:
            departure_dt = dt.datetime.combine(arrival_by.date(), departure.time, arrival_by.tzinfo)
            if departure_dt > arrival_by:
                departure_dt -= dt.timedelta(days=1)
            arrival_dt = self._calculate_arrival_time(to_station_id, direction, day_type, departure_dt)
            if arrival_dt and arrival_dt <= arrival_by:
                return departure_dt, arrival_dt

        return None, None

    def _calculate_arrival_time(
        self,
        station_id: str,
        direction: str,
        day_type: DayType,
        after_time: dt.datetime,
    ) -> dt.datetime | None:
        """Calculate arrival time at station based on schedule.

        Looks up when a train arrives at the given station heading in the specified direction.
        Returns None if no schedule is available.
        """
        # Look up arrivals at the next station heading to the same terminal
        after_time_only = dt.time(after_time.hour, after_time.minute)
        arrivals = self._get_next_departures(
            station_id,
            direction,
            day_type,
            after_time_only,
            limit=1,
        )

        if arrivals:
            arrival = arrivals[0]
            # Preserve timezone from after_time - create new datetime with proper tzinfo
            arrival_dt = dt.datetime.combine(after_time.date(), arrival.time, after_time.tzinfo)
            if arrival_dt < after_time:
                arrival_dt += dt.timedelta(days=1)
            return arrival_dt

        return None

    def _get_line_terminals(self) -> dict[Line, tuple[str, str]]:
        """Precompute terminal stations for all lines.

        Returns dict mapping line to (first_terminal_id, last_terminal_id).
        """
        if self._line_terminals is not None:
            return self._line_terminals

        terminals: dict[Line, tuple[str, str]] = {}

        for line in [Line.KHOLODNOHIRSKO_ZAVODSKA, Line.SALTIVSKA, Line.OLEKSIIVSKA]:
            line_stations = [(sid, s.order) for sid, s in self.stations.items() if s.line == line]
            if line_stations:
                min_order = min(order for _, order in line_stations)
                max_order = max(order for _, order in line_stations)
                first_terminal = next(sid for sid, order in line_stations if order == min_order)
                last_terminal = next(sid for sid, order in line_stations if order == max_order)
                terminals[line] = (first_terminal, last_terminal)

        self._line_terminals = terminals
        return terminals

    def _find_terminal_in_path_fast(
        self,
        path: list[str],
        start_idx: int,
        line: Line,
        line_terminals: dict[Line, tuple[str, str]],
    ) -> str:
        """Find terminal station in path for given line starting from index.

        Uses precomputed terminals for better performance.
        """
        # Local variables for faster access (Pattern 9)
        stations = self.stations
        path_len = len(path)

        # Find first and last station on this line in the path
        first_station_idx = start_idx
        last_station_idx = start_idx

        for i in range(start_idx, path_len):
            if stations[path[i]].line == line:
                last_station_idx = i
            else:
                break

        if last_station_idx > first_station_idx:
            first_order = stations[path[first_station_idx]].order
            last_order = stations[path[last_station_idx]].order

            first_terminal, last_terminal = line_terminals.get(line, (path[start_idx], path[start_idx]))

            if last_order > first_order:
                return last_terminal  # Going forward - return last terminal
            else:
                return first_terminal  # Going backward - return first terminal

        return path[start_idx]

    def _find_terminal_in_path(self, path: list[str], start_idx: int, line: Line) -> str:
        """Find terminal station in path for given line starting from index."""
        # Delegate to optimized version with cached terminals
        line_terminals = self._get_line_terminals()
        return self._find_terminal_in_path_fast(path, start_idx, line, line_terminals)

    def _get_next_departures(
        self,
        station_id: str,
        direction_station_id: str,
        day_type: DayType,
        after_time: dt.time,
        limit: int = 3,
    ) -> list:
        """Cached next departures lookup."""
        key = (station_id, direction_station_id, day_type, after_time.hour, after_time.minute, limit)
        if key in self._next_departure_cache:
            return self._next_departure_cache[key]
        result = self.db.get_next_departures(station_id, direction_station_id, day_type, after_time, limit=limit)
        self._next_departure_cache[key] = result
        return result

    def _get_previous_departures(
        self,
        station_id: str,
        direction_station_id: str,
        day_type: DayType,
        before_time: dt.time,
        limit: int = 3,
    ) -> list:
        """Cached previous departures lookup."""
        key = (station_id, direction_station_id, day_type, before_time.hour, before_time.minute, limit)
        if key in self._previous_departure_cache:
            return self._previous_departure_cache[key]
        result = self.db.get_previous_departures(station_id, direction_station_id, day_type, before_time, limit=limit)
        self._previous_departure_cache[key] = result
        return result

    def _get_day_type(self, current_dt: dt.datetime) -> DayType:
        """Determine if date is weekday or weekend."""
        if current_dt.weekday() >= 5:
            return DayType.WEEKEND
        return DayType.WEEKDAY

    def get_station_schedule(
        self,
        station_id: str,
        direction_id: str | None = None,
        day_type: DayType | None = None,
    ) -> list[StationSchedule]:
        """Get schedule for a station."""
        if day_type is None:
            from .time_utils import now

            day_type = self._get_day_type(now())

        if direction_id:
            schedule = self.db.get_station_schedule(station_id, direction_id, day_type)
            return [schedule] if schedule else []
        else:
            return self.db.get_all_schedules_for_station(station_id, day_type)

    def find_station_by_name(self, name: str, lang: str = "ua") -> Station | None:
        """Find station by name."""
        return self.graph.find_station_by_name(name, lang)
