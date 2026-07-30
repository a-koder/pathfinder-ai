"""
Golden-dataset accuracy test for the Intent Router Agent (decision D034).

Usage (from project root, with .venv_win active):
    python src/scripts/test_intent_router.py

What this script does:
    Unlike every other manual test script in this folder (eyeball/acceptance-style),
    this one computes real classification metrics - per-class precision/recall/F1 and
    a confusion matrix - because intent routing is the one stage in this system with
    genuine, checkable ground truth. RASCEF quality scoring is inherently subjective
    (a 1-5 LLM judgment call); "explore" vs "roadmap" vs "related_topic" vs "general_chat"
    is a discrete label a human can verify a test case against in advance.

    Runs IntentRouterAgent.classify_intent() against a curated set of 20 hand-written
    cases (5 per intent) against the real OpenAI API - no mocks, consistent with every
    other script in this folder.

Prerequisites:
    OPENAI_API_KEY must be set in .env
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from infrastructure.openai_client import OpenAIClient
from services.llm_service import LLMService
from agents.intent_router_agent import IntentRouterAgent

_INTENTS = ["explore", "roadmap", "related_topic", "general_chat"]

# What "good" means for this test, stated explicitly rather than left as raw numbers to
# eyeball (unlike RASCEF's 24/30 or the guardrail's pass/fail, this test had no declared
# bar until decision D035's fix was verified against one). Misrouting is user-visible and
# silent - a student never sees "intent classification failed," they just get the wrong
# flow - so the bar is intentionally stricter than RASCEF's: 90% overall, and no single
# intent allowed to fall below 80% recall, since a systematically-weak class is a worse
# signal than the same number of errors spread evenly across classes.
_MIN_OVERALL_ACCURACY = 0.90
_MIN_ANCHOR_ACCURACY = 0.90
_MIN_PER_CLASS_RECALL = 0.80

_DEFAULT_LAST_RECS = [
    {"title": "Data Scientist", "type": "career"},
    {"title": "Software Engineer", "type": "career"},
    {"title": "University of Michigan", "type": "college_pathway"},
]


def _turn(role: str, content: str) -> dict:
    return {"role": role, "content": content}


GOLDEN_DATASET = [
    # ---- explore (5): new recommendations, no clear anchor to something already offered ----
    {
        "label": "explore-1: first message, no prior context",
        "recent_messages": [],
        "last_recommendations": [],
        "user_message": "I like gaming and math, what career fits me?",
        "expected_intent": "explore",
        "expected_anchor_title": None,
    },
    {
        "label": "explore-2: new unrelated topic despite prior recommendations",
        "recent_messages": [
            _turn("user", "I like coding and data."),
            _turn("assistant", "Great! Data Scientist and Software Engineer could be strong fits."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "Actually, what careers involve working with animals?",
        "expected_intent": "explore",
        "expected_anchor_title": None,
    },
    {
        "label": "explore-3: explicit ask for different/more options",
        "recent_messages": [
            _turn("user", "I like coding and data."),
            _turn("assistant", "Data Scientist and Software Engineer could be strong fits."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "Can you show me some completely different career options?",
        "expected_intent": "explore",
        "expected_anchor_title": None,
    },
    {
        "label": "explore-4: pivoting to a new stated interest",
        "recent_messages": [
            _turn("user", "I like coding and data."),
            _turn("assistant", "Data Scientist and Software Engineer could be strong fits."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "I've actually decided I want to explore business and entrepreneurship instead.",
        "expected_intent": "explore",
        "expected_anchor_title": None,
    },
    {
        "label": "explore-5: implicit reference with nothing to anchor to",
        "recent_messages": [],
        "last_recommendations": [],
        "user_message": "Can you build a roadmap for that?",
        "expected_intent": "explore",
        "expected_anchor_title": None,
    },
    # ---- roadmap (5): a plan for something already offered, exact or implicit ----
    {
        "label": "roadmap-1: exact title match",
        "recent_messages": [
            _turn("user", "I like coding and data."),
            _turn("assistant", "Data Scientist and Software Engineer could be strong fits."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "Can you give me a roadmap for Software Engineer?",
        "expected_intent": "roadmap",
        "expected_anchor_title": "Software Engineer",
    },
    {
        "label": "roadmap-2: implicit 'that one' right after discussing one item",
        "recent_messages": [
            _turn("user", "Tell me more about Data Scientist specifically."),
            _turn("assistant", "Data Scientist involves statistics, Python, and machine learning."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "Ok, give me a plan for that one.",
        "expected_intent": "roadmap",
        "expected_anchor_title": "Data Scientist",
    },
    {
        "label": "roadmap-3: 'same' referring to the just-discussed item",
        "recent_messages": [
            _turn("user", "What would it take to become a Software Engineer?"),
            _turn("assistant", "Software Engineer typically needs strong programming skills and a CS-related degree."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "roadmap for same please",
        "expected_intent": "roadmap",
        "expected_anchor_title": "Software Engineer",
    },
    {
        "label": "roadmap-4: ordinal reference ('the first one')",
        "recent_messages": [
            _turn("user", "I like coding and data."),
            _turn("assistant", "Here are three options: 1. Data Scientist 2. Software Engineer 3. University of Michigan."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "What's the roadmap for the first option?",
        "expected_intent": "roadmap",
        "expected_anchor_title": "Data Scientist",
    },
    {
        "label": "roadmap-5: differently-phrased plan request, exact title",
        "recent_messages": [
            _turn("user", "I like coding and data."),
            _turn("assistant", "Data Scientist and Software Engineer could be strong fits."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "What steps should I take to become a Data Scientist?",
        "expected_intent": "roadmap",
        "expected_anchor_title": "Data Scientist",
    },
    # ---- related_topic (5): more career/college info tied to an established anchor ----
    {
        "label": "related_topic-1: colleges for a named career",
        "recent_messages": [
            _turn("user", "I like coding and data."),
            _turn("assistant", "Data Scientist and Software Engineer could be strong fits."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "What colleges would be good for Data Scientist?",
        "expected_intent": "related_topic",
        "expected_anchor_title": "Data Scientist",
    },
    {
        "label": "related_topic-2: implicit 'that path' college follow-up",
        "recent_messages": [
            _turn("user", "Tell me more about Software Engineer."),
            _turn("assistant", "Software Engineer involves building and maintaining software systems."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "Any good colleges for that path?",
        "expected_intent": "related_topic",
        "expected_anchor_title": "Software Engineer",
    },
    {
        "label": "related_topic-3: similar careers to a named one",
        "recent_messages": [
            _turn("user", "I like coding and data."),
            _turn("assistant", "Data Scientist and Software Engineer could be strong fits."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "Are there careers similar to Software Engineer I should consider?",
        "expected_intent": "related_topic",
        "expected_anchor_title": "Software Engineer",
    },
    {
        "label": "related_topic-4: 'the second one' info request (not a plan)",
        "recent_messages": [
            _turn("user", "I like coding and data."),
            _turn("assistant", "Here are three options: 1. Data Scientist 2. Software Engineer 3. University of Michigan."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "Can you tell me more about the second one and similar roles?",
        "expected_intent": "related_topic",
        "expected_anchor_title": "Software Engineer",
    },
    {
        "label": "related_topic-5: affordability-scoped follow-up on 'this'",
        "recent_messages": [
            _turn("user", "What would it take to become a Data Scientist?"),
            _turn("assistant", "Data Scientist typically needs strong statistics and programming skills."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "What about affordable public schools for this?",
        "expected_intent": "related_topic",
        "expected_anchor_title": "Data Scientist",
    },
    # ---- general_chat (5): genuine questions outside the recommendation flow ----
    {
        "label": "general_chat-1: term definition",
        "recent_messages": [
            _turn("user", "I like coding and data."),
            _turn("assistant", "Data Scientist and Software Engineer could be strong fits."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "What does deferred admission mean?",
        "expected_intent": "general_chat",
        "expected_anchor_title": None,
    },
    {
        "label": "general_chat-2: financial aid process question",
        "recent_messages": [],
        "last_recommendations": [],
        "user_message": "How does financial aid work in general?",
        "expected_intent": "general_chat",
        "expected_anchor_title": None,
    },
    {
        "label": "general_chat-3: essay help request",
        "recent_messages": [
            _turn("user", "I like coding and data."),
            _turn("assistant", "Data Scientist and Software Engineer could be strong fits."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "Can you help me brainstorm a topic for my college essay?",
        "expected_intent": "general_chat",
        "expected_anchor_title": None,
    },
    {
        "label": "general_chat-4: deadline question",
        "recent_messages": [],
        "last_recommendations": [],
        "user_message": "When is the FAFSA deadline usually?",
        "expected_intent": "general_chat",
        "expected_anchor_title": None,
    },
    {
        "label": "general_chat-5: unrelated small talk",
        "recent_messages": [
            _turn("user", "I like coding and data."),
            _turn("assistant", "Data Scientist and Software Engineer could be strong fits."),
        ],
        "last_recommendations": _DEFAULT_LAST_RECS,
        "user_message": "Totally unrelated - what's a fun fact about octopuses?",
        "expected_intent": "general_chat",
        "expected_anchor_title": None,
    },
]


def _print_confusion_matrix(results: list[dict]) -> None:
    matrix = {actual: {predicted: 0 for predicted in _INTENTS} for actual in _INTENTS}
    for r in results:
        matrix[r["expected_intent"]][r["predicted_intent"]] += 1

    header = "actual \\ predicted".ljust(20) + "".join(i[:10].ljust(16) for i in _INTENTS)
    print(header)
    for actual in _INTENTS:
        row = actual.ljust(20) + "".join(str(matrix[actual][p]).ljust(16) for p in _INTENTS)
        print(row)


def _print_metrics(results: list[dict]) -> list[str]:
    """Returns a list of per-class recall violations (empty if none) so the caller can
    fold them into the overall verdict."""
    print(f"\nPer-class precision / recall / F1 (recall floor: {_MIN_PER_CLASS_RECALL:.0%}):")
    violations = []
    for intent in _INTENTS:
        tp = sum(1 for r in results if r["expected_intent"] == intent and r["predicted_intent"] == intent)
        fp = sum(1 for r in results if r["expected_intent"] != intent and r["predicted_intent"] == intent)
        fn = sum(1 for r in results if r["expected_intent"] == intent and r["predicted_intent"] != intent)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        flag = "" if recall >= _MIN_PER_CLASS_RECALL else "  <-- below recall floor"
        print(f"  {intent:15} precision={precision:.2f}  recall={recall:.2f}  f1={f1:.2f}  (support={tp + fn}){flag}")
        if recall < _MIN_PER_CLASS_RECALL:
            violations.append(f"{intent} recall {recall:.0%} < {_MIN_PER_CLASS_RECALL:.0%} floor")
    return violations


def run(agent: IntentRouterAgent) -> None:
    results = []
    for case in GOLDEN_DATASET:
        outcome = agent.classify_intent(
            user_message=case["user_message"],
            recent_messages=case["recent_messages"],
            last_recommendations=case["last_recommendations"],
        )
        predicted_intent = outcome.get("intent")
        predicted_anchor = outcome.get("anchor_title")
        intent_correct = predicted_intent == case["expected_intent"]
        anchor_correct = predicted_anchor == case["expected_anchor_title"]

        results.append({
            "label": case["label"],
            "expected_intent": case["expected_intent"],
            "predicted_intent": predicted_intent,
            "expected_anchor_title": case["expected_anchor_title"],
            "predicted_anchor": predicted_anchor,
            "intent_correct": intent_correct,
            "anchor_correct": anchor_correct,
        })

        status = "PASS" if intent_correct and anchor_correct else "FAIL"
        print(f"[{status}] {case['label']}")
        print(f"    message: \"{case['user_message']}\"")
        print(f"    expected intent={case['expected_intent']!r} anchor={case['expected_anchor_title']!r}")
        print(f"    got      intent={predicted_intent!r} anchor={predicted_anchor!r}")
        if outcome.get("reasoning"):
            print(f"    reasoning: {outcome['reasoning']}")
        print()

    print("=" * 70)
    print("CONFUSION MATRIX (rows = expected, cols = predicted)")
    print("=" * 70)
    _print_confusion_matrix(results)
    recall_violations = _print_metrics(results)

    intent_accuracy = sum(r["intent_correct"] for r in results) / len(results)
    anchor_cases = [r for r in results if r["expected_anchor_title"] is not None]
    anchor_accuracy = (
        sum(r["anchor_correct"] for r in anchor_cases) / len(anchor_cases) if anchor_cases else 1.0
    )

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Overall intent accuracy: {intent_accuracy:.1%} ({sum(r['intent_correct'] for r in results)}/{len(results)})"
          f"  [floor: {_MIN_OVERALL_ACCURACY:.0%}]")
    print(f"Anchor resolution accuracy (roadmap/related_topic cases only): "
          f"{anchor_accuracy:.1%} ({sum(r['anchor_correct'] for r in anchor_cases)}/{len(anchor_cases)})"
          f"  [floor: {_MIN_ANCHOR_ACCURACY:.0%}]")

    failures = [r for r in results if not (r["intent_correct"] and r["anchor_correct"])]
    if failures:
        print(f"\n{len(failures)} case(s) failed:")
        for r in failures:
            print(f"  - {r['label']}")
    else:
        print("\nAll cases passed.")

    verdict_pass = (
        intent_accuracy >= _MIN_OVERALL_ACCURACY
        and anchor_accuracy >= _MIN_ANCHOR_ACCURACY
        and not recall_violations
    )
    print("\n" + "=" * 70)
    print(f"VERDICT: {'PASS' if verdict_pass else 'FAIL'}")
    print("=" * 70)
    if not verdict_pass:
        if intent_accuracy < _MIN_OVERALL_ACCURACY:
            print(f"  - Overall accuracy {intent_accuracy:.1%} is below the {_MIN_OVERALL_ACCURACY:.0%} floor.")
        if anchor_accuracy < _MIN_ANCHOR_ACCURACY:
            print(f"  - Anchor accuracy {anchor_accuracy:.1%} is below the {_MIN_ANCHOR_ACCURACY:.0%} floor.")
        for v in recall_violations:
            print(f"  - {v}")


if __name__ == "__main__":
    if not config.has_openai_key():
        print("ERROR: OPENAI_API_KEY is not configured. Add it to .env and retry.")
        sys.exit(1)

    openai_client = OpenAIClient()
    llm_service = LLMService(openai_client)
    intent_router = IntentRouterAgent(llm_service)

    run(intent_router)
