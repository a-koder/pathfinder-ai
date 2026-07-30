import config
from services.llm_service import LLMService
from services.prompt_loader import load_prompt
from services.tracing_service import TracingService
from services.usage_tracker import UsageTracker

_LIST_FIELDS = [
    "short_term_steps",
    "medium_term_steps",
    "long_term_steps",
    "skills_to_build",
    "suggested_projects",
    "college_preparation_steps",
]

_REQUIRED_LIST_FIELDS = ["short_term_steps", "medium_term_steps", "long_term_steps"]

# Priority: career > major > college_pathway. Matched as "career", then "major", then
# whatever's left - the recommendation prompt asks the model for "college_pathway" but
# GPT-4o-mini sometimes drifts to a plain "college" (or other variants), so rather than
# match "college_pathway" literally, everything that isn't career/major falls into the
# same lowest tier. In practice that remaining tier is always college-type items.
_TYPE_SELECTION_PRIORITY = ["career", "major"]


def _select_recommendation(items: list[dict]) -> dict:
    """
    Picks which recommendation to build a roadmap for: the highest-ranked career if one
    exists, else the highest-ranked major, else the highest-ranked remaining item (in
    practice, a college_pathway). A career/major roadmap ("what should I do next?") is
    more actionable for a student than one anchored to a single named college.
    """
    for target_type in _TYPE_SELECTION_PRIORITY:
        for item in items:
            if isinstance(item, dict) and str(item.get("type", "")).strip().lower() == target_type:
                return item
    return items[0] if items else {}


class PathPlanningAgent:
    """
    Builds a personalized multi-horizon roadmap - short-term (3-6 months),
    medium-term (1-3 years), and long-term (college prep and career direction) -
    anchored to the student's profile and whichever recommendation they actually chose.
    When the student's message names one of last turn's offered recommendations, the
    orchestrator passes it in as `selected_override` and that wins; otherwise this falls
    back to the highest-ranked career (or major, or college_pathway, in that priority
    order) among their recommendations.

    Service dependencies: LLMService, TracingService (optional)
    """

    def __init__(
        self,
        llm_service: LLMService,
        prompt_version: str | None = None,
        tracing_service: TracingService | None = None,
    ):
        self._llm = llm_service
        self._prompt_version = prompt_version or config.PATH_PLANNING_PROMPT_VERSION
        self._system_prompt = load_prompt("path_planning", self._prompt_version)
        self._tracing = tracing_service or TracingService()

    def generate_path_plan(
        self,
        profile: dict,
        recommendations: dict,
        selected_override: dict | None = None,
        usage: UsageTracker | None = None,
    ) -> dict:
        """
        Runs GPT-4o-mini to build a phased roadmap for the selected recommendation.

        `selected_override`, when given, is used in place of the career > major >
        college_pathway priority pick - the orchestrator passes this in when the
        student's message names one of last turn's offered recommendations, so the
        roadmap is anchored to what the student actually chose rather than a guess.
        """
        items = recommendations.get("recommendations", []) if isinstance(recommendations, dict) else []
        selected = selected_override if selected_override else _select_recommendation(items)
        selected_title = selected.get("title", "") if isinstance(selected, dict) else ""
        source = "student_choice" if selected_override else "auto_priority"

        if not selected:
            result = self._fallback(selected_title, source)
        else:
            user_prompt = self._build_user_prompt(profile, selected)
            raw = self._llm.generate_json(system_prompt=self._system_prompt, user_prompt=user_prompt, usage=usage)
            parsed = self._validate(raw, selected_title, source)
            result = parsed if parsed is not None else self._fallback(selected_title, source)

        self._tracing.trace_event(
            name="path_planning",
            inputs={"selected_title": selected_title, "source": source},
            outputs={"selected_path": result.get("selected_path", "")},
            metadata={"source": source},
        )
        return result

    def _build_user_prompt(self, profile: dict, selected: dict) -> str:
        lines = [f"Selected path: {selected.get('title', '')} ({selected.get('type', 'career')})"]

        if selected.get("why_it_fits"):
            lines.append(f"Why it fits this student: {selected['why_it_fits']}")
        if selected.get("related_majors"):
            lines.append(f"Related majors: {', '.join(selected['related_majors'])}")
        if selected.get("skills_to_build"):
            lines.append(f"Skills already identified: {', '.join(selected['skills_to_build'])}")
        if selected.get("adjacent_paths"):
            lines.append(f"Adjacent paths: {', '.join(selected['adjacent_paths'])}")

        lines.append("\nStudent profile:")
        if profile.get("grade_level"):
            lines.append(f"- Grade level: {profile['grade_level']}")
        if profile.get("gpa") not in (None, ""):
            lines.append(f"- GPA: {profile['gpa']}")
        if profile.get("interests"):
            lines.append(f"- Interests: {', '.join(profile['interests'])}")
        if profile.get("strengths"):
            lines.append(f"- Strengths: {', '.join(profile['strengths'])}")

        return "\n".join(lines)

    def _validate(self, raw: dict, fallback_title: str, source: str) -> dict | None:
        if not isinstance(raw, dict):
            return None

        selected_path = raw.get("selected_path")
        selected_path = selected_path.strip() if isinstance(selected_path, str) and selected_path.strip() else fallback_title

        result = {"selected_path": selected_path, "source": source}
        for field in _LIST_FIELDS:
            value = raw.get(field)
            result[field] = [str(v) for v in value if v] if isinstance(value, list) else []

        if any(not result[field] for field in _REQUIRED_LIST_FIELDS):
            return None

        return result

    def _fallback(self, selected_title: str, source: str) -> dict:
        """Safe generic roadmap used when the model output is unusable or nothing was selected."""
        return {
            "selected_path": selected_title or "your chosen path",
            "source": source,
            "short_term_steps": [
                "Talk with a school counselor about courses and activities that align with this interest.",
            ],
            "medium_term_steps": [
                "Look for related clubs, electives, or volunteer opportunities over the next year or two.",
            ],
            "long_term_steps": [
                "Research colleges or programs that support this direction as application season approaches.",
            ],
            "skills_to_build": [],
            "suggested_projects": [],
            "college_preparation_steps": [],
        }
