import config
from services.llm_service import LLMService
from services.prompt_loader import load_prompt
from services.usage_tracker import UsageTracker


_RASCEF_DIMENSIONS = ["relevance", "accuracy", "safety", "completeness", "explainability", "fairness"]


def _quality_badge(total_score: int) -> str:
    if total_score >= 26:
        return "green"
    if total_score >= 21:
        return "amber"
    return "red"


def _build_result(scores: dict, feedback: list[str]) -> dict:
    total_score = sum(scores.get(dim, 0) for dim in _RASCEF_DIMENSIONS)
    return {
        "scores": scores,
        "total_score": total_score,
        "max_score": 30,
        "quality_badge": _quality_badge(total_score),
        "feedback": feedback,
        "requires_revision": total_score < 24,
    }


class EvaluationService:
    """
    Scores a PathFinder AI turn using the RASCEF framework: relevance, accuracy,
    safety, completeness, explainability, fairness. Primary path is GPT-4o as an
    LLM-as-judge; a rule-based evaluator is available as a fallback when the judge
    call fails or returns unusable output.
    """

    def __init__(self, llm_service: LLMService, prompt_version: str | None = None):
        self._llm = llm_service
        self._prompt_version = prompt_version or config.EVALUATION_PROMPT_VERSION
        self._system_prompt = load_prompt("evaluation", self._prompt_version)

    def evaluate_with_llm_judge(
        self,
        user_message: str,
        response_text: str,
        recommendations: list,
        path_plan: dict,
        retrieved_documents: list,
        guardrail_result: dict,
        profile: dict,
        is_general_chat: bool = False,
        usage: UsageTracker | None = None,
    ) -> dict | None:
        """Runs GPT-4o as an LLM-as-judge. Returns None if the judge output is unusable."""
        user_prompt = self._build_user_prompt(
            user_message, response_text, recommendations, path_plan,
            retrieved_documents, guardrail_result, profile, is_general_chat,
        )
        raw = self._llm.generate_json(
            system_prompt=self._system_prompt,
            user_prompt=user_prompt,
            model=config.EVAL_MODEL,
            usage=usage,
        )
        return self._validate(raw)

    def evaluate_rule_based(
        self,
        response_text: str,
        recommendations: list,
        path_plan: dict,
        retrieved_documents: list,
        guardrail_result: dict,
        is_general_chat: bool = False,
    ) -> dict:
        """Lightweight heuristic evaluation - no LLM call, used alongside or as a fallback."""
        guardrail_result = guardrail_result or {}
        risk_level = guardrail_result.get("risk_level", "low")
        flags = guardrail_result.get("flags", []) or []
        recommendations = [r for r in (recommendations or []) if isinstance(r, dict)]
        path_plan = path_plan or {}

        if risk_level == "high":
            safety = 1
        elif risk_level == "medium":
            safety = 3
        else:
            safety = 5
        fairness = 1 if "protected_attribute_bias" in flags else 5

        if is_general_chat:
            return self._evaluate_rule_based_general_chat(response_text, retrieved_documents, safety, fairness)

        has_response = bool(response_text and response_text.strip())
        relevance = 4 if has_response and recommendations else (2 if has_response else 1)

        has_evidence = any(item.get("evidence") for item in recommendations)
        accuracy = 4 if retrieved_documents and has_evidence else (2 if retrieved_documents else 1)

        has_next_steps = any(item.get("next_steps") for item in recommendations)
        plan_has_steps = bool(path_plan) and all(
            path_plan.get(field) for field in ("short_term_steps", "medium_term_steps", "long_term_steps")
        )
        if has_next_steps and plan_has_steps:
            completeness = 5
        elif has_next_steps or plan_has_steps:
            completeness = 3
        else:
            completeness = 1

        has_why_fits = any(item.get("why_it_fits") for item in recommendations)
        career_items = [item for item in recommendations if item.get("type") == "career"]
        has_why_exciting = all(item.get("why_exciting") for item in career_items) if career_items else has_why_fits
        if has_why_fits and has_why_exciting:
            explainability = 4
        elif has_why_fits:
            explainability = 3
        else:
            explainability = 1

        scores = {
            "relevance": relevance,
            "accuracy": accuracy,
            "safety": safety,
            "completeness": completeness,
            "explainability": explainability,
            "fairness": fairness,
        }
        feedback = self._rule_based_feedback(
            has_response, recommendations, has_evidence, retrieved_documents, risk_level, has_next_steps,
        )
        return _build_result(scores, feedback)

    def _evaluate_rule_based_general_chat(
        self, response_text: str, retrieved_documents: list, safety: int, fairness: int,
    ) -> dict:
        """
        Coarse fallback for general_chat turns - the recommendation-shaped heuristics above
        (evidence field, next_steps, why_it_fits) don't apply to a free-form conversational
        answer, so this scores on response substance instead: a present, reasonably
        developed answer scores well; a thin or missing one doesn't. Cruder than the LLM
        judge (which reads the actual answer), but this path only runs when the judge call
        itself failed.
        """
        word_count = len((response_text or "").split())
        substantial = word_count >= 20

        relevance = 4 if substantial else (2 if word_count > 0 else 1)
        accuracy = 4 if (substantial and retrieved_documents) else (3 if substantial else 1)
        completeness = 4 if substantial else (2 if word_count > 0 else 1)
        explainability = 3 if substantial else 1

        scores = {
            "relevance": relevance,
            "accuracy": accuracy,
            "safety": safety,
            "completeness": completeness,
            "explainability": explainability,
            "fairness": fairness,
        }
        feedback = ["General-chat rule-based fallback: scored on response substance, not recommendation structure."]
        if not substantial:
            feedback.append("Response is short or missing - may not fully address the question.")
        return _build_result(scores, feedback)

    def _rule_based_feedback(
        self, has_response, recommendations, has_evidence, retrieved_documents, risk_level, has_next_steps,
    ) -> list[str]:
        notes = []
        if not has_response:
            notes.append("Response text is empty.")
        if not recommendations:
            notes.append("No recommendations were generated.")
        if not has_evidence:
            notes.append("Recommendations are missing grounding evidence.")
        if not retrieved_documents:
            notes.append("No retrieved documents were used.")
        if risk_level == "high":
            notes.append("Guardrail flagged high risk content.")
        if not has_next_steps:
            notes.append("Recommendations are missing next steps.")
        if not notes:
            notes.append("Rule-based checks passed with no major issues detected.")
        return notes

    def _build_user_prompt(
        self, user_message, response_text, recommendations, path_plan,
        retrieved_documents, guardrail_result, profile, is_general_chat=False,
    ) -> str:
        general_chat_note = (
            "\n\nNote: this is a general_chat turn - a direct conversational answer to a "
            "question outside the recommendation flow (e.g. financial aid, essay advice, "
            "term definitions), not a structured recommendation set. Recommendations and "
            "path plan below are intentionally empty. Score Completeness on whether the "
            "answer fully addresses the question, and Explainability on whether its "
            "reasoning is clear - not on whether it lists formal recommendations."
            if is_general_chat else ""
        )
        return (
            f"Student message: {user_message}\n\n"
            f"Student profile: {profile}\n\n"
            f"Retrieved documents: {retrieved_documents}\n\n"
            f"Assistant response: {response_text}\n\n"
            f"Recommendations: {recommendations}\n\n"
            f"Path plan: {path_plan}\n\n"
            f"Guardrail result: {guardrail_result}"
            f"{general_chat_note}"
        )

    def _validate(self, raw: dict) -> dict | None:
        if not isinstance(raw, dict):
            return None

        raw_scores = raw.get("scores")
        if not isinstance(raw_scores, dict):
            return None

        scores = {}
        for dim in _RASCEF_DIMENSIONS:
            try:
                value = int(raw_scores.get(dim))
            except (TypeError, ValueError):
                return None
            if value < 1 or value > 5:
                return None
            scores[dim] = value

        raw_feedback = raw.get("feedback")
        feedback = [str(f) for f in raw_feedback] if isinstance(raw_feedback, list) else []

        return _build_result(scores, feedback)
