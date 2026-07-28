import concurrent.futures
import time
from datetime import datetime, timezone

import config
from infrastructure.sqlite_client import SQLiteClient
from infrastructure.openai_client import OpenAIClient
from infrastructure.pinecone_client import PineconeClient
from infrastructure.knowledge_loader import KnowledgeLoader
from repositories.student_repository import StudentRepository
from repositories.profile_repository import ProfileRepository
from repositories.message_repository import MessageRepository
from repositories.conversation_summary_repository import ConversationSummaryRepository
from repositories.observability_repository import ObservabilityRepository
from services.embedding_service import EmbeddingService
from services.retrieval_service import RetrievalService
from services.llm_service import LLMService
from services.prompt_service import PromptService
from services.evaluation_service import EvaluationService

from agents.memory_agent import MemoryAgent
from agents.input_guardrail_agent import InputGuardrailAgent
from agents.discovery_agent import DiscoveryAgent
from agents.retrieval_agent import RetrievalAgent
from agents.recommendation_agent import RecommendationAgent
from agents.path_planning_agent import PathPlanningAgent
from agents.guardrail_agent import GuardrailAgent
from agents.evaluation_agent import EvaluationAgent
from agents.observability_agent import ObservabilityAgent


# ── Infrastructure startup ────────────────────────────────────────────────────
_sqlite = SQLiteClient()
_sqlite.create_tables()

_student_repo = StudentRepository(_sqlite)
_profile_repo = ProfileRepository(_sqlite)
_message_repo = MessageRepository(_sqlite)
_summary_repo = ConversationSummaryRepository(_sqlite)
_observability_repo = ObservabilityRepository(_sqlite)

# ── Service wiring ────────────────────────────────────────────────────────────
_openai_client = OpenAIClient()
_pinecone_client = PineconeClient()
_knowledge_loader = KnowledgeLoader()
_embedding_service = EmbeddingService(_openai_client)
_retrieval_service = RetrievalService(_embedding_service, _pinecone_client, _knowledge_loader)
_llm_service = LLMService(_openai_client)
_prompt_service = PromptService()
_evaluation_service = EvaluationService(_llm_service)

# ── Agent wiring ──────────────────────────────────────────────────────────────
_memory = MemoryAgent(_student_repo, _profile_repo, _message_repo, _summary_repo)
_input_guardrail = InputGuardrailAgent()
_discovery = DiscoveryAgent(_llm_service)
_retrieval = RetrievalAgent(_retrieval_service)
_recommendation = RecommendationAgent(_llm_service, _prompt_service)
_path_planning = PathPlanningAgent(_llm_service)
_guardrail = GuardrailAgent()
_evaluation = EvaluationAgent(_evaluation_service)
_observability = ObservabilityAgent(_observability_repo)


_HIGH_RISK_SAFE_NOTE = (
    "I want to keep this guidance realistic and exploratory. Final college or career "
    "decisions should be discussed with a counselor, parent, or trusted advisor."
)

_REVISION_NEEDED_NOTE = (
    "This guidance may need more information to be more precise. Sharing GPA, location, "
    "budget, or preferred learning style can improve the recommendation."
)


def _apply_guardrail_note(response_text: str, guardrail: dict) -> str:
    """
    Appends the fixed safety note to the stored response text when risk is high - that's
    a real safety consideration, important enough to persist even in restored/stored
    history. Medium-risk "keep in mind" nudges (e.g. "share your GPA") are deliberately
    NOT baked in here - they're rendered live-only by the UI (see chat.py's
    _render_notes), deduped per session so a recurring flag doesn't repeat verbatim on
    every single turn. guardrail_required_revisions is still returned on every turn's
    result for the UI to use; this function just controls what gets permanently stored.
    """
    if guardrail.get("risk_level", "low") == "high":
        return f"{response_text}\n\n_{_HIGH_RISK_SAFE_NOTE}_"
    return response_text


def _format_response_text(student_name: str, recommendations: dict) -> str:
    """Turns a RecommendationOutput-shaped dict into a readable counselor-style message."""
    items = recommendations.get("recommendations", [])
    summary = (recommendations.get("summary") or "").strip()
    follow_up = (recommendations.get("follow_up_question") or "").strip()

    greeting = f"Thanks, {student_name}!" if student_name else "Thanks!"
    lines = [f"{greeting} {summary}".strip() if summary else greeting]

    for i, item in enumerate(items, start=1):
        title = (item.get("title") or "").strip()
        if not title:
            continue
        lines.append(f"\n**{i}. {title}**")

        why_it_fits = (item.get("why_it_fits") or "").strip()
        if why_it_fits:
            lines.append(why_it_fits)

        why_exciting = (item.get("why_exciting") or "").strip()
        if why_exciting:
            lines.append(why_exciting)

        next_steps = item.get("next_steps") or []
        if next_steps:
            lines.append("Next steps: " + "; ".join(next_steps[:3]))

    if follow_up:
        lines.append(f"\n{follow_up}")

    return "\n".join(lines).strip()


_ENRICHMENT_SYSTEM_PROMPT = (
    "You add short, engaging, positively-framed enrichment to a list of career, major, or "
    "college recommendations for a high school student. For each title given, provide: "
    "1) 2 to 3 short fun facts (concrete and specific, not generic filler) and 2) a one-sentence "
    "future outlook framed positively (e.g. growing field, emerging opportunity, increasing "
    "demand, strong societal impact) - never promise a guaranteed salary, admission, or job "
    "outcome. Respond as JSON: "
    '{"enrichment": {"<exact title>": {"fun_facts": ["...", "..."], "future_outlook": "..."}}}. '
    "Include every title given, using the exact same spelling."
)


def _enrich_recommendations(recommendation_items: list[dict]) -> list[dict]:
    """
    Adds fun_facts and future_outlook to each recommendation, for display only. Generated
    fresh every turn from a small standalone LLM call - not the RecommendationAgent's prompt
    or logic - and run after guardrails/evaluation have already scored the response, so it
    never affects RASCEF scoring or guardrail checks. Never persisted.
    """
    titles = [item.get("title", "") for item in recommendation_items if item.get("title")]
    if not titles:
        return recommendation_items

    enrichment = {}
    try:
        user_prompt = "Titles:\n" + "\n".join(f"- {title}" for title in titles)
        raw = _llm_service.generate_json(system_prompt=_ENRICHMENT_SYSTEM_PROMPT, user_prompt=user_prompt)
        if isinstance(raw, dict):
            enrichment = raw.get("enrichment", {}) or {}
    except Exception:
        enrichment = {}

    enriched = []
    for item in recommendation_items:
        entry = dict(item)
        details = enrichment.get(item.get("title", ""), {}) if isinstance(enrichment, dict) else {}
        details = details if isinstance(details, dict) else {}
        fun_facts = details.get("fun_facts")
        entry["fun_facts"] = [str(fact) for fact in fun_facts][:3] if isinstance(fun_facts, list) else []
        future_outlook = details.get("future_outlook")
        entry["future_outlook"] = future_outlook if isinstance(future_outlook, str) else ""
        enriched.append(entry)

    return enriched


def _generate_and_score(
    student_name: str,
    user_message: str,
    current_profile: dict,
    retrieval: dict,
    input_guardrail_flags: list,
    revision_attempted: bool,
) -> tuple[dict, dict, str, dict, dict, dict]:
    """
    Runs one full generate-and-check attempt: recommendation -> path planning -> response
    assembly -> post-generation guardrails -> RASCEF evaluation. Used for both the initial
    attempt and the single critic/revision retry, so both attempts go through identical logic.
    """
    recommendations = _recommendation.generate_recommendations(
        user_message=user_message,
        profile=current_profile,
        retrieved_context=retrieval,
    )

    path_plan = _path_planning.generate_path_plan(
        profile=current_profile,
        recommendations=recommendations,
    )

    response_text = _format_response_text(student_name, recommendations)
    response_payload = {
        "response": response_text,
        "recommendations": recommendations,
        "path_plan": path_plan,
    }

    guardrail = _guardrail.check_guardrails(
        response_payload=response_payload,
        profile=current_profile,
        user_message=user_message,
    )
    response_text = _apply_guardrail_note(response_text, guardrail)
    response_payload["response"] = response_text

    evaluation = _evaluation.evaluate(
        user_message=user_message,
        response_payload=response_payload,
        retrieved_context=retrieval,
        profile=current_profile,
        guardrail_result=guardrail,
        input_guardrail_flags=input_guardrail_flags,
        revision_attempted=revision_attempted,
    )

    return recommendations, path_plan, response_text, response_payload, guardrail, evaluation


def submit_feedback(log_id: int, helpful: bool, feedback_text: str | None = None) -> None:
    """Records human-in-the-loop feedback against one observability log row. Swallows failures."""
    try:
        _observability_repo.save_feedback(log_id, helpful, feedback_text)
    except Exception:
        pass


def load_history(student_name: str) -> list[dict]:
    """
    Returns this student's recent stored messages ({role, content, timestamp}, oldest
    first) so the UI can repopulate the chat window on a return visit - the AI already
    silently recalls this via memory.load_memory() every turn, this just makes the same
    stored history visible. Swallows failures, returning an empty list rather than
    breaking the page.
    """
    try:
        memory = _memory.load_memory(student_name)
        return memory.get("recent_messages", [])
    except Exception:
        return []


def get_profile_snapshot(student_name: str) -> dict:
    """
    Returns a lightweight snapshot of what PathFinder already knows about this student
    (interests, GPA, grade level, favorite careers) - lets the UI show a live "what we
    know about you" summary instead of a static, generic sidebar. Swallows failures,
    returning {} rather than breaking the page.
    """
    try:
        memory = _memory.load_memory(student_name)
        return memory.get("profile", {})
    except Exception:
        return {}


def run_turn(student_name: str, user_message: str) -> dict:
    """
    Coordinates all agents in sequence and returns a typed result dict.

    Agent sequence:
      input guardrail → memory.load → [discovery ‖ retrieval] → merge profile →
      recommendation → path_planning → guardrail → evaluation →
      (critic/revision retry, max 1) → observability → memory.save

    Discovery and Retrieval run concurrently on worker threads: Discovery only needs the
    pre-turn profile from memory.load, and Retrieval only needs the raw user_message (its
    `profile` argument is accepted but unused - see RetrievalAgent) - neither depends on the
    other's output, so there is no behavior change from running them in parallel.
    """
    start_time = time.perf_counter()

    # 1. Input guardrail - detection only, a pure function of the raw message, so it can run
    # before memory load with no change in output.
    input_guardrail = _input_guardrail.check_input(user_message)

    # 2. Load memory (profile + recent messages)
    memory = _memory.load_memory(student_name)
    student_id = memory.get("student_id")

    # 3 & 4. Discovery (needs memory's pre-turn profile) and Retrieval (needs only the
    # message) are independent of each other, so they run concurrently. Both are I/O-bound
    # network calls (OpenAI / Pinecone), so this overlaps wait time rather than parallelizing
    # CPU work - expected to shave roughly the smaller of the two calls' latency off the turn
    # (typically ~1-2s) compared to running them back to back.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        discovery_future = pool.submit(
            _discovery.extract_profile_updates,
            student_name=student_name,
            user_message=user_message,
            existing_profile=memory["profile"],
        )
        retrieval_future = pool.submit(
            _retrieval.retrieve_relevant_context,
            user_message=user_message,
            profile=memory["profile"],
            top_k=5,
        )
        discovery = discovery_future.result()
        retrieval = retrieval_future.result()

    # 4b. Merge and persist the updated profile - depends on Discovery's output, so this
    # happens only after both parallel branches have finished.
    current_profile = _memory.update_profile(
        student_name=student_name,
        profile_updates=discovery["student_profile_updates"],
    )

    input_guardrail_flags = input_guardrail.get("flags", [])

    # 5-9. Generate recommendations, path plan, response, guardrails, and evaluation
    recommendations, path_plan, response_text, response_payload, guardrail, evaluation = _generate_and_score(
        student_name, user_message, current_profile, retrieval,
        input_guardrail_flags=input_guardrail_flags, revision_attempted=False,
    )

    # 9b. Critic / revision loop - at most one retry, only when the RASCEF score is low
    revision_attempted = False
    if evaluation.get("requires_revision"):  # equivalent to evaluation["total_score"] < 24
        revision_attempted = True
        recommendations, path_plan, response_text, response_payload, guardrail, evaluation = _generate_and_score(
            student_name, user_message, current_profile, retrieval,
            input_guardrail_flags=input_guardrail_flags, revision_attempted=True,
        )

    # 9c. Append a note if the (possibly revised) response still needs more information
    if evaluation.get("requires_revision"):
        response_text = f"{response_text}\n\n_{_REVISION_NEEDED_NOTE}_"
        response_payload["response"] = response_text

    # 9d. Display-only enrichment (fun facts, future outlook) - runs after guardrails and
    # evaluation have already scored the response, so it never affects RASCEF or guardrails.
    enriched_recommendation_items = _enrich_recommendations(recommendations.get("recommendations", []))

    # 10. Log turn to observability - never let a logging failure break the response
    end_time = time.perf_counter()
    log_id = None
    try:
        log_id = _observability.log_turn({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "student_id": student_id,
            "student_name": student_name,
            "user_message": user_message,
            "model": config.DEFAULT_MODEL,
            "evaluation_model": config.EVAL_MODEL,
            "embedding_model": config.EMBEDDING_MODEL,
            "retrieved_document_count": len(retrieval.get("retrieved_documents", [])),
            "guardrail_flags": guardrail.get("flags", []),
            "guardrail_risk_level": guardrail.get("risk_level", "low"),
            "input_guardrail_flags": input_guardrail_flags,
            "evaluation_score": evaluation.get("total_score", 0),
            "quality_badge": evaluation.get("quality_badge", "not_evaluated"),
            "evaluation_scores": evaluation.get("scores", {}),
            "prompt_versions": config.prompt_version_metadata(),
            "revision_attempted": revision_attempted,
            "latency_ms": int((end_time - start_time) * 1000),
            "error": "",
        })
    except Exception:
        pass

    # 11. Save turn to memory
    _memory.save_turn(
        student_name=student_name,
        user_message=user_message,
        assistant_response=response_text,
        metadata={
            "evaluation_score": evaluation.get("total_score", 0),
            "guardrail_flags": guardrail.get("flags", []),
        },
    )

    return {
        "student_name": student_name,
        "response": response_text,
        "quality_badge": evaluation.get("quality_badge", "not_evaluated"),
        "guardrail_flags": guardrail.get("flags", []),
        "guardrail_risk_level": guardrail.get("risk_level", "low"),
        "guardrail_required_revisions": guardrail.get("required_revisions", []),
        "input_guardrail_flags": input_guardrail_flags,
        "evaluation_score": evaluation.get("total_score", 0),
        "evaluation_feedback": evaluation.get("feedback", []),
        "evaluation_scores": evaluation.get("scores", {}),
        "evaluation_requires_revision": evaluation.get("requires_revision", False),
        "revision_attempted": revision_attempted,
        "retrieved_document_count": len(retrieval.get("retrieved_documents", [])),
        "retrieved_documents": retrieval.get("retrieved_documents", []),
        "recommendations": enriched_recommendation_items,
        "recommendation_summary": recommendations.get("summary", ""),
        "follow_up_question": recommendations.get("follow_up_question", ""),
        "profile": current_profile,
        "missing_information": discovery.get("missing_information", []),
        "next_question": discovery.get("next_question", ""),
        "path_plan": path_plan,
        "observability_log_id": log_id,
        **config.prompt_version_metadata(),
    }
