import datetime
import uuid

import config
from infrastructure.langsmith_client import LangSmithClient


class TracingService:
    """
    Optional, no-op-safe wrapper around LangSmith run logging. Injected into any agent
    that wants to emit a trace, the same way LLMService/RetrievalService are injected -
    so adding tracing to a new stage is a constructor-level dependency on this
    abstraction, not a bare import of a concrete module.
    """

    def __init__(self):
        self._client = None
        self._client_initialized = False

    def is_enabled(self) -> bool:
        """True only when LANGSMITH_TRACING=true and a LangSmith API key is configured."""
        return bool(config.LANGSMITH_TRACING and config.has_langsmith_key())

    def _get_client(self):
        if self._client_initialized:
            return self._client

        self._client_initialized = True
        if not self.is_enabled():
            return None

        try:
            self._client = LangSmithClient()
        except Exception:
            self._client = None
        return self._client

    def _governance_metadata(self) -> dict:
        """
        Prompt/ruleset version tags and the overall agent version - attached to every trace
        automatically so callers never need to know about prompt versioning themselves.
        """
        return {
            **config.prompt_version_metadata(),
            "agent_version": config.AGENT_VERSION,
        }

    def trace_event(self, name: str, inputs: dict, outputs: dict, metadata: dict | None = None) -> None:
        """
        Logs one LangSmith run if tracing is configured. A no-op otherwise.
        Never raises - a LangSmith outage or misconfiguration must never break a turn.

        Every trace is automatically enriched with governance metadata (prompt/ruleset
        versions, agent version) merged underneath the caller-supplied `metadata` - caller
        keys win on collision.
        """
        client = self._get_client()
        if client is None:
            return

        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            full_metadata = {**self._governance_metadata(), **(metadata or {})}
            client.create_run(
                run_id=uuid.uuid4(),
                name=name,
                run_type="chain",
                inputs=inputs or {},
                outputs=outputs or {},
                metadata=full_metadata,
                project_name=config.LANGSMITH_PROJECT,
                start_time=now,
                end_time=now,
            )
        except Exception:
            pass
