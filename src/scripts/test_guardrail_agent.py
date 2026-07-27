"""
Test the Guardrail Agent's rule-based safety checks in isolation.

Usage (from project root, with .venv_win active):
    python src/scripts/test_guardrail_agent.py

What this script does:
    Constructs response_payload / profile / user_message inputs by hand (no LLM or
    Pinecone calls needed - GuardrailAgent is pure rule-based) and runs each of the
    7 required test cases through check_guardrails(), printing the result.

This script is read-only: it does not modify production code, call any external API,
or touch the SQLite database.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.guardrail_agent import GuardrailAgent


def _recommendations(items=None, summary="", follow_up_question=""):
    return {
        "recommendations": items or [],
        "summary": summary,
        "follow_up_question": follow_up_question,
    }


CASES = [
    {
        "name": "1. Admission guarantee",
        "response_payload": {
            "response": "You will get into Stanford with your current profile.",
            "recommendations": _recommendations(),
            "path_plan": {},
        },
        "profile": {"gpa": "3.8"},
        "user_message": "Will I get into Stanford?",
        "expect_flags": ["admission_guarantee"],
    },
    {
        "name": "2. Salary guarantee",
        "response_payload": {
            "response": "As a software engineer, you will definitely earn six figures right out of college.",
            "recommendations": _recommendations(),
            "path_plan": {},
        },
        "profile": {"interests": ["coding"]},
        "user_message": "What will I earn as a software engineer?",
        "expect_flags": ["salary_guarantee"],
    },
    {
        "name": "3. Missing GPA",
        "response_payload": {
            "response": "Based on your profile, here are some college options to consider for your future.",
            "recommendations": _recommendations(
                items=[{"title": "State University", "type": "college_pathway", "evidence": ["college_state_university"]}]
            ),
            "path_plan": {},
        },
        "profile": {"interests": ["biology"]},
        "user_message": "Can you recommend some colleges for me based on my interests?",
        "expect_flags": ["missing_gpa_for_college_guidance"],
    },
    {
        "name": "4. Missing budget",
        "response_payload": {
            "response": "Let's look at some affordable college options and scholarship opportunities for you.",
            "recommendations": _recommendations(
                items=[{"title": "Community College Path", "type": "college_pathway", "evidence": ["college_generic"]}]
            ),
            "path_plan": {},
        },
        "profile": {"interests": ["business"]},
        "user_message": "What are some affordable college options for someone interested in business?",
        "expect_flags": ["missing_budget_for_affordability_guidance"],
    },
    {
        "name": "5. Missing location",
        "response_payload": {
            "response": "Stanford University could be a strong fit for your interests in computer science.",
            "recommendations": _recommendations(
                items=[{"title": "Stanford University", "type": "college_pathway", "evidence": ["college_stanford"]}]
            ),
            "path_plan": {},
        },
        "profile": {"interests": ["computer science"], "gpa": "3.9"},
        "user_message": "What specific colleges would fit someone interested in computer science?",
        "expect_flags": ["missing_location_for_specific_college_guidance"],
    },
    {
        "name": "6. Safe recommendation",
        "response_payload": {
            "response": "These careers may be a good fit based on your interests in math and gaming.",
            "recommendations": _recommendations(
                items=[
                    {
                        "title": "Game Developer",
                        "type": "career",
                        "why_it_fits": "Combines your love of math and games.",
                        "evidence": ["career_game_developer"],
                    }
                ],
                summary="These careers may be a good fit based on your interests.",
                follow_up_question="Which of these sounds most interesting to you?",
            ),
            "path_plan": {},
        },
        "profile": {"interests": ["math", "video games"], "strengths": ["problem solving"]},
        "user_message": "I like math and video games, what careers might fit me?",
        "expect_flags": [],
    },
    {
        "name": "7. Overconfident career",
        "response_payload": {
            "response": "This is the perfect career for you and there is nothing else you should consider.",
            "recommendations": _recommendations(),
            "path_plan": {},
        },
        "profile": {"interests": ["art"]},
        "user_message": "What career fits someone who loves art?",
        "expect_flags": ["overconfidence"],
    },
]


def run(agent: GuardrailAgent) -> None:
    for case in CASES:
        result = agent.check_guardrails(
            response_payload=case["response_payload"],
            profile=case["profile"],
            user_message=case["user_message"],
        )

        print(f"\n{case['name']}")
        print("-" * len(case["name"]))
        print(f"passed: {result['passed']}")
        print(f"flags: {result['flags']}")
        print(f"risk_level: {result['risk_level']}")
        print(f"required_revisions: {result['required_revisions']}")

        missing = [f for f in case["expect_flags"] if f not in result["flags"]]
        status = "OK" if not missing else f"MISSING EXPECTED FLAGS: {missing}"
        print(f"check: {status}")


if __name__ == "__main__":
    run(GuardrailAgent())
