import datetime
import uuid
from concurrent.futures import ThreadPoolExecutor

import config
from infrastructure.langsmith_client import LangSmithClient

_MAX_WORKERS = 4


class TracingService:
    """
    Optional, no-op-safe wrapper around LangSmith run logging. Injected into any agent
    that wants to emit a trace, the same way LLMService/RetrievalService are injected -
    so adding tracing to a new stage is a constructor-level dependency on this
    abstraction, not a bare import of a concrete module.

    Every trace is sent on a background thread, not inline - a real, measured call to
    LangSmith's create_run() takes ~80-1000ms, and with tracing now covering 7 stages per
    turn, sending them synchronously would add that latency to every one of those stages
    on the critical path. Nothing in the same turn depends on a trace's return value
    (trace_event() always returns None), so there's no correctness reason to wait for it.
    """

    def __init__(self):
        self._client = None
        self._client_initialized = False
        self._executor = None

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
            self._executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS, thread_name_prefix="tracing")
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
        Fires one LangSmith run on a background thread if tracing is configured. A no-op
        otherwise. Never raises, and never blocks the caller - a LangSmith outage,
        misconfiguration, or slow response must never break or slow down a turn.

        Every trace is automatically enriched with governance metadata (prompt/ruleset
        versions, agent version) merged underneath the caller-supplied `metadata` - caller
        keys win on collision. Metadata is built here, on the caller's thread (cheap, no
        I/O); only the actual network call happens on the background thread.
        """
        client = self._get_client()
        if client is None:
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        full_metadata = {**self._governance_metadata(), **(metadata or {})}
        self._executor.submit(self._send, client, name, inputs or {}, outputs or {}, full_metadata, now)

    def _send(self, client, name: str, inputs: dict, outputs: dict, metadata: dict, now) -> None:
        """
        Runs on the background thread. The calling agent has already returned by the time
        this executes, so any failure here is swallowed - there's no one left to hand it to.
        """
        try:
            client.create_run(
                run_id=uuid.uuid4(),
                name=name,
                run_type="chain",
                inputs=inputs,
                outputs=outputs,
                metadata=metadata,
                project_name=config.LANGSMITH_PROJECT,
                start_time=now,
                end_time=now,
            )
        except Exception:
            pass
