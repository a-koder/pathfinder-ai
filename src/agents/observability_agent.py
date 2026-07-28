import datetime

import config
from repositories.observability_repository import ObservabilityRepository


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class ObservabilityAgent:
    """
    Logs per-turn metrics to SQLite via ObservabilityRepository. Captures latency,
    model, guardrail flags/risk, evaluation score/badge, and real token usage/cost
    (decision D029 - the orchestrator's UsageTracker sums usage across every LLM/
    embedding call made this turn, across every model, before calling log_turn()).
    Never raises - a logging failure must never break the student's response.

    Service dependencies: ObservabilityRepository
    """

    def __init__(self, observability_repository: ObservabilityRepository):
        self._repo = observability_repository

    def log_turn(self, event: dict) -> int | None:
        """Writes one ObservabilityLog entry to SQLite. Returns the new log_id, or None on failure."""
        log_entry = {
            "timestamp": event.get("timestamp") or _utc_now_iso(),
            "student_id": event.get("student_id"),
            "student_name": event.get("student_name", ""),
            "user_message": event.get("user_message", ""),
            "agent": "Orchestrator",
            "model": event.get("model") or config.DEFAULT_MODEL,
            "evaluation_model": event.get("evaluation_model") or config.EVAL_MODEL,
            "embedding_model": event.get("embedding_model") or config.EMBEDDING_MODEL,
            "prompt_tokens": event.get("prompt_tokens", 0),
            "completion_tokens": event.get("completion_tokens", 0),
            "token_usage_by_model": event.get("token_usage_by_model", {}),
            "estimated_cost": event.get("estimated_cost", 0.0),
            "latency_ms": event.get("latency_ms", 0),
            "retrieved_document_count": event.get("retrieved_document_count", 0),
            "guardrail_flags": event.get("guardrail_flags", []),
            "guardrail_risk_level": event.get("guardrail_risk_level", ""),
            "input_guardrail_flags": event.get("input_guardrail_flags", []),
            "evaluation_score": event.get("evaluation_score", 0),
            "quality_badge": event.get("quality_badge", "not_evaluated"),
            "evaluation_scores": event.get("evaluation_scores", {}),
            "prompt_versions": event.get("prompt_versions", {}),
            "revision_attempted": event.get("revision_attempted", False),
            "error": event.get("error", ""),
        }

        try:
            return self._repo.save_log(log_entry)
        except Exception:
            return None
