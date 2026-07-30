# PathFinder AI

A chat-first career discovery and college pathway guidance platform for high school students, parents, and school counselors — built as a multi-agent AI system demonstrating RAG, persistent memory, guardrails, LLM-as-judge evaluation, and observability.

---

## Project Overview

Many high school students don't know what careers exist beyond the familiar defaults, what majors connect to those careers, or what a realistic next step looks like given their actual academic profile. PathFinder AI meets students in conversation — no forms, no quizzes — and:

- Surfaces careers a student may not know exist, including non-obvious ones
- Connects those careers to relevant college majors
- Gives GPA-aware college pathway guidance without ever promising an outcome
- Builds a personalized, phased next-step roadmap
- Remembers the student across turns and sessions, so a returning student continues rather than restarts

---

## Architecture Overview

Clean Architecture, six layers, explicit constructor injection, no agent framework:

```
Presentation   src/app.py                Streamlit UI — no business logic
Application    src/agents/                11 agents + orchestrator
Service        src/services/              LLM, embeddings, retrieval, prompts, evaluation, tracing
Repository     src/repositories/          All SQL lives here
Infrastructure src/infrastructure/        Only layer that imports openai / pinecone / sqlite3 / langsmith
Domain         src/schemas/models.py      Reference Pydantic models
```

Every conversation turn runs the same first few steps, then branches on intent (decision D034, "suggest" added in D037):

```
Student message
  → Input Guardrail Agent (flag profanity / frustration / prompt injection - runs first,
    before memory load, since it only needs the raw message)
  → Memory Agent (load profile + history)
  → Discovery Agent (extract profile updates)   ┐  run concurrently on worker threads -
  → Intent Router Agent (classify the turn)     ┘  neither depends on the other's output
  → Memory Agent (merge + persist profile, after both threads join)
  → Resolve the router's anchor_title against the merged profile's last_recommendations
    (also forces "suggest" -> "explore" if this is a genuinely first message, decision D037)
  → Branch on intent:
      "roadmap"       → skip Retrieval + Recommendation; reuse last turn's items verbatim;
                         Path Planning builds a roadmap around the resolved anchor
      "general_chat"  → Retrieval only if relevant (no anchor); a direct conversational
                         answer; no Recommendation, no Path Planning
      "suggest"       → Retrieval (no anchor); a short reply naming 2-4 career/major
                         directions, no colleges yet; no Recommendation, no Path Planning
      "explore" /
      "related_topic" → Retrieval (related_topic adds the anchor as grounding context)
                         → Recommendation (3-5 grounded options) → Path Planning (roadmap
                         for the top option)
  → Guardrail Agent (rule-based safety check, every branch)
  → Evaluation Agent (RASCEF quality score, every branch - general_chat/suggest scored on
    answer substance rather than recommendation structure; traced to LangSmith if configured)
  → [critic/revision loop: if score < 24, re-run only the branch that ran above, once]
  → Enrichment (fun facts + future outlook added per recommendation, display-only)
  → Observability Agent (log the turn)
  → Memory Agent (save the turn; last_recommendations left untouched after general_chat/suggest)
  → Response + trace → Streamlit UI
```

Full contracts for every agent: `docs/09_Agent_Contracts.md`. Full architecture detail: `docs/04_Architecture.md`.

---

## Features

- Conversational profile building — no forms, one clarifying question at a time
- Non-obvious career discovery grounded in a curated knowledge base (not hallucinated)
- Major and college-pathway guidance connected to career recommendations
- Phased, actionable roadmaps (short/medium/long-term steps, skills, project ideas)
- Persistent memory across turns and sessions
- Rule-based safety guardrails on every response, plus a pre-generation input guardrail on every incoming message
- LLM-as-judge quality scoring on every response, with a single automatic regenerate-and-recheck retry when the score is low
- Human-in-the-loop 👍/👎 feedback on every response, no login required
- Local observability logging, with optional LangSmith tracing

---

## Multi-Agent Architecture

| Agent | Responsibility |
|---|---|
| Orchestrator | Runs the fixed pipeline above; assembles the final response and trace; runs the critic/revision retry |
| Input Guardrail Agent | Rule-based pre-generation check on the raw message (profanity/frustration/prompt-injection flags); runs first, before memory load; blocks the turn only on `prompt_injection_detected`, profanity/frustration remain detection-only |
| Memory Agent | Loads/merges/persists the student profile and message history |
| Intent Router Agent | Classifies each turn as suggest/explore/roadmap/related_topic/general_chat and resolves implicit references ("same", "that one") against last turn's offered items, using real conversation history; runs concurrently with Discovery |
| Discovery Agent | Extracts profile fields from the latest message only; never invents GPA or grade level; runs concurrently with Intent Router |
| Retrieval Agent | Semantic search over the knowledge base via Pinecone; skipped for "roadmap", anchor-grounded for "related_topic" |
| Recommendation Agent | 3-5 grounded career/major/college recommendations, each with why-it-fits, why-exciting, opportunities, risks, and next steps; skipped for "roadmap"/"general_chat" |
| Path Planning Agent | Turns the top (or anchor-resolved) recommendation into a phased roadmap; skipped for "general_chat" |
| Guardrail Agent | Rule-based post-generation safety check (10 flags); runs on every turn regardless of intent |
| Evaluation Agent | RASCEF quality score via GPT-4o judge, with a rule-based fallback; runs on every turn regardless of intent, and again if the critic/revision loop retries |
| Observability Agent | Writes one row per turn to SQLite; returns the row's `log_id` for HITL feedback |

Each agent is a small class receiving its dependencies via constructor injection — no agent instantiates its own OpenAI/Pinecone/SQLite client. See `docs/09_Agent_Contracts.md` for exact input/output shapes.

**Parallelization:** Discovery and Intent Router run concurrently on worker threads (`concurrent.futures.ThreadPoolExecutor`) instead of sequentially. Both depend only on the state Memory Load already produced — Discovery needs the pre-turn profile, Intent Router needs that same pre-turn profile's `last_recommendations` plus recent conversation history — and neither depends on the other's output, so there's no behavior change from running them in parallel, only reduced latency. Retrieval runs afterward, not in this pair, since whether it runs at all - and what grounding it gets - depends on the intent that was just resolved (decision D034).

---

## Intent Routing

Every message used to be forced through the same "generate new recommendations" pipeline, regardless of what the student was actually asking. Decision D034 fixed that: `IntentRouterAgent` classifies each turn — using recent conversation history and last turn's offered titles, not just the raw message — into one of five intents (D037 added `suggest`):

- **`suggest`** — pure interest/strength-sharing with no explicit ask and no uncertainty signal ("I like gaming and reading"). A short, lightweight reply naming 2-4 career/major directions — no full recommendation detail, no colleges yet, no `RecommendationAgent`/Path Planning call. Never fires on a genuinely first message (enforced in code, not just prompt wording) — a first-time visitor typically wants to see real options quickly, so a first message always goes to `explore` even if it's pure interest-sharing
- **`explore`** — new recommendations: either an explicit ask, or interests paired with uncertainty ("I don't know what career I want," "I don't know if college is right for me") — that's a real request for guidance, just phrased indirectly (today's default pipeline: Retrieval → Recommendation → Path Planning)
- **`roadmap`** — a plan for something already offered, named exactly or implicitly ("that one", "the same one"). Recommendations are reused verbatim (nothing about them was wrong); only a fresh roadmap is generated, anchored to the resolved item
- **`related_topic`** — more information (career or college) tied to an established anchor, e.g. "colleges for same." Retrieval and Recommendation still run, but grounded by the resolved anchor's title/type instead of guessing blind from an ambiguous message
- **`general_chat`** — a genuine question outside the recommendation flow (FAFSA, essay advice, term definitions). Answered directly and conversationally — grounded by RAG when the knowledge base is actually relevant, but never forced into the structured recommendation JSON shape. No Recommendation or Path Planning call at all

An anchor resolved with low confidence, or that doesn't match anything actually offered last turn, falls back to `explore` rather than guessing — see `IntentRouterAgent._validate()`. Guardrail and RASCEF evaluation run on every intent, unmodified in scope; only the generation work differs. `last_recommendations` is left untouched after a `general_chat` or `suggest` turn, so a side question or a lightweight reply mid-conversation doesn't erase the ability to refer back to what was being discussed.

This replaces the old `_match_previous_choice()` (D028) outright: that mechanism could only recognize an *exact, literal* title mention in the message, with zero visibility into conversation history — it had no way to resolve "same," "that one," or any other implicit reference, which is exactly the failure mode that motivated D034.

Chat also surfaces clickable next-step chips (decision D037) matched to the resolved intent: a `suggest` reply offers "Show me career choices" / "Show me major options"; an `explore`/`roadmap` reply anchored to a career or major (not already a college) offers "Show me college options for `<X>`." Clicking one feeds that exact text through the same message-handling path as typing it.

---

## Memory

SQLite (`data/memory.db`), four tables plus observability: `students`, `profiles`, `messages`, `conversation_summaries`, `observability_logs`. The student profile is a JSON blob merged incrementally every turn:

- List fields (`interests`, `strengths`, `career_preferences`, `college_preferences`, `favorite_careers`) accumulate without duplicates
- Scalar fields (`grade_level`, `gpa`) only change when the student actually states a new value — never guessed or overwritten with something weaker
- `location_preference` and `budget_preference` are extracted by `DiscoveryAgent` (prompt v2) like any other field, and feed both the guardrail checks and Retrieval's college filtering (see Pinecone RAG below). Two further optional fields, `college_type_preference` and `pathway_preference`, exist on the profile but aren't extracted yet — see Known Limitations

A student is recognized by name (case-insensitive) — no authentication in this prototype.

---

## Pinecone RAG

Four curated local datasets — `data/careers.json` (73), `data/majors.json` (47), `data/colleges.json` (45), `data/interests.json` (58) — embedded with OpenAI `text-embedding-3-small` and indexed in Pinecone (223 vectors, single `default` namespace, `doc_type` metadata filtering instead of separate indexes/namespaces).

At query time, `RetrievalAgent` runs two searches instead of one blended `search_all()`: `RetrievalService.search_non_colleges()` covers careers/majors/interests exactly as before, while `search_colleges()` is state- and gpa_band-aware — each college's `location` is normalized to a 2-letter `state` field at ingestion time, so a student's stated `location_preference` becomes a real Pinecone metadata filter (with a fallback to an unfiltered college search if the state match comes up short — the catalog is only 45 colleges). A stated `budget_preference` doesn't hard-filter — there's no real per-college cost data, only editorial notes — so it soft-boosts public colleges above private ones of similar relevance instead (see decision D033). If Pinecone is unreachable, retrieval falls back transparently to a local tag-intersection search over the same JSON files (`KnowledgeLoader.search_by_tags()`) — the system stays functional, just with lower-quality matching.

Full design rationale (why one namespace, why metadata filtering over multiple indexes, ingestion instructions): `docs/13_RAG_Implementation.md`.

**Recommendation Engine:** GPT-4o-mini generates 3-5 recommendations grounded in the retrieved documents. Every recommendation includes `why_it_fits`, `why_exciting`, `opportunities`, `real_world_impact`, `related_majors`, `skills_to_build`, `adjacent_paths`, `evidence` (which retrieved document backs this up), `confidence`, honest `risks_or_limitations`, and concrete `next_steps`. The prompt explicitly asks for at least one less-obvious option alongside the familiar ones, and forbids salary/admission/job-security guarantees regardless of how positive the framing is. If the model returns unusable JSON, the agent falls back to a safe response built from the retrieved document titles instead of crashing.

**Display-only enrichment:** after guardrails and evaluation have already scored the response, the orchestrator makes one additional LLM call to add `fun_facts` (2-3 short facts) and `future_outlook` (a positively-framed sentence) to each recommendation. This is a separate, unversioned prompt — not part of the Recommendation Agent's own contract or the RASCEF-scored `response_payload` — regenerated fresh every turn and never persisted.

**Path Planning:** a recommendation answers "what might fit me?" — a path plan answers "what should I do next?" GPT-4o-mini turns one selected recommendation into short-term (3-6 months), medium-term (1-3 years), and long-term steps, skills to build, concrete project ideas (portfolio piece, volunteer work, club activity, hackathon, design or research project), and college-preparation steps. Selection priority: the agent picks the highest-ranked **career** recommendation to build a roadmap around; if none exists, the highest-ranked **major**; otherwise whatever ranked first (in practice, a college) — this exists because a roadmap anchored to a specific college name reads oddly compared to one anchored to a career or major direction (see decision D018 in `docs/12_DECISION_LOG.md`).

---

## Input + Output Guardrails

**Input Guardrails:** before any other agent sees the student's message, the Input Guardrail Agent runs a rule-based check for `profanity_detected`, `frustration_detected`, and `prompt_injection_detected` (`src/prompts/input_guardrail/v1.yaml`). `profanity_detected` and `frustration_detected` remain detection-only — flags are recorded on the turn and shown in the trace, but the conversation proceeds unchanged. `prompt_injection_detected` is the exception: the turn short-circuits immediately after memory load, before Intent Router/Discovery/Retrieval/Recommendation ever run, and returns a fixed safe response instead — no LLM call is made, so a blocked turn costs $0.00. The check itself still runs before memory load, since it's a pure function of the raw message with no dependency on stored state; the block is applied right after memory load (see `docs/09_Agent_Contracts.md` for the exact sequencing).

**Output Guardrails:** rule-based, no LLM call. Scans the full turn's text for unsafe language and checks the profile for context the response implicitly depends on:

| Flag | Risk |
|---|---|
| `admission_guarantee`, `salary_guarantee`, `protected_attribute_bias` | high |
| `overconfidence`, `pressure_language`, `missing_gpa_for_college_guidance`, `missing_budget_for_affordability_guidance`, `missing_grounding` | medium |
| `missing_location_for_specific_college_guidance`, `insufficient_profile` | low |

A `high` risk_level appends a fixed note redirecting the student to a counselor, parent, or trusted advisor. `medium` appends a "keep in mind" limitations note. `low` leaves the response untouched. Rules (phrases, keywords, risk levels, revision text) are externalized in `src/prompts/guardrail/v1.yaml` — not hardcoded — see Prompt Governance below. Full trigger phrases and flag-by-flag detail: `docs/09_Agent_Contracts.md`.

---

## RASCEF Evaluation

Every response is scored 1-5 on six dimensions (max 30) by GPT-4o acting as an LLM-as-judge, instructed not to be overly generous and to mark a response down on safety/accuracy if it's unsafe or unsupported even when it reads fluently:

- **R**elevance — does it address the student's actual message?
- **A**ccuracy / groundedness — supported by retrieved context, no unsupported claims?
- **S**afety — no guarantees, pressure, or inappropriate certainty?
- **C**ompleteness — useful options, next steps, enough detail?
- **E**xplainability — explains why recommendations fit and what they open up?
- **F**airness — no biased or protected-characteristic-based reasoning?

| Badge | Score | Meaning |
|---|---|---|
| Green | 26-30 | Pass |
| Amber | 21-25 | Marginal — a "needs more info" note is appended |
| Red | 0-20 | Fail — still returned (never withheld), but flagged |

If the LLM judge call fails, a rule-based fallback evaluator scores the same six dimensions from heuristics (grounding evidence present, guardrail risk level, next steps present, etc.) — and is capped at `amber` even if its raw score would be green, so a degraded evaluation is never presented as a fully-judged one. `requires_revision` is always recomputed from the score in code, never trusted from the model's own opinion.

---

## Revision Loop

Every response is scored by the Evaluation Agent (RASCEF, pass threshold 24/30). If the score comes in below threshold, the orchestrator regenerates the recommendation, path plan, guardrail check, and evaluation exactly once — reusing the same retrieval results — and accepts whatever score comes back, even if it's still low. `revision_attempted: true/false` is carried on the orchestrator result and the observability log row, and the UI shows a note under the trace when a response was auto-regenerated. There is no loop beyond one retry: the code is a single `if`, not a `while`.

---

## Observability

Every turn writes one row to the local `observability_logs` SQLite table: timestamp, student id/name, user message, model names (generation/evaluation/embedding), retrieved document count, guardrail flags/risk level, RASCEF score/badge/dimension breakdown, prompt/ruleset versions, latency, and a cost estimate. Logging failures are swallowed at both the agent and the orchestrator call site — a broken log write never affects the response the student sees.

**Cost tracking is real, not a placeholder:** `UsageTracker` sums token usage across every LLM/embedding call made in a turn (generation, evaluation, embedding, including a critic/revision retry), broken down per model, and `estimated_cost_usd` is priced from that real breakdown using per-model $/1M-token rates.

---

## LangSmith

Optional. Set these in `.env` to enable tracing of every reasoning stage in a turn:

```
LANGSMITH_API_KEY=your-langsmith-key-here
LANGSMITH_PROJECT=pathfinder-ai
LANGSMITH_TRACING=true
```

Unset, unconfigured, or unreachable — the app works identically either way. Every tracing call is wrapped so a LangSmith outage can never break a turn. `TracingService` (`src/services/tracing_service.py`) owns that safety wrapper, governance-metadata enrichment, and the lazy singleton client; it delegates the actual SDK call to `LangSmithClient` (`src/infrastructure/langsmith_client.py`), the same pattern every other external dependency (OpenAI, Pinecone, SQLite) follows. When enabled, every trace is auto-enriched with the 9 prompt/ruleset version tags plus an overall `agent_version` — callers never need to know about prompt versioning to produce a fully-tagged trace. `EvaluationAgent._trace()` additionally sets evaluation score, quality badge, guardrail flags/risk level, `input_guardrail_flags`, and `revision_attempted` explicitly on every trace.

**Scope:** every agent in the "one turn, in order" sequence traces itself — Input Guardrail, Intent Router, Discovery, Retrieval, Recommendation, Path Planning, output Guardrail, and Evaluation — each receiving the same shared `TracingService` instance via constructor injection, exactly like `LLMService` or `RetrievalService` are injected elsewhere. Memory Agent and Observability Agent are deliberately excluded: they're bookkeeping steps already logged to SQLite, not AI decision points LangSmith is meant to explain. Because tracing is a constructor dependency rather than a bare module import, adding it to a new stage later means passing `tracing_service=_tracing_service` at the wiring site in `orchestrator.py`, not editing `tracing_service.py` itself.

**Every trace fires on a background thread, not inline.** A measured direct call to LangSmith's `create_run()` takes ~80-1000ms; blocking on that seven times per turn would add real, visible latency to every response. `TracingService.trace_event()` builds the trace payload on the caller's thread (cheap, no I/O) and submits the actual network call to a small shared `ThreadPoolExecutor`, returning immediately — measured at ~1-8ms per call after this change, versus ~80-1000ms before. Nothing in the same turn depends on a trace's return value, so there's no correctness cost to not waiting for it; a slow or unreachable LangSmith degrades to "the trace arrives late" instead of "the turn gets slower."

---

## Prompt Governance

All 7 LLM prompts (Discovery, Intent Router, Recommendation, Path Planning, RASCEF judge, General Chat, Suggestions) are externalized to versioned files under `src/prompts/<category>/<version>.md` and loaded through `src/services/prompt_loader.py` — none are hardcoded Python string constants anymore. The Guardrail Agent and Input Guardrail Agent's rule taxonomies (no LLM call, so no prompt) are externalized the same way as structured data: `src/prompts/guardrail/v1.yaml` and `src/prompts/input_guardrail/v1.yaml`.

- **Versioned:** each component's active version is set independently via `.env` (`DISCOVERY_PROMPT_VERSION`, `INTENT_ROUTER_PROMPT_VERSION`, `RECOMMENDATION_PROMPT_VERSION`, `PATH_PLANNING_PROMPT_VERSION`, `EVALUATION_PROMPT_VERSION`, `GENERAL_CHAT_PROMPT_VERSION`, `SUGGESTIONS_PROMPT_VERSION`, `GUARDRAIL_RULESET_VERSION`, `INPUT_GUARDRAIL_RULESET_VERSION`), each defaulting to today's content
- **Logged:** every orchestrator result and every `observability_logs` row carries the exact version tags that produced it
- **Traced:** every LangSmith trace carries the same version tags automatically

Bumping a prompt to a new version means adding a new file (e.g. `v2.md`) and changing one env var — no code change, and the previous version stays on disk for comparison or rollback. See decision D020 in `docs/12_DECISION_LOG.md`.

---

## Human-in-the-Loop

Every assistant response in the Streamlit UI has 👍 Helpful / 👎 Not Helpful buttons, no login required. Clicking one calls `orchestrator.submit_feedback(log_id, helpful)`, a thin wrapper around `ObservabilityRepository.save_feedback(log_id, helpful, feedback_text=None)` that attaches the rating directly to the observability row for that turn — so feedback is always linked to the exact model, prompts, and RASCEF scores that produced the response, with no extra join needed. `get_feedback_summary()` aggregates helpful/not-helpful counts across every rated turn. This is the foundation for future continuous improvement: spotting weak prompts, regressions, or systematically low-rated response patterns.

---

## Testing

No `pytest` suite — verification is via standalone scripts in `src/scripts/` that exercise real agents against the live OpenAI/Pinecone APIs:

```powershell
.venv_win\Scripts\python.exe src/scripts/test_retrieval.py               # Pinecone retrieval quality
.venv_win\Scripts\python.exe src/scripts/test_recommendation_agent.py    # Recommendation quality
.venv_win\Scripts\python.exe src/scripts/test_profile_extraction.py      # Discovery + profile merge
.venv_win\Scripts\python.exe src/scripts/test_path_planning.py           # Path planning + selection priority
.venv_win\Scripts\python.exe src/scripts/test_guardrail_agent.py         # All 10 guardrail flags in isolation
.venv_win\Scripts\python.exe src/scripts/test_guardrail_integration.py   # Guardrails through the full pipeline
.venv_win\Scripts\python.exe src/scripts/test_evaluation_agent.py        # RASCEF judge on 5 hand-built cases
.venv_win\Scripts\python.exe src/scripts/test_evaluation_integration.py  # RASCEF through the full pipeline
.venv_win\Scripts\python.exe src/scripts/test_observability.py           # Confirms a log row is persisted
.venv_win\Scripts\python.exe src/scripts/test_full_workflow.py           # Full acceptance test, 5 scenarios
.venv_win\Scripts\python.exe src/scripts/test_prompt_versioning.py       # Prompts load, agents run, versions reach the result
.venv_win\Scripts\python.exe src/scripts/test_human_feedback.py          # HITL feedback capture end to end
.venv_win\Scripts\python.exe src/scripts/test_revision_loop.py           # Critic/revision loop: low score retries once, never more
.venv_win\Scripts\python.exe src/scripts/test_intent_router.py           # Intent Router golden-dataset accuracy: confusion matrix + per-class precision/recall/F1
```

`docs/11_Test_Scenarios_and_Golden_Dataset.md` has 10 mock student profiles and 9 manual-review scenarios for prompt tuning and pre-demo review.

---

## Demo Scenarios

Three scenarios, chosen to each showcase a different part of the system in one turn:

1. **Undecided student** ("I like gaming, storytelling, and technology but I do not know what career I want.") — cleanest full-pipeline showcase: retrieval, 3 grounded recommendations, a path plan, no guardrail noise.
2. **College guidance without GPA** ("I want college recommendations for computer science but I do not know my GPA.") — best guardrail demo: `missing_gpa_for_college_guidance` and `missing_budget_for_affordability_guidance` fire live, and the response gets a visible limitations note.
3. **Returning student, two turns** (same name, second message adds GPA and a new interest) — best memory demo: profile visibly grows turn to turn, and the guardrail risk drops once GPA becomes known.

---

## Known Limitations

- `src/schemas/models.py` Pydantic models have drifted from the actual dict shapes agents pass around — no runtime validation layer enforces them today (see `docs/09_Agent_Contracts.md`)
- `DiscoveryAgent` doesn't yet extract `college_type_preference` / `pathway_preference` — those two profile fields stay empty unless populated some other way (`location_preference` / `budget_preference` are extracted as of prompt v2, see `docs/12_DECISION_LOG.md` D033)
- No automated `pytest` suite — verification is via the scripts above, run manually against live APIs
- Name-based student recognition only — no authentication, not suitable for real student data (see "Real Authentication (OAuth/SSO)" in `docs/19_Future_Vision.md`)
- `feedback_text` (free-text HITL comment) has no UI entry point yet — only the 👍/👎 buttons are wired; the column is only reachable with free text via `ObservabilityRepository` directly or `test_human_feedback.py`

---

## Requirements

- Python 3.13+
- OpenAI API key
- Pinecone API key
- LangSmith API key (optional — only needed for tracing; the app runs fully without it)

---

## Installation

**1. Set up the environment (Windows):**
```powershell
python -m venv .venv_win
.venv_win\Scripts\activate
pip install -r requirements.txt
```

Linux/WSL uses `.venv_linux` the same way; reserved for non-Windows work, not used in active development.

**2. Configure API keys:**
```powershell
copy .env.example .env
```
Then fill in `.env`:

| Variable | Required | Where to get it |
|---|---|---|
| `OPENAI_API_KEY` | Yes — used for generation, evaluation, and embeddings | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `PINECONE_API_KEY` | Yes — used for retrieval | [app.pinecone.io](https://app.pinecone.io) (free tier is enough for this project) |
| `PINECONE_INDEX_NAME` | No — defaults to `pathfinder-ai` | Only change this if you want a different index name |
| `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_TRACING` | No — see LangSmith below | [smith.langchain.com](https://smith.langchain.com) |

The app runs fully without LangSmith configured.

**3. Populate Pinecone (first run only, or after editing `data/*.json`):**
```powershell
.venv_win\Scripts\python.exe src/scripts/ingest_knowledge_base.py
```

---

## Run Instructions

```powershell
.venv_win\Scripts\activate
streamlit run src/app.py
```
Opens at `http://localhost:8501`.

---

## Project Structure

```
pathfinder-ai/
├── src/
│   ├── app.py                    # Streamlit UI
│   ├── config.py                 # Environment variables
│   ├── agents/                   # 11 agents + orchestrator
│   ├── services/                 # LLM, embeddings, retrieval, prompts, evaluation, tracing
│   ├── repositories/              # All SQL
│   ├── infrastructure/           # OpenAI, Pinecone, SQLite, KnowledgeLoader, LangSmith adapters
│   ├── schemas/models.py         # Reference domain models
│   ├── prompts/                  # Externalized, versioned prompts (discovery, recommendation,
│   │                              #   path_planning, evaluation .md; guardrail + input_guardrail .yaml rulesets)
│   └── scripts/                  # Ingestion + 13 verification scripts
├── data/                         # careers.json, majors.json, colleges.json, interests.json
├── docs/                         # Architecture, contracts, decisions, RAG design, test scenarios
├── requirements.txt
├── .env.example
└── README.md
```

---

## Documentation

Full documentation index, organized by topic (problem statement, architecture, RAG, guardrails,
evaluation, observability, roadmap, and more): **[`docs/README.md`](docs/README.md)**.

Highlights: the capstone-to-code mapping and full pattern list live in
[`docs/07_Capstone_Requirements_Mapping.md`](docs/07_Capstone_Requirements_Mapping.md);
the presentation deck is [`docs/14_Presentation_Deck.md`](docs/14_Presentation_Deck.md); what's
next beyond this MVP is [`docs/19_Future_Vision.md`](docs/19_Future_Vision.md).
