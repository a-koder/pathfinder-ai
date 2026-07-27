from datetime import datetime, timezone
from infrastructure.sqlite_client import SQLiteClient


class MessageRepository:
    """All SQL for the messages table."""

    def __init__(self, client: SQLiteClient):
        self._db = client

    def save_message(self, student_id: int, role: str, content: str) -> None:
        """Append one message row for the student."""
        self._db.insert(
            "INSERT INTO messages (student_id, session_number, role, content, timestamp) "
            "VALUES (?, 1, ?, ?, ?)",
            (student_id, role, content, self._now()),
        )

    def get_recent_messages(self, student_id: int, limit: int = 20) -> list[dict]:
        """Return the most recent messages in chronological order (oldest first)."""
        rows = self._db.execute(
            "SELECT role, content FROM messages "
            "WHERE student_id = ? "
            "ORDER BY message_id DESC LIMIT ?",
            (student_id, limit),
        )
        return list(reversed(rows))

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
