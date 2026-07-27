from datetime import datetime, timezone
from infrastructure.sqlite_client import SQLiteClient


class StudentRepository:
    """All SQL for the students table."""

    def __init__(self, client: SQLiteClient):
        self._db = client

    def create_or_get_student(self, name: str) -> int:
        """Return the student_id for name, creating the row if it does not exist."""
        rows = self._db.execute(
            "SELECT student_id FROM students WHERE LOWER(name) = LOWER(?)",
            (name,),
        )
        if rows:
            return rows[0]["student_id"]
        return self._db.insert(
            "INSERT INTO students (name, created_at, last_seen_at, session_count) VALUES (?, ?, ?, ?)",
            (name, self._now(), self._now(), 1),
        )

    def get_student(self, student_id: int) -> dict:
        """Return the full student row as a dict, or {} if not found."""
        rows = self._db.execute(
            "SELECT student_id, name, created_at, last_seen_at, session_count "
            "FROM students WHERE student_id = ?",
            (student_id,),
        )
        return rows[0] if rows else {}

    def update_last_seen(self, student_id: int) -> None:
        """Stamp last_seen_at with the current UTC time."""
        self._db.execute(
            "UPDATE students SET last_seen_at = ? WHERE student_id = ?",
            (self._now(), student_id),
        )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
