"""SQLite store for conversation history and user preferences."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    used_tools INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT NOT NULL,
    due_at TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class MemoryStore:
    def __init__(self, path: Path) -> None:
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)  # reminders fire from a thread
        self._db.executescript(SCHEMA)
        columns = [row[1] for row in self._db.execute("PRAGMA table_info(messages)")]
        if "used_tools" not in columns:  # database created before this column existed
            with self._db:
                self._db.execute(
                    "ALTER TABLE messages ADD COLUMN used_tools INTEGER NOT NULL DEFAULT 0"
                )

    def add_message(self, role: str, content: str, used_tools: bool = False) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO messages (role, content, created_at, used_tools) VALUES (?, ?, ?, ?)",
                (role, content, _now(), int(used_tools)),
            )

    def recent_messages(self, limit: int) -> list[dict]:
        """The last `limit` messages, oldest first, in the format the LLM expects.

        Turns where tools ran are skipped: their tool steps are not saved, so replaying
        "Notepad opened." with no tool call teaches the model to claim actions without acting.
        """
        rows = self._db.execute(
            "SELECT role, content FROM messages WHERE used_tools = 0 ORDER BY id DESC LIMIT ?",
            (limit,),
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

    def add_reminder(self, message: str, due_at: datetime) -> int:
        """Save a reminder due at an aware datetime and return its id."""
        with self._db:
            cursor = self._db.execute(
                "INSERT INTO reminders (message, due_at) VALUES (?, ?)",
                (message, due_at.astimezone(UTC).isoformat(timespec="seconds")),
            )
        return cursor.lastrowid

    def pending_reminders(self) -> list[tuple[int, str, datetime]]:
        """Reminders that have not fired yet, soonest first, as (id, message, due_at)."""
        rows = self._db.execute(
            "SELECT id, message, due_at FROM reminders WHERE done = 0 ORDER BY due_at"
        ).fetchall()
        return [(i, m, datetime.fromisoformat(d)) for i, m, d in rows]

    def finish_reminder(self, reminder_id: int) -> None:
        with self._db:
            self._db.execute("UPDATE reminders SET done = 1 WHERE id = ?", (reminder_id,))

    def forget_all(self) -> None:
        with self._db:
            self._db.execute("DELETE FROM messages")
            self._db.execute("DELETE FROM preferences")

    def close(self) -> None:
        self._db.close()
