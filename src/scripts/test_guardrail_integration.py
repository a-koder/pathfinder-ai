"""
Run full PathFinder AI turns through the orchestrator and inspect guardrail output.

Usage (from project root, with .venv_win active):
    python src/scripts/test_guardrail_integration.py

What this script does:
    Sends a sequence of realistic student messages through the full orchestrator
    pipeline (memory -> discovery -> retrieval -> recommendation -> path planning
    -> guardrails) via run_turn(), printing a short response summary plus the
    guardrail flags and risk level for each turn.

This script writes to the local SQLite database (data/memory.db) under a dedicated
test student name, and calls the live OpenAI and Pinecone APIs, but does not modify
production code or the knowledge base.

Prerequisites:
    OPENAI_API_KEY and PINECONE_API_KEY must be set in .env

No Streamlit testing is needed for this phase - this script exercises the same
orchestrator code path the UI calls, without a browser.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config

TEST_STUDENT = "GuardrailIntegrationStudent"

MESSAGES = [
    "I like fashion, creativity, and business. What careers fit me?",
    "I want college recommendations but I do not know my GPA.",
    "I like building things with my hands and want a stable path.",
    "I enjoy travel and learning about cultures.",
]


def run() -> None:
    from agents.orchestrator import run_turn

    for i, message in enumerate(MESSAGES, start=1):
        print(f"\nTurn {i}: \"{message}\"")
        print("=" * (len(message) + 10))

        result = run_turn(student_name=TEST_STUDENT, user_message=message)

        response = result["response"]
        summary = response if len(response) <= 300 else response[:300] + "..."
        print(f"Response summary: {summary}")
        print(f"Guardrail flags: {result['guardrail_flags']}")
        print(f"Guardrail risk level: {result['guardrail_risk_level']}")
        if result.get("guardrail_required_revisions"):
            print(f"Required revisions: {result['guardrail_required_revisions']}")


if __name__ == "__main__":
    if not config.has_openai_key():
        print("ERROR: OPENAI_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)
    if not config.has_pinecone_key():
        print("ERROR: PINECONE_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)

    run()
