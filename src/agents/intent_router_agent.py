import re

import config
from services.llm_service import LLMService
from services.prompt_loader import load_prompt
from services.tracing_service import TracingService
from services.usage_tracker import UsageTracker

_VALID_INTENTS = {"suggest", "explore", "roadmap", "related_topic", "general_chat"}
_ANCHORED_INTENTS = {"roadmap", "related_topic"}
_HISTORY_LIMIT = 6
_TRAILING_TYPE_SUFFIX = re.compile(r"\s*\([a-z_]+\)\s*$", re.IGNORECASE)


def _strip_type_suffix(text: str) -> str:
    """Removes a trailing "(career)"/"(college_pathway)"-style annotation the model
    sometimes echoes back into anchor_title despite the prompt's explicit instruction not
    to - `_format_last_recommendations()` displays "title (type)", and models occasionally
    copy the whole shown string rather than just the title. Defense in depth alongside the
    prompt fix (v2): a formatting slip shouldn't cost a correct classification."""
    return _TRAILING_TYPE_SUFFIX.sub("", text).strip()


def _format_history(recent_messages: list[dict]) -> str:
    if not recent_messages:
        return "(no prior conversation)"
    lines = [f"- {m.get('role', 'user')}: {m.get('content', '')}" for m in recent_messages[-_HISTORY_LIMIT:]]
    return "\n".join(lines)


def _format_last_recommendations(last_recommendations: list[dict]) -> str:
    if not last_recommendations:
        return "(none offered last turn)"
    lines = []
    for item in last_recommendations:
        if not isinstance(item, dict):
            continue
        title = item.get("title", "")
        item_type = item.get("type", "")
        if title:
            lines.append(f"- {title} ({item_type})" if item_type else f"- {title}")
    return "\n".join(lines) if lines else "(none offered last turn)"


class IntentRouterAgent:
    """
    Classifies each turn's intent - suggest (sharing interests without an explicit ask;
    a lightweight career/major-only response), explore (an explicit ask for
    recommendations - full detail), roadmap (plan for an already-offered item),
    related_topic (more career/college info tied to an already-offered item - this is
    where a settled career/major naturally leads into college suggestions), or
    general_chat (a genuine question outside the recommendation flow, e.g. FAFSA, essay
    advice, term definitions) - so the orchestrator can route to the right amount of work
    instead of forcing every message through the same "generate new recommendations"
    pipeline (decision D037 added "suggest" on top of D034's original four). Replaces the
    old literal-title-only _match_previous_choice() with something that can resolve
    implicit references ("same", "that one") using actual conversation history, which the
    old mechanism never had access to.

    Service dependencies: LLMService, TracingService (optional)
    """

    def __init__(
        self,
        llm_service: LLMService,
        prompt_version: str | None = None,
        tracing_service: TracingService | None = None,
    ):
        self._llm = llm_service
        self._prompt_version = prompt_version or config.INTENT_ROUTER_PROMPT_VERSION
        self._system_prompt = load_prompt("intent_router", self._prompt_version)
        self._tracing = tracing_service or TracingService()

    def classify_intent(
        self,
        user_message: str,
        recent_messages: list[dict],
        last_recommendations: list[dict],
        usage: UsageTracker | None = None,
    ) -> dict:
        """Returns {"intent": str, "anchor_title": str | None, "reasoning": str}."""
        user_prompt = (
            f"Recent conversation:\n{_format_history(recent_messages)}\n\n"
            f"Recommendations offered last turn:\n{_format_last_recommendations(last_recommendations)}\n\n"
            f"Student's newest message: {user_message}"
        )

        raw = self._llm.generate_json(system_prompt=self._system_prompt, user_prompt=user_prompt, usage=usage)
        result = self._validate(raw, last_recommendations, is_first_message=not recent_messages)

        self._tracing.trace_event(
            name="intent_router",
            inputs={"user_message": user_message},
            outputs=result,
            metadata={"had_last_recommendations": bool(last_recommendations)},
        )
        return result

    def _validate(self, raw: dict, last_recommendations: list[dict], is_first_message: bool) -> dict:
        """
        Never trusts the raw model output blindly: an unparseable response, an invalid
        intent, or an anchor_title that doesn't exactly match a title actually offered
        last turn all fall back to "explore" - the same full-pipeline behavior this turn
        would have gotten before this agent existed, so a bad classification degrades to
        today's behavior rather than breaking the turn or acting on a hallucinated anchor.

        "suggest" is also forced to "explore" on a genuinely first message (no prior
        conversation at all) - decision D037 narrowed this in code rather than leaving it
        to prompt instructions alone, after the prompt's own judgment turned out to be
        unreliable on this exact boundary: it broke the capstone's own scripted live demo
        line ("I like gaming, storytelling, and technology.") by routing a first message
        to a lightweight response instead of the full recommendation pipeline that demo
        depends on. A real first-time visitor typically wants to see options fairly
        quickly; "suggest" is more useful once a conversation is already warming up.
        """
        fallback = {"intent": "explore", "anchor_title": None, "reasoning": ""}
        if not isinstance(raw, dict):
            return fallback

        intent = raw.get("intent")
        if intent not in _VALID_INTENTS:
            return fallback

        if intent == "suggest" and is_first_message:
            intent = "explore"

        reasoning = raw.get("reasoning")
        reasoning = reasoning.strip() if isinstance(reasoning, str) else ""

        if intent not in _ANCHORED_INTENTS:
            return {"intent": intent, "anchor_title": None, "reasoning": reasoning}

        valid_titles = {
            item.get("title", "").strip()
            for item in (last_recommendations or [])
            if isinstance(item, dict) and item.get("title")
        }
        anchor_title = raw.get("anchor_title")
        anchor_title = anchor_title.strip() if isinstance(anchor_title, str) else ""

        if anchor_title and anchor_title not in valid_titles:
            stripped = _strip_type_suffix(anchor_title)
            if stripped in valid_titles:
                anchor_title = stripped

        if not valid_titles or anchor_title not in valid_titles:
            return fallback

        return {"intent": intent, "anchor_title": anchor_title, "reasoning": reasoning}
