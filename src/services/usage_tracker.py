# USD per 1M tokens. Single source of truth for pricing - both the per-turn cost
# estimate below and (previously) observability_agent.py read from this table.
_PRICING_PER_MILLION_TOKENS = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
}


class UsageTracker:
    """
    Accumulates token usage across every LLM/embedding call made during a single
    orchestrator turn, broken down per model (a turn calls several different models -
    gpt-4o-mini for generation, gpt-4o for evaluation, text-embedding-3-small for
    retrieval - and the critic/revision loop can call some of them twice).

    Create one fresh instance per `run_turn()` call rather than sharing one across
    turns or requests - that keeps concurrent turns (different students, or the
    Discovery/Retrieval worker threads within the same turn) from ever mixing token
    counts. `list.append` is atomic under the GIL, so no explicit lock is needed for
    the concurrent Discovery/Retrieval step recording into the same instance.
    """

    def __init__(self):
        self._calls: list[dict] = []

    def record(self, model: str, prompt_tokens: int, completion_tokens: int = 0) -> None:
        self._calls.append({
            "model": model,
            "prompt_tokens": prompt_tokens or 0,
            "completion_tokens": completion_tokens or 0,
        })

    def by_model(self) -> dict:
        """Returns {model: {prompt_tokens, completion_tokens}} summed across all recorded calls."""
        totals: dict = {}
        for call in self._calls:
            bucket = totals.setdefault(call["model"], {"prompt_tokens": 0, "completion_tokens": 0})
            bucket["prompt_tokens"] += call["prompt_tokens"]
            bucket["completion_tokens"] += call["completion_tokens"]
        return totals

    def totals(self) -> tuple[int, int]:
        """Grand total (prompt_tokens, completion_tokens) across every model combined."""
        prompt_total = sum(call["prompt_tokens"] for call in self._calls)
        completion_total = sum(call["completion_tokens"] for call in self._calls)
        return prompt_total, completion_total

    def estimated_cost_usd(self) -> float:
        """Sums cost across every model recorded this turn using the pricing table above."""
        total = 0.0
        for model, tokens in self.by_model().items():
            pricing = _PRICING_PER_MILLION_TOKENS.get(model)
            if not pricing:
                continue
            total += (tokens["prompt_tokens"] / 1_000_000) * pricing["input"]
            total += (tokens["completion_tokens"] / 1_000_000) * pricing["output"]
        return total
