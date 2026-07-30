import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "pathfinder-ai")
DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
EVAL_MODEL: str = os.getenv("EVAL_MODEL", "gpt-4o")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "pathfinder-ai")
LANGSMITH_TRACING: bool = os.getenv("LANGSMITH_TRACING", "false").strip().lower() == "true"

# Prompt / ruleset versions. Each defaults to the current "v1" content so behavior is
# unchanged unless a version is explicitly bumped. See src/services/prompt_loader.py
# and src/prompts/<category>/<version>.md|.yaml.
DISCOVERY_PROMPT_VERSION: str = os.getenv("DISCOVERY_PROMPT_VERSION", "v2")
INTENT_ROUTER_PROMPT_VERSION: str = os.getenv("INTENT_ROUTER_PROMPT_VERSION", "v4")
RECOMMENDATION_PROMPT_VERSION: str = os.getenv("RECOMMENDATION_PROMPT_VERSION", "v1")
PATH_PLANNING_PROMPT_VERSION: str = os.getenv("PATH_PLANNING_PROMPT_VERSION", "v1")
EVALUATION_PROMPT_VERSION: str = os.getenv("EVALUATION_PROMPT_VERSION", "rascef_v1")
GENERAL_CHAT_PROMPT_VERSION: str = os.getenv("GENERAL_CHAT_PROMPT_VERSION", "v1")
SUGGESTIONS_PROMPT_VERSION: str = os.getenv("SUGGESTIONS_PROMPT_VERSION", "v1")
GUARDRAIL_RULESET_VERSION: str = os.getenv("GUARDRAIL_RULESET_VERSION", "v1")
INPUT_GUARDRAIL_RULESET_VERSION: str = os.getenv("INPUT_GUARDRAIL_RULESET_VERSION", "v1")

# Overall agent/system version tag, surfaced in LangSmith metadata for governance.
AGENT_VERSION: str = os.getenv("AGENT_VERSION", "v1")


def has_openai_key() -> bool:
    return bool(OPENAI_API_KEY and OPENAI_API_KEY != "your-openai-key-here")


def has_pinecone_key() -> bool:
    return bool(PINECONE_API_KEY and PINECONE_API_KEY != "your-pinecone-key-here")


def has_langsmith_key() -> bool:
    return bool(LANGSMITH_API_KEY and LANGSMITH_API_KEY != "your-langsmith-key-here")


def prompt_version_metadata() -> dict:
    """
    Single source of truth for the prompt/ruleset version tags attached to every turn's
    orchestrator result, observability log, and LangSmith trace. Component name is baked
    into the tag (e.g. "discovery_v1") except evaluation, whose configured version already
    includes the framework name (e.g. "rascef_v1").
    """
    return {
        "discovery_prompt_version": f"discovery_{DISCOVERY_PROMPT_VERSION}",
        "intent_router_prompt_version": f"intent_router_{INTENT_ROUTER_PROMPT_VERSION}",
        "recommendation_prompt_version": f"recommendation_{RECOMMENDATION_PROMPT_VERSION}",
        "path_planning_prompt_version": f"path_planning_{PATH_PLANNING_PROMPT_VERSION}",
        "evaluation_prompt_version": EVALUATION_PROMPT_VERSION,
        "general_chat_prompt_version": f"general_chat_{GENERAL_CHAT_PROMPT_VERSION}",
        "suggestions_prompt_version": f"suggestions_{SUGGESTIONS_PROMPT_VERSION}",
        "guardrail_ruleset_version": f"guardrail_{GUARDRAIL_RULESET_VERSION}",
        "input_guardrail_ruleset_version": f"input_guardrail_{INPUT_GUARDRAIL_RULESET_VERSION}",
    }


def config_summary() -> dict:
    return {
        "openai_key_configured": has_openai_key(),
        "pinecone_key_configured": has_pinecone_key(),
        "pinecone_index": PINECONE_INDEX_NAME,
        "default_model": DEFAULT_MODEL,
        "eval_model": EVAL_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "langsmith_configured": LANGSMITH_TRACING and has_langsmith_key(),
    }
