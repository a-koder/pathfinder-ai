"""
Test observability logging end-to-end.

Usage (from project root, with .venv_win active):
    python src/scripts/test_observability.py

What this script does:
    Runs one full turn through the orchestrator, then reads the most recent
    observability log rows directly from SQLite (bypassing the orchestrator) to
    confirm the turn was actually persisted to observability_logs.

This script writes to the local SQLite database (data/memory.db) under a dedicated
test student name, and calls the live OpenAI and Pinecone APIs, but does not modify
production code, Pinecone data, or the knowledge base.

Prerequisites:
    OPENAI_API_KEY and PINECONE_API_KEY must be set in .env

No Streamlit testing is needed for this phase.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config

TEST_STUDENT = "ObservabilityTestStudent"
TEST_MESSAGE = "I like math and video games. What careers might fit me?"


def run() -> None:
    from agents.orchestrator import run_turn
    from infrastructure.sqlite_client import SQLiteClient
    from repositories.observability_repository import ObservabilityRepository
    from repositories.student_repository import StudentRepository

    print(f"Running one turn for '{TEST_STUDENT}': \"{TEST_MESSAGE}\"")
    result = run_turn(student_name=TEST_STUDENT, user_message=TEST_MESSAGE)

    print(f"\nResponse summary: {result['response'][:200]}...")
    print(f"Quality badge: {result['quality_badge']} ({result['evaluation_score']}/30)")
    print(f"Guardrail flags: {result['guardrail_flags']}")

    sqlite_client = SQLiteClient()
    sqlite_client.create_tables()
    obs_repo = ObservabilityRepository(sqlite_client)
    student_repo = StudentRepository(sqlite_client)

    student_id = student_repo.create_or_get_student(TEST_STUDENT)
    student_logs = obs_repo.get_logs_for_student(student_id, limit=5)
    recent_logs = obs_repo.get_recent_logs(limit=5)

    print(f"\nMost recent {len(recent_logs)} observability log(s) (any student):")
    for log in recent_logs:
        print(f"\n- log_id: {log.get('log_id')}")
        print(f"  timestamp: {log.get('timestamp')}")
        print(f"  student_id: {log.get('student_id')}  student_name: {log.get('student_name')}")
        print(f"  user_message: {log.get('user_message')}")
        print(
            f"  model: {log.get('model')}  evaluation_model: {log.get('evaluation_model')}  "
            f"embedding_model: {log.get('embedding_model')}"
        )
        print(f"  retrieved_doc_count: {log.get('retrieved_doc_count')}")
        print(f"  guardrail_flags: {log.get('guardrail_flags')}  guardrail_risk_level: {log.get('guardrail_risk_level')}")
        print(f"  eval_score: {log.get('eval_score')}  quality_badge: {log.get('quality_badge')}")
        print(f"  evaluation_scores: {log.get('evaluation_scores')}")
        print(f"  latency_ms: {log.get('latency_ms')}  estimated_cost_usd: {log.get('estimated_cost_usd')}")
        print(
            f"  prompt_tokens: {log.get('prompt_tokens')}  completion_tokens: {log.get('completion_tokens')}  "
            f"token_usage_by_model: {log.get('token_usage_by_model')}"
        )
        print(f"  error: {log.get('error')!r}")

    print(f"\nCheck: log saved for student_id {student_id}: {'OK' if student_logs else 'MISSING'}")


if __name__ == "__main__":
    if not config.has_openai_key():
        print("ERROR: OPENAI_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)
    if not config.has_pinecone_key():
        print("ERROR: PINECONE_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)

    run()
