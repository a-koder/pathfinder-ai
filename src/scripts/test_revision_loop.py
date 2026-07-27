"""
Test the critic/revision loop: a low RASCEF score triggers exactly one
regenerate-and-recheck attempt, and never more than one.

Usage (from project root, with .venv_win active):
    python src/scripts/test_revision_loop.py

What this script does:
    A live LLM judge can't be forced to reliably return a low (or high) score on demand,
    so this monkeypatches the orchestrator module's evaluation agent with a small object
    that returns pre-scripted scores in order, then runs run_turn() through 3 scenarios:

    1. High first-attempt score -> no retry should happen at all.
    2. Low first-attempt score, high retry score -> exactly one retry, and the final
       result reflects the retry's (better) outcome.
    3. Low first-attempt score, low retry score too -> the loop still stops after exactly
       one retry (it does not loop indefinitely trying to hit a passing score).

    Recommendation, Retrieval, Path Planning, and Guardrail agents still run for real
    against the live OpenAI/Pinecone APIs - only the evaluation step is scripted, so this
    exercises the real control flow with a real recommendation attached to each attempt.

This script writes to the local SQLite database under dedicated test student names, and
restores the orchestrator's real EvaluationAgent when it finishes. No Streamlit involved.
Does not modify recommendation logic, Pinecone, or the evaluation rubric - it only injects
a stand-in for the *result* of evaluation to make the control flow deterministic to test.

Prerequisites:
    OPENAI_API_KEY and PINECONE_API_KEY must be set in .env
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config

TEST_MESSAGE = "I like math and video games. What careers might fit me?"


def _badge_for(total_score: int) -> str:
    if total_score >= 26:
        return "green"
    if total_score >= 21:
        return "amber"
    return "red"


class _ScriptedEvaluationAgent:
    """Stands in for the real EvaluationAgent - returns pre-scripted scores in order."""

    def __init__(self, scripted_scores: list[int]):
        self._scripted_scores = list(scripted_scores)
        self.call_count = 0

    def evaluate(self, **kwargs) -> dict:
        self.call_count += 1
        index = min(self.call_count, len(self._scripted_scores)) - 1
        total_score = self._scripted_scores[index]
        return {
            "scores": {
                "relevance": 0, "accuracy": 0, "safety": 0,
                "completeness": 0, "explainability": 0, "fairness": 0,
            },
            "total_score": total_score,
            "max_score": 30,
            "quality_badge": _badge_for(total_score),
            "feedback": [f"Scripted score for test_revision_loop.py: {total_score}"],
            "requires_revision": total_score < 24,
        }


def _reset_student(sqlite_client, name: str) -> None:
    sqlite_client.execute(
        "DELETE FROM profiles WHERE student_id IN (SELECT student_id FROM students WHERE name = ?)", (name,)
    )
    sqlite_client.execute(
        "DELETE FROM messages WHERE student_id IN (SELECT student_id FROM students WHERE name = ?)", (name,)
    )
    sqlite_client.execute(
        "DELETE FROM observability_logs WHERE student_id IN (SELECT student_id FROM students WHERE name = ?)", (name,)
    )
    sqlite_client.execute("DELETE FROM students WHERE name = ?", (name,))


def run() -> None:
    import agents.orchestrator as orchestrator
    from infrastructure.sqlite_client import SQLiteClient

    sqlite_client = SQLiteClient()
    sqlite_client.create_tables()

    original_evaluation = orchestrator._evaluation
    checks: list[bool] = []

    try:
        # --- Case 1: high first score -> no retry at all ---
        student = "RevisionLoopHighScoreStudent"
        _reset_student(sqlite_client, student)
        scripted = _ScriptedEvaluationAgent([28])
        orchestrator._evaluation = scripted
        result = orchestrator.run_turn(student_name=student, user_message=TEST_MESSAGE)
        ok = result["revision_attempted"] is False and scripted.call_count == 1
        checks.append(ok)
        print(f"Case 1 (high score -> no retry): revision_attempted={result['revision_attempted']} "
              f"evaluate_calls={scripted.call_count} final_score={result['evaluation_score']} - "
              f"{'PASS' if ok else 'FAIL'}")

        # --- Case 2: low first score, high retry score -> exactly one retry ---
        student = "RevisionLoopOneRetryStudent"
        _reset_student(sqlite_client, student)
        scripted = _ScriptedEvaluationAgent([18, 27])
        orchestrator._evaluation = scripted
        result = orchestrator.run_turn(student_name=student, user_message=TEST_MESSAGE)
        ok = (
            result["revision_attempted"] is True
            and scripted.call_count == 2
            and result["evaluation_score"] == 27
        )
        checks.append(ok)
        print(f"Case 2 (low then high -> one retry): revision_attempted={result['revision_attempted']} "
              f"evaluate_calls={scripted.call_count} final_score={result['evaluation_score']} - "
              f"{'PASS' if ok else 'FAIL'}")

        # --- Case 3: low first score, low retry score too -> stops after exactly one retry ---
        student = "RevisionLoopMaxOneRetryStudent"
        _reset_student(sqlite_client, student)
        scripted = _ScriptedEvaluationAgent([10, 15])
        orchestrator._evaluation = scripted
        result = orchestrator.run_turn(student_name=student, user_message=TEST_MESSAGE)
        ok = (
            result["revision_attempted"] is True
            and scripted.call_count == 2
            and result["evaluation_score"] == 15
        )
        checks.append(ok)
        print(f"Case 3 (low then still low -> max one retry): revision_attempted={result['revision_attempted']} "
              f"evaluate_calls={scripted.call_count} final_score={result['evaluation_score']} - "
              f"{'PASS' if ok else 'FAIL'}")
    finally:
        orchestrator._evaluation = original_evaluation

    print(f"\n{sum(checks)}/{len(checks)} checks passed.")
    if sum(checks) != len(checks):
        sys.exit(1)


if __name__ == "__main__":
    if not config.has_openai_key():
        print("ERROR: OPENAI_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)
    if not config.has_pinecone_key():
        print("ERROR: PINECONE_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)

    run()
