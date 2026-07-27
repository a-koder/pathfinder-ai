import datetime
import uuid

import config

_client = None
_client_initialized = False


def is_tracing_enabled() -> bool:
    """True only when LANGSMITH_TRACING=true and a LangSmith API key is configured."""
    return bool(config.LANGSMITH_TRACING and config.has_langsmith_key())


def _get_client():
    global _client, _client_initialized
    if _client_initialized:
        return _client

    _client_initialized = True
    if not is_tracing_enabled():
        return None

    try:
        from langsmith import Client
        _client = Client(api_key=config.LANGSMITH_API_KEY)
    except Exception:
        _client = None
    return _client


def _governance_metadata() -> dict:
    """
    Prompt/ruleset version tags and the overall agent version - attached to every trace
    automatically so callers never need to know about prompt versioning themselves.
    """
    return {
        **config.prompt_version_metadata(),
        "agent_version": config.AGENT_VERSION,
    }


def trace_event(name: str, inputs: dict, outputs: dict, metadata: dict | None = None) -> None:
    """
    Logs one LangSmith run if tracing is configured. A no-op otherwise.
    Never raises - a LangSmith outage or misconfiguration must never break the app.

    Every trace is automatically enriched with governance metadata (prompt/ruleset
    versions, agent version) merged underneath the caller-supplied `metadata` - caller
    keys win on collision.
    """
    client = _get_client()
    if client is None:
        return

    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        full_metadata = {**_governance_metadata(), **(metadata or {})}
        client.create_run(
            id=uuid.uuid4(),
            name=name,
            run_type="chain",
            inputs=inputs or {},
            outputs=outputs or {},
            extra={"metadata": full_metadata},
            project_name=config.LANGSMITH_PROJECT,
            start_time=now,
            end_time=now,
        )
    except Exception:
        pass
