"""MCP server for Kharkiv metro route planning."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from typing import Any

from kharkiv_metro_core import DayType, MetroDatabase, MetroRouter, Route, now
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


class MetroMCPServer:
    """MCP server for metro route planning."""

    def __init__(self, db_path: str | None = None) -> None:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        self.logger = logging.getLogger(__name__)
        self.router = MetroRouter(db=MetroDatabase.shared(db_path))
        self.server = Server("kharkiv-metro")
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Setup MCP handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="get_route",
                    description="Find route between two metro stations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "from_station": {
                                "type": "string",
                                "description": "Starting station name (Ukrainian or English)",
                            },
                            "to_station": {
                                "type": "string",
                                "description": "Destination station name (Ukrainian or English)",
                            },
                            "departure_time": {
                                "type": "string",
                                "description": "Departure time in HH:MM format (optional, default: now)",
                            },
                            "day_type": {
                                "type": "string",
                                "enum": ["weekday", "weekend"],
                                "description": "Day type (optional, default: auto-detect)",
                            },
                            "language": {
                                "type": "string",
                                "enum": ["ua", "en"],
                                "description": "Language for station names (default: ua)",
                            },
                            "format": {
                                "type": "string",
                                "enum": ["simple", "detailed"],
                                "description": "Output format: simple (compact) or detailed (full route). Default: simple",
                            },
                        },
                        "required": ["from_station", "to_station"],
                    },
                ),
                Tool(
                    name="get_schedule",
                    description="Get train schedule for a station",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "station": {
                                "type": "string",
                                "description": "Station name",
                            },
                            "direction": {
                                "type": "string",
                                "description": "Direction (terminal station, optional)",
                            },
                            "day_type": {
                                "type": "string",
                                "enum": ["weekday", "weekend"],
                                "description": "Day type (optional)",
                            },
                            "language": {
                                "type": "string",
                                "enum": ["ua", "en"],
                                "description": "Language (default: ua)",
                            },
                        },
                        "required": ["station"],
                    },
                ),
                Tool(
                    name="list_stations",
                    description="List all metro stations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "line": {
                                "type": "string",
                                "enum": [
                                    "kholodnohirsko_zavodska",
                                    "saltivska",
                                    "oleksiivska",
                                ],
                                "description": "Filter by line (optional)",
                            },
                            "language": {
                                "type": "string",
                                "enum": ["ua", "en"],
                                "description": "Language (default: ua)",
                            },
                        },
                    },
                ),
                Tool(
                    name="find_station",
                    description="Find station by name (fuzzy search)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Station name to search",
                            },
                            "language": {
                                "type": "string",
                                "enum": ["ua", "en"],
                                "description": "Language (default: ua)",
                            },
                        },
                        "required": ["name"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            if name == "get_route":
                return await self._handle_get_route(arguments)
            elif name == "get_schedule":
                return await self._handle_get_schedule(arguments)
            elif name == "list_stations":
                return await self._handle_list_stations(arguments)
            elif name == "find_station":
                return await self._handle_find_station(arguments)
            else:
                self.logger.warning("Unknown tool requested: %s", name)
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

    async def _handle_get_route(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle get_route tool."""
        from_station = arguments["from_station"]
        to_station = arguments["to_station"]
        lang = arguments.get("language", "ua")

        # Parse departure time
        time_str = arguments.get("departure_time")
        if time_str:
            hour, minute = map(int, time_str.split(":"))
            departure_time = now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            departure_time = now()

        # Parse day type
        day_type_str = arguments.get("day_type")
        day_type = (DayType.WEEKDAY if day_type_str == "weekday" else DayType.WEEKEND) if day_type_str else None

        # Find stations
        from_st = self.router.find_station_by_name(from_station, lang)
        to_st = self.router.find_station_by_name(to_station, lang)

        if not from_st:
            self.logger.info("Station not found: %s", from_station)
            return [TextContent(type="text", text=f"Station not found: {from_station}")]

        if not to_st:
            self.logger.info("Station not found: %s", to_station)
            return [TextContent(type="text", text=f"Station not found: {to_station}")]

        # Find route
        route = self.router.find_route(from_st.id, to_st.id, departure_time, day_type)

        if not route:
            self.logger.info("No route found for %s -> %s", from_station, to_station)
            return [TextContent(type="text", text="No route found")]

        # Format result
        result = route.to_dict(lang)

        # Check format preference
        output_format = arguments.get("format", "simple")

        # Create human-readable text
        if output_format == "simple":
            text = self._format_route_simple(route, lang)
        else:
            text = self._format_route_text(route, lang)

        import json

        return [
            TextContent(type="text", text=text),
            TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False)),
        ]

    def _format_route_text(self, route: Route, lang: str) -> str:
        """Format route as human-readable text."""
        name_attr = f"name_{lang}"
        lines = []

        if route.departure_time and route.arrival_time:
            dep = route.departure_time.strftime("%H:%M")
            arr = route.arrival_time.strftime("%H:%M")
            lines.append(f"Route: {dep} → {arr} ({route.total_duration_minutes} min, {route.num_transfers} transfers)")
        else:
            lines.append(f"Route: {route.total_duration_minutes} min, {route.num_transfers} transfers")

        lines.append("")

        for i, segment in enumerate(route.segments, 1):
            from_name = getattr(segment.from_station, name_attr)
            to_name = getattr(segment.to_station, name_attr)

            if segment.is_transfer:
                lines.append(f"{i}. Transfer: {from_name} → {to_name} ({segment.duration_minutes} min)")
            else:
                line_name = getattr(segment.from_station.line, f"display_name_{lang}")
                if segment.departure_time and segment.arrival_time:
                    dep = segment.departure_time.strftime("%H:%M")
                    arr = segment.arrival_time.strftime("%H:%M")
                    lines.append(f"{i}. {line_name}: {from_name} → {to_name} ({dep} → {arr})")
                else:
                    lines.append(f"{i}. {line_name}: {from_name} → {to_name} ({segment.duration_minutes} min)")

        return "\n".join(lines)

    def _format_route_simple(self, route: Route, lang: str) -> str:
        """Format route in compact inline format."""
        name_attr = f"name_{lang}"

        # Build the path showing all stations
        path_parts = []
        added_stations = set()

        # Always add the first station
        if route.segments:
            first_station = route.segments[0].from_station
            first_name = getattr(first_station, name_attr)
            path_parts.append(first_name)
            added_stations.add(first_name)

        # Add all stations along the route
        for segment in route.segments:
            to_name = getattr(segment.to_station, name_attr)

            if segment.is_transfer:
                # At transfer, add the transfer destination station
                transfer_line = segment.to_station.line
                transfer_color = transfer_line.color
                path_parts.append(f"[{transfer_color}]{to_name}[/{transfer_color}]")
                added_stations.add(to_name)
            else:
                # For train segments, add the destination station if not already added
                if to_name not in added_stations:
                    path_parts.append(to_name)
                    added_stations.add(to_name)

        # Create the path string
        path_str = " → ".join(path_parts)

        # Summary info
        total_time = route.total_duration_minutes
        transfers = route.num_transfers

        if route.departure_time and route.arrival_time:
            dep = route.departure_time.strftime("%H:%M")
            arr = route.arrival_time.strftime("%H:%M")
            time_str = f"{dep} → {arr} ({total_time} min)"
        else:
            time_str = f"{total_time} min"

        transfers_str = (
            f"{transfers} пересадка"
            if transfers == 1
            else f"{transfers} пересадки"
            if transfers > 0
            else "без пересадок"
        )

        return f"{path_str}\n{time_str} | {transfers_str}"

    async def _handle_get_schedule(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle get_schedule tool."""
        station_name = arguments["station"]
        lang = arguments.get("language", "ua")

        # Find station
        station = self.router.find_station_by_name(station_name, lang)
        if not station:
            self.logger.info("Station not found: %s", station_name)
            return [TextContent(type="text", text=f"Station not found: {station_name}")]

        # Parse day type
        day_type_str = arguments.get("day_type")
        if day_type_str:
            day_type = DayType.WEEKDAY if day_type_str == "weekday" else DayType.WEEKEND
        else:
            day_type = DayType.WEEKDAY if now().weekday() < 5 else DayType.WEEKEND

        # Get direction if specified
        direction_id = None
        direction_name = arguments.get("direction")
        if direction_name:
            dir_st = self.router.find_station_by_name(direction_name, lang)
            if dir_st:
                direction_id = dir_st.id

        # Get schedules
        schedules = self.router.get_station_schedule(station.id, direction_id, day_type)

        if not schedules:
            self.logger.info("No schedule found for %s", station_name)
            return [TextContent(type="text", text="No schedule found")]

        # Format result
        lines = [f"Schedule for {getattr(station, f'name_{lang}')}:", ""]

        for schedule in schedules:
            dir_st = self.router.stations.get(schedule.direction_station_id)
            if dir_st:
                dir_name = getattr(dir_st, f"name_{lang}")
                lines.append(f"Direction: {dir_name}")

                # Show next few departures
                current_time = now()
                now_time = dt.time(current_time.hour, current_time.minute)
                next_deps = schedule.get_next_departures(now_time, 5)
                if next_deps:
                    lines.append("Next departures:")
                    for dep in next_deps:
                        lines.append(f"  {dep.time.strftime('%H:%M')}")
                lines.append("")

        return [TextContent(type="text", text="\n".join(lines))]

    async def _handle_list_stations(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle list_stations tool."""
        lang = arguments.get("language", "ua")
        line = arguments.get("line")

        name_attr = f"name_{lang}"

        stations_data = self.router.db.get_stations_by_line(line) if line else self.router.db.get_all_stations()

        lines = []
        for station in stations_data:
            from kharkiv_metro_core import Line

            line_name = Line(station["line"]).display_name_ua if lang == "ua" else Line(station["line"]).display_name_en
            lines.append(f"{line_name}: {station[name_attr]}")

        return [TextContent(type="text", text="\n".join(lines))]

    async def _handle_find_station(self, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle find_station tool."""
        name = arguments["name"]
        lang = arguments.get("language", "ua")

        station = self.router.find_station_by_name(name, lang)

        if not station:
            self.logger.info("Station not found: %s", name)
            return [TextContent(type="text", text=f"Station not found: {name}")]

        name_attr = f"name_{lang}"
        line_name = getattr(station.line, f"display_name_{lang}")

        text = f"Found: {getattr(station, name_attr)}\nLine: {line_name}"
        if station.transfer_to:
            transfer_st = self.router.stations.get(station.transfer_to)
            if transfer_st:
                text += f"\nTransfer to: {getattr(transfer_st, name_attr)}"

        return [TextContent(type="text", text=text)]

    async def run(self) -> None:
        """Run the MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


def main() -> None:
    """Main entry point."""
    server = MetroMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
