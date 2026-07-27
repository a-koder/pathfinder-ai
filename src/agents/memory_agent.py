from repositories.student_repository import StudentRepository
from repositories.profile_repository import ProfileRepository
from repositories.message_repository import MessageRepository
from repositories.conversation_summary_repository import ConversationSummaryRepository


class MemoryAgent:
    """Loads and saves student memory across turns."""

    def __init__(
        self,
        student_repo: StudentRepository,
        profile_repo: ProfileRepository,
        message_repo: MessageRepository,
        summary_repo: ConversationSummaryRepository,
    ):
        self._students = student_repo
        self._profiles = profile_repo
        self._messages = message_repo
        self._summaries = summary_repo

    def load_memory(self, student_name: str) -> dict:
        """
        Return persisted state for the student.
        Falls back to empty state if SQLite is unavailable.
        """
        try:
            student_id = self._students.create_or_get_student(student_name)
            self._students.update_last_seen(student_id)
            student = self._students.get_student(student_id)
            profile = self._profiles.get_profile(student_id)
            profile["conversation_summary"] = self._summaries.get_summary(student_id)
            recent_messages = self._messages.get_recent_messages(student_id, limit=20)
            return {
                "student_id": student_id,
                "profile": profile,
                "recent_messages": recent_messages,
                "session_number": student.get("session_count", 1),
            }
        except Exception:
            return {
                "student_id": 0,
                "profile": {"conversation_summary": ""},
                "recent_messages": [],
                "session_number": 1,
            }

    def save_turn(
        self,
        student_name: str,
        user_message: str,
        assistant_response: str,
        metadata: dict,
    ) -> None:
        """Persist both sides of one conversation turn."""
        try:
            student_id = self._students.create_or_get_student(student_name)
            self._messages.save_message(student_id, "user", user_message)
            self._messages.save_message(student_id, "assistant", assistant_response)
        except Exception:
            pass

    def update_profile(self, student_name: str, profile_updates: dict) -> dict:
        """
        Merge new profile fields into the student's persisted profile and save it.
        List fields are merged without duplicates; scalar fields are only overwritten
        when the new value is present. Falls back to a best-effort merged profile
        (without persisting) if SQLite is unavailable.
        """
        student_id = None
        existing: dict = {}
        try:
            student_id = self._students.create_or_get_student(student_name)
            existing = self._profiles.get_profile(student_id)
        except Exception:
            pass

        merged = self._merge(existing, profile_updates)
        merged["name"] = student_name

        if student_id is not None:
            try:
                self._profiles.upsert_profile(student_id, merged)
            except Exception:
                pass

        return merged

    def _merge(self, existing: dict, updates: dict) -> dict:
        merged = dict(existing)
        for key, value in updates.items():
            if isinstance(value, list):
                current = merged.get(key, [])
                if not isinstance(current, list):
                    current = []
                seen = {str(item).strip().lower() for item in current}
                for item in value:
                    normalized = str(item).strip().lower() if item is not None else ""
                    if item and normalized not in seen:
                        current.append(item)
                        seen.add(normalized)
                merged[key] = current
            elif value not in (None, ""):
                merged[key] = value
        return merged
