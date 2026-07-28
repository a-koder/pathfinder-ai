# PathFinder AI — Compact Reference

This file is optimized for Claude Code sessions. Read this first. Load detailed docs only when the task requires them.

---

## Project Summary

PathFinder AI is a chat-first career discovery and college pathway guidance platform for high school students, parents, and school counselors. It is fully implemented end to end — memory, RAG retrieval, recommendations, path planning, guardrails, RASCEF evaluation, and observability all work together on every turn. Every LLM prompt is externalized and versioned, and every turn supports human-in-the-loop feedback.

---

## Primary Users

- High school students (primary)
- Parents (secondary)
- School counselors (secondary)

---

## Core Conversation Flow

```
Student message
  → Streamlit UI (src/app.py)
  → Orchestrator.run_turn()
  → Input Guardrail Agent   check_input() — flags profanity/frustration/prompt-injection; never blocks;
                             runs first, before memory load (pure function of the message)
  → Memory Agent            load_memory() — profile + recent history
  → Discovery Agent    ┐    extract_profile_updates() from this message
  → Retrieval Agent    ┘    Pinecone RAG (search_all, top_k=5) — runs concurrently with Discovery
                             on worker threads; neither depends on the other's output (decision D025)
  → Memory Agent            update_profile() — merge + persist (after both threads join)
  → Recommendation Agent    3-5 grounded career/major/college recommendations
  → Path Planning Agent     phased roadmap for the top career/major
  → Guardrail Agent         rule-based safety check; appends a note if flagged
  → Evaluation Agent        RASCEF score via GPT-4o judge (rule-based fallback); traces to
                             LangSmith if configured
  → Critic/revision loop    if requires_revision: regenerate recommendation → path plan →
                             guardrail → evaluation once more (max 1 retry)
  → Enrichment              fun_facts + future_outlook added per recommendation, display-only,
                             one extra LLM call after scoring (decision D026)
  → Observability Agent     writes one row to observability_logs, returns log_id
  → Memory Agent            save_turn() — persist messages
  → Response → UI (✅/⚠️ summary line + collapsed "Technical details" expander; 👍/👎 feedback buttons)
```

---

## Agent Roster

| Agent | File | Key Method |
|---|---|---|
| Orchestrator | `src/agents/orchestrator.py` | `run_turn(student_name, user_message)` |
| Input Guardrail Agent | `src/agents/input_guardrail_agent.py` | `check_input()` |
| Memory Agent | `src/agents/memory_agent.py` | `load_memory()`, `update_profile()`, `save_turn()` |
| Discovery Agent | `src/agents/discovery_agent.py` | `extract_profile_updates()` (concurrent with Retrieval) |
| Retrieval Agent | `src/agents/retrieval_agent.py` | `retrieve_relevant_context()` (concurrent with Discovery) |
| Recommendation Agent | `src/agents/recommendation_agent.py` | `generate_recommendations()` |
| Path Planning Agent | `src/agents/path_planning_agent.py` | `generate_path_plan()` |
| Guardrail Agent | `src/agents/guardrail_agent.py` | `check_guardrails()` |
| Evaluation Agent | `src/agents/evaluation_agent.py` | `evaluate()` |
| Observability Agent | `src/agents/observability_agent.py` | `log_turn()` |

Full contracts (inputs, outputs, validation, failure behavior): `docs/09_Agent_Contracts.md`.

---

## Storage

| Store | Purpose |
|---|---|
| SQLite (`data/memory.db`) | `students`, `profiles`, `messages`, `conversation_summaries`, `observability_logs` |
| Pinecone (index `pathfinder-ai`) | Semantic vector index of careers, majors, colleges, and interests (~170 vectors) |
| `data/careers.json` | 54 curated careers |
| `data/majors.json` | 44 curated majors |
| `data/colleges.json` | 27 curated colleges |
| `data/interests.json` | 45 curated interest areas (bridges vague interests to career directions) |

---

## Models

| Use | Model |
|---|---|
| All generation (discovery, recommendations, path planning) | `gpt-4o-mini` |
| RASCEF evaluation (LLM-as-judge) | `gpt-4o` |
| Embeddings | `text-embedding-3-small` |

---

## Career Recommendation Must Include

Every career recommendation item must contain:

| Field | Requirement |
|---|---|
| `title` | Career name |
| `why_it_fits` | Why it matches this student's profile |
| `why_exciting` | Why this career is worth being excited about |
| `opportunities` | Positive opportunity points |
| `real_world_impact` | What impact this career has in the world |
| `related_majors` | Majors that lead to this career |
| `skills_to_build` | Skills the student should develop |
| `adjacent_paths` | Related career paths |
| `evidence` | Retrieved document(s) supporting the recommendation |
| `confidence` | Float between 0.0 and 1.0 |
| `risks_or_limitations` | Honest limitations |
| `next_steps` | Concrete next steps |

**Constraint:** Positives must not overpromise salary, job security, admissions, or outcomes.

**Display-only additions (not part of this contract):** `fun_facts` and `future_outlook` also appear on each recommendation in the final orchestrator result, but they are added afterward by `orchestrator._enrich_recommendations()` — a separate, unversioned LLM call that runs after evaluation (decision D026) — not generated by the Recommendation Agent itself.

---

## Guardrail Flags

The Guardrail Agent (`src/agents/guardrail_agent.py`) is rule-based, no LLM call. Ten flags, in the order checked:

| Flag | Risk |
|---|---|
| `admission_guarantee` | high |
| `salary_guarantee` | high |
| `protected_attribute_bias` | high |
| `overconfidence` | medium |
| `pressure_language` | medium |
| `missing_gpa_for_college_guidance` | medium |
| `missing_budget_for_affordability_guidance` | medium |
| `missing_grounding` | medium |
| `missing_location_for_specific_college_guidance` | low |
| `insufficient_profile` | low |

`risk_level` on the result is the highest severity across triggered flags. `high` → a fixed safe note is appended to the response. `medium` → a "keep in mind" limitations note is appended. Full trigger phrases: `docs/09_Agent_Contracts.md`.

---

## Input Guardrail Flags

The Input Guardrail Agent (`src/agents/input_guardrail_agent.py`) is rule-based, no LLM call. Runs on the raw student message before Discovery. Three flags, detection only — never blocks or rewrites the message:

| Flag | Trigger |
|---|---|
| `profanity_detected` | Common profanity, word-boundary matched |
| `frustration_detected` | Phrases like "this is stupid", "i give up", "why is this so hard" |
| `prompt_injection_detected` | Phrases like "ignore previous instructions", "reveal your system prompt", "developer mode" |

Flags are recorded on the turn (`input_guardrail_flags`) and shown in the collapsed "Technical details" section. Full trigger phrases: `docs/09_Agent_Contracts.md`.

---

## RASCEF Evaluation

Each response is scored 1–5 per dimension by GPT-4o (LLM-as-judge), with a rule-based fallback if the judge call fails. Max total: 30.

- **R**elevance
- **A**ccuracy / groundedness
- **S**afety
- **C**ompleteness
- **E**xplainability
- **F**airness

## Quality Badges

| Badge | Score Range | Meaning |
|---|---|---|
| Green | 26–30 | Pass |
| Amber | 21–25 | Marginal — response returned with a "needs more info" note; rule-based-fallback results are capped here even if the raw score would be green |
| Red | 0–20 | Fail — response still returned (never withheld), but flagged |

**Pass threshold:** 24/30. `requires_revision` is computed deterministically from `total_score`, never trusted from the model.

**Critic / revision loop (decision D023):** If `requires_revision` is true on the first attempt, the orchestrator regenerates the recommendation, path plan, guardrail check, and evaluation exactly once more (same retrieved context reused), and accepts whatever the retry produces — never more than one retry. `revision_attempted: true/false` is carried on the result and the observability row.

---

## Observability

Every turn writes one row to `observability_logs` via `ObservabilityRepository`: timestamp, student id/name, user message, model names (generation/evaluation/embedding), retrieved doc count, guardrail flags/risk level, RASCEF score/badge/dimension breakdown, prompt versions, latency, and a real cost estimate. `UsageTracker` (decision D029) sums token usage across every LLM/embedding call made that turn, per model, and `estimated_cost_usd` is priced from that real breakdown — no longer a placeholder.

## Prompt Governance

All 4 LLM prompts (Discovery, Recommendation, Path Planning, RASCEF judge) live in versioned files under `src/prompts/<category>/<version>.md`, loaded via `src/services/prompt_loader.py` — none are hardcoded in agent code. `GuardrailAgent` and `InputGuardrailAgent`'s rule taxonomies (no LLM call) are similarly externalized as `src/prompts/guardrail/v1.yaml` and `src/prompts/input_guardrail/v1.yaml`. Active versions are configured per component in `.env` (`DISCOVERY_PROMPT_VERSION`, `RECOMMENDATION_PROMPT_VERSION`, `PATH_PLANNING_PROMPT_VERSION`, `EVALUATION_PROMPT_VERSION`, `GUARDRAIL_RULESET_VERSION`, `INPUT_GUARDRAIL_RULESET_VERSION`), all defaulting to today's content. Version tags are attached to every orchestrator result, observability log row, and LangSmith trace. Full detail: `docs/09_Agent_Contracts.md`.

## Human-in-the-Loop Feedback

Every assistant response in the Streamlit UI has 👍 Helpful / 👎 Not Helpful buttons (no authentication required), wired to `orchestrator.submit_feedback(log_id, helpful)` → `ObservabilityRepository.save_feedback(log_id, helpful, feedback_text=None)` — recording the rating directly on the observability row that produced the response, keeping feedback naturally linked to the exact model, prompts, and scores behind that turn. `get_feedback_summary()` returns aggregate helpful/not-helpful counts. `feedback_text` (free-text comment) has no UI entry point yet — only reachable directly via `ObservabilityRepository` or `src/scripts/test_human_feedback.py`. Supports future continuous improvement (prompt tuning, regression detection) once enough feedback accumulates.

## LangSmith (optional)

Set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` in `.env` to log each evaluation's inputs/outputs to LangSmith via `src/services/tracing_service.py`. Each trace explicitly carries: prompt versions, `agent_version`, evaluation score, quality badge, guardrail flags, guardrail risk level, `input_guardrail_flags`, and `revision_attempted` — the first two are auto-merged by `trace_event()` from `config.prompt_version_metadata()` and `config.AGENT_VERSION`; the rest are set explicitly by `EvaluationAgent._trace()`. Since `evaluate()` runs once per attempt, a turn that hits the critic/revision loop produces two traces. Fully optional — unset or misconfigured, every tracing call is a no-op and never affects the app.

---

## Parallelization

Discovery and Retrieval run concurrently on worker threads (`concurrent.futures.ThreadPoolExecutor(max_workers=2)` in `orchestrator.run_turn()`) — both depend only on the state memory load already produced, not on each other, and both are I/O-bound OpenAI/Pinecone calls through a shared, thread-safe SDK client. The Input Guardrail check also moved to run before memory load, since it's a pure function of the raw message. Neither change alters output for any given input — only turn latency (decision D025).

---

## Clean Architecture Layers

**Layering:** `UI → Orchestrator → Agents → Services → Repositories → Infrastructure → Schemas`

Inner layers never import from outer layers. Agents call services only — never `openai`, `pinecone`, or `sqlite3` directly.

| Layer | Location | Rule |
|---|---|---|
| Presentation | `src/app.py` | No business logic; no infrastructure calls |
| Application | `src/agents/` | Call services only; never import infrastructure |
| Service | `src/services/` | Wrap infrastructure; expose clean interfaces to agents |
| Repository | `src/repositories/` | All SQL lives here; no SQL in agents or services |
| Infrastructure | `src/infrastructure/` | Only layer that imports `openai`, `pinecone`, `sqlite3` |
| Domain | `src/schemas/models.py` | No imports from any other layer; not currently enforced at runtime (see `docs/09_Agent_Contracts.md`) |

---

## Testing

No `pytest`-style `tests/` directory — verification is done via standalone scripts in `src/scripts/` that exercise real agents against the live OpenAI/Pinecone APIs (and a local SQLite test student). Run any of them with `.venv_win\Scripts\python.exe src/scripts/<name>.py`:

| Script | Covers |
|---|---|
| `test_retrieval.py` | Pinecone retrieval quality across sample queries |
| `test_recommendation_agent.py` | Recommendation Agent output quality |
| `test_profile_extraction.py` | Discovery Agent + profile merge across turns |
| `test_path_planning.py` | Path Planning Agent, incl. career-over-college selection priority |
| `test_guardrail_agent.py` | All 10 guardrail flags in isolation |
| `test_guardrail_integration.py` | Guardrails through the full orchestrator flow |
| `test_evaluation_agent.py` | RASCEF judge on 5 hand-built cases (strong/weak/unsafe responses) |
| `test_evaluation_integration.py` | RASCEF evaluation through the full orchestrator flow |
| `test_observability.py` | One turn logs a row to `observability_logs` |
| `test_full_workflow.py` | Full backend acceptance test — 5 scenarios covering the entire pipeline, no Streamlit |
| `test_prompt_versioning.py` | Every prompt/ruleset loads, all affected agents still run, version tags reach the orchestrator result |
| `test_human_feedback.py` | HITL feedback capture: `save_feedback()`, `get_feedback_summary()` |
| `test_revision_loop.py` | Critic/revision loop: low first score triggers exactly one retry, never more, via a scripted `EvaluationAgent` double |

`src/scripts/ingest_knowledge_base.py` is the one-time (or re-run-as-needed) Pinecone ingestion script — not a test.

---

## Token Optimization Rules

1. Load this file first in every Claude Code session.
2. Load only the specific detailed doc required for the current task:
   - Architecture questions → `docs/04_Architecture.md`
   - Agent contracts → `docs/09_Agent_Contracts.md`
   - Error handling → `docs/10_Error_Handling_and_Fallbacks.md`
   - Test scenarios / golden dataset → `docs/11_Test_Scenarios_and_Golden_Dataset.md`
   - RAG / Pinecone details → `docs/13_RAG_Implementation.md`
   - Prior decisions → `docs/12_DECISION_LOG.md`
3. Do not load all docs for a focused coding task.
4. Prefer structured, specific prompts over "fix everything" requests.
5. Use summaries and diffs rather than full file reads when reviewing changes.

---

## Known Limitations

- `src/schemas/models.py` Pydantic models have drifted from the actual dict shapes agents pass around (see `docs/09_Agent_Contracts.md`) — no runtime validation layer enforces them today
- `DiscoveryAgent` doesn't yet extract `location_preference` / `budget_preference` / `college_type_preference` / `pathway_preference`, so those `StudentProfile` fields stay empty unless populated some other way
- No automated `pytest` suite — verification is via the `src/scripts/test_*.py` scripts listed above, run manually against live APIs
- `feedback_text` (free-text HITL comment) has no UI entry point yet — the 👍/👎 buttons are wired, but free text is only reachable via `ObservabilityRepository` directly (or `test_human_feedback.py`)
- No `out_of_scope` guardrail — scholarship/FAFSA questions aren't redirected, they're passed to the Recommendation Agent, which will attempt a weak, ungrounded answer
