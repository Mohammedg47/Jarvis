"""SQLite store for conversation history and user preferences."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class MemoryStore:
    def __init__(self, path: Path) -> None:
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.executescript(SCHEMA)

    def add_message(self, role: str, content: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO messages (role, content, created_at) VALUES (?, ?, ?)",
                (role, content, _now()),
            )

    def recent_messages(self, limit: int) -> list[dict]:
        """The last `limit` messages, oldest first, in the format the LLM expects."""
        rows = self._db.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{"role": role, "content": content} for role, content in reversed(rows)]

    def set_preference(self, key: str, value: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO preferences (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "updated_at = excluded.updated_at",
                (key.strip().lower(), value.strip(), _now()),
            )

    def preferences(self) -> dict[str, str]:
        rows = self._db.execute("SELECT key, value FROM preferences ORDER BY key").fetchall()
        return dict(rows)

    def forget_all(self) -> None:
        with self._db:
            self._db.execute("DELETE FROM messages")
            self._db.execute("DELETE FROM preferences")

    def close(self) -> None:
        self._db.close()
