# PathFinder AI — Architecture Document

## Overview

PathFinder AI is a single-machine, local-first prototype built with Clean Architecture principles. The codebase is structured in explicit layers so that agents, infrastructure, and data access can evolve and be tested independently. The goal is not over-engineering — it is building a prototype that demonstrates real software design discipline alongside the AI system patterns.

---

## Design Principles

### SOLID

| Principle | How It Applies in PathFinder AI |
|---|---|
| **Single Responsibility** | Each agent, service, and repository has exactly one job. `StudentRepository` only does student CRUD. `LLMService` only wraps the generation API. Agents do not touch databases or API clients directly. |
| **Open / Closed** | The `LLMService` can be extended with a new model provider (e.g., switch from OpenAI to Anthropic) without changing any agent code. Agents call `llm_service.generate()` — the provider behind it is irrelevant to them. |
| **Liskov Substitution** | `LLMService` and `EmbeddingService` can be replaced with test doubles in unit tests. No agent breaks when a mock service is injected in place of a real one. |
| **Interface Segregation** | Services expose only the methods agents need. `RetrievalService` does not expose raw Pinecone SDK methods — it exposes `retrieve(query, top_k)`. Agents are not coupled to the SDK interface. |
| **Dependency Inversion** | Agents depend on service abstractions injected at construction time — not on `openai.OpenAI()`, `pinecone.Index()`, or `sqlite3` directly. The high-level agent policy does not depend on the low-level infrastructure detail. |

### Clean Architecture

The codebase is organized in four concentric layers. Inner layers have no knowledge of outer layers. Outer layers depend on inner layers — never the reverse.

```
┌───────────────────────────────────────────────────────────────────┐
│  Presentation Layer    src/app.py                                  │
│  Streamlit UI — no business logic, no infrastructure calls        │
├───────────────────────────────────────────────────────────────────┤
│  Application Layer     src/agents/                                 │
│  Agent use cases — depend on service abstractions, not infra      │
├───────────────────────────────────────────────────────────────────┤
│  Service Layer         src/services/                               │
│  Orchestrate infra for agents — LLM, embeddings, prompts, search  │
├───────────────────────────────────────────────────────────────────┤
│  Repository Layer      src/repositories/                           │
│  All data access — student, profile, message, observability CRUD  │
├───────────────────────────────────────────────────────────────────┤
│  Infrastructure Layer  src/infrastructure/                         │
│  External adapters — OpenAI SDK, Pinecone SDK, SQLite, JSON files │
├───────────────────────────────────────────────────────────────────┤
│  Domain Layer          src/schemas/                                │
│  Pure Pydantic models — no imports from any other layer           │
└───────────────────────────────────────────────────────────────────┘
```

### Repository Pattern

All database access is encapsulated in repository classes. Agents and services never write raw SQL or call `sqlite3` directly. This means:
- The database schema can change without touching agent logic
- Repositories can be mocked in tests without a real database
- Every data operation has one defined location to find or change

### Service Layer

Services sit between agents and infrastructure. An agent that needs to generate a response calls `LLMService.generate()` — it does not know or care whether the underlying model is GPT-4o-mini, GPT-4o, or a test stub. This is where the dependency inversion is applied concretely.

### Dependency Injection (Lightweight)

No DI framework is used — services are instantiated in `Orchestrator.__init__()` or passed as constructor arguments. This keeps it simple while still honoring the principle:

```python
# Agents receive services — they never instantiate infrastructure directly
class RecommendationAgent:
    def __init__(self, llm_service: LLMService, prompt_service: PromptService):
        self.llm = llm_service
        self.prompts = prompt_service
```

In tests, `LLMService` is replaced with a mock that returns a fixed response. No OpenAI key required to test agent logic.

---

## Layer Descriptions

### Layer 1 — Presentation (`src/app.py`)
- Streamlit chat UI
- Calls Orchestrator with student name and message
- Renders the response, recommendations, roadmap, and quality badge; keeps model names and config status out of the UI entirely
- No business logic, no infrastructure calls
- The only file in this layer

### Layer 2 — Agents (`src/agents/`)
- Each agent is a class with a single public method
- Agents receive their service dependencies via constructor injection
- Agents return plain dicts matching the shapes documented in `docs/09_Agent_Contracts.md`
- Agents never import from `src/infrastructure/` — only from `src/services/` and `src/schemas/`

| Agent | Class | Public Method | Depends On |
|---|---|---|---|
| Orchestrator | (module-level, `agents/orchestrator.py`) | `run_turn(student_name, user_message) → dict` | All agents |
| Memory Agent | `MemoryAgent` | `load_memory(name)`, `update_profile(name, updates)`, `save_turn(name, message, response, metadata)` | `StudentRepository`, `ProfileRepository`, `MessageRepository`, `ConversationSummaryRepository` |
| Input Guardrail Agent | `InputGuardrailAgent` | `check_input(user_message) → dict` | `TracingService` (optional, rule-based otherwise) |
| Intent Router Agent | `IntentRouterAgent` | `classify_intent(user_message, recent_messages, last_recommendations) → dict` | `LLMService`, `TracingService` (optional) |
| Discovery Agent | `DiscoveryAgent` | `extract_profile_updates(student_name, user_message, existing_profile) → dict` | `LLMService`, `TracingService` (optional) |
| Retrieval Agent | `RetrievalAgent` | `retrieve_relevant_context(user_message, profile, top_k, anchor_context) → dict` | `RetrievalService`, `TracingService` (optional) |
| Recommendation Agent | `RecommendationAgent` | `generate_recommendations(user_message, profile, retrieved_context, anchor_context) → dict` | `LLMService`, `PromptService`, `TracingService` (optional) |
| Path Planning Agent | `PathPlanningAgent` | `generate_path_plan(profile, recommendations) → dict` | `LLMService`, `TracingService` (optional) |
| Guardrail Agent | `GuardrailAgent` | `check_guardrails(response_payload, profile, user_message) → dict` | `TracingService` (optional, rule-based otherwise) |
| Evaluation Agent | `EvaluationAgent` | `evaluate(user_message, response_payload, retrieved_context, profile, guardrail_result, input_guardrail_flags=None, revision_attempted=False) → dict` | `EvaluationService`, `TracingService` (optional) |
| Observability Agent | `ObservabilityAgent` | `log_turn(event) → int \| None` | `ObservabilityRepository` |

Full input/output contracts: `docs/09_Agent_Contracts.md`. Agents pass plain dicts matching those documented contracts — see the implementation note at the top of that document regarding `src/schemas/models.py`.

### Agent Inventory — Purpose, Failure Handling, External Services

At-a-glance version of what's fully detailed in `docs/09_Agent_Contracts.md`. "External services" means direct network/DB dependencies — always reached through the Service or Infrastructure layer, never imported directly by the agent.

| Agent | Purpose | Key Inputs | Key Outputs | Failure Handling | External Services |
|---|---|---|---|---|---|
| Orchestrator | Runs the fixed per-turn pipeline; applies the one-retry critic/revision loop | `student_name`, `user_message` | Full turn result (response, recommendations, path plan, scores, trace) | Each stage degrades independently (no single global try/except); guardrail/evaluation notes appended rather than blocking; logging failures swallowed | None directly — delegates to every agent below |
| Input Guardrail Agent | Pre-generation rule-based check (profanity / frustration / prompt-injection); blocks the turn on `prompt_injection_detected` only, profanity/frustration stay detection-only | `user_message` | `{flags, passed}` | Pure string/dict logic, no I/O — nothing to fail | Optional LangSmith trace |
| Memory Agent | Load, merge, and persist student profile + conversation history | `student_name`, profile updates, message content | Profile dict, `recent_messages`, `session_number` | SQLite unavailable → empty in-memory profile for that turn; saves become no-ops rather than raising | SQLite (via repositories) |
| Intent Router Agent | Classify the turn (explore/roadmap/related_topic/general_chat) and resolve implicit references ("same") against last turn's offered items, using real conversation history (decision D034) | `user_message`, `recent_messages`, `last_recommendations` | `{intent, anchor_title, reasoning}` | Unparseable output, invalid intent, or an anchor_title not actually in last turn's list → falls back to `explore` rather than acting on a bad classification | OpenAI (`gpt-4o-mini` via `LLMService`); optional LangSmith trace |
| Discovery Agent | Extract profile fields from the latest message only; never invents GPA/grade | `student_name`, `user_message`, `existing_profile` | `student_profile_updates`, `confidence`, `missing_information`, `next_question` | Low-confidence/failed extraction → returns the existing profile unchanged plus a safe open-ended fallback question | OpenAI (`gpt-4o-mini` via `LLMService`); optional LangSmith trace |
| Retrieval Agent | Semantic search over the knowledge base; college results are state-filtered from `location_preference` and budget-boosted from `budget_preference` (decision D033); skipped entirely for "roadmap" intent, anchor-grounded for "related_topic" (decision D034) | `user_message`, `profile`, `top_k`, `anchor_context` | `query`, `retrieved_documents`, `retrieval_confidence` | Pinecone unreachable → transparent fallback to local tag-match search over the same JSON files | OpenAI (embeddings), Pinecone; optional LangSmith trace |
| Recommendation Agent | Generate 3–5 grounded career/major/college recommendations; skipped for "roadmap" (reused verbatim) and "general_chat" (decision D034); `anchor_context` grounds "related_topic" follow-ups | `user_message`, `profile`, `retrieved_context`, `anchor_context` | `recommendations[]`, `summary`, `follow_up_question` | Invalid/unusable model JSON → safe fallback response built from retrieved document titles instead of crashing | OpenAI (`gpt-4o-mini`); optional LangSmith trace |
| Path Planning Agent | Turn one selected recommendation into a phased roadmap; skipped for "general_chat" (decision D034) | `profile`, `recommendations`, `selected_override` | `selected_path`, `source`, short/medium/long-term steps, skills, projects | Unusable output or nothing to plan around → generic 3-step fallback roadmap | OpenAI (`gpt-4o-mini`); optional LangSmith trace |
| Guardrail Agent | Post-generation rule-based safety check (10 flags) | `response_payload`, `profile`, `user_message` | `passed`, `flags`, `risk_level`, `required_revisions` | Pure string/dict logic, no I/O — nothing to fail | Optional LangSmith trace |
| Evaluation Agent | RASCEF quality scoring — LLM-as-judge with a rule-based fallback | `user_message`, `response_payload`, `retrieved_context`, `profile`, `guardrail_result` | `scores`, `total_score`, `quality_badge`, `feedback`, `requires_revision` | Judge call fails → rule-based fallback (capped at `amber`); both fail → `not_evaluated` with zeroed scores, never a crash | OpenAI (`gpt-4o`); optional LangSmith trace |
| Observability Agent | Persist one log row per turn, including real per-model cost | Event dict (models, token usage, flags, scores, latency) | `log_id` (or `None` on failure) | Write failure swallowed at both the agent and the orchestrator call site — never blocks the response | SQLite |

### Layer 3 — Services (`src/services/`)
Services orchestrate infrastructure for agents. Each service wraps one or more infrastructure clients and exposes a clean, agent-friendly interface.

| Service | File | Responsibility |
|---|---|---|
| `LLMService` | `llm_service.py` | Call OpenAI chat completions (text or JSON mode); optional per-call model override (used to run GPT-4o for evaluation while everything else stays on GPT-4o-mini) |
| `EmbeddingService` | `embedding_service.py` | Call OpenAI embeddings; return vector |
| `RetrievalService` | `retrieval_service.py` | Build query, embed it, call Pinecone; fall back to local JSON tag-match on failure |
| `PromptService` | `prompt_service.py` | Format student profile + retrieved context + history into prompt text |
| `EvaluationService` | `evaluation_service.py` | RASCEF LLM-as-judge via GPT-4o; rule-based fallback evaluator |
| `TracingService` | `tracing_service.py` | Optional, no-op-safe LangSmith event logging; delegates the actual SDK call to `LangSmithClient` |

### Layer 4 — Repositories (`src/repositories/`)
Each repository is responsible for one table. All SQL lives here.

| Repository | File | Table | Operations |
|---|---|---|---|
| `StudentRepository` | `student_repository.py` | `students` | `create_or_get_student(name)`, `get_student(id)`, `update_last_seen(id)` |
| `ProfileRepository` | `profile_repository.py` | `profiles` | `get_profile(student_id)`, `upsert_profile(student_id, profile)` |
| `MessageRepository` | `message_repository.py` | `messages` | `save_message(student_id, role, content)`, `get_recent_messages(student_id, limit)` |
| `ConversationSummaryRepository` | `conversation_summary_repository.py` | `conversation_summaries` | `get_summary(student_id)`, `save_summary(student_id, session_number, text)` |
| `ObservabilityRepository` | `observability_repository.py` | `observability_logs` | `save_log(event)`, `get_recent_logs(limit)`, `get_logs_for_student(student_id, limit)` |

### Layer 5 — Infrastructure (`src/infrastructure/`)
Concrete external adapters. Only this layer imports `openai`, `pinecone`, `sqlite3`, or `langsmith`.

| Client | File | Wraps |
|---|---|---|
| `OpenAIClient` | `openai_client.py` | `openai.OpenAI()` — chat completions and embeddings |
| `PineconeClient` | `pinecone_client.py` | `pinecone.Pinecone()` — index init, upsert, query |
| `SQLiteClient` | `sqlite_client.py` | `sqlite3` — connection management, schema init, migrations |
| `KnowledgeLoader` | `knowledge_loader.py` | Load and parse `careers.json`, `majors.json`, `colleges.json`, `interests.json`; local tag-match fallback search |
| `LangSmithClient` | `langsmith_client.py` | `langsmith.Client()` — creates one run per trace event |

### Layer 6 — Domain (`src/schemas/`)
Pure Pydantic models. No imports from any other layer.

Key models: `StudentProfile`, `RetrievedDocument`, `DiscoveryOutput`, `RetrievalOutput`, `RecommendationOutput`, `PathPlanningOutput`, `GuardrailResult`, `EvaluationScores`/`EvaluationResult`, `ObservabilityLog`, `OrchestratorTurnResult`. These are reference domain models — they are not used to validate agent inputs/outputs at runtime today (agents pass plain dicts; see `docs/09_Agent_Contracts.md`), and some have drifted from the actual dict shapes as fields were added during implementation.

---

## Prompt Governance

Distinct from `PromptService` (Layer 3, above — formats profile/retrieval context into prompt *inputs*), prompt governance is about where prompt *text* itself lives. Every LLM-facing prompt is an externalized, versioned file under `src/prompts/<category>/<version>` — `discovery/v1.md`, `recommendation/v1.md`, `path_planning/v1.md`, `evaluation/rascef_v1.md`, `guardrail/v1.yaml`, `input_guardrail/v1.yaml` — none are hardcoded string constants in agent code. `src/services/prompt_loader.py` (`load_prompt()` / `load_ruleset()`) resolves paths from its own file location, caches via `functools.lru_cache`, and raises `PromptNotFoundError` at agent construction time on a missing file. Active versions are set per component in `.env` and aggregated by `config.prompt_version_metadata()`, which is attached to every orchestrator result, `observability_logs` row, and LangSmith trace. Full detail and the version table: `docs/09_Agent_Contracts.md`.

---

## Directory Structure

```
pathfinder-ai/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
│
├── docs/
│
├── data/
│   ├── careers.json                        # 73 curated careers
│   ├── majors.json                         # 47 curated majors
│   ├── colleges.json                       # 45 curated colleges
│   └── interests.json                      # 58 curated interest areas
│
├── src/
│   ├── app.py                              # Presentation — Streamlit UI only
│   ├── config.py                           # Environment variable loading
│   │
│   ├── agents/                             # Application layer
│   │   ├── orchestrator.py
│   │   ├── memory_agent.py
│   │   ├── input_guardrail_agent.py
│   │   ├── intent_router_agent.py
│   │   ├── discovery_agent.py
│   │   ├── retrieval_agent.py
│   │   ├── recommendation_agent.py
│   │   ├── path_planning_agent.py
│   │   ├── guardrail_agent.py
│   │   ├── evaluation_agent.py
│   │   └── observability_agent.py
│   │
│   ├── services/                           # Service layer
│   │   ├── llm_service.py                  # LLM generation (abstracts OpenAI)
│   │   ├── embedding_service.py            # Embedding generation (abstracts OpenAI)
│   │   ├── retrieval_service.py            # Semantic search + local fallback
│   │   ├── prompt_service.py               # Prompt context construction
│   │   ├── evaluation_service.py           # RASCEF LLM-as-judge + rule-based fallback
│   │   └── tracing_service.py              # Optional LangSmith tracing
│   │
│   ├── repositories/                       # Repository pattern
│   │   ├── student_repository.py
│   │   ├── profile_repository.py
│   │   ├── message_repository.py
│   │   ├── conversation_summary_repository.py
│   │   └── observability_repository.py
│   │
│   ├── infrastructure/                     # Infrastructure adapters
│   │   ├── openai_client.py
│   │   ├── pinecone_client.py
│   │   ├── sqlite_client.py
│   │   ├── knowledge_loader.py
│   │   └── langsmith_client.py
│   │
│   ├── schemas/                            # Domain models
│   │   └── models.py
│   │
│   └── scripts/                            # Ops + verification scripts (no pytest suite)
│       ├── ingest_knowledge_base.py        # One-time/re-runnable Pinecone ingestion
│       └── test_*.py                       # 13 scripts exercising real agents end to end
```

---

## Dependency Flow Diagram

The allowed import directions. Inner layers never import from outer layers.

```
app.py
  └── imports → agents/orchestrator.py
                   └── imports → agents/*.py
                                   └── imports → services/*.py
                                                   └── imports → infrastructure/*.py
                                   └── imports → repositories/*.py
                                                   └── imports → infrastructure/sqlite_client.py
                                   └── imports → schemas/models.py
```

**Strictly forbidden imports:**
- `agents/` importing from `infrastructure/` directly
- `schemas/` importing from anywhere (pure domain)
- `infrastructure/` importing from `agents/` or `services/`

---

## Data Flow — Conversation Turn

```
Student types message
        │
        ▼
app.py calls orchestrator.run_turn(student_name, user_message)
        │
        ▼
InputGuardrailAgent.check_input(user_message)
  └── Rule-based checks — no LLM call — profanity/frustration flags recorded, never block
  └── prompt_injection_detected is the exception: blocks the turn (decision D032, see below)
  └── Runs first: a pure function of user_message, no dependency on memory (decision D025)
        │
        ▼
MemoryAgent.load_memory(student_name)
  └── ProfileRepository.get_profile() + MessageRepository.get_recent_messages()
        │  (via SQLiteClient)
        ▼
[if prompt_injection_detected] → return blocked-turn result immediately (decision D032)
  └── Fixed safe response, no LLM call made, $0.00 cost, still logged + saved to memory
  └── Discovery / Retrieval / Recommendation / Path Planning / Guardrail / Evaluation all skipped
        │  (assume not blocked below)
        ▼
┌─────────────────────────── concurrent.futures.ThreadPoolExecutor(max_workers=2) ───────────────────────────┐
│ DiscoveryAgent.extract_profile_updates(student_name, user_message, existing_profile)                        │
│   └── LLMService.generate_json(extraction_prompt)  (via OpenAIClient, gpt-4o-mini)                          │
│                                                    ‖  (runs concurrently — decision D034)                    │
│ IntentRouterAgent.classify_intent(user_message, recent_messages, last_recommendations)                       │
│   └── LLMService.generate_json(...)  (via OpenAIClient, gpt-4o-mini)                                        │
│   └── returns {intent, anchor_title, reasoning} - falls back to "explore" if unparseable/invalid            │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────┘
        │  (both threads joined before continuing)
        ▼
MemoryAgent.update_profile(student_name, profile_updates)
  └── merge (list fields dedup, scalar fields only if non-empty) + ProfileRepository.upsert_profile()
        │
        ▼
Resolve anchor_title against current_profile["last_recommendations"] (decision D034)
  └── not found (or intent was "roadmap"/"related_topic" with nothing to anchor to) → intent falls back to "explore"
        │
        ▼
Branch on intent:
  ├── "roadmap" → skip Retrieval + RecommendationAgent entirely; reuse last_recommendations verbatim
  │     └── PathPlanningAgent.generate_path_plan(profile, recommendations, selected_override=anchor_item)
  ├── "general_chat" → RetrievalAgent runs (no anchor) if relevant; RecommendationAgent/PathPlanningAgent skipped
  │     └── orchestrator._generate_general_chat_response(...) — LLMService.generate_text(...), plain-text answer
  └── "explore" / "related_topic" → today's pipeline, "related_topic" adds anchor_context as extra grounding
        RetrievalAgent.retrieve_relevant_context(user_message, profile, top_k=5, anchor_context)
          └── RetrievalService.search_non_colleges(query)  (careers/majors/interests, unfiltered blend)
          └── RetrievalService.search_colleges(query, state=from location_preference)  (decision D033)
                ├── EmbeddingService.generate_embedding(query)  (via OpenAIClient)
                └── PineconeClient.query_vectors(vector)  └── fallback: KnowledgeLoader.search_by_tags()
                (budget_preference soft-boosts Public college_type in _rank_colleges(), no hard filter)
              ▼
        RecommendationAgent.generate_recommendations(user_message, profile, retrieved_context, anchor_context)
          └── PromptService.build(profile, retrieved_docs, history)
          └── LLMService.generate_json(system_prompt, user_prompt)  (via OpenAIClient, gpt-4o-mini)
              ▼
        PathPlanningAgent.generate_path_plan(profile, recommendations)
          └── selects top career > major > college_pathway, then LLMService.generate_json(...)
        │
        ▼
GuardrailAgent.check_guardrails(response_payload, profile, user_message)
  └── Rule-based checks — no LLM call — response gets a safe/limitations note appended if flagged
  └── Runs regardless of intent, including "general_chat" (empty recommendations/path_plan handled gracefully)
        │
        ▼
EvaluationAgent.evaluate(user_message, response_payload, retrieved_context, profile, guardrail_result,
                          input_guardrail_flags, revision_attempted, is_general_chat)
  └── EvaluationService.evaluate_with_llm_judge(...)  (via OpenAIClient, gpt-4o) — RASCEF scores
  └── is_general_chat=True: judge scores completeness/explainability on answer substance, not recommendation shape
  └── falls back to EvaluationService.evaluate_rule_based(...) if the judge call fails
  └── traces to LangSmith if configured (prompt versions, score, badge, guardrail + input guardrail flags, revision_attempted)
        │
        ▼
Critic / revision loop — at most one retry (decision D023)
  └── if requires_revision (total_score < 24): re-run the same branch that ran above once more
      (roadmap re-runs only PathPlanningAgent; general_chat re-runs only the answer call;
      explore/related_topic re-run RecommendationAgent → PathPlanningAgent), reusing retrieved_context,
      then GuardrailAgent → EvaluationAgent again
  └── response gets a "needs more info" note appended if still requires_revision after the retry
        ▼
orchestrator._enrich_recommendations(recommendations) — decision D026
  └── One extra LLM call (inline, unversioned prompt) adds fun_facts + future_outlook to each
      recommendation for display only — runs after scoring, so RASCEF/guardrails are unaffected
        ▼
ObservabilityAgent.log_turn(event)
  └── ObservabilityRepository.save_log(event) → returns new log_id
        │  (via SQLiteClient)
        ▼
MemoryAgent.save_turn(student_name, user_message, assistant_response, metadata)
  └── MessageRepository.save_message()
        │  (via SQLiteClient)
        ▼
Return response + full trace dict (incl. observability_log_id) → app.py → Streamlit UI
  (✅/⚠️ summary line + collapsed "Technical details" expander; 👍/👎 feedback buttons wired to
   orchestrator.submit_feedback(log_id, helpful) → ObservabilityRepository.save_feedback())
```

---

## Technology Choices

| Component | Technology | Reason |
|---|---|---|
| UI | Streamlit | Chat-native; no frontend code; isolates presentation layer cleanly |
| LLM generation | OpenAI GPT-4o-mini (via `LLMService`) | Cost-efficient; strong reasoning; abstracted behind service |
| LLM evaluation | OpenAI GPT-4o (via `LLMService`, selective) | Higher-quality scoring; same service abstraction, different model param |
| Embeddings | OpenAI `text-embedding-3-small` (via `EmbeddingService`) | Low cost; 1536 dimensions; sufficient for curated dataset |
| Vector store | Pinecone (via `PineconeClient`) | Managed; simple SDK; good free tier for prototype |
| Memory | SQLite (via `SQLiteClient`) | Zero-config; local; all access goes through repositories |
| Data schemas | Pydantic v2 | Reference domain models in `src/schemas/models.py`; not runtime-enforced at agent boundaries today (see `docs/09_Agent_Contracts.md`) |
| Knowledge base | JSON files (via `KnowledgeLoader`) | Human-editable; no DB overhead; fallback source for retrieval |
| Language | Python 3.13 | Ecosystem fit; full LLM SDK support |
| Optional tracing | LangSmith (via `TracingService`) | No-op-safe when unconfigured; logs RASCEF evaluation runs when `LANGSMITH_TRACING=true` |

---

## Constraints and Non-Goals

- No cloud deployment in MVP — runs fully local on Windows with `.venv_win`
- No authentication — student recognition is name-based for the prototype
- No LangGraph, LangChain, or agent framework — the orchestration loop is explicit and readable
- No abstract base classes or Protocol types — add them if tests demand mocking
- No dependency injection framework — constructor injection is sufficient at this scale
