"""Graph representation of metro network for pathfinding."""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from .models import ALIAS_STATION_NAMES, TRANSFERS, Line, Station, create_stations


@dataclass
class Edge:
    """Edge in the metro graph."""

    to_station_id: str
    weight: float  # minutes
    is_transfer: bool = False


@dataclass
class GraphNode:
    """Node in the metro graph."""

    station_id: str
    edges: list[Edge] = field(default_factory=list)


class MetroGraph:
    """Graph representation of metro network."""

    TRANSFER_TIME_MINUTES = 3

    def __init__(self, stations: dict[str, Station] | None = None) -> None:
        self.stations = stations or create_stations()
        self.nodes: dict[str, GraphNode] = {}
        self._build_graph()

    def _build_graph(self) -> None:
        """Build graph from stations."""
        # Create nodes for all stations
        for station_id in self.stations:
            self.nodes[station_id] = GraphNode(station_id=station_id)

        # Add edges between consecutive stations on same line
        lines_stations: dict[Line, list[Station]] = {
            Line.KHOLODNOHIRSKO_ZAVODSKA: [],
            Line.SALTIVSKA: [],
            Line.OLEKSIIVSKA: [],
        }

        for station in self.stations.values():
            lines_stations[station.line].append(station)

        # Sort by order and add edges
        for line, stations in lines_stations.items():
            stations.sort(key=lambda s: s.order)
            for i in range(len(stations) - 1):
                current = stations[i]
                next_station = stations[i + 1]

                # Bidirectional edges
                self._add_edge(current.id, next_station.id, 2.0)  # Approx 2 min per segment
                self._add_edge(next_station.id, current.id, 2.0)

        # Add transfer edges
        for from_id, to_id in TRANSFERS.items():
            self._add_edge(from_id, to_id, self.TRANSFER_TIME_MINUTES, is_transfer=True)

    def _add_edge(self, from_id: str, to_id: str, weight: float, is_transfer: bool = False) -> None:
        """Add edge to graph."""
        if from_id in self.nodes:
            self.nodes[from_id].edges.append(Edge(to_station_id=to_id, weight=weight, is_transfer=is_transfer))

    def find_shortest_path(self, start_id: str, end_id: str) -> tuple[list[str], float] | None:
        """Find shortest path using Dijkstra's algorithm."""
        if start_id not in self.nodes or end_id not in self.nodes:
            return None

        # Dijkstra's algorithm
        distances: dict[str, float] = {sid: float("inf") for sid in self.nodes}
        distances[start_id] = 0
        previous: dict[str, str | None] = dict.fromkeys(self.nodes)
        visited: set[str] = set()

        # Priority queue: (distance, station_id)
        pq = [(0.0, start_id)]

        while pq:
            current_dist, current_id = heapq.heappop(pq)

            if current_id in visited:
                continue
            visited.add(current_id)

            if current_id == end_id:
                break

            node = self.nodes[current_id]
            for edge in node.edges:
                neighbor_id = edge.to_station_id
                if neighbor_id in visited:
                    continue

                new_dist = current_dist + edge.weight
                if new_dist < distances[neighbor_id]:
                    distances[neighbor_id] = new_dist
                    previous[neighbor_id] = current_id
                    heapq.heappush(pq, (new_dist, neighbor_id))

        # Reconstruct path
        if distances[end_id] == float("inf"):
            return None

        path = []
        current = end_id
        while current is not None:
            path.append(current)
            current = previous[current]
        path.reverse()

        return path, distances[end_id]

    def get_station(self, station_id: str) -> Station | None:
        """Get station by ID."""
        return self.stations.get(station_id)

    def find_station_by_name(self, name: str, lang: str = "ua") -> Station | None:
        """Find station by name (fuzzy matching with old name support)."""
        name_lower = name.lower().strip()
        name_attr = f"name_{lang}"

        # Check if it's an old name and resolve to new name
        if name_lower in ALIAS_STATION_NAMES:
            resolved_name = ALIAS_STATION_NAMES[name_lower]
            name_lower = resolved_name.lower()

        # Exact match
        for station in self.stations.values():
            station_name = getattr(station, name_attr).lower()
            if name_lower == station_name:
                return station

        # Try partial match
        for station in self.stations.values():
            station_name = getattr(station, name_attr).lower()
            if name_lower in station_name or station_name in name_lower:
                return station

        return None

    def get_neighbors(self, station_id: str) -> list[tuple[Station, float, bool]]:
        """Get neighboring stations with weights."""
        if station_id not in self.nodes:
            return []

        result = []
        for edge in self.nodes[station_id].edges:
            neighbor = self.stations.get(edge.to_station_id)
            if neighbor:
                result.append((neighbor, edge.weight, edge.is_transfer))
        return result
