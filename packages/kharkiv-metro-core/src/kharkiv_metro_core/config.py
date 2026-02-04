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
# path = "~/.local/share/kharkiv-metro-rp/metro.db"  # used if auto = false

[preferences]
language = "ua"
output_format = "table"

[preferences.route]
format = "full"  # "full" (table), "simple" (inline), or "json"
compact = false  # true = show only key stations (start, transfers, end)

[scraper]
timeout = 30
user_agent = "kharkiv-metro-rp/1.0"
"""


class Config:
    """Configuration manager using XDG directories."""

    TIMEZONE: ZoneInfo = ZoneInfo(os.getenv("TZ", "Europe/Kyiv"))
    LINE_ORDER: list[str] = ["Холодногірсько-заводська", "Салтівська", "Олексіївська"]

    def __init__(self) -> None:
        self.config_dir = self._get_config_dir()
        self.data_dir = self._get_data_dir()
        self.config_file = self.config_dir / "config.toml"
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

    def _parse_default(self) -> dict[str, Any]:
        """Parse default configuration."""
        return tomllib.loads(DEFAULT_CONFIG)

    def ensure_dirs(self) -> None:
        """Ensure configuration and data directories exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def create_default(self) -> None:
        """Create default configuration file."""
        self.ensure_dirs()
        if not self.config_file.exists():
            with open(self.config_file, "w", encoding="utf-8") as f:
                f.write(DEFAULT_CONFIG)

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

    def set(self, key: str, value: Any) -> None:
        """Set configuration value by key."""
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self._save()

    def _save(self) -> None:
        """Save configuration to file."""
        import toml

        with open(self.config_file, "w", encoding="utf-8") as f:
            toml.dump(self._config, f)

    def reset(self) -> None:
        """Reset configuration to defaults."""
        self._config = self._parse_default()
        self._save()

    def get_db_path(self, cli_override: str | None = None) -> str:
        """Get database path based on configuration."""
        if cli_override:
            return cli_override

        auto = self.get("database.auto", True)
        if auto:
            return str(self.data_dir / "metro.db")
        else:
            path = self.get("database.path")
            if path:
                return os.path.expanduser(path)
            return str(self.data_dir / "metro.db")

    def to_dict(self) -> dict[str, Any]:
        """Return configuration as dictionary."""
        return self._config.copy()

    @property
    def config_path(self) -> str:
        """Return path to configuration file."""
        return str(self.config_file)

    @property
    def data_path(self) -> str:
        """Return path to data directory."""
        return str(self.data_dir)
