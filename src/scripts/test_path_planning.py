"""
Test the Path Planning Agent's GPT-4o-mini roadmap output for a set of student profiles.

Usage (from project root, with .venv_win active):
    python src/scripts/test_path_planning.py

What this script does:
    For each test student, runs RetrievalAgent -> RecommendationAgent -> PathPlanningAgent
    and prints the selected path plus top skills and top project ideas from the roadmap.
    Also runs a dedicated selection-priority test: given hand-built recommendations where
    a college_pathway item ranks above a career item, verifies PathPlanningAgent still
    selects the career (selection priority: career > major > college_pathway).

This script is read-only: it does not modify production code, Pinecone data, or the
SQLite database.

Prerequisites:
    OPENAI_API_KEY and PINECONE_API_KEY must be set in .env
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from infrastructure.openai_client import OpenAIClient
from infrastructure.pinecone_client import PineconeClient
from infrastructure.knowledge_loader import KnowledgeLoader
from services.embedding_service import EmbeddingService
from services.retrieval_service import RetrievalService
from services.llm_service import LLMService
from services.prompt_service import PromptService
from agents.retrieval_agent import RetrievalAgent
from agents.recommendation_agent import RecommendationAgent
from agents.path_planning_agent import PathPlanningAgent, _select_recommendation


TEST_STUDENTS = [
    {
        "label": "Gaming student",
        "message": "I like math and video games. What careers might fit me?",
        "profile": {"name": "GamingStudent", "grade_level": "10", "gpa": "3.5",
                     "interests": ["math", "video games"], "strengths": ["problem solving"]},
    },
    {
        "label": "Healthcare student",
        "message": "I enjoy helping people and healthcare.",
        "profile": {"name": "HealthcareStudent", "grade_level": "11", "gpa": "3.7",
                     "interests": ["healthcare", "helping people"], "strengths": ["empathy"]},
    },
    {
        "label": "Fashion student",
        "message": "I like fashion, creativity, and business.",
        "profile": {"name": "FashionStudent", "grade_level": "12", "gpa": "3.2",
                     "interests": ["fashion", "business"], "strengths": ["creativity"]},
    },
    {
        "label": "Trades student",
        "message": "I like building things with my hands.",
        "profile": {"name": "TradesStudent", "grade_level": "9", "gpa": "3.0",
                     "interests": ["building", "hands-on work"], "strengths": ["mechanical aptitude"]},
    },
    {
        "label": "Travel student",
        "message": "I enjoy travel, cultures, and languages.",
        "profile": {"name": "TravelStudent", "grade_level": "11", "gpa": "3.6",
                     "interests": ["travel", "languages"], "strengths": ["communication"]},
    },
]


PRIORITY_TEST_PROFILE = {
    "name": "PriorityTestStudent", "grade_level": "11", "gpa": "3.5",
    "interests": ["computer science"], "strengths": ["math"],
}

# College ranked first (index 0), career ranked second - PathPlanningAgent must still
# select the career per the priority order: career > major > college_pathway.
PRIORITY_TEST_RECOMMENDATIONS = {
    "summary": "A mix of college and career options.",
    "follow_up_question": "Which one interests you most?",
    "recommendations": [
        {
            "type": "college_pathway",
            "title": "Georgia Institute of Technology",
            "why_it_fits": "Strong computer science program.",
            "evidence": ["college_georgia_tech"],
        },
        {
            "type": "career",
            "title": "Software Engineer",
            "why_it_fits": "Matches your interest in computer science and math.",
            "evidence": ["career_software_engineer"],
        },
    ],
}


# Same scenario, but using type "college" instead of "college_pathway" - GPT-4o-mini does
# not always echo the exact "college_pathway" string the recommendation prompt asks for,
# so the selection logic must not depend on that literal value.
PRIORITY_TEST_RECOMMENDATIONS_TYPE_DRIFT = {
    "summary": "A mix of college and career options.",
    "follow_up_question": "Which one interests you most?",
    "recommendations": [
        {"type": "college", "title": "Carnegie Mellon University", "why_it_fits": "Strong CS program."},
        {"type": "career", "title": "Software Engineer", "why_it_fits": "Matches your interests."},
    ],
}


def run_priority_selection_test(path_planning_agent: PathPlanningAgent) -> None:
    label = "Priority test: college ranked above career"
    print(f"\n{label}")
    print("=" * len(label))

    # Deterministic, LLM-independent check of the selection logic itself.
    selected_item = _select_recommendation(PRIORITY_TEST_RECOMMENDATIONS["recommendations"])
    print(f"_select_recommendation() picked: {selected_item.get('title', '')} ({selected_item.get('type', '')})")
    selection_passed = selected_item.get("title") == "Software Engineer"
    print(f"Check: {'PASS' if selection_passed else 'FAIL'} (selection logic must pick the career, not the college)")

    # Same check, but with type "college" instead of "college_pathway" (real-world drift).
    drifted_item = _select_recommendation(PRIORITY_TEST_RECOMMENDATIONS_TYPE_DRIFT["recommendations"])
    print(f"_select_recommendation() picked (type drift case): {drifted_item.get('title', '')} ({drifted_item.get('type', '')})")
    drift_passed = drifted_item.get("title") == "Software Engineer"
    print(f"Check: {'PASS' if drift_passed else 'FAIL'} (must still pick the career when type is 'college', not 'college_pathway')")

    # End-to-end check through the full roadmap generation call.
    path_plan = path_planning_agent.generate_path_plan(
        profile=PRIORITY_TEST_PROFILE,
        recommendations=PRIORITY_TEST_RECOMMENDATIONS,
    )
    selected_path = path_plan.get("selected_path", "")
    print(f"generate_path_plan() selected_path: {selected_path}")

    e2e_passed = "Software Engineer" in selected_path and "Georgia Institute of Technology" not in selected_path
    print(f"Check: {'PASS' if e2e_passed else 'FAIL'} (expected career 'Software Engineer' to be selected over the college)")


def run(
    retrieval_agent: RetrievalAgent,
    recommendation_agent: RecommendationAgent,
    path_planning_agent: PathPlanningAgent,
) -> None:
    for student in TEST_STUDENTS:
        print(f"\n{student['label']}: \"{student['message']}\"")
        print("=" * (len(student["label"]) + len(student["message"]) + 4))

        retrieval = retrieval_agent.retrieve_relevant_context(
            user_message=student["message"],
            profile=student["profile"],
            top_k=5,
        )
        recommendations = recommendation_agent.generate_recommendations(
            user_message=student["message"],
            profile=student["profile"],
            retrieved_context=retrieval,
        )
        path_plan = path_planning_agent.generate_path_plan(
            profile=student["profile"],
            recommendations=recommendations,
        )

        print(f"Selected path: {path_plan.get('selected_path', '')}")

        skills = path_plan.get("skills_to_build", [])
        print(f"Top skills: {', '.join(skills[:3]) if skills else '(none)'}")

        projects = path_plan.get("suggested_projects", [])
        print(f"Top projects: {', '.join(projects[:3]) if projects else '(none)'}")


if __name__ == "__main__":
    if not config.has_openai_key():
        print("ERROR: OPENAI_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)
    if not config.has_pinecone_key():
        print("ERROR: PINECONE_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)

    openai_client = OpenAIClient()
    pinecone_client = PineconeClient()
    knowledge_loader = KnowledgeLoader()
    embedding_service = EmbeddingService(openai_client)
    retrieval_service = RetrievalService(embedding_service, pinecone_client, knowledge_loader)
    llm_service = LLMService(openai_client)
    prompt_service = PromptService()

    retrieval_agent = RetrievalAgent(retrieval_service)
    recommendation_agent = RecommendationAgent(llm_service, prompt_service)
    path_planning_agent = PathPlanningAgent(llm_service)

    run(retrieval_agent, recommendation_agent, path_planning_agent)
    run_priority_selection_test(path_planning_agent)
