from datetime import datetime, timezone
from infrastructure.sqlite_client import SQLiteClient


class ConversationSummaryRepository:
    """All SQL for the conversation_summaries table."""

    def __init__(self, client: SQLiteClient):
        self._db = client

    def get_summary(self, student_id: int) -> str:
        """Return the most recent summary text for the student, or '' if none exists."""
        rows = self._db.execute(
            "SELECT summary_text FROM conversation_summaries "
            "WHERE student_id = ? "
            "ORDER BY summary_id DESC LIMIT 1",
            (student_id,),
        )
        return rows[0]["summary_text"] if rows else ""

    def save_summary(self, student_id: int, summary: str) -> None:
        """Append a new summary row for the student."""
        self._db.insert(
            "INSERT INTO conversation_summaries (student_id, session_number, summary_text, created_at) "
            "VALUES (?, 1, ?, ?)",
            (student_id, summary, self._now()),
        )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
