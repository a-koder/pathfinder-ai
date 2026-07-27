import openai
import config


class OpenAIClient:
    """Wraps openai.OpenAI() for chat completions and embeddings. Only layer that imports openai."""

    def __init__(self):
        self._client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        # Force the SDK's lazily-loaded .chat/.embeddings submodules to import now, on
        # this single thread, rather than on first use. Discovery and Retrieval run
        # concurrently on worker threads (see orchestrator.run_turn) and both touch these
        # properties for the first time; if that first import happens on two threads at
        # once, Python's import lock can raise _DeadlockError.
        self._client.chat
        self._client.embeddings

    def complete(
        self,
        model: str,
        messages: list[dict],
        response_format: dict | None = None,
    ) -> str:
        kwargs = {"model": model, "messages": messages}
        if response_format is not None:
            kwargs["response_format"] = response_format
        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def embed(self, text: str, model: str = "text-embedding-3-small") -> list[float]:
        response = self._client.embeddings.create(input=text, model=model)
        return response.data[0].embedding
