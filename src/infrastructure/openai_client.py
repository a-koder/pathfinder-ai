import openai
import config


class OpenAIClient:
    """Wraps openai.OpenAI() for chat completions and embeddings. Only layer that imports openai."""

    def __init__(self):
        self._client = openai.OpenAI(api_key=config.OPENAI_API_KEY)

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
