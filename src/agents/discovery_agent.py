import config
from services.llm_service import LLMService
from services.prompt_loader import load_prompt
from services.tracing_service import TracingService
from services.usage_tracker import UsageTracker

_PROFILE_FIELDS = [
    "grade_level",
    "gpa",
    "interests",
    "strengths",
    "career_preferences",
    "college_preferences",
    "favorite_careers",
    "location_preference",
    "budget_preference",
]

_LIST_FIELDS = {"interests", "strengths", "career_preferences", "college_preferences", "favorite_careers"}

_EMPTY_UPDATES = {
    "grade_level": "",
    "gpa": None,
    "interests": [],
    "strengths": [],
    "career_preferences": [],
    "college_preferences": [],
    "favorite_careers": [],
    "location_preference": "",
    "budget_preference": "",
}

_SAFE_QUESTION = "Tell me a bit about what subjects or activities you enjoy, or what you feel you're good at."


class DiscoveryAgent:
    """
    Extracts student interests, strengths, grade level, GPA, and preferences
    from the latest message. Asks one clarifying question at a time. Never
    invents a grade level or GPA the student did not state.

    Service dependencies: LLMService, TracingService (optional)
    """

    def __init__(
        self,
        llm_service: LLMService,
        prompt_version: str | None = None,
        tracing_service: TracingService | None = None,
    ):
        self._llm = llm_service
        self._prompt_version = prompt_version or config.DISCOVERY_PROMPT_VERSION
        self._system_prompt = load_prompt("discovery", self._prompt_version)
        self._tracing = tracing_service or TracingService()

    def extract_profile_updates(
        self,
        student_name: str,
        user_message: str,
        existing_profile: dict,
        usage: UsageTracker | None = None,
    ) -> dict:
        """Runs GPT-4o-mini over the latest message and returns a DiscoveryOutput-shaped dict."""
        user_prompt = (
            f"Existing known profile (context only - do not repeat it back, only report what "
            f"this new message adds): {existing_profile}\n\n"
            f"Student's latest message: {user_message}"
        )

        raw = self._llm.generate_json(system_prompt=self._system_prompt, user_prompt=user_prompt, usage=usage)
        result = self._validate(raw, existing_profile)
        self._tracing.trace_event(
            name="discovery",
            inputs={"student_name": student_name, "user_message": user_message},
            outputs=result,
            metadata={"confidence": result.get("confidence", 0.0)},
        )
        return result

    def _validate(self, raw: dict, existing_profile: dict) -> dict:
        if not isinstance(raw, dict):
            return self._unchanged(existing_profile)

        raw_updates = raw.get("student_profile_updates")
        if not isinstance(raw_updates, dict):
            return self._unchanged(existing_profile)

        updates = dict(_EMPTY_UPDATES)
        for field in _PROFILE_FIELDS:
            value = raw_updates.get(field)
            if field == "gpa":
                updates["gpa"] = self._parse_gpa(value)
            elif field in _LIST_FIELDS:
                updates[field] = [str(v) for v in value if v] if isinstance(value, list) else []
            else:
                updates[field] = value if isinstance(value, str) else ""

        try:
            confidence = float(raw.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        raw_missing = raw.get("missing_information")
        missing_information = (
            [m for m in raw_missing if m in _PROFILE_FIELDS] if isinstance(raw_missing, list) else []
        )

        next_question = raw.get("next_question")
        next_question = next_question.strip() if isinstance(next_question, str) and next_question.strip() else _SAFE_QUESTION

        # Contract: extraction failure or low confidence (<0.5) returns the current profile unchanged.
        if confidence < 0.5:
            return {
                "student_profile_updates": existing_profile,
                "confidence": confidence,
                "missing_information": missing_information,
                "next_question": next_question,
            }

        return {
            "student_profile_updates": updates,
            "confidence": confidence,
            "missing_information": missing_information,
            "next_question": next_question,
        }

    def _parse_gpa(self, value) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _unchanged(self, existing_profile: dict) -> dict:
        return {
            "student_profile_updates": existing_profile,
            "confidence": 0.0,
            "missing_information": list(_PROFILE_FIELDS),
            "next_question": _SAFE_QUESTION,
        }
