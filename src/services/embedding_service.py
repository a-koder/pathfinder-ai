import config
from infrastructure.openai_client import OpenAIClient
from services.usage_tracker import UsageTracker


class EmbeddingService:
    """Generates OpenAI text embeddings via OpenAIClient. Never imports openai directly."""

    def __init__(self, openai_client: OpenAIClient):
        self._client = openai_client
        self._model = config.EMBEDDING_MODEL

    def generate_embedding(self, text: str, usage: UsageTracker | None = None) -> list[float]:
        """Return a 1536-dim float vector for the given text using text-embedding-3-small."""
        vector, prompt_tokens = self._client.embed(text=text, model=self._model)
        if usage is not None:
            usage.record(self._model, prompt_tokens, 0)
        return vector
