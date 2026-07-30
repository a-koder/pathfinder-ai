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
from services.prompt_loader import load_prompt
from services.evaluation_service import EvaluationService
from services.tracing_service import TracingService
from services.usage_tracker import UsageTracker

from agents.memory_agent import MemoryAgent
from agents.input_guardrail_agent import InputGuardrailAgent
from agents.intent_router_agent import IntentRouterAgent
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
_tracing_service = TracingService()

# ── Agent wiring ──────────────────────────────────────────────────────────────
# One shared TracingService instance goes into every agent whose stage is worth tracing
# (the reasoning/decision steps in the "At a Glance" diagram) - Memory Agent and
# Observability Agent are deliberately excluded, since they're bookkeeping steps already
# logged to SQLite, not AI decision points LangSmith is meant to explain.
_memory = MemoryAgent(_student_repo, _profile_repo, _message_repo, _summary_repo)
_input_guardrail = InputGuardrailAgent(tracing_service=_tracing_service)
_intent_router = IntentRouterAgent(_llm_service, tracing_service=_tracing_service)
_discovery = DiscoveryAgent(_llm_service, tracing_service=_tracing_service)
_retrieval = RetrievalAgent(_retrieval_service, tracing_service=_tracing_service)
_recommendation = RecommendationAgent(_llm_service, _prompt_service, tracing_service=_tracing_service)
_path_planning = PathPlanningAgent(_llm_service, tracing_service=_tracing_service)
_guardrail = GuardrailAgent(tracing_service=_tracing_service)
_evaluation = EvaluationAgent(_evaluation_service, tracing_service=_tracing_service)
_observability = ObservabilityAgent(_observability_repo)


_HIGH_RISK_SAFE_NOTE = (
    "I want to keep this guidance realistic and exploratory. Final college or career "
    "decisions should be discussed with a counselor, parent, or trusted advisor."
)

_REVISION_NEEDED_NOTE = (
    "This guidance may need more information to be more precise. Sharing GPA, location, "
    "budget, or preferred learning style can improve the recommendation."
)

_PROMPT_INJECTION_SAFE_RESPONSE = (
    "I want to keep our conversation focused on your career and college questions. "
    "Could you tell me more about your interests, or ask me something about careers, "
    "majors, or colleges you're curious about?"
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


def _format_roadmap_only_response_text(student_name: str, anchor_title: str) -> str:
    """Used for the intent router's "roadmap" flow: the recommendation cards are reused
    verbatim (rendered separately by the UI), so the response text just introduces the
    roadmap instead of re-listing why_it_fits/why_exciting/next_steps for every card again."""
    greeting = f"Thanks, {student_name}!" if student_name else "Thanks!"
    return f"{greeting} Here's your roadmap for {anchor_title}."


_GENERAL_CHAT_SYSTEM_PROMPT = load_prompt("general_chat", config.GENERAL_CHAT_PROMPT_VERSION)


def _generate_general_chat_response(
    user_message: str,
    profile: dict,
    recent_messages: list[dict],
    retrieved_context: dict,
    usage: UsageTracker | None = None,
) -> str:
    """
    Used for the intent router's "general_chat" flow: a direct conversational answer to a
    question outside the recommendation/roadmap flow (FAFSA, essay advice, term
    definitions), grounded by retrieved knowledge-base context when actually relevant and
    by recent conversation history for continuity, but never forced into the structured
    recommendation JSON shape. Traced like every other reasoning stage (Discovery, Intent
    Router, Retrieval, Recommendation, Path Planning, Guardrail, Evaluation) - this was
    the one stage without a trace_event call until decision D035 caught the gap.
    """
    retrieved_documents = (retrieved_context or {}).get("retrieved_documents", [])
    history_lines = [f"- {m.get('role', 'user')}: {m.get('content', '')}" for m in (recent_messages or [])[-6:]]
    history_block = "\n".join(history_lines) if history_lines else "(no prior conversation)"
    doc_titles = [d.get("title", "") for d in retrieved_documents if d.get("title")]
    context_block = f"Possibly relevant knowledge-base topics: {', '.join(doc_titles)}" if doc_titles else (
        "No closely relevant knowledge-base documents were retrieved for this question."
    )

    user_prompt = (
        f"Student profile: {profile}\n\n"
        f"Recent conversation:\n{history_block}\n\n"
        f"{context_block}\n\n"
        f"Student's question: {user_message}"
    )
    response_text = _llm_service.generate_text(
        system_prompt=_GENERAL_CHAT_SYSTEM_PROMPT, user_prompt=user_prompt, usage=usage,
    )
    _tracing_service.trace_event(
        name="general_chat",
        inputs={"user_message": user_message, "retrieved_document_count": len(retrieved_documents)},
        outputs={"response": response_text},
        metadata={"retrieved_titles": doc_titles},
    )
    return response_text


_SUGGESTIONS_SYSTEM_PROMPT = load_prompt("suggestions", config.SUGGESTIONS_PROMPT_VERSION)


def _generate_suggestions_response(
    user_message: str,
    profile: dict,
    retrieved_context: dict,
    usage: UsageTracker | None = None,
) -> str:
    """
    Used for the intent router's "suggest" flow (decision D037): the student shared
    interests/strengths without explicitly asking for a full list yet, so this returns a
    short, lightweight response naming 2-4 career/major directions - not the full
    why-it-fits/opportunities/risks/next-steps detail RecommendationAgent produces, and
    never mentions specific colleges (those come once a career/major direction is settled,
    via the "related_topic" flow). Grounded by retrieved career/major context when
    relevant; no path plan, since it's too early for one.
    """
    retrieved_documents = (retrieved_context or {}).get("retrieved_documents", [])
    doc_titles = [d.get("title", "") for d in retrieved_documents if d.get("title")]
    context_block = f"Possibly relevant knowledge-base topics: {', '.join(doc_titles)}" if doc_titles else (
        "No closely relevant knowledge-base documents were retrieved yet."
    )

    user_prompt = (
        f"Student profile: {profile}\n\n"
        f"{context_block}\n\n"
        f"Student's message: {user_message}"
    )
    response_text = _llm_service.generate_text(
        system_prompt=_SUGGESTIONS_SYSTEM_PROMPT, user_prompt=user_prompt, usage=usage,
    )
    _tracing_service.trace_event(
        name="suggestions",
        inputs={"user_message": user_message, "retrieved_document_count": len(retrieved_documents)},
        outputs={"response": response_text},
        metadata={"retrieved_titles": doc_titles},
    )
    return response_text


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


def _enrich_recommendations(recommendation_items: list[dict], usage: UsageTracker | None = None) -> list[dict]:
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
        raw = _llm_service.generate_json(
            system_prompt=_ENRICHMENT_SYSTEM_PROMPT, user_prompt=user_prompt, usage=usage,
        )
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
    mode: str = "explore",
    selected_override: dict | None = None,
    reused_recommendation_items: list[dict] | None = None,
    anchor_context: str = "",
    recent_messages: list[dict] | None = None,
    usage: UsageTracker | None = None,
) -> tuple[dict, dict, str, dict, dict, dict]:
    """
    Runs one full generate-and-check attempt, branching on the intent router's decision
    (decision D034, "suggest" added in D037):
      - "suggest": skip recommendation/path-plan generation entirely - a short, lightweight
        response naming a few career/major directions, no full detail, no colleges yet.
      - "explore"/"related_topic": generate a fresh recommendation set (related_topic adds
        anchor_context so an ambiguous follow-up like "colleges for same" stays grounded in
        what was actually being discussed) -> path plan -> response text.
      - "roadmap": skip recommendation generation entirely - reuse last turn's offered
        items verbatim (nothing about them was wrong; only a plan was asked for) -> path
        plan anchored to the resolved item -> a short roadmap-only response text.
      - "general_chat": skip recommendation/path-plan generation entirely - a direct
        conversational answer to a question outside the recommendation flow.
    Guardrail and RASCEF evaluation always run, regardless of mode - safety/quality
    scoring is never skipped, only the generation work differs. Used for both the initial
    attempt and the single critic/revision retry, so both attempts go through identical
    logic; both record into the same `usage` tracker, so a retry's tokens are counted too.
    """
    if mode == "suggest":
        response_text = _generate_suggestions_response(
            user_message, current_profile, retrieval, usage=usage,
        )
        recommendations = {"recommendations": [], "summary": "", "follow_up_question": ""}
        path_plan = {}
    elif mode == "general_chat":
        response_text = _generate_general_chat_response(
            user_message, current_profile, recent_messages or [], retrieval, usage=usage,
        )
        recommendations = {"recommendations": [], "summary": "", "follow_up_question": ""}
        path_plan = {}
    elif mode == "roadmap":
        recommendations = {
            "recommendations": reused_recommendation_items or [],
            "summary": "",
            "follow_up_question": "",
        }
        path_plan = _path_planning.generate_path_plan(
            profile=current_profile,
            recommendations=recommendations,
            selected_override=selected_override,
            usage=usage,
        )
        anchor_title = (selected_override or {}).get("title", "this path")
        response_text = _format_roadmap_only_response_text(student_name, anchor_title)
    else:  # "explore" or "related_topic"
        recommendations = _recommendation.generate_recommendations(
            user_message=user_message,
            profile=current_profile,
            retrieved_context=retrieval,
            anchor_context=anchor_context,
            usage=usage,
        )
        path_plan = _path_planning.generate_path_plan(
            profile=current_profile,
            recommendations=recommendations,
            selected_override=selected_override,
            usage=usage,
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
        # "suggest" reuses general_chat's evaluation adaptation (decision D037): both are
        # free-form text with no recommendation structure to score against, so the same
        # is_general_chat flag applies to both rather than adding a near-duplicate param.
        is_general_chat=(mode in ("general_chat", "suggest")),
        usage=usage,
    )

    return recommendations, path_plan, response_text, response_payload, guardrail, evaluation


def _blocked_turn_result(
    student_name: str,
    user_message: str,
    student_id,
    memory: dict,
    input_guardrail_flags: list,
    start_time: float,
    usage: UsageTracker,
) -> dict:
    """
    Short-circuits the turn when the input guardrail flags a prompt-injection attempt -
    the only input guardrail flag that actually blocks (profanity/frustration remain
    detection-only, per decision D023's original scope, unchanged by this). No LLM call
    is ever made on this path, so a blocked turn costs $0.00 and adds no LLM-driven
    latency - only the local memory/SQLite work already done before this point runs.
    """
    response_text = _PROMPT_INJECTION_SAFE_RESPONSE
    end_time = time.perf_counter()

    log_id = None
    try:
        prompt_tokens, completion_tokens = usage.totals()
        log_id = _observability.log_turn({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "student_id": student_id,
            "student_name": student_name,
            "user_message": user_message,
            "model": config.DEFAULT_MODEL,
            "evaluation_model": config.EVAL_MODEL,
            "embedding_model": config.EMBEDDING_MODEL,
            "retrieved_document_count": 0,
            "guardrail_flags": [],
            "guardrail_risk_level": "high",
            "input_guardrail_flags": input_guardrail_flags,
            "evaluation_score": 0,
            "quality_badge": "blocked",
            "evaluation_scores": {},
            "prompt_versions": config.prompt_version_metadata(),
            "revision_attempted": False,
            "latency_ms": int((end_time - start_time) * 1000),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "token_usage_by_model": usage.by_model(),
            "estimated_cost": usage.estimated_cost_usd(),
            "error": "blocked_prompt_injection",
        })
    except Exception:
        pass

    _memory.save_turn(
        student_name=student_name,
        user_message=user_message,
        assistant_response=response_text,
        metadata={"evaluation_score": 0, "guardrail_flags": []},
    )

    return {
        "student_name": student_name,
        "response": response_text,
        "intent": "blocked",
        "intent_anchor_title": None,
        "quality_badge": "blocked",
        "guardrail_flags": [],
        "guardrail_risk_level": "high",
        "guardrail_required_revisions": [],
        "input_guardrail_flags": input_guardrail_flags,
        "evaluation_score": 0,
        "evaluation_feedback": [],
        "evaluation_scores": {},
        "evaluation_requires_revision": False,
        "revision_attempted": False,
        "retrieved_document_count": 0,
        "retrieved_documents": [],
        "recommendations": [],
        "recommendation_summary": "",
        "follow_up_question": "",
        "profile": memory.get("profile", {}),
        "missing_information": [],
        "next_question": "",
        "path_plan": {},
        "observability_log_id": log_id,
        "token_usage_by_model": usage.by_model(),
        "estimated_cost_usd": usage.estimated_cost_usd(),
        **config.prompt_version_metadata(),
    }


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
      input guardrail → memory.load → (block here if prompt injection detected) →
      [discovery ‖ intent_router] → merge profile → resolve anchor → retrieval (skipped for
      "roadmap") → suggest/recommendation/roadmap/general-chat (branches on intent,
      decision D037) → guardrail → evaluation → (critic/revision retry, max 1) → remember
      recommendations (skipped for "suggest"/"general_chat") → observability → memory.save

    Discovery and Intent Router run concurrently on worker threads: Discovery needs the
    pre-turn profile from memory.load to extract updates, and Intent Router needs that same
    pre-turn profile's last_recommendations plus recent conversation history to classify
    the turn (decision D034) - neither depends on the other's output, so there is no
    behavior change from running them in parallel. Retrieval runs afterward, since whether
    it runs at all - and what grounding it gets - depends on the resolved intent.
    """
    start_time = time.perf_counter()
    usage = UsageTracker()

    # 1. Input guardrail - detection only for profanity/frustration (D023's original
    # scope, unchanged), but prompt_injection_detected now actually blocks (see step 2b).
    # A pure function of the raw message, so it can run before memory load either way.
    input_guardrail = _input_guardrail.check_input(user_message)
    input_guardrail_flags = input_guardrail.get("flags", [])

    # 2. Load memory (profile + recent messages) - needed either way, to populate the
    # response and to log/save the turn even if step 2b blocks it below.
    memory = _memory.load_memory(student_name)
    student_id = memory.get("student_id")

    # 2b. Block on a detected prompt-injection attempt only - no LLM call has been made
    # yet, so this costs nothing. Everything past this point (Discovery, Retrieval,
    # Recommendation, Path Planning, output Guardrail, Evaluation) is skipped entirely.
    if "prompt_injection_detected" in input_guardrail_flags:
        return _blocked_turn_result(
            student_name, user_message, student_id, memory, input_guardrail_flags, start_time, usage,
        )

    # 3 & 4. Discovery (needs memory's pre-turn profile) and Intent Router (needs that same
    # pre-turn profile's last_recommendations, plus recent conversation history) are
    # independent of each other, so they run concurrently. Both are I/O-bound network calls
    # (OpenAI), so this overlaps wait time rather than parallelizing CPU work.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        discovery_future = pool.submit(
            _discovery.extract_profile_updates,
            student_name=student_name,
            user_message=user_message,
            existing_profile=memory["profile"],
            usage=usage,
        )
        intent_future = pool.submit(
            _intent_router.classify_intent,
            user_message=user_message,
            recent_messages=memory["recent_messages"],
            last_recommendations=memory["profile"].get("last_recommendations", []),
            usage=usage,
        )
        discovery = discovery_future.result()
        intent_result = intent_future.result()

    # 4b. Merge and persist the updated profile - depends on Discovery's output, so this
    # happens only after both parallel branches have finished.
    current_profile = _memory.update_profile(
        student_name=student_name,
        profile_updates=discovery["student_profile_updates"],
    )

    # 4c. Resolve the intent router's decision (decision D034) against the merged profile's
    # last_recommendations. Replaces the old literal-title-only _match_previous_choice():
    # the router can resolve implicit references ("same", "that one") using actual
    # conversation history, which the old mechanism never had access to. If the resolved
    # anchor_title somehow isn't in the list (shouldn't normally happen - IntentRouterAgent
    # already validated it against the pre-turn list), fall back to "explore" rather than
    # act on a broken anchor.
    intent = intent_result.get("intent", "explore")
    anchor_title = intent_result.get("anchor_title")
    last_recommendations = current_profile.get("last_recommendations", [])
    anchor_item = next(
        (item for item in last_recommendations if isinstance(item, dict) and item.get("title") == anchor_title),
        None,
    ) if anchor_title else None
    if intent in ("roadmap", "related_topic") and anchor_item is None:
        intent = "explore"

    anchor_context = ""
    if intent == "related_topic" and anchor_item:
        item_type = anchor_item.get("type", "")
        anchor_context = f"{anchor_item.get('title', '')} ({item_type})" if item_type else anchor_item.get("title", "")

    selected_override = anchor_item if intent == "roadmap" else None

    # 5. Retrieval - skipped entirely for "roadmap" (the recommendations are reused
    # verbatim, so there's nothing new to ground). "related_topic" passes the resolved
    # anchor as extra grounding context so an ambiguous follow-up like "colleges for same"
    # stays on-topic instead of the model guessing blind (decision D034).
    if intent == "roadmap":
        retrieval = {"query": user_message, "retrieved_documents": [], "retrieval_confidence": 0.0}
    else:
        retrieval = _retrieval.retrieve_relevant_context(
            user_message=user_message,
            profile=current_profile,
            top_k=5,
            anchor_context=anchor_context,
            usage=usage,
        )

    # 6-9. Generate (recommendations, a reused-verbatim roadmap, or a general-chat answer,
    # depending on intent), then guardrails and evaluation - always run, regardless of intent.
    recommendations, path_plan, response_text, response_payload, guardrail, evaluation = _generate_and_score(
        student_name, user_message, current_profile, retrieval,
        input_guardrail_flags=input_guardrail_flags, revision_attempted=False,
        mode=intent, selected_override=selected_override,
        reused_recommendation_items=last_recommendations if intent == "roadmap" else None,
        anchor_context=anchor_context, recent_messages=memory["recent_messages"], usage=usage,
    )

    # 9b. Critic / revision loop - at most one retry, only when the RASCEF score is low
    revision_attempted = False
    if evaluation.get("requires_revision"):  # equivalent to evaluation["total_score"] < 24
        revision_attempted = True
        recommendations, path_plan, response_text, response_payload, guardrail, evaluation = _generate_and_score(
            student_name, user_message, current_profile, retrieval,
            input_guardrail_flags=input_guardrail_flags, revision_attempted=True,
            mode=intent, selected_override=selected_override,
            reused_recommendation_items=last_recommendations if intent == "roadmap" else None,
            anchor_context=anchor_context, recent_messages=memory["recent_messages"], usage=usage,
        )

    # 9c. Append a note if the (possibly revised) response still needs more information
    if evaluation.get("requires_revision"):
        response_text = f"{response_text}\n\n_{_REVISION_NEEDED_NOTE}_"
        response_payload["response"] = response_text

    # 9d. Remember this turn's offered recommendations so a later turn can recognize the
    # student's reply naming one of them. Skipped for "general_chat" and "suggest" - neither
    # produces a structured recommendation list, and overwriting with an empty list would
    # erase a still-relevant earlier anchor (e.g. a side question mid-conversation about
    # Mental Health Counselor shouldn't wipe out the ability to later ask for "a roadmap
    # for that", and a lightweight "suggest" reply shouldn't either).
    if intent not in ("general_chat", "suggest"):
        _memory.remember_last_recommendations(student_id, recommendations.get("recommendations", []))

    # 9e. Display-only enrichment (fun facts, future outlook) - runs after guardrails and
    # evaluation have already scored the response, so it never affects RASCEF or guardrails.
    enriched_recommendation_items = _enrich_recommendations(recommendations.get("recommendations", []), usage=usage)

    # 10. Log turn to observability - never let a logging failure break the response
    end_time = time.perf_counter()
    log_id = None
    try:
        prompt_tokens, completion_tokens = usage.totals()
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
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "token_usage_by_model": usage.by_model(),
            "estimated_cost": usage.estimated_cost_usd(),
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
        "intent": intent,
        "intent_anchor_title": anchor_title if intent in ("roadmap", "related_topic") else None,
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
        "token_usage_by_model": usage.by_model(),
        "estimated_cost_usd": usage.estimated_cost_usd(),
        **config.prompt_version_metadata(),
    }
