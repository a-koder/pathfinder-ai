import json

import config
from infrastructure.openai_client import OpenAIClient
from services.usage_tracker import UsageTracker


class LLMService:
    """Wraps OpenAI chat completions via OpenAIClient. Returns plain text or parsed JSON."""

    def __init__(self, openai_client: OpenAIClient):
        self._client = openai_client
        self._model = config.DEFAULT_MODEL

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        usage: UsageTracker | None = None,
    ) -> str:
        """Return the raw text completion for a system/user prompt pair."""
        resolved_model = model or self._model
        text, prompt_tokens, completion_tokens = self._client.complete(
            model=resolved_model, messages=self._messages(system_prompt, user_prompt),
        )
        if usage is not None:
            usage.record(resolved_model, prompt_tokens, completion_tokens)
        return text

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        usage: UsageTracker | None = None,
    ) -> dict:
        """Return a parsed JSON dict, or {} if the model did not return valid JSON."""
        resolved_model = model or self._model
        raw, prompt_tokens, completion_tokens = self._client.complete(
            model=resolved_model,
            messages=self._messages(system_prompt, user_prompt),
            response_format={"type": "json_object"},
        )
        if usage is not None:
            usage.record(resolved_model, prompt_tokens, completion_tokens)
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _messages(self, system_prompt: str, user_prompt: str) -> list[dict]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
