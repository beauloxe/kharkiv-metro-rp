"""Configuration management for Kharkiv Metro Route Planner."""

from __future__ import annotations

import os
import platform
import tomllib  # Python 3.11+ only
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DEFAULT_CONFIG = """[database]
auto = true
# path = "~/.local/share/kharkiv-metro-rp/metro.db"

[preferences]
language = "ua"
output_format = "table"

[preferences.route]
format = "full"
compact = false

[user_data]
enabled = true
# path = "~/.local/share/kharkiv-metro-rp/user_data.db"
"""


class Config:
    """Read-only configuration for CLI and services."""

    TIMEZONE: ZoneInfo = ZoneInfo(os.getenv("TZ", "Europe/Kyiv"))

    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config_dir = self._get_config_dir()
        self.data_dir = self._get_data_dir()
        self.config_file = Path(config_path) if config_path else self.config_dir / "config.toml"
        self._config: dict[str, Any] = {}
        self._load()

    def _get_config_dir(self) -> Path:
        """Get XDG config directory."""
        if platform.system() == "Windows":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        elif platform.system() == "Darwin":  # macOS
            base = Path.home() / "Library" / "Application Support"
        else:  # Linux and other Unix
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

        return base / "kharkiv-metro-rp"

    def _get_data_dir(self) -> Path:
        """Get XDG data directory."""
        if platform.system() == "Windows":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        elif platform.system() == "Darwin":  # macOS
            base = Path.home() / "Library" / "Application Support"
        else:  # Linux and other Unix
            base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

        return base / "kharkiv-metro-rp"

    def _load(self) -> None:
        """Load configuration from file or create default."""
        if self.config_file.exists():
            with open(self.config_file, "rb") as f:
                self._config = tomllib.load(f)
        else:
            self._config = tomllib.loads(DEFAULT_CONFIG)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (e.g., 'database.auto')."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def get_db_path(self, cli_override: str | None = None) -> str:
        """Get database path based on configuration."""
        if cli_override:
            return cli_override

        env_path = os.getenv("METRO_DB_PATH")
        if env_path:
            return os.path.expanduser(env_path)

        auto = self.get("database.auto", True)
        if auto:
            return str(self.data_dir / "metro.db")
        else:
            path = self.get("database.path")
            if path:
                return os.path.expanduser(path)
            return str(self.data_dir / "metro.db")

    def get_user_data_db_path(self) -> str:
        """Get user data database path.

        Supports USER_DATA_DB_PATH environment variable for persistent storage.
        """
        env_path = os.getenv("USER_DATA_DB_PATH")
        if env_path:
            return os.path.expanduser(env_path)

        path = self.get("user_data.path")
        if path:
            return os.path.expanduser(path)
        return str(self.data_dir / "user_data.db")

    def is_user_data_enabled(self) -> bool:
        """Check if user data storage is enabled."""
        return self.get("user_data.enabled", True)
