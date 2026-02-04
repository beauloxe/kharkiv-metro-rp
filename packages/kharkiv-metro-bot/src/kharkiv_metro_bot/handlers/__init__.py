"""Bot handlers package."""

from .common import register_common_handlers
from .route import register_route_handlers
from .schedule import register_schedule_handlers
from .stations import register_stations_handlers

__all__ = [
    "register_common_handlers",
    "register_route_handlers",
    "register_schedule_handlers",
    "register_stations_handlers",
]
