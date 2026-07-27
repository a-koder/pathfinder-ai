"""
Test prompt externalization and versioning end to end.

Usage (from project root, with .venv_win active):
    python src/scripts/test_prompt_versioning.py

What this script does:
    1. Loads every externalized prompt/ruleset directly via PromptLoader and confirms
       non-empty content.
    2. Prints the configured prompt/ruleset versions and the derived version metadata.
    3. Constructs GuardrailAgent from the YAML ruleset and confirms a known trigger
       phrase still fires the admission_guarantee flag at high risk.
    4. Constructs Discovery, Retrieval, Recommendation, Path Planning, and Evaluation
       directly (loading their prompts from src/prompts/) and runs one real call through
       each to confirm behavior is unchanged.
    5. Runs one full orchestrator turn and confirms all 5 prompt-version keys are present
       in the result.

This script calls the live OpenAI and Pinecone APIs, and writes to the local SQLite
database under a dedicated test student name, but does not modify production code,
Pinecone data, or the knowledge base. No Streamlit involved.

Prerequisites:
    OPENAI_API_KEY and PINECONE_API_KEY must be set in .env
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config

TEST_STUDENT = "PromptVersioningTestStudent"
MESSAGE = "I like math and video games. What careers might fit me?"


def run() -> None:
    from services.prompt_loader import load_prompt, load_ruleset

    checks: list[bool] = []

    print("1. Loading externalized prompts/rulesets directly")
    print("-" * 60)
    discovery_prompt = load_prompt("discovery", config.DISCOVERY_PROMPT_VERSION)
    recommendation_prompt = load_prompt("recommendation", config.RECOMMENDATION_PROMPT_VERSION)
    path_planning_prompt = load_prompt("path_planning", config.PATH_PLANNING_PROMPT_VERSION)
    evaluation_prompt = load_prompt("evaluation", config.EVALUATION_PROMPT_VERSION)
    guardrail_ruleset = load_ruleset("guardrail", config.GUARDRAIL_RULESET_VERSION)

    for label, content in [
        ("discovery", discovery_prompt),
        ("recommendation", recommendation_prompt),
        ("path_planning", path_planning_prompt),
        ("evaluation", evaluation_prompt),
    ]:
        ok = bool(content and content.strip())
        checks.append(ok)
        print(f"  {label}: {len(content)} chars - {'OK' if ok else 'EMPTY (FAIL)'}")

    flag_count = len(guardrail_ruleset.get("flags", {}))
    ok = flag_count > 0
    checks.append(ok)
    print(f"  guardrail ruleset: {flag_count} flags loaded - {'OK' if ok else 'EMPTY (FAIL)'}")

    print("\n2. Configured prompt versions")
    print("-" * 60)
    print(f"  DISCOVERY_PROMPT_VERSION = {config.DISCOVERY_PROMPT_VERSION}")
    print(f"  RECOMMENDATION_PROMPT_VERSION = {config.RECOMMENDATION_PROMPT_VERSION}")
    print(f"  PATH_PLANNING_PROMPT_VERSION = {config.PATH_PLANNING_PROMPT_VERSION}")
    print(f"  EVALUATION_PROMPT_VERSION = {config.EVALUATION_PROMPT_VERSION}")
    print(f"  GUARDRAIL_RULESET_VERSION = {config.GUARDRAIL_RULESET_VERSION}")
    print(f"  AGENT_VERSION = {config.AGENT_VERSION}")
    print(f"  prompt_version_metadata() = {config.prompt_version_metadata()}")

    print("\n3. Guardrail rules loaded from YAML - known trigger case")
    print("-" * 60)
    from agents.guardrail_agent import GuardrailAgent

    guardrail_agent = GuardrailAgent()
    guardrail_result = guardrail_agent.check_guardrails(
        response_payload={
            "response": "You will get into Stanford with your GPA.",
            "recommendations": {"recommendations": []},
            "path_plan": {},
        },
        profile={"gpa": "3.8"},
        user_message="Will I get into Stanford?",
    )
    print(f"  flags: {guardrail_result['flags']}")
    print(f"  risk_level: {guardrail_result['risk_level']}")
    ok = "admission_guarantee" in guardrail_result["flags"] and guardrail_result["risk_level"] == "high"
    checks.append(ok)
    print(f"  check: {'PASS' if ok else 'FAIL'} (expected admission_guarantee flag, risk high)")

    print("\n4. Discovery / Recommendation / Path Planning / Evaluation still run")
    print("-" * 60)
    from infrastructure.openai_client import OpenAIClient
    from infrastructure.pinecone_client import PineconeClient
    from infrastructure.knowledge_loader import KnowledgeLoader
    from services.embedding_service import EmbeddingService
    from services.retrieval_service import RetrievalService
    from services.llm_service import LLMService
    from services.prompt_service import PromptService
    from services.evaluation_service import EvaluationService
    from agents.discovery_agent import DiscoveryAgent
    from agents.retrieval_agent import RetrievalAgent
    from agents.recommendation_agent import RecommendationAgent
    from agents.path_planning_agent import PathPlanningAgent
    from agents.evaluation_agent import EvaluationAgent

    openai_client = OpenAIClient()
    pinecone_client = PineconeClient()
    knowledge_loader = KnowledgeLoader()
    embedding_service = EmbeddingService(openai_client)
    retrieval_service = RetrievalService(embedding_service, pinecone_client, knowledge_loader)
    llm_service = LLMService(openai_client)
    prompt_service = PromptService()
    evaluation_service = EvaluationService(llm_service)

    discovery_agent = DiscoveryAgent(llm_service)
    retrieval_agent = RetrievalAgent(retrieval_service)
    recommendation_agent = RecommendationAgent(llm_service, prompt_service)
    path_planning_agent = PathPlanningAgent(llm_service)
    evaluation_agent = EvaluationAgent(evaluation_service)

    profile = {"name": TEST_STUDENT, "interests": ["math", "video games"]}

    discovery = discovery_agent.extract_profile_updates(
        student_name=TEST_STUDENT, user_message=MESSAGE, existing_profile=profile,
    )
    ok = discovery.get("confidence", 0) > 0
    checks.append(ok)
    print(f"  Discovery: confidence={discovery['confidence']:.2f} - {'OK' if ok else 'FAIL'}")

    retrieval = retrieval_agent.retrieve_relevant_context(user_message=MESSAGE, profile=profile, top_k=5)
    ok = len(retrieval["retrieved_documents"]) > 0
    checks.append(ok)
    print(f"  Retrieval: {len(retrieval['retrieved_documents'])} documents - {'OK' if ok else 'FAIL'}")

    recommendations = recommendation_agent.generate_recommendations(
        user_message=MESSAGE, profile=profile, retrieved_context=retrieval,
    )
    rec_count = len(recommendations.get("recommendations", []))
    ok = rec_count > 0
    checks.append(ok)
    print(f"  Recommendation: {rec_count} recommendations - {'OK' if ok else 'FAIL'}")

    path_plan = path_planning_agent.generate_path_plan(profile=profile, recommendations=recommendations)
    ok = bool(path_plan.get("selected_path"))
    checks.append(ok)
    print(f"  Path planning: selected_path={path_plan.get('selected_path', '')!r} - {'OK' if ok else 'FAIL'}")

    sample_payload = {"response": "Sample response.", "recommendations": recommendations, "path_plan": path_plan}
    sample_guardrail = guardrail_agent.check_guardrails(
        response_payload=sample_payload, profile=profile, user_message=MESSAGE,
    )
    evaluation = evaluation_agent.evaluate(
        user_message=MESSAGE,
        response_payload=sample_payload,
        retrieved_context=retrieval,
        profile=profile,
        guardrail_result=sample_guardrail,
    )
    ok = evaluation.get("quality_badge") != "not_evaluated"
    checks.append(ok)
    print(f"  Evaluation: total_score={evaluation['total_score']}/30 badge={evaluation['quality_badge']} - {'OK' if ok else 'FAIL'}")

    print("\n5. Prompt versions appear in orchestrator result")
    print("-" * 60)
    from agents.orchestrator import run_turn

    result = run_turn(student_name=TEST_STUDENT, user_message=MESSAGE)
    version_keys = [
        "discovery_prompt_version",
        "recommendation_prompt_version",
        "path_planning_prompt_version",
        "evaluation_prompt_version",
        "guardrail_ruleset_version",
    ]
    for key in version_keys:
        print(f"  {key}: {result.get(key, '(MISSING)')}")
    ok = all(key in result for key in version_keys)
    checks.append(ok)
    print(f"  check: {'PASS' if ok else 'FAIL'} (all 5 prompt-version keys present in orchestrator result)")

    print("\n" + "=" * 60)
    print(f"{sum(checks)}/{len(checks)} checks passed.")
    print("=" * 60)


if __name__ == "__main__":
    if not config.has_openai_key():
        print("ERROR: OPENAI_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)
    if not config.has_pinecone_key():
        print("ERROR: PINECONE_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)

    run()
