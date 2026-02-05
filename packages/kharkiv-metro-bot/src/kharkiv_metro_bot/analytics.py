"""Analytics module for tracking anonymized user usage."""

import hashlib
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from kharkiv_metro_core import Config

# Get config instance
_config = Config()

# Configuration from config file (with env override)
ANALYTICS_ENABLED = os.getenv("ENABLE_ANALYTICS", str(_config.is_analytics_enabled())).lower() == "true"
ANALYTICS_SALT = os.getenv("ANALYTICS_SALT", _config.get("analytics.salt", "default-salt-change-me"))

# Database path (uses same data directory as metro.db)
ANALYTICS_DB_PATH = Path(_config.get_analytics_db_path())


def is_analytics_enabled() -> bool:
    """Check if analytics is enabled."""
    return ANALYTICS_ENABLED


def get_admin_id() -> int | None:
    """Get admin user ID from environment."""
    admin_id = os.getenv("ADMIN_USER_ID")
    return int(admin_id) if admin_id else None


def anonymize_user_id(telegram_user_id: int) -> str:
    """Create anonymous but unique identifier."""
    data = f"{telegram_user_id}:{ANALYTICS_SALT}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


class AnalyticsDatabase:
    """SQLite database for analytics data."""

    def __init__(self, db_path: Path = ANALYTICS_DB_PATH) -> None:
        self.db_path = db_path
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

            # Users table - anonymized
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_hash TEXT PRIMARY KEY,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    interaction_count INTEGER DEFAULT 1
                )
            """)

            # Interactions table - feature usage
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_hash TEXT NOT NULL,
                    feature TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_hash) REFERENCES users(user_hash)
                )
            """)

            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_interactions_user
                ON interactions(user_hash)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_interactions_timestamp
                ON interactions(timestamp)
            """)

            conn.commit()

    def track_user(self, telegram_user_id: int, feature: str) -> None:
        """Track a user interaction."""
        if not is_analytics_enabled():
            return

        user_hash = anonymize_user_id(telegram_user_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Upsert user
            cursor.execute(
                """
                INSERT INTO users (user_hash, last_seen)
                VALUES (?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_hash) DO UPDATE SET
                    last_seen = CURRENT_TIMESTAMP,
                    interaction_count = interaction_count + 1
            """,
                (user_hash,),
            )

            # Track interaction
            cursor.execute(
                """
                INSERT INTO interactions (user_hash, feature)
                VALUES (?, ?)
            """,
                (user_hash, feature),
            )

            conn.commit()

    def get_stats(self) -> dict:
        """Get analytics statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total unique users
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]

            # Active today
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cursor.execute(
                """
                SELECT COUNT(DISTINCT user_hash) FROM interactions
                WHERE timestamp >= ?
            """,
                (today,),
            )
            active_today = cursor.fetchone()[0]

            # Active this week
            week_ago = datetime.now() - timedelta(days=7)
            cursor.execute(
                """
                SELECT COUNT(DISTINCT user_hash) FROM interactions
                WHERE timestamp >= ?
            """,
                (week_ago,),
            )
            active_this_week = cursor.fetchone()[0]

            # Feature usage
            cursor.execute("""
                SELECT feature, COUNT(*) as count
                FROM interactions
                GROUP BY feature
                ORDER BY count DESC
            """)
            feature_usage = {row[0]: row[1] for row in cursor.fetchall()}

            return {
                "total_users": total_users,
                "active_today": active_today,
                "active_this_week": active_this_week,
                "feature_usage": feature_usage,
            }

    def delete_user_data(self, telegram_user_id: int) -> bool:
        """Delete all data for a user."""
        user_hash = anonymize_user_id(telegram_user_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM interactions WHERE user_hash = ?", (user_hash,))
            cursor.execute("DELETE FROM users WHERE user_hash = ?", (user_hash,))
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted


# Global instance
_analytics_db: AnalyticsDatabase | None = None


def get_analytics_db() -> AnalyticsDatabase | None:
    """Get or create analytics database instance."""
    global _analytics_db
    if _analytics_db is None and is_analytics_enabled():
        _analytics_db = AnalyticsDatabase()
    return _analytics_db


async def track_user(telegram_user_id: int, feature: str = "general") -> None:
    """Track user interaction (async wrapper)."""
    if not is_analytics_enabled():
        return

    db = get_analytics_db()
    if db:
        db.track_user(telegram_user_id, feature)
