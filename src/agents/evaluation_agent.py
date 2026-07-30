import config
from services.evaluation_service import EvaluationService
from services.tracing_service import TracingService
from services.usage_tracker import UsageTracker

_NOT_EVALUATED_RESULT = {
    "scores": {
        "relevance": 0,
        "accuracy": 0,
        "safety": 0,
        "completeness": 0,
        "explainability": 0,
        "fairness": 0,
    },
    "total_score": 0,
    "max_score": 30,
    "quality_badge": "not_evaluated",
    "feedback": ["Evaluation could not be completed."],
    "requires_revision": False,
}


class EvaluationAgent:
    """
    Scores every response using the RASCEF framework (relevance, accuracy, safety,
    completeness, explainability, fairness), each 1-5, max 30. Pass threshold is
    24/30. Primary path is GPT-4o as an LLM-as-judge, with a rule-based fallback
    if the judge call fails, so a response is never left unevaluated.

    Service dependencies: EvaluationService, TracingService (optional)
    """

    def __init__(self, evaluation_service: EvaluationService, tracing_service: TracingService | None = None):
        self._evaluation_service = evaluation_service
        self._tracing = tracing_service or TracingService()

    def evaluate(
        self,
        user_message: str,
        response_payload: dict,
        retrieved_context: dict,
        profile: dict,
        guardrail_result: dict,
        input_guardrail_flags: list | None = None,
        revision_attempted: bool = False,
        usage: UsageTracker | None = None,
    ) -> dict:
        response_text = response_payload.get("response", "")
        recommendations_payload = response_payload.get("recommendations", {})
        recommendation_items = (
            recommendations_payload.get("recommendations", [])
            if isinstance(recommendations_payload, dict) else []
        )
        path_plan = response_payload.get("path_plan", {}) or {}
        retrieved_documents = (retrieved_context or {}).get("retrieved_documents", [])
        guardrail_result = guardrail_result or {}
        profile = profile or {}

        result = self._evaluate_with_fallback(
            user_message, response_text, recommendation_items, path_plan,
            retrieved_documents, guardrail_result, profile, usage,
        )

        self._trace(
            user_message, response_text, guardrail_result, result,
            input_guardrail_flags=input_guardrail_flags or [],
            revision_attempted=revision_attempted,
        )
        return result

    def _evaluate_with_fallback(
        self, user_message, response_text, recommendation_items, path_plan,
        retrieved_documents, guardrail_result, profile, usage=None,
    ) -> dict:
        try:
            judged = self._evaluation_service.evaluate_with_llm_judge(
                user_message=user_message,
                response_text=response_text,
                recommendations=recommendation_items,
                path_plan=path_plan,
                retrieved_documents=retrieved_documents,
                guardrail_result=guardrail_result,
                profile=profile,
                usage=usage,
            )
            if judged is not None:
                return judged
        except Exception:
            pass

        try:
            fallback = self._evaluation_service.evaluate_rule_based(
                response_text=response_text,
                recommendations=recommendation_items,
                path_plan=path_plan,
                retrieved_documents=retrieved_documents,
                guardrail_result=guardrail_result,
            )
            # Rule-based-only results never get the top badge - the LLM judge didn't confirm it.
            if fallback["quality_badge"] == "green":
                fallback["quality_badge"] = "amber"
            fallback["feedback"] = fallback["feedback"] + [
                "LLM judge unavailable - showing rule-based evaluation only."
            ]
            return fallback
        except Exception:
            return dict(_NOT_EVALUATED_RESULT)

    def _trace(
        self,
        user_message: str,
        response_text: str,
        guardrail_result: dict,
        result: dict,
        input_guardrail_flags: list,
        revision_attempted: bool,
    ) -> None:
        if not self._tracing.is_enabled():
            return
        try:
            self._tracing.trace_event(
                name="evaluation",
                inputs={
                    "user_message": user_message,
                    "response_text": response_text,
                    "guardrail_flags": guardrail_result.get("flags", []),
                    "input_guardrail_flags": input_guardrail_flags,
                },
                outputs={
                    "scores": result.get("scores", {}),
                    "total_score": result.get("total_score", 0),
                    "quality_badge": result.get("quality_badge", "not_evaluated"),
                    "requires_revision": result.get("requires_revision", False),
                },
                metadata={
                    "model": config.EVAL_MODEL,
                    "quality_badge": result.get("quality_badge", "not_evaluated"),
                    "evaluation_score": result.get("total_score", 0),
                    "guardrail_flags": guardrail_result.get("flags", []),
                    "guardrail_risk_level": guardrail_result.get("risk_level", "low"),
                    "input_guardrail_flags": input_guardrail_flags,
                    "revision_attempted": revision_attempted,
                },
            )
        except Exception:
            pass
