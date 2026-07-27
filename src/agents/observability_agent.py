import datetime

import config
from repositories.observability_repository import ObservabilityRepository

# USD per 1M tokens. Source: docs/09_Agent_Contracts.md cost calculation table.
_COST_PER_MILLION_TOKENS = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
}


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Estimate USD cost from token counts and per-model pricing.

    TODO: OpenAIClient does not currently surface response.usage token counts, so
    prompt_tokens/completion_tokens are always 0 for now and this returns 0.0. Wire
    real usage through OpenAIClient -> LLMService -> here once available.
    """
    pricing = _COST_PER_MILLION_TOKENS.get(model)
    if not pricing or (not prompt_tokens and not completion_tokens):
        return 0.0
    return (
        (prompt_tokens / 1_000_000) * pricing["input"]
        + (completion_tokens / 1_000_000) * pricing["output"]
    )


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class ObservabilityAgent:
    """
    Logs per-turn metrics to SQLite via ObservabilityRepository. Captures latency,
    model, guardrail flags/risk, evaluation score/badge, and a cost estimate.
    Never raises - a logging failure must never break the student's response.

    Service dependencies: ObservabilityRepository
    """

    def __init__(self, observability_repository: ObservabilityRepository):
        self._repo = observability_repository

    def log_turn(self, event: dict) -> int | None:
        """Writes one ObservabilityLog entry to SQLite. Returns the new log_id, or None on failure."""
        prompt_tokens = event.get("prompt_tokens", 0)
        completion_tokens = event.get("completion_tokens", 0)
        model = event.get("model") or config.DEFAULT_MODEL

        log_entry = {
            "timestamp": event.get("timestamp") or _utc_now_iso(),
            "student_id": event.get("student_id"),
            "student_name": event.get("student_name", ""),
            "user_message": event.get("user_message", ""),
            "agent": "Orchestrator",
            "model": model,
            "evaluation_model": event.get("evaluation_model") or config.EVAL_MODEL,
            "embedding_model": event.get("embedding_model") or config.EMBEDDING_MODEL,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated_cost": _estimate_cost(model, prompt_tokens, completion_tokens),
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
