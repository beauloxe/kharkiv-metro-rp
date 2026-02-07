"""SQLite-backed FSM storage for bot state persistence."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey


class SqliteStorage(BaseStorage):
    """SQLite-based storage for FSM state and data."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @classmethod
    def from_user_data_db(cls) -> SqliteStorage:
        """Create storage using user data database path."""
        from .user_data import USER_DATA_DB_PATH

        return cls(USER_DATA_DB_PATH)

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS fsm_state (
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    destiny TEXT NOT NULL,
                    state TEXT,
                    data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (chat_id, user_id, destiny)
                )
                """
            )
            conn.commit()

    def cleanup_stale_states(self, max_age: timedelta) -> int:
        """Remove stale FSM states older than max_age."""
        cutoff = datetime.utcnow() - max_age
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM fsm_state
                WHERE updated_at < ?
                """,
                (cutoff.isoformat(),),
            )
            conn.commit()
            return cursor.rowcount

    @staticmethod
    def _state_to_str(state: State | str | None) -> str | None:
        if state is None:
            return None
        if isinstance(state, State):
            return state.state
        if isinstance(state, str):
            return state
        return str(state)

    async def set_state(self, key: StorageKey, state: State | str | None = None) -> None:
        state_value = self._state_to_str(state)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO fsm_state (chat_id, user_id, destiny, state, data, updated_at)
                VALUES (?, ?, ?, ?, COALESCE((SELECT data FROM fsm_state
                    WHERE chat_id = ? AND user_id = ? AND destiny = ?), '{}'), ?)
                ON CONFLICT (chat_id, user_id, destiny)
                DO UPDATE SET state = excluded.state, updated_at = excluded.updated_at
                """,
                (
                    key.chat_id,
                    key.user_id,
                    key.destiny,
                    state_value,
                    key.chat_id,
                    key.user_id,
                    key.destiny,
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()

    async def get_state(self, key: StorageKey) -> str | None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT state FROM fsm_state
                WHERE chat_id = ? AND user_id = ? AND destiny = ?
                """,
                (key.chat_id, key.user_id, key.destiny),
            )
            row = cursor.fetchone()
            return row["state"] if row else None

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        payload = json.dumps(data or {})
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO fsm_state (chat_id, user_id, destiny, state, data, updated_at)
                VALUES (?, ?, ?, COALESCE((SELECT state FROM fsm_state
                    WHERE chat_id = ? AND user_id = ? AND destiny = ?), NULL), ?, ?)
                ON CONFLICT (chat_id, user_id, destiny)
                DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
                """,
                (
                    key.chat_id,
                    key.user_id,
                    key.destiny,
                    key.chat_id,
                    key.user_id,
                    key.destiny,
                    payload,
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT data FROM fsm_state
                WHERE chat_id = ? AND user_id = ? AND destiny = ?
                """,
                (key.chat_id, key.user_id, key.destiny),
            )
            row = cursor.fetchone()
            if not row or row["data"] is None:
                return {}
            try:
                return json.loads(row["data"]) or {}
            except json.JSONDecodeError:
                return {}

    async def update_data(self, key: StorageKey, data: dict[str, Any]) -> dict[str, Any]:
        stored = await self.get_data(key)
        stored.update(data)
        await self.set_data(key, stored)
        return stored

    async def clear(self, key: StorageKey) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM fsm_state
                WHERE chat_id = ? AND user_id = ? AND destiny = ?
                """,
                (key.chat_id, key.user_id, key.destiny),
            )
            conn.commit()

    async def close(self) -> None:
        return None

    async def wait_closed(self) -> None:
        return None

    async def get_value(self, key: StorageKey) -> str | None:
        return await self.get_state(key)

    async def set_value(self, key: StorageKey, value: str | State | None) -> None:
        await self.set_state(key, value)
