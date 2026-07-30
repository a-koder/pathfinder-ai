import re

import config
from services.prompt_loader import load_ruleset
from services.tracing_service import TracingService


def _contains_any_phrase(text: str, phrases: list[str]) -> bool:
    """Word-boundary phrase match - avoids false positives like 'ass' inside 'assistant'."""
    lowered = text.lower()
    for phrase in phrases:
        if re.search(r"\b" + re.escape(phrase) + r"\b", lowered):
            return True
    return False


class InputGuardrailAgent:
    """
    Pre-generation safety check on the raw student message, before any other agent
    (Discovery, Retrieval, Recommendation, ...) sees it. Rule-based, no LLM call.
    Detects profanity, frustration, and prompt-injection attempts. Detection only -
    it flags, it does not block or rewrite the message.

    Rules are loaded from src/prompts/input_guardrail/<version>.yaml via PromptLoader.

    Service dependencies: TracingService (optional)
    """

    def __init__(self, ruleset_version: str | None = None, tracing_service: TracingService | None = None):
        self._ruleset_version = ruleset_version or config.INPUT_GUARDRAIL_RULESET_VERSION
        ruleset = load_ruleset("input_guardrail", self._ruleset_version)
        self._rules = ruleset.get("rules", {})
        self._tracing = tracing_service or TracingService()

    def check_input(self, user_message: str) -> dict:
        """Runs every input-side rule check and returns {"flags": [...], "passed": bool}."""
        text = user_message or ""
        flags: list[str] = []

        for flag_name in ("profanity_detected", "frustration_detected", "prompt_injection_detected"):
            phrases = self._rules.get(flag_name, {}).get("phrases", [])
            if _contains_any_phrase(text, phrases):
                flags.append(flag_name)

        result = {"flags": flags, "passed": len(flags) == 0}
        self._tracing.trace_event(
            name="input_guardrail",
            inputs={"user_message": text},
            outputs=result,
            metadata={"flags": flags},
        )
        return result
