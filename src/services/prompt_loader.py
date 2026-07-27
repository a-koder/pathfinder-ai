"""
Loads externalized prompts and rulesets from src/prompts/, with in-memory caching.

Path resolution is anchored to this file's location (src/services/prompt_loader.py),
not the current working directory, so callers work the same regardless of where the
process was launched from.
"""
from functools import lru_cache
from pathlib import Path

import yaml

_PROMPTS_ROOT = Path(__file__).resolve().parent.parent / "prompts"


class PromptNotFoundError(FileNotFoundError):
    """Raised when a requested prompt or ruleset file does not exist."""


@lru_cache(maxsize=None)
def load_prompt(category: str, version: str) -> str:
    """
    Load a prompt's raw text from src/prompts/<category>/<version>.md.
    Cached in memory after the first read for a given (category, version) pair.
    """
    path = _PROMPTS_ROOT / category / f"{version}.md"
    if not path.exists():
        raise PromptNotFoundError(
            f"Prompt not found: category={category!r} version={version!r} "
            f"(expected a file at {path})"
        )
    return path.read_text(encoding="utf-8").strip()


@lru_cache(maxsize=None)
def load_ruleset(category: str, version: str) -> dict:
    """
    Load a structured ruleset from src/prompts/<category>/<version>.yaml.
    Cached in memory after the first read for a given (category, version) pair.
    """
    path = _PROMPTS_ROOT / category / f"{version}.yaml"
    if not path.exists():
        raise PromptNotFoundError(
            f"Ruleset not found: category={category!r} version={version!r} "
            f"(expected a file at {path})"
        )
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise PromptNotFoundError(
            f"Ruleset at {path} did not parse to a mapping (got {type(data).__name__})"
        )
    return data
