# PathFinder AI — Error Handling and Fallback Strategy

## 1. Why Error Handling Matters

A capstone AI system is not just evaluated on whether it works when everything goes right. It is evaluated on whether it degrades gracefully when things go wrong — API timeouts, missing data, low-confidence outputs, or unsafe generated content.

PathFinder AI is designed with explicit failure handling at every layer:

- **Retries** for transient API failures
- **Fallbacks** when a dependency is unavailable
- **Graceful degradation** when data or confidence is insufficient
- **Safe defaults** that never expose a bad or unsafe response to the student
- **Observability** so every failure is logged, traceable, and fixable

This document defines the failure scenarios, detection methods, fallback behaviors, and user-facing messaging for the full multi-agent workflow.

---

## 2. Failure Scenarios

| # | Failure Scenario | Detection Method | Fallback Behavior | User-Facing Message | Logged Fields |
|---|---|---|---|---|---|
| 1 | Missing OpenAI API key | `config.has_openai_key()` returns False at startup | App shows config warning; no LLM calls attempted | "PathFinder AI is not fully configured yet. Please contact the administrator." | `error: missing_openai_key` |
| 2 | Missing Pinecone API key | `config.has_pinecone_key()` returns False at startup | Skip retrieval; use curated JSON context directly | No user-facing warning; response quality may be lower | `error: missing_pinecone_key` |
| 3 | Pinecone unavailable (timeout or network) | `pinecone.query()` raises exception | Fall back to curated JSON context injected directly into prompt | No user-facing warning; response continues with local data | `error: pinecone_unavailable`, `retrieved_doc_count: 0` |
| 4 | OpenAI generation failure (5xx, timeout) | `openai.chat.completions.create()` raises exception | Retry up to 2 times with 2s backoff; if all retries fail, return safe fallback message | "I'm having a moment — please try again in a few seconds." | `error: openai_generation_failure`, retry count |
| 5 | OpenAI embedding failure | `openai.embeddings.create()` raises exception | Retry up to 2 times; if all fail, skip semantic search and inject curated JSON fallback | No user-facing warning; recommendation quality may be lower | `error: openai_embedding_failure` |
| 6 | Empty retrieval results (0 docs returned) | `len(retrieved_documents) == 0` | Inject pre-built curated context block for student's top interest tag | Response proceeds; no explicit warning unless profile is also sparse | `retrieved_doc_count: 0`, `retrieval_confidence: 0.0` |
| 7 | Low retrieval confidence (avg score < 0.6) | `retrieval_confidence < 0.6` | Include top results anyway; add a note in the response that recommendations are broad | "These suggestions are based on general information — as I learn more about you, they'll get more specific." | `retrieval_confidence`, `guardrail_flags` |
| 8 | Missing GPA when college guidance is requested | `profile.gpa` is empty when college question detected | Ask for GPA before proceeding; do not guess or assume | "To give you honest college guidance, it helps to know your GPA. What's your approximate GPA?" | `missing_fields: ["gpa"]` |
| 9 | Student gives vague or very short input | `len(user_message.split()) < 3` or Discovery confidence < 0.4 | Discovery Agent returns `next_question` only; no recommendation attempted | Ask a specific follow-up question | `discovery_confidence: low` |
| 10 | Unsafe or overconfident recommendation generated | Guardrail Agent detects flag (`risk_level: high`) | Append a safe revision to the response or replace flagged sentence with hedged language | Response is returned with guardrail revision applied; no raw unsafe content shown | `guardrail_flags`, `risk_level: high` |
| 11 | Guardrail Agent itself throws exception | Exception caught in Orchestrator | Default to `passed: false, risk_level: high`; return safe fallback message | "I want to make sure I give you accurate guidance — let me rephrase that." | `error: guardrail_agent_failure` |
| 12 | Evaluation score below threshold (< 24/30) | `evaluation_result.total_score < 24` | Return response with confidence note appended; log for prompt review | "(Note: this response is based on limited context. The more I know about you, the better I can guide you.)" | `evaluation_score`, `quality_badge: amber/red` |
| 13 | SQLite database unavailable | `sqlite3` raises `OperationalError` | Continue turn with empty profile; skip memory write; warn student | "I'm unable to save your session right now. Your responses won't be remembered this time." | `error: sqlite_unavailable` |
| 14 | Profile extraction confidence low | `DiscoveryOutput.confidence < 0.5` | Return profile unchanged; set `next_question` to a safe open-ended prompt | The Discovery Agent's `next_question` is surfaced naturally in the response | `discovery_confidence`, `missing_information` |
| 15 | Invalid structured output from an agent | Pydantic `ValidationError` caught by Orchestrator | Log the bad output, skip the failed agent's result, use safe default for that stage | No direct user-facing error; fallback response returned | `error: validation_error`, `agent_name`, raw output snippet |

---

## 3. Retry Strategy

**Applies to:** Transient API failures only — OpenAI generation, OpenAI embedding.  
**Does not apply to:** Validation failures, missing keys, guardrail failures, or evaluation failures.

### Rules

- **Max retries:** 2 (3 total attempts)
- **Backoff:** 2 seconds between retries (no exponential backoff needed at prototype scale)
- **Retry conditions:** HTTP 429 (rate limit), HTTP 5xx (server error), connection timeout
- **No-retry conditions:** HTTP 400 (bad request), HTTP 401 (invalid key), Pydantic validation errors
- **After max retries:** Return a safe user-facing fallback and log the final error

### Retry Log Fields

Every retry attempt writes to `observability_logs`:

```json
{
  "agent_name": "RecommendationAgent",
  "model": "gpt-4o-mini",
  "error": "openai_generation_failure",
  "retry_count": 2,
  "final_outcome": "fallback_returned"
}
```

---

## 4. Fallback Strategy

### 4.1 Pinecone Unavailable → Local JSON Fallback

If Pinecone is unreachable or returns no results:

1. Load `data/careers.json`, `data/majors.json`, `data/colleges.json` from disk
2. Filter documents by matching `interest_tags` against `profile.interests` using simple string intersection
3. Take the top 5 matches by tag overlap count
4. Format them as a context block and inject into the system prompt as if they were retrieved
5. Set `retrieved_doc_count` to the number of fallback docs used; log `retrieval_method: local_fallback`

This means the system always has grounded context — even without Pinecone.

### 4.2 OpenAI Embedding Fails → Skip Semantic Search

If the embedding call fails after retries:

1. Skip semantic similarity — use the local JSON fallback (4.1) with tag matching instead
2. Do not block the response turn
3. Log `error: embedding_failure, retrieval_method: tag_fallback`

### 4.3 OpenAI Generation Fails → Safe Fallback Message

If the main LLM call fails after retries:

Return this safe message to the student:

> "I'm having a moment connecting — please try sending your message again in a few seconds. Your information is saved and I'll pick up where we left off."

Log: `error: generation_failure, fallback_returned: true`

### 4.4 Low Evaluation Score → Confidence Note Appended

If `evaluation_result.total_score < 24`:

Append to the response before returning it:

> *(Note: This guidance is based on limited context. The more we talk, the more specific and accurate my recommendations will become.)*

Do not withhold the response entirely — partial guidance is better than silence.

### 4.5 Guardrail Flag → Revise Before Returning

If `guardrail_result.passed == false`:

1. If `risk_level: medium` — append the `required_revision` text and return
2. If `risk_level: high` — replace the flagged sentence using the `required_revision` instruction via a second short LLM call (or rule-based substitution for speed)
3. Never return a `risk_level: high` response to the student unmodified
4. Log all flags in `observability_logs.guardrail_flags`

### 4.6 SQLite Unavailable → In-Memory Session Only

If the database cannot be reached:

1. Warn the student once at the start of the session
2. Continue the session using only in-memory state (Streamlit session state)
3. Do not attempt writes that will fail repeatedly — disable memory writes for the session
4. Log `error: sqlite_unavailable` on every affected turn

---

## 5. State Management

The Orchestrator maintains a per-turn state object passed between agents. This prevents agents from needing to re-query shared state independently.

### Turn State Object

```python
@dataclass
class TurnState:
    student_id: int
    student_name: str
    user_message: str
    profile: StudentProfile
    recent_messages: list[dict]
    session_number: int
    retrieved_documents: list[RetrievedDocument]
    draft_response: str
    guardrail_result: GuardrailResult
    evaluation_result: EvaluationResult
    errors: list[str]
    fallbacks_used: list[str]
```

- Each agent receives only the fields it needs from `TurnState`
- Each agent writes its output back into `TurnState`
- The Orchestrator reads the final state and assembles the response
- `errors` and `fallbacks_used` are accumulated across agents and logged at end of turn

---

## 6. User-Facing Error Principles

1. **Never expose internal errors** — no stack traces, agent names, or technical messages shown to students
2. **Never go silent** — always return something, even if it is only a safe fallback message
3. **Be honest about limitations** — if the system cannot give specific guidance, say so simply and ask a follow-up
4. **Maintain conversational tone** — error states feel like a natural part of the conversation, not a system failure
5. **Preserve session continuity** — even if a turn fails, the next turn picks up from where the memory left off

---

## 7. Observability Integration

Every error, retry, and fallback is logged to `observability_logs`. Key fields for debugging:

| Field | What It Tells You |
|---|---|
| `error` | What failed and where |
| `guardrail_flags` | Which safety rules were triggered |
| `evaluation_score` | Quality of the response that was returned |
| `retrieved_doc_count` | Whether retrieval worked or fell back |
| `fallbacks_used` | Which fallback path was taken |
| `retry_count` | How many API retries were needed |
| `latency_ms` | Whether failures are causing latency spikes |

A session with `error` fields across multiple turns indicates a systemic issue (API key, network, data) — not a one-off.

---

## 8. Error Handling by Phase

| Phase | Error Handling Added |
|---|---|
| Phase 1 | Config validation: warn if keys missing on startup |
| Phase 2 | SQLite unavailable fallback; in-memory session mode |
| Phase 4 | Embedding failure fallback to tag-based matching |
| Phase 5 | Pinecone unavailable fallback to local JSON |
| Phase 6 | Generation retry (2x); safe fallback message |
| Phase 7 | Guardrail failure defaults; high-risk revision flow |
| Phase 8 | Evaluation failure defaults; confidence note for low scores |
| Phase 9 | Full error logging in observability; fallback print if SQLite down |
