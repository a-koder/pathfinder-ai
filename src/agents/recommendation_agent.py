import config
from services.llm_service import LLMService
from services.prompt_service import PromptService
from services.prompt_loader import load_prompt

_RECOMMENDATION_FIELDS = [
    "type",
    "why_it_fits",
    "why_exciting",
    "opportunities",
    "real_world_impact",
    "related_majors",
    "skills_to_build",
    "adjacent_paths",
    "evidence",
    "risks_or_limitations",
    "next_steps",
]

_LIST_FIELDS = {
    "opportunities",
    "related_majors",
    "skills_to_build",
    "adjacent_paths",
    "evidence",
    "risks_or_limitations",
    "next_steps",
}


class RecommendationAgent:
    """
    Generates a structured, grounded recommendation response using the student
    profile, retrieved career / major / college context, and conversation history.

    Service dependencies: LLMService, PromptService
    """

    def __init__(self, llm_service: LLMService, prompt_service: PromptService, prompt_version: str | None = None):
        self._llm = llm_service
        self._prompts = prompt_service
        self._prompt_version = prompt_version or config.RECOMMENDATION_PROMPT_VERSION
        self._system_prompt = load_prompt("recommendation", self._prompt_version)

    def generate_recommendations(
        self,
        user_message: str,
        profile: dict,
        retrieved_context: dict,
    ) -> dict:
        """Runs GPT-4o-mini over the retrieved context and returns a RecommendationOutput-shaped dict."""
        retrieved_documents = retrieved_context.get("retrieved_documents", [])

        context_block = self._prompts.build(profile=profile, retrieved_docs=retrieved_documents, history=[])
        user_prompt = (
            f"Student message: {user_message}\n\n"
            f"{context_block}\n\n"
            "Generate 3 to 5 grounded recommendations following the system instructions."
        )

        raw = self._llm.generate_json(system_prompt=self._system_prompt, user_prompt=user_prompt)
        parsed = self._validate(raw)
        if parsed is not None:
            return parsed

        return self._fallback(profile, retrieved_documents)

    def _validate(self, raw: dict) -> dict | None:
        if not isinstance(raw, dict):
            return None

        raw_recommendations = raw.get("recommendations")
        if not isinstance(raw_recommendations, list):
            return None

        cleaned = []
        for item in raw_recommendations:
            if not isinstance(item, dict) or not item.get("title"):
                continue
            entry = {"title": str(item["title"])}
            for field in _RECOMMENDATION_FIELDS:
                value = item.get(field)
                if field in _LIST_FIELDS:
                    entry[field] = list(value) if isinstance(value, list) else []
                else:
                    entry[field] = value if isinstance(value, str) else ""
            try:
                entry["confidence"] = float(item.get("confidence", 0.0))
            except (TypeError, ValueError):
                entry["confidence"] = 0.0
            cleaned.append(entry)

        if not cleaned:
            return None

        return {
            "recommendations": cleaned,
            "summary": raw.get("summary") if isinstance(raw.get("summary"), str) else "",
            "follow_up_question": (
                raw.get("follow_up_question") if isinstance(raw.get("follow_up_question"), str) else ""
            ),
        }

    def _fallback(self, profile: dict, retrieved_documents: list[dict]) -> dict:
        """Safe fallback used when the model does not return usable JSON."""
        titles = [doc.get("title", "") for doc in retrieved_documents if doc.get("title")]

        if titles:
            summary = (
                "I found some relevant paths, but I could not structure the recommendations cleanly. "
                f"Based on the retrieved context, we can explore these options next: {', '.join(titles)}."
            )
        else:
            summary = (
                "I could not find enough grounded information to build recommendations yet. "
                "Tell me a bit more about what you enjoy or are good at."
            )

        return {
            "recommendations": [],
            "summary": summary,
            "follow_up_question": (
                "Which of these directions sounds most interesting to you, "
                "or is there something else you'd like to explore?"
            ),
        }
