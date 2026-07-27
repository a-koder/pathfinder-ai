"""
Test human-in-the-loop feedback capture.

Usage (from project root, with .venv_win active):
    python src/scripts/test_human_feedback.py

What this script does:
    Runs one normal PathFinder AI turn, finds the resulting observability log row,
    saves a "helpful" feedback entry, then overwrites it with a "not helpful" entry
    plus free-text feedback (simulating feedback being revised), and prints both the
    updated row and the aggregated feedback summary across all logs.

This script writes to the local SQLite database (data/memory.db) under a dedicated
test student name, and calls the live OpenAI and Pinecone APIs, but does not modify
production code, Pinecone data, or the knowledge base. No Streamlit involved.

Prerequisites:
    OPENAI_API_KEY and PINECONE_API_KEY must be set in .env
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config

TEST_STUDENT = "HITLFeedbackTestStudent"
TEST_MESSAGE = "I like math and video games. What careers might fit me?"


def run() -> None:
    from agents.orchestrator import run_turn
    from infrastructure.sqlite_client import SQLiteClient
    from repositories.observability_repository import ObservabilityRepository
    from repositories.student_repository import StudentRepository

    print(f"Running one turn for '{TEST_STUDENT}': \"{TEST_MESSAGE}\"")
    result = run_turn(student_name=TEST_STUDENT, user_message=TEST_MESSAGE)
    print(f"Response summary: {result['response'][:150]}...")

    sqlite_client = SQLiteClient()
    sqlite_client.create_tables()
    obs_repo = ObservabilityRepository(sqlite_client)
    student_repo = StudentRepository(sqlite_client)

    student_id = student_repo.create_or_get_student(TEST_STUDENT)
    logs = obs_repo.get_logs_for_student(student_id, limit=1)
    if not logs:
        print("ERROR: no observability log found for this turn.")
        sys.exit(1)

    log_id = logs[0]["log_id"]
    print(f"\nLatest observability log_id: {log_id}")
    print(f"Prompt versions recorded on this row: {logs[0].get('prompt_versions')}")

    print(f"\nSaving helpful=True for log_id {log_id}...")
    obs_repo.save_feedback(log_id, helpful=True)
    after_true = obs_repo.get_logs_for_student(student_id, limit=1)[0]
    print(f"  helpful={after_true['helpful']!r} feedback_text={after_true['feedback_text']!r}")

    print(f"\nSaving helpful=False with feedback text for log_id {log_id} (overwrites the prior feedback)...")
    obs_repo.save_feedback(
        log_id,
        helpful=False,
        feedback_text="This recommendation felt generic and didn't reflect my interests well.",
    )
    after_false = obs_repo.get_logs_for_student(student_id, limit=1)[0]
    print(f"  helpful={after_false['helpful']!r} feedback_text={after_false['feedback_text']!r}")

    summary = obs_repo.get_feedback_summary()
    print(f"\nFeedback summary (across all logs in the database): {summary}")

    checks = [
        after_true["helpful"] is True,
        after_false["helpful"] is False,
        after_false["feedback_text"] is not None,
        summary["total_feedback"] >= 1,
    ]
    print(f"\nCheck: {'PASS' if all(checks) else 'FAIL'} ({sum(checks)}/{len(checks)} sub-checks passed)")


if __name__ == "__main__":
    if not config.has_openai_key():
        print("ERROR: OPENAI_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)
    if not config.has_pinecone_key():
        print("ERROR: PINECONE_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)

    run()
