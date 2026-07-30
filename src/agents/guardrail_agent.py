import re

import config
from services.prompt_loader import load_ruleset
from services.tracing_service import TracingService

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def _extract_text(response_payload: dict) -> str:
    """Concatenate every user-facing text field so phrase checks can scan it in one pass."""
    parts = [str(response_payload.get("response", ""))]

    recommendations = response_payload.get("recommendations", {})
    if isinstance(recommendations, dict):
        parts.append(str(recommendations.get("summary", "")))
        parts.append(str(recommendations.get("follow_up_question", "")))
        for item in recommendations.get("recommendations", []) or []:
            if not isinstance(item, dict):
                continue
            parts.append(str(item.get("why_it_fits", "")))
            parts.append(str(item.get("why_exciting", "")))
            parts.append(str(item.get("real_world_impact", "")))
            parts.append(" ".join(item.get("opportunities", []) or []))
            parts.append(" ".join(item.get("risks_or_limitations", []) or []))
            parts.append(" ".join(item.get("next_steps", []) or []))

    path_plan = response_payload.get("path_plan", {})
    if isinstance(path_plan, dict):
        for field in (
            "short_term_steps", "medium_term_steps", "long_term_steps",
            "skills_to_build", "suggested_projects", "college_preparation_steps",
        ):
            parts.append(" ".join(path_plan.get(field, []) or []))

    return " ".join(p for p in parts if p)


def _contains_any_phrase(text: str, phrases: list[str]) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in phrases)


def _contains_protected_attribute_reasoning(
    text: str, connectors: list[str], traits: list[str], window_chars: int,
) -> bool:
    """Flags reasoning like 'because you're a woman...' - a connector followed by a protected trait."""
    if not connectors or not traits:
        return False
    lowered = text.lower()
    connector_pattern = re.compile("|".join(re.escape(c) for c in connectors), re.IGNORECASE)
    for match in connector_pattern.finditer(lowered):
        window = lowered[match.end(): match.end() + window_chars]
        if any(re.search(rf"\b{re.escape(trait)}\b", window) for trait in traits):
            return True
    return False


def _mentions_specific_colleges(response_payload: dict) -> bool:
    """True if any recommendation item is a named college/college-pathway suggestion."""
    recommendations = response_payload.get("recommendations", {})
    items = recommendations.get("recommendations", []) if isinstance(recommendations, dict) else []
    return any(
        isinstance(item, dict) and str(item.get("type", "")).strip().lower() == "college_pathway"
        for item in items
    )


def _has_profile_value(profile: dict, key: str) -> bool:
    if not profile:
        return False
    value = profile.get(key)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0
    return bool(value)


def _has_recommendations(response_payload: dict) -> bool:
    recommendations = response_payload.get("recommendations", {})
    items = recommendations.get("recommendations", []) if isinstance(recommendations, dict) else []
    return len(items) > 0


def _has_grounding_evidence(response_payload: dict) -> bool:
    recommendations = response_payload.get("recommendations", {})
    items = recommendations.get("recommendations", []) if isinstance(recommendations, dict) else []
    return any(isinstance(item, dict) and item.get("evidence") for item in items)


def _combine_risk(risk_levels: list[str]) -> str:
    if not risk_levels:
        return "low"
    return max(risk_levels, key=lambda level: _RISK_ORDER.get(level, 0))


class GuardrailAgent:
    """
    Post-generation safety check. Rule-based, no LLM call. Detects unsafe,
    overconfident, incomplete, or irresponsible recommendations before the
    final response reaches a high school student.

    Rules (phrases, keywords, risk levels, revision text) are loaded from
    src/prompts/guardrail/<version>.yaml rather than hardcoded, via PromptLoader.

    Service dependencies: TracingService (optional)
    """

    def __init__(self, ruleset_version: str | None = None, tracing_service: TracingService | None = None):
        self._ruleset_version = ruleset_version or config.GUARDRAIL_RULESET_VERSION
        ruleset = load_ruleset("guardrail", self._ruleset_version)
        self._flags = ruleset.get("flags", {})
        settings = ruleset.get("settings", {})
        self._vague_message_max_words = settings.get("vague_message_max_words", 3)
        self._sparse_profile_fields = settings.get("sparse_profile_fields", [])
        self._tracing = tracing_service or TracingService()

    def check_guardrails(self, response_payload: dict, profile: dict, user_message: str) -> dict:
        """Runs every rule-based check and returns a GuardrailResult-shaped dict."""
        text = _extract_text(response_payload)

        flags: list[str] = []
        risk_levels: list[str] = []
        required_revisions: list[str] = []

        def flag(name: str) -> None:
            rule = self._flags.get(name, {})
            flags.append(name)
            risk_levels.append(rule.get("risk", "medium"))
            required_revisions.append(rule.get("revision", ""))

        # A. Admission guarantee
        admission_rule = self._flags.get("admission_guarantee", {})
        if _contains_any_phrase(text, admission_rule.get("phrases", [])):
            flag("admission_guarantee")

        # B. Salary / outcome guarantee
        salary_rule = self._flags.get("salary_guarantee", {})
        if _contains_any_phrase(text, salary_rule.get("phrases", [])):
            flag("salary_guarantee")

        # C. Overconfidence
        overconfidence_rule = self._flags.get("overconfidence", {})
        if _contains_any_phrase(text, overconfidence_rule.get("phrases", [])):
            flag("overconfidence")

        # G. Protected attribute
        pa_rule = self._flags.get("protected_attribute_bias", {})
        if _contains_protected_attribute_reasoning(
            text, pa_rule.get("connectors", []), pa_rule.get("traits", []), pa_rule.get("window_chars", 40),
        ):
            flag("protected_attribute_bias")

        # H. Sensitive minor/student guidance - detected as pressure language
        pressure_rule = self._flags.get("pressure_language", {})
        if _contains_any_phrase(text, pressure_rule.get("phrases", [])):
            flag("pressure_language")

        # D. GPA-aware college guardrail
        gpa_rule = self._flags.get("missing_gpa_for_college_guidance", {})
        if _contains_any_phrase(text, gpa_rule.get("college_keywords", [])) and not _has_profile_value(
            profile, gpa_rule.get("profile_key", "gpa"),
        ):
            flag("missing_gpa_for_college_guidance")

        # E. Budget-aware college guardrail
        budget_rule = self._flags.get("missing_budget_for_affordability_guidance", {})
        if _contains_any_phrase(text, budget_rule.get("affordability_keywords", [])) and not _has_profile_value(
            profile, budget_rule.get("profile_key", "budget_preference"),
        ):
            flag("missing_budget_for_affordability_guidance")

        # F. Location-aware college guardrail
        location_rule = self._flags.get("missing_location_for_specific_college_guidance", {})
        if _mentions_specific_colleges(response_payload) and not _has_profile_value(
            profile, location_rule.get("profile_key", "location_preference"),
        ):
            flag("missing_location_for_specific_college_guidance")

        # I. Evidence/grounding guardrail
        if _has_recommendations(response_payload) and not _has_grounding_evidence(response_payload):
            flag("missing_grounding")

        # J. Missing profile guardrail
        if self._is_vague_message(user_message) and self._profile_is_sparse(profile):
            flag("insufficient_profile")

        risk_level = _combine_risk(risk_levels)
        result = {
            "passed": risk_level != "high",
            "flags": flags,
            "risk_level": risk_level,
            "required_revisions": required_revisions,
        }
        self._tracing.trace_event(
            name="guardrail",
            inputs={"user_message": user_message},
            outputs=result,
            metadata={"flags": flags, "risk_level": risk_level},
        )
        return result

    def _is_vague_message(self, user_message: str) -> bool:
        return len((user_message or "").split()) < self._vague_message_max_words

    def _profile_is_sparse(self, profile: dict) -> bool:
        if not profile:
            return True
        return not any(_has_profile_value(profile, field) for field in self._sparse_profile_fields)
