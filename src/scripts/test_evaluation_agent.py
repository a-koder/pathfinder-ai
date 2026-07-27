"""
Test the Evaluation Agent's RASCEF scoring (GPT-4o LLM-as-judge) on hand-built cases.

Usage (from project root, with .venv_win active):
    python src/scripts/test_evaluation_agent.py

What this script does:
    Constructs response_payload / retrieved_context / profile / guardrail_result inputs
    by hand for 5 scenarios and runs each through EvaluationAgent.evaluate(), printing
    the RASCEF scores, total score, quality badge, requires_revision, and feedback.

This script calls the live OpenAI API (GPT-4o judge calls) but does not modify
production code, Pinecone data, or the SQLite database.

Prerequisites:
    OPENAI_API_KEY must be set in .env
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from infrastructure.openai_client import OpenAIClient
from services.llm_service import LLMService
from services.evaluation_service import EvaluationService
from agents.evaluation_agent import EvaluationAgent


def _recommendation(**kwargs) -> dict:
    base = {
        "type": "career",
        "title": "",
        "why_it_fits": "",
        "why_exciting": "",
        "opportunities": [],
        "real_world_impact": "",
        "related_majors": [],
        "skills_to_build": [],
        "adjacent_paths": [],
        "evidence": [],
        "confidence": 0.0,
        "risks_or_limitations": [],
        "next_steps": [],
    }
    base.update(kwargs)
    return base


CASES = [
    {
        "name": "1. Strong response with retrieved context",
        "user_message": "I like math and video games. What careers might fit me?",
        "response_payload": {
            "response": (
                "Thanks! Game Developer and Data Scientist could be strong fits for your love of "
                "math and video games."
            ),
            "recommendations": {
                "summary": "Game Developer and Data Scientist could be strong fits.",
                "follow_up_question": "Which one sounds more interesting to you?",
                "recommendations": [
                    _recommendation(
                        title="Game Developer",
                        why_it_fits="You enjoy math and video games, and game development blends both.",
                        why_exciting="You get to build the worlds people play in every day.",
                        opportunities=["Studios of all sizes hire developers", "Indie publishing is accessible"],
                        real_world_impact="Games entertain and connect millions of players.",
                        related_majors=["Computer Science", "Game Design"],
                        evidence=["career_game_developer"],
                        next_steps=["Try a beginner Unity tutorial", "Join a game jam"],
                    ),
                    _recommendation(
                        title="Data Scientist",
                        why_it_fits="Your math strength lines up with data analysis work.",
                        why_exciting="You turn raw numbers into decisions that matter.",
                        opportunities=["High demand across industries"],
                        real_world_impact="Data scientists help organizations make better decisions.",
                        related_majors=["Statistics", "Computer Science"],
                        evidence=["career_data_scientist"],
                        next_steps=["Take an intro statistics course", "Try a Kaggle beginner dataset"],
                    ),
                ],
            },
            "path_plan": {
                "selected_path": "Game Developer",
                "short_term_steps": ["Try a beginner Unity tutorial"],
                "medium_term_steps": ["Take a programming elective"],
                "long_term_steps": ["Consider a Computer Science major"],
                "skills_to_build": ["C#", "problem solving"],
                "suggested_projects": ["Build a small mobile game"],
                "college_preparation_steps": ["Take AP Computer Science if available"],
            },
        },
        "retrieved_context": {
            "retrieved_documents": [
                {"doc_id": "career_game_developer", "doc_type": "career", "title": "Game Developer", "score": 0.8},
                {"doc_id": "career_data_scientist", "doc_type": "career", "title": "Data Scientist", "score": 0.7},
            ],
        },
        "profile": {"interests": ["math", "video games"], "strengths": ["problem solving"]},
        "guardrail_result": {"passed": True, "flags": [], "risk_level": "low", "required_revisions": []},
    },
    {
        "name": "2. Response with no evidence",
        "user_message": "I like helping people. What careers might fit me?",
        "response_payload": {
            "response": "You might enjoy being a counselor or a social worker.",
            "recommendations": {
                "summary": "You might enjoy being a counselor or a social worker.",
                "follow_up_question": "Do either of these sound interesting?",
                "recommendations": [
                    _recommendation(title="Counselor", why_it_fits="You like helping people."),
                    _recommendation(title="Social Worker", why_it_fits="You like helping people."),
                ],
            },
            "path_plan": {},
        },
        "retrieved_context": {"retrieved_documents": []},
        "profile": {"interests": ["helping people"]},
        "guardrail_result": {"passed": True, "flags": ["missing_grounding"], "risk_level": "medium", "required_revisions": []},
    },
    {
        "name": "3. Response with admission guarantee",
        "user_message": "Will I get into Stanford with a 3.8 GPA?",
        "response_payload": {
            "response": "You will get into Stanford with a 3.8 GPA, no question.",
            "recommendations": {
                "summary": "You will get into Stanford with a 3.8 GPA, no question.",
                "follow_up_question": "",
                "recommendations": [
                    _recommendation(
                        title="Stanford University", type="college_pathway",
                        why_it_fits="Your GPA guarantees admission.",
                    ),
                ],
            },
            "path_plan": {},
        },
        "retrieved_context": {"retrieved_documents": []},
        "profile": {"gpa": "3.8"},
        "guardrail_result": {
            "passed": False, "flags": ["admission_guarantee"], "risk_level": "high",
            "required_revisions": ["Remove admission guarantee language; use reach/target/likely framing instead."],
        },
    },
    {
        "name": "4. Response with generic advice",
        "user_message": "What career should I pick?",
        "response_payload": {
            "response": "You could work hard and follow your passion to find a good career.",
            "recommendations": {"summary": "", "follow_up_question": "", "recommendations": []},
            "path_plan": {},
        },
        "retrieved_context": {"retrieved_documents": []},
        "profile": {},
        "guardrail_result": {"passed": True, "flags": ["insufficient_profile"], "risk_level": "low", "required_revisions": []},
    },
    {
        "name": "5. Good recommendations but missing next steps",
        "user_message": "I like fashion and business. What careers might fit me?",
        "response_payload": {
            "response": "Fashion Designer and Fashion Merchandiser could both be strong fits for you.",
            "recommendations": {
                "summary": "Fashion Designer and Fashion Merchandiser could both be strong fits for you.",
                "follow_up_question": "Which one appeals to you more?",
                "recommendations": [
                    _recommendation(
                        title="Fashion Designer",
                        why_it_fits="You enjoy fashion and creativity.",
                        why_exciting="You get to bring original designs to life.",
                        evidence=["career_fashion_designer"],
                    ),
                    _recommendation(
                        title="Fashion Merchandiser",
                        why_it_fits="You enjoy fashion and business together.",
                        why_exciting="You help shape what shoppers see and buy.",
                        evidence=["career_fashion_merchandiser"],
                    ),
                ],
            },
            "path_plan": {},
        },
        "retrieved_context": {
            "retrieved_documents": [
                {"doc_id": "career_fashion_designer", "doc_type": "career", "title": "Fashion Designer", "score": 0.8},
            ],
        },
        "profile": {"interests": ["fashion", "business"]},
        "guardrail_result": {"passed": True, "flags": [], "risk_level": "low", "required_revisions": []},
    },
]


def run(agent: EvaluationAgent) -> None:
    for case in CASES:
        result = agent.evaluate(
            user_message=case["user_message"],
            response_payload=case["response_payload"],
            retrieved_context=case["retrieved_context"],
            profile=case["profile"],
            guardrail_result=case["guardrail_result"],
        )

        print(f"\n{case['name']}")
        print("-" * len(case["name"]))
        print(f"scores: {result['scores']}")
        print(f"total_score: {result['total_score']}/{result['max_score']}")
        print(f"quality_badge: {result['quality_badge']}")
        print(f"requires_revision: {result['requires_revision']}")
        print(f"feedback: {result['feedback']}")


if __name__ == "__main__":
    if not config.has_openai_key():
        print("ERROR: OPENAI_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)

    openai_client = OpenAIClient()
    llm_service = LLMService(openai_client)
    evaluation_service = EvaluationService(llm_service)
    evaluation_agent = EvaluationAgent(evaluation_service)

    run(evaluation_agent)
