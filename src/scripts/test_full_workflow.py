"""
Final backend acceptance test for PathFinder AI - no Streamlit involved.

Usage (from project root, with .venv_win active):
    python src/scripts/test_full_workflow.py

What this script does:
    Exercises the complete orchestrator pipeline end to end:
        memory -> discovery -> retrieval -> recommendation -> path planning
        -> guardrails -> evaluation -> observability
    across 5 scenarios (4 single-turn, 1 two-turn returning-student check), calling
    the live OpenAI and Pinecone APIs. Each test student's prior data is reset first
    so results are reproducible across runs. Observability persistence is verified
    by reading rows back directly from SQLite via ObservabilityRepository.

This script writes to the local SQLite database (data/memory.db) under dedicated
test student names, but does not modify production code, Pinecone data, or the
knowledge base. No Streamlit/browser testing is performed.

Prerequisites:
    OPENAI_API_KEY and PINECONE_API_KEY must be set in .env
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config


def _reset_student(sqlite_client, name: str) -> None:
    """Delete any prior data for one test student so each run is reproducible."""
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


def _observability_log_saved(obs_repo, student_repo, student_name: str) -> bool:
    student_id = student_repo.create_or_get_student(student_name)
    return len(obs_repo.get_logs_for_student(student_id, limit=1)) > 0


def _print_turn(label: str, student_name: str, message: str, result: dict, obs_repo, student_repo) -> dict:
    response = result["response"]
    summary = response if len(response) <= 300 else response[:300] + "..."
    recommendation_titles = [r.get("title", "") for r in result.get("recommendations", [])]
    saved = _observability_log_saved(obs_repo, student_repo, student_name)

    print(f"\n{label}")
    print("-" * len(label))
    print(f"Student name: {student_name}")
    print(f"Message: \"{message}\"")
    print(f"Response summary: {summary}")
    print(f"Profile interests: {result.get('profile', {}).get('interests', [])}")
    print(f"Retrieved document count: {result.get('retrieved_document_count', 0)}")
    print(f"Recommendation titles: {recommendation_titles}")
    print(f"Selected path: {result.get('path_plan', {}).get('selected_path', '')}")
    print(f"Guardrail flags: {result.get('guardrail_flags', [])}")
    print(f"Guardrail risk level: {result.get('guardrail_risk_level', '')}")
    print(f"RASCEF total score: {result.get('evaluation_score', 0)}/30")
    print(f"Quality badge: {result.get('quality_badge', 'not_evaluated')}")
    print(f"Requires revision: {result.get('evaluation_requires_revision', False)}")
    print(f"Observability log saved: {'yes' if saved else 'no'}")

    passed = (
        bool(response.strip())
        and len(recommendation_titles) > 0
        and saved
    )
    print(f"Scenario check: {'PASS' if passed else 'FAIL'}")
    return {
        "label": label,
        "passed": passed,
        "quality_badge": result.get("quality_badge", "not_evaluated"),
        "evaluation_score": result.get("evaluation_score", 0),
        "guardrail_risk_level": result.get("guardrail_risk_level", ""),
    }


def run() -> list[dict]:
    from agents.orchestrator import run_turn
    from infrastructure.sqlite_client import SQLiteClient
    from repositories.observability_repository import ObservabilityRepository
    from repositories.student_repository import StudentRepository

    sqlite_client = SQLiteClient()
    sqlite_client.create_tables()
    obs_repo = ObservabilityRepository(sqlite_client)
    student_repo = StudentRepository(sqlite_client)

    outcomes: list[dict] = []

    # --- Scenario 1: Undecided student ---------------------------------------
    name = "AcceptanceUndecidedStudent"
    _reset_student(sqlite_client, name)
    message = "I like gaming, storytelling, and technology but I do not know what career I want."
    result = run_turn(student_name=name, user_message=message)
    outcomes.append(_print_turn("Scenario 1: Undecided student", name, message, result, obs_repo, student_repo))

    # --- Scenario 2: Fashion/business student ---------------------------------
    name = "AcceptanceFashionBusinessStudent"
    _reset_student(sqlite_client, name)
    message = "I like fashion, creativity, social media, and business."
    result = run_turn(student_name=name, user_message=message)
    outcomes.append(_print_turn("Scenario 2: Fashion/business student", name, message, result, obs_repo, student_repo))

    # --- Scenario 3: Trades student -------------------------------------------
    name = "AcceptanceTradesStudent"
    _reset_student(sqlite_client, name)
    message = "I like building things with my hands and I do not know if college is right for me."
    result = run_turn(student_name=name, user_message=message)
    outcomes.append(_print_turn("Scenario 3: Trades student", name, message, result, obs_repo, student_repo))

    # --- Scenario 4: College guidance without GPA ------------------------------
    name = "AcceptanceCollegeNoGpaStudent"
    _reset_student(sqlite_client, name)
    message = "I want college recommendations for computer science but I do not know my GPA."
    result = run_turn(student_name=name, user_message=message)
    outcome = _print_turn("Scenario 4: College guidance without GPA", name, message, result, obs_repo, student_repo)
    if "missing_gpa_for_college_guidance" not in result.get("guardrail_flags", []):
        outcome["passed"] = False
        print("Scenario check: FAIL (expected missing_gpa_for_college_guidance flag)")
    outcomes.append(outcome)

    # --- Scenario 5: Returning student - memory/profile growth across turns ----
    name = "AcceptanceReturningStudent"
    _reset_student(sqlite_client, name)

    message_1 = "I'm in 11th grade and I like biology and helping people."
    result_1 = run_turn(student_name=name, user_message=message_1)
    outcomes.append(_print_turn("Scenario 5a: Returning student - turn 1", name, message_1, result_1, obs_repo, student_repo))
    profile_1 = result_1.get("profile", {})

    message_2 = "My GPA is 3.5 and I'm also interested in psychology."
    result_2 = run_turn(student_name=name, user_message=message_2)
    outcomes.append(_print_turn("Scenario 5b: Returning student - turn 2", name, message_2, result_2, obs_repo, student_repo))
    profile_2 = result_2.get("profile", {})

    print("\nScenario 5 memory growth check")
    print("-------------------------------")
    print(f"Profile after turn 1: {profile_1}")
    print(f"Profile after turn 2: {profile_2}")
    interests_grew = len(profile_2.get("interests", [])) >= len(profile_1.get("interests", []))
    gpa_learned = bool(profile_2.get("gpa")) and not profile_1.get("gpa")
    grew = interests_grew and gpa_learned
    print(f"Interests count: {len(profile_1.get('interests', []))} -> {len(profile_2.get('interests', []))}")
    print(f"GPA learned between turns: {gpa_learned} (turn 1: {profile_1.get('gpa')!r}, turn 2: {profile_2.get('gpa')!r})")
    print(f"Scenario check: {'PASS' if grew else 'FAIL'} (profile grew across turns)")
    outcomes.append({
        "label": "Scenario 5: Memory/profile growth across turns",
        "passed": grew,
        "quality_badge": result_2.get("quality_badge", "not_evaluated"),
        "evaluation_score": result_2.get("evaluation_score", 0),
        "guardrail_risk_level": result_2.get("guardrail_risk_level", ""),
    })

    return outcomes


def _print_summary(outcomes: list[dict]) -> None:
    print("\n" + "=" * 70)
    print("ACCEPTANCE TEST SUMMARY")
    print("=" * 70)
    for outcome in outcomes:
        status = "PASS" if outcome["passed"] else "FAIL"
        print(
            f"[{status}] {outcome['label']} - badge={outcome['quality_badge']} "
            f"score={outcome['evaluation_score']}/30 risk={outcome['guardrail_risk_level']}"
        )
    total = len(outcomes)
    passed = sum(1 for o in outcomes if o["passed"])
    print(f"\n{passed}/{total} checks passed.")


if __name__ == "__main__":
    if not config.has_openai_key():
        print("ERROR: OPENAI_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)
    if not config.has_pinecone_key():
        print("ERROR: PINECONE_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)

    outcomes = run()
    _print_summary(outcomes)
