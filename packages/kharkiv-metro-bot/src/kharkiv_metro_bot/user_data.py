"""User data module for language, reminders, and usage tracking."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from kharkiv_metro_core import DEFAULT_LANGUAGE, Config, Language

# Config instance
_config = Config()

# Feature flag
_env_enabled = os.getenv("ENABLE_USER_DATA")
USER_DATA_ENABLED = _env_enabled.lower() == "true" if _env_enabled is not None else _config.is_user_data_enabled()

# Database path
USER_DATA_DB_PATH = Path(_config.get_user_data_db_path())

USER_DATA_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def is_user_data_enabled() -> bool:
    """Check if user data storage is enabled."""
    return USER_DATA_ENABLED


def get_admin_id() -> int | None:
    """Get admin user ID from environment."""
    admin_id = os.getenv("ADMIN_USER_ID")
    return int(admin_id) if admin_id else None


class UserDataDatabase:
    """SQLite database for user data, usage, and reminders."""

    def __init__(self, db_path: Path = USER_DATA_DB_PATH) -> None:
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

            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    interaction_count INTEGER DEFAULT 1,
                    language TEXT DEFAULT 'ua'
                )
            """)

            # Migration: add language column if it doesn't exist
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            if "language" not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ua'")

            # Interactions table - feature usage
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    feature TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            # Reminders table - active reminders per user
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    route_key TEXT,
                    station_id TEXT,
                    remind_at TIMESTAMP NOT NULL,
                    lang TEXT DEFAULT 'ua',
                    active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_interactions_user
                ON interactions(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_interactions_timestamp
                ON interactions(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reminders_user_active
                ON reminders(user_id, active)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_reminders_time
                ON reminders(remind_at)
            """)

            conn.commit()

    def track_user(self, telegram_user_id: int, feature: str) -> None:
        """Track a user interaction."""
        if not is_user_data_enabled():
            return

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Upsert user
            cursor.execute(
                """
                INSERT INTO users (user_id, last_seen)
                VALUES (?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    last_seen = CURRENT_TIMESTAMP,
                    interaction_count = interaction_count + 1
            """,
                (telegram_user_id,),
            )

            # Track interaction
            cursor.execute(
                """
                INSERT INTO interactions (user_id, feature)
                VALUES (?, ?)
            """,
                (telegram_user_id, feature),
            )

            conn.commit()

    def get_user_language(self, telegram_user_id: int) -> Language:
        """Get user language preference."""

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT language FROM users WHERE user_id = ?", (telegram_user_id,))
            row = cursor.fetchone()
            if row and row["language"]:
                return row["language"]
            return DEFAULT_LANGUAGE

    def set_user_language(self, telegram_user_id: int, language: Language) -> None:
        """Set user language preference."""

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (user_id, language)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    language = excluded.language
            """,
                (telegram_user_id, language),
            )
            conn.commit()

    def save_reminder(
        self,
        telegram_user_id: int,
        route_key: str,
        station_id: str,
        remind_at: datetime,
        lang: Language,
    ) -> int:
        """Save active reminder for a user."""

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO users (user_id, last_seen, language)
                VALUES (?, CURRENT_TIMESTAMP, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    last_seen = CURRENT_TIMESTAMP,
                    language = excluded.language
            """,
                (telegram_user_id, lang),
            )

            cursor.execute(
                """
                INSERT INTO reminders (user_id, route_key, station_id, remind_at, lang, active)
                VALUES (?, ?, ?, ?, ?, 1)
            """,
                (telegram_user_id, route_key, station_id, remind_at.isoformat(), lang),
            )

            conn.commit()
            return cursor.lastrowid

    def get_active_reminders(self, telegram_user_id: int) -> list[dict]:
        """Get active reminders for a user."""

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM reminders
                WHERE user_id = ? AND active = 1
                ORDER BY remind_at
            """,
                (telegram_user_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_active_reminders(self) -> list[dict]:
        """Get all active reminders."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM reminders
                WHERE active = 1
                ORDER BY remind_at
            """
            )
            return [dict(row) for row in cursor.fetchall()]

    def deactivate_reminder(self, reminder_id: int) -> None:
        """Deactivate a reminder by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE reminders
                SET active = 0
                WHERE id = ?
            """,
                (reminder_id,),
            )
            conn.commit()

    def clear_user_reminders(self, telegram_user_id: int) -> None:
        """Deactivate all active reminders for a user."""

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE reminders
                SET active = 0
                WHERE user_id = ? AND active = 1
            """,
                (telegram_user_id,),
            )
            conn.commit()

    def get_stats(self) -> dict:
        """Get analytics statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]

            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cursor.execute(
                """
                SELECT COUNT(DISTINCT user_id) FROM interactions
                WHERE timestamp >= ?
            """,
                (today,),
            )
            active_today = cursor.fetchone()[0]

            week_ago = datetime.now() - timedelta(days=7)
            cursor.execute(
                """
                SELECT COUNT(DISTINCT user_id) FROM interactions
                WHERE timestamp >= ?
            """,
                (week_ago,),
            )
            active_this_week = cursor.fetchone()[0]

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

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM interactions WHERE user_id = ?", (telegram_user_id,))
            cursor.execute("DELETE FROM reminders WHERE user_id = ?", (telegram_user_id,))
            cursor.execute("DELETE FROM users WHERE user_id = ?", (telegram_user_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted


# Global instance
_user_data_db: UserDataDatabase | None = None


def get_user_data_db() -> UserDataDatabase | None:
    """Get or create user data database instance."""
    global _user_data_db
    if _user_data_db is None:
        _user_data_db = UserDataDatabase()
    return _user_data_db


async def track_user(telegram_user_id: int, feature: str = "general") -> None:
    """Track user interaction (async wrapper)."""
    if not is_user_data_enabled():
        return

    db = get_user_data_db()
    if db:
        db.track_user(telegram_user_id, feature)


def get_user_language(telegram_user_id: int) -> Language:
    """Get user language preference (helper function)."""
    db = get_user_data_db()
    if db:
        return db.get_user_language(telegram_user_id)
    return DEFAULT_LANGUAGE


def set_user_language(telegram_user_id: int, language: Language) -> None:
    """Set user language preference (helper function)."""
    db = get_user_data_db()
    if db:
        db.set_user_language(telegram_user_id, language)


def save_user_reminder(
    telegram_user_id: int,
    route_key: str,
    station_id: str,
    remind_at: datetime,
    lang: Language,
) -> int | None:
    """Save active reminder for a user (helper function)."""
    db = get_user_data_db()
    if db:
        return db.save_reminder(telegram_user_id, route_key, station_id, remind_at, lang)
    return None


def get_active_user_reminders(telegram_user_id: int) -> list[dict]:
    """Get active reminders for a user (helper function)."""
    db = get_user_data_db()
    if db:
        return db.get_active_reminders(telegram_user_id)
    return []


def get_all_active_reminders() -> list[dict]:
    """Get all active reminders (helper function)."""
    db = get_user_data_db()
    if db:
        return db.get_all_active_reminders()
    return []


def deactivate_user_reminder(reminder_id: int) -> None:
    """Deactivate a reminder by ID (helper function)."""
    db = get_user_data_db()
    if db:
        db.deactivate_reminder(reminder_id)


def clear_user_reminders(telegram_user_id: int) -> None:
    """Deactivate all active reminders for a user (helper function)."""
    db = get_user_data_db()
    if db:
        db.clear_user_reminders(telegram_user_id)
