import re

from services.retrieval_service import RetrievalService
from services.tracing_service import TracingService
from services.usage_tracker import UsageTracker

_STATE_NAME_TO_CODE = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY", "washington dc": "DC", "washington d.c.": "DC", "d.c.": "DC",
}
_VALID_STATE_CODES = set(_STATE_NAME_TO_CODE.values())

_AFFORDABILITY_KEYWORDS = [
    "afford", "budget", "low cost", "low-cost", "cheap", "inexpensive", "financial aid",
    "scholarship", "in-state", "in state", "public school", "public college",
    "public university", "cost is a concern", "cost-conscious", "tuition",
]

_MAX_COLLEGE_SLOTS = 2
_CANDIDATE_POOL_MULTIPLIER = 3


def _normalize_document(result: dict) -> dict:
    """Normalize a Pinecone match or a tag-fallback record into a common shape."""
    if "metadata" in result:
        metadata = result.get("metadata", {})
        return {
            "doc_id": result.get("id", ""),
            "doc_type": metadata.get("doc_type", ""),
            "title": metadata.get("title", ""),
            "score": result.get("score", 0.0),
            "metadata": metadata,
        }
    # KnowledgeLoader.search_by_tags fallback shape: raw knowledge base record
    title = result.get("title") or result.get("name") or result.get("label") or ""
    return {
        "doc_id": result.get("id", ""),
        "doc_type": result.get("doc_type", ""),
        "title": title,
        "score": 0.0,
        "metadata": result,
    }


def _infer_state_code(location_preference: str) -> str | None:
    """Best-effort mapping from a free-text location preference (as extracted by the
    Discovery Agent, e.g. "California", "stay in Texas", "somewhere warm") to a 2-letter
    state code matching the ingestion-time `state` metadata field. Returns None for
    anything that doesn't clearly name a specific state - vague preferences fall back to
    unfiltered semantic search rather than guessing."""
    if not location_preference:
        return None
    text = location_preference.strip().lower()

    direct = text.upper()
    if len(direct) == 2 and direct in _VALID_STATE_CODES:
        return direct

    for name, code in _STATE_NAME_TO_CODE.items():
        if re.search(rf"\b{re.escape(name)}\b", text):
            return code
    return None


_PROFILE_CONTEXT_FIELDS = ("interests", "strengths", "favorite_careers", "career_preferences")


def _build_profile_context(profile: dict) -> str:
    """Folds what's already known about the student (interests, strengths, favorite
    careers) into the retrieval query, not just the current message's literal wording.
    Without this, a topically-thin follow-up like "give me career choices" - which states
    an intent but repeats none of the student's actual interests - retrieves nearly at
    random, since the embedding search has almost nothing to match against. Discovery
    accumulates these fields turn over turn specifically so later turns don't have to
    restate them (decision D037 surfaced this gap: splitting "share interests" (suggest)
    from "ask for options" (explore) into separate turns made it much more visible, but
    the gap predates that split - explore's retrieval query was always message-only)."""
    parts = []
    for field in _PROFILE_CONTEXT_FIELDS:
        values = profile.get(field) or []
        if values:
            parts.append(", ".join(str(v) for v in values))
    return "; ".join(parts)


def _wants_affordability(budget_preference: str) -> bool:
    if not budget_preference:
        return False
    lowered = budget_preference.lower()
    return any(keyword in lowered for keyword in _AFFORDABILITY_KEYWORDS)


def _rank_colleges(colleges: list[dict], state: str | None, budget_preference: str) -> list[dict]:
    """Rank the candidate pool: an actual state match always outranks a backfilled
    out-of-state candidate (state is a stated hard preference; backfill only exists to
    pad out a small catalog), then a soft public-college boost when the student has
    signaled affordability, then raw semantic score as the final tie-break. The budget
    signal is intentionally a re-rank, not a hard filter - the dataset has no per-college
    cost figures, only editorial affordability_notes text, so a hard cutoff would
    overclaim precision the data doesn't support."""
    wants_affordability = _wants_affordability(budget_preference)

    def _sort_key(doc: dict) -> tuple:
        doc_state = doc.get("metadata", {}).get("state", "")
        state_rank = 0 if (state and doc_state == state) else 1
        college_type = str(doc.get("metadata", {}).get("college_type", "")).lower()
        is_public = "public" in college_type
        budget_rank = 0 if (wants_affordability and is_public) else 1
        return (state_rank, budget_rank, -doc.get("score", 0.0))

    return sorted(colleges, key=_sort_key)


class RetrievalAgent:
    """
    Retrieves the top-k most relevant career, major, and interest documents from
    Pinecone for the student's current message, plus a separate college search that
    can be narrowed by the student's stated location/budget preferences (structured
    Pinecone metadata filtering with a soft budget-based re-rank, not a hard exclude -
    the catalog is small enough that an exact-match filter can come up short even for
    a perfectly reasonable preference).

    Service dependencies: RetrievalService, TracingService (optional)
    """

    def __init__(self, retrieval_service: RetrievalService, tracing_service: TracingService | None = None):
        self._retrieval_service = retrieval_service
        self._tracing = tracing_service or TracingService()

    def retrieve_relevant_context(
        self,
        user_message: str,
        profile: dict,
        top_k: int = 5,
        anchor_context: str = "",
        usage: UsageTracker | None = None,
    ) -> dict:
        """Runs a non-college search plus a location/budget-aware college search and
        returns a RetrievalOutput-shaped dict. The embedding search text folds in the
        student's already-known interests/strengths/favorite careers (not just the literal
        current message - decision D037) plus `anchor_context` (e.g. "Mental Health
        Counselor (career)") when the intent router's related_topic flow needs to ground
        an ambiguous follow-up ("colleges for same") in what it actually refers to. Neither
        is folded into the displayed `query` field, so the turn's record of what the
        student literally asked stays accurate."""
        profile = profile or {}
        state = _infer_state_code(profile.get("location_preference", ""))
        budget_preference = profile.get("budget_preference", "")
        profile_context = _build_profile_context(profile)
        search_text = " ".join(part for part in (user_message, profile_context, anchor_context) if part)

        college_slots = min(_MAX_COLLEGE_SLOTS, top_k)
        non_college_slots = top_k - college_slots

        non_college_docs = self._retrieval_service.search_non_colleges(
            search_text, top_k=non_college_slots, usage=usage,
        ) if non_college_slots > 0 else []
        college_candidates = self._retrieval_service.search_colleges(
            search_text, top_k=college_slots * _CANDIDATE_POOL_MULTIPLIER, state=state, usage=usage,
        ) if college_slots > 0 else []

        normalized_colleges = _rank_colleges(
            [_normalize_document(r) for r in college_candidates], state, budget_preference,
        )[:college_slots]
        normalized_non_colleges = [_normalize_document(r) for r in non_college_docs]

        retrieved_documents = normalized_non_colleges + normalized_colleges
        scores = [d["score"] for d in retrieved_documents]
        retrieval_confidence = sum(scores) / len(scores) if scores else 0.0

        result = {
            "query": user_message,
            "retrieved_documents": retrieved_documents,
            "retrieval_confidence": retrieval_confidence,
        }
        self._tracing.trace_event(
            name="retrieval",
            inputs={"user_message": user_message, "top_k": top_k, "state_filter": state},
            outputs={
                "retrieved_titles": [d["title"] for d in retrieved_documents],
                "retrieval_confidence": retrieval_confidence,
            },
            metadata={
                "retrieved_document_count": len(retrieved_documents),
                "state_filter": state,
                "budget_boost_applied": _wants_affordability(budget_preference),
            },
        )
        return result
