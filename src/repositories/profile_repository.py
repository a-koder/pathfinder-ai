import json
from datetime import datetime, timezone
from infrastructure.sqlite_client import SQLiteClient


class ProfileRepository:
    """All SQL for the profiles table."""

    def __init__(self, client: SQLiteClient):
        self._db = client

    def get_profile(self, student_id: int) -> dict:
        """Return the student's profile as a dict, or {} if no profile exists yet."""
        rows = self._db.execute(
            "SELECT profile_json FROM profiles WHERE student_id = ?",
            (student_id,),
        )
        if not rows:
            return {}
        return json.loads(rows[0]["profile_json"])

    def upsert_profile(self, student_id: int, profile: dict) -> None:
        """Insert or replace the student's profile JSON."""
        self._db.execute(
            """
            INSERT INTO profiles (student_id, profile_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                profile_json = excluded.profile_json,
                updated_at   = excluded.updated_at
            """,
            (student_id, json.dumps(profile, ensure_ascii=False), self._now()),
        )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
