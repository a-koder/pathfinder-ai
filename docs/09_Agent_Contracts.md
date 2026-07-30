# PathFinder AI — Agent Contracts

## Purpose

This document defines the input/output shapes for every agent in PathFinder AI. These contracts make the system verifiably multi-agent — each agent has a bounded responsibility and a defined failure behavior. Without contracts, a "multi-agent system" is just a single prompt with sections.

**Implementation note:** Agents pass plain Python dicts matching the shapes below — not validated Pydantic model instances. `src/schemas/models.py` defines the target domain models for reference and for any future consumer that wants typed objects, but no runtime validation layer currently enforces these shapes at agent boundaries. Treat the JSON examples in this document as the authoritative contract; `src/schemas/models.py` has not been kept fully in sync with every field added during implementation (see `docs/12_DECISION_LOG.md`).

---

## Agent Persona

The system doesn't just return structured data — the `response` text a student actually reads has a deliberate voice, set in `src/prompts/recommendation/v1.md`:

- **Name:** PathFinder
- **Tone:** Warm, encouraging, honest, and practical — like a counselor who already knows the student, not a search engine reading off a list
- **Rules that hold across every response:** never guarantee admission, salary, or job security; always include at least one less-obvious option alongside familiar ones when the data supports it; end with one follow-up question, never several at once

This shows up directly in the demo — the difference between "Data Analyst: high-paying field with strong job security" (a claim the guardrails would catch) and "Data Analyst: turns raw numbers into decisions that change how hospitals and governments operate" (grounded, exciting, and something the model is actually allowed to say) is this persona doing its job.

---

## Prompt Governance

Every LLM-facing prompt is externalized and versioned (decision D020) — none are hardcoded in agent code anymore.

| Component | Prompt file | Configured via | Default |
|---|---|---|---|
| Discovery Agent | `src/prompts/discovery/v1.md` | `DISCOVERY_PROMPT_VERSION` | `v1` |
| Recommendation Agent | `src/prompts/recommendation/v1.md` | `RECOMMENDATION_PROMPT_VERSION` | `v1` |
| Path Planning Agent | `src/prompts/path_planning/v1.md` | `PATH_PLANNING_PROMPT_VERSION` | `v1` |
| Evaluation Service (RASCEF judge) | `src/prompts/evaluation/rascef_v1.md` | `EVALUATION_PROMPT_VERSION` | `rascef_v1` |
| Guardrail Agent (ruleset, not a prompt — no LLM call) | `src/prompts/guardrail/v1.yaml` | `GUARDRAIL_RULESET_VERSION` | `v1` |
| Input Guardrail Agent (ruleset, not a prompt — no LLM call) | `src/prompts/input_guardrail/v1.yaml` | `INPUT_GUARDRAIL_RULESET_VERSION` | `v1` |

`src/services/prompt_loader.py` exposes `load_prompt(category, version) -> str` (markdown) and `load_ruleset(category, version) -> dict` (YAML). Both resolve paths from the loader's own file location — not the working directory — and cache results in memory via `functools.lru_cache`, so repeated agent construction never re-reads disk. A missing file raises `PromptNotFoundError` (a clear, typed exception naming the expected path) at agent construction time — fast failure at startup, not a silent gap discovered mid-conversation.

Every agent constructor accepts an optional `prompt_version` (or `ruleset_version` for `GuardrailAgent` / `InputGuardrailAgent`) override; when omitted, it reads the matching `config.py` constant. Bumping a version (env var or constructor arg) requires no code change.

`config.prompt_version_metadata()` is the single source of truth for the version tags attached to every turn: `discovery_prompt_version`, `recommendation_prompt_version`, `path_planning_prompt_version`, `evaluation_prompt_version`, `guardrail_ruleset_version`, `input_guardrail_ruleset_version` (each formatted as `"<component>_<version>"`, e.g. `"discovery_v1"`, except evaluation whose configured version already includes the framework name). This same dict is merged into: the `run_turn()` return value, every `observability_logs` row (`prompt_versions` column, JSON), and every LangSmith trace (`tracing_service._governance_metadata()`, which also adds `agent_version` from `config.AGENT_VERSION`).

---

## Agent Roster

| Agent | File | Key Method | When Called | Service Dependencies |
|---|---|---|---|---|
| Orchestrator | `src/agents/orchestrator.py` | `run_turn(student_name, user_message)` | Every conversation turn | All agents + services (injected) |
| Input Guardrail Agent | `src/agents/input_guardrail_agent.py` | `check_input(user_message)` | First step in the turn, before memory load | `TracingService` (optional) |
| Memory Agent | `src/agents/memory_agent.py` | `load_memory()`, `update_profile()`, `save_turn()` | Load right after the input guardrail; merge after Discovery; save at turn end | `StudentRepository`, `ProfileRepository`, `MessageRepository`, `ConversationSummaryRepository` |
| Discovery Agent | `src/agents/discovery_agent.py` | `extract_profile_updates()` | Concurrently with Retrieval, after memory load | `LLMService`, `TracingService` (optional) |
| Retrieval Agent | `src/agents/retrieval_agent.py` | `retrieve_relevant_context()` | Concurrently with Discovery, after memory load | `RetrievalService`, `TracingService` (optional) |
| Recommendation Agent | `src/agents/recommendation_agent.py` | `generate_recommendations()` | After Discovery and Retrieval both complete and the profile is merged | `LLMService`, `PromptService`, `TracingService` (optional) |
| Path Planning Agent | `src/agents/path_planning_agent.py` | `generate_path_plan()` | After Recommendation | `LLMService`, `TracingService` (optional) |
| Guardrail Agent | `src/agents/guardrail_agent.py` | `check_guardrails()` | After Path Planning, before Evaluation | `TracingService` (optional) |
| Evaluation Agent | `src/agents/evaluation_agent.py` | `evaluate()` | After Guardrail | `EvaluationService`, `TracingService` (optional) |
| Observability Agent | `src/agents/observability_agent.py` | `log_turn()` | End of every turn | `ObservabilityRepository` |

**"Optional" above means the constructor accepts `tracing_service: TracingService | None = None` and falls back to constructing its own (safe, no-op-when-unconfigured) instance if none is given — so every existing call site that constructs an agent directly, including the test scripts, keeps working unchanged. In the running app, `orchestrator.py` injects one shared `TracingService` instance into all seven, so a single client connection (when tracing is actually enabled) serves the whole turn.**

## Dependency Injection Pattern

Agents never instantiate their own infrastructure or service dependencies. All dependencies are injected via constructor. This enforces Dependency Inversion and makes every agent independently testable with mock services.

**`orchestrator.py` wires all dependencies once at module load:**

```python
# Infrastructure
sqlite = SQLiteClient()
openai_client = OpenAIClient()
pinecone_client = PineconeClient()
knowledge_loader = KnowledgeLoader()

# Repositories
student_repo = StudentRepository(sqlite)
profile_repo = ProfileRepository(sqlite)
message_repo = MessageRepository(sqlite)
summary_repo = ConversationSummaryRepository(sqlite)
observability_repo = ObservabilityRepository(sqlite)

# Services
embedding_service = EmbeddingService(openai_client)
retrieval_service = RetrievalService(embedding_service, pinecone_client, knowledge_loader)
llm_service = LLMService(openai_client)
prompt_service = PromptService()
evaluation_service = EvaluationService(llm_service)
tracing_service = TracingService()

# Agents — receive only what they need
memory = MemoryAgent(student_repo, profile_repo, message_repo, summary_repo)
input_guardrail = InputGuardrailAgent(tracing_service=tracing_service)
discovery = DiscoveryAgent(llm_service, tracing_service=tracing_service)
retrieval = RetrievalAgent(retrieval_service, tracing_service=tracing_service)
recommendation = RecommendationAgent(llm_service, prompt_service, tracing_service=tracing_service)
path_planning = PathPlanningAgent(llm_service, tracing_service=tracing_service)
guardrail = GuardrailAgent(tracing_service=tracing_service)
evaluation = EvaluationAgent(evaluation_service, tracing_service=tracing_service)
observability = ObservabilityAgent(observability_repo)
```

The same `tracing_service` instance is passed to all seven — one shared client connection, not one per agent. This is the same dependency-injection style every other cross-cutting service already follows (`llm_service` reused across four agents above); tracing was the one exception before this pass, importing `langsmith` as a bare module call from inside `EvaluationAgent` instead of receiving it as a constructor argument.

**What this enables:**
- In tests, pass a fake `LLMService` to any agent — no real API key needed (see `src/scripts/test_*.py`, which mostly use the real services against live APIs, but the agents themselves don't care)
- Swap `OpenAIClient` for another provider without changing any agent
- Add a new agent that needs a new service — only the wiring block in `orchestrator.py` changes

---

## 1. Orchestrator

**Responsibility:** Controls the full per-turn flow. Calls each agent in order, threads state between them, and returns the final response plus a full trace dict to the UI.

**When called:** On every student message, via `run_turn(student_name, user_message)`.

**Actual flow:** `input_guardrail.check_input(user_message)` → `memory.load_memory()` → (if `prompt_injection_detected` fired, short-circuit here and return a blocked-turn result — see decision D032 and the Input Guardrail Agent section below; everything past this point assumes it did not) → **`discovery.extract_profile_updates()` ‖ `retrieval.retrieve_relevant_context()` (concurrent)** → `memory.update_profile()` → `_match_previous_choice()` (checks whether this message names one of last turn's offered recommendations, decision D028) → `recommendation.generate_recommendations()` → `path_planning.generate_path_plan()` (using the matched item as `selected_override` if one was found) → `guardrail.check_guardrails()` → (append safe note if high/medium risk) → `evaluation.evaluate()` → **critic/revision loop** (if `evaluation.requires_revision` is true: regenerate recommendation → path plan → guardrail → evaluation exactly once more, reusing the same retrieval results and the same `selected_override`) → (append "needs more info" note if the possibly-revised `requires_revision` is still true) → `memory.remember_last_recommendations()` (persists this turn's offered items for the next turn's choice matching) → **enrichment** (fun facts + future outlook, display-only) → `observability.log_turn()` → `memory.save_turn()` → return.

**Parallelization (decision D025):** Discovery and Retrieval both depend only on memory load's output — Discovery needs the pre-turn profile, Retrieval only needs the raw message (its `profile` argument is accepted but unused, see Retrieval Agent below) — and neither depends on the other's output, so they run concurrently via `concurrent.futures.ThreadPoolExecutor(max_workers=2)` in `orchestrator.run_turn()`. Both are I/O-bound network calls (OpenAI / Pinecone through a shared, thread-safe SDK client), so this overlaps wait time rather than parallelizing CPU work — no change in output for any given input, only latency. The Input Guardrail check was also moved to run before memory load, since it is a pure function of `user_message` alone and has no dependency on memory either way.

**Critic / revision loop (decision D023):** `input_guardrail`, `discovery`, and `retrieval` run once per turn regardless of evaluation outcome — only `recommendation.generate_recommendations()`, `path_planning.generate_path_plan()`, `guardrail.check_guardrails()`, and `evaluation.evaluate()` are re-run on a retry, via the shared `_generate_and_score()` helper in `orchestrator.py`. At most one retry ever happens: the loop is a single `if`, not a `while`, so a still-low score after the retry is accepted and surfaced (with the "needs more info" note) rather than retried again. `revision_attempted` is `true` whenever a retry happened, `false` otherwise — set once and never re-evaluated after the retry decision.

**Enrichment (decision D026):** After the revision loop settles on a final response, `orchestrator._enrich_recommendations()` makes one additional LLM call (not through `PromptLoader` — an inline, unversioned system prompt, since this is display-only polish, not a governed generation step) to add `fun_facts` (list of 2-3 strings) and `future_outlook` (one positively-framed sentence) to each recommendation item. This runs strictly after guardrails and evaluation have already scored the response, so it never affects RASCEF scoring or guardrail checks, and its output is never persisted — it is regenerated fresh on every turn and only appears in the `recommendations` list returned to the UI. See the Recommendation Agent section below for how this relates to that agent's own contract.

**Output contract (`run_turn` return value):**
```json
{
  "student_name": "Jordan",
  "response": "Thanks, Jordan! ...(full counselor-style reply, with any guardrail/evaluation notes appended)...",
  "quality_badge": "green",
  "guardrail_flags": ["missing_gpa_for_college_guidance"],
  "guardrail_risk_level": "medium",
  "guardrail_required_revisions": ["Ask for GPA or provide only broad college pathway categories."],
  "input_guardrail_flags": [],
  "revision_attempted": false,
  "evaluation_score": 27,
  "evaluation_feedback": ["Relevance: ...", "Safety: ..."],
  "evaluation_scores": {"relevance": 5, "accuracy": 4, "safety": 5, "completeness": 4, "explainability": 5, "fairness": 4},
  "evaluation_requires_revision": false,
  "retrieved_document_count": 5,
  "retrieved_documents": [ {"doc_id": "career_data_analyst", "doc_type": "career", "title": "Data Analyst", "score": 0.62, "metadata": {}} ],
  "recommendations": [ {"type": "career", "title": "Data Analyst", "fun_facts": ["...", "..."], "future_outlook": "...", "...": "..."} ],
  "profile": {"name": "Jordan", "grade_level": "11", "gpa": 3.4, "interests": ["math", "video games"], "...": "..."},
  "missing_information": ["strengths", "career_preferences"],
  "next_question": "What subjects or activities do you feel you excel in?",
  "path_plan": {"selected_path": "Data Analyst", "source": "auto_priority", "short_term_steps": ["..."], "...": "..."},
  "observability_log_id": 27,
  "token_usage_by_model": {"gpt-4o-mini": {"prompt_tokens": 1957, "completion_tokens": 1618}, "...": "..."},
  "estimated_cost_usd": 0.0090,
  "discovery_prompt_version": "discovery_v1",
  "recommendation_prompt_version": "recommendation_v1",
  "path_planning_prompt_version": "path_planning_v1",
  "evaluation_prompt_version": "rascef_v1",
  "guardrail_ruleset_version": "guardrail_v1",
  "input_guardrail_ruleset_version": "input_guardrail_v1"
}
```

The `*_version` keys come from `config.prompt_version_metadata()` (see Prompt Governance above) — static per process, not computed per turn, but included on every result for traceability. `observability_log_id` is the `observability_logs.log_id` row written by this turn (or `None` if logging failed) — the UI uses it to wire the 👍/👎 feedback buttons to `ObservabilityRepository.save_feedback()`, via a thin `submit_feedback(log_id, helpful, feedback_text=None)` wrapper in `orchestrator.py` (so `app.py` never imports repositories directly).

**Failure behavior:**
- A detected `prompt_injection_detected` input flag blocks the turn entirely (decision D032) — a fixed safe response is returned and Discovery/Retrieval/Recommendation/Path Planning/Guardrail/Evaluation are all skipped; see the Input Guardrail Agent section below.
- A guardrail `risk_level: high` gets a fixed safe note appended to the response (never returned unmodified); `medium` gets a "keep in mind" limitations note built from `required_revisions`.
- If `evaluation.requires_revision` is still true after the critic/revision retry (see above), a short note is appended asking the student to share more profile detail.
- Logging failures (`observability.log_turn()`) are swallowed at both the agent and orchestrator call site — a broken log write never breaks the response; `observability_log_id` is simply `None` in that case, and the feedback buttons don't render.
- Retrieval, LLM generation, and profile persistence each degrade independently (see the Retrieval Agent, Recommendation Agent, and Memory Agent sections below for each one's specific fallback); there is no single global exception handler around the whole turn today — each stage is responsible for its own safe fallback.

---

## 2. Memory Agent

**Responsibility:** Reads the student's profile and recent conversation history at turn start (`load_memory`). Merges new profile fields into the persisted profile (`update_profile`). Overwrites the turn's offered recommendations for next-turn choice matching (`remember_last_recommendations`, decision D028). Saves both sides of the turn (`save_turn`).

**When called:** `load_memory()` at turn start; `update_profile()` right after Discovery; `remember_last_recommendations()` after the critic/revision loop settles; `save_turn()` at turn end.

**`load_memory(student_name)` output:**
```json
{
  "student_id": 42,
  "profile": {
    "name": "Jordan",
    "grade_level": "11",
    "gpa": 3.4,
    "interests": ["math", "video games"],
    "strengths": ["analytical thinking"],
    "career_preferences": [],
    "college_preferences": [],
    "favorite_careers": [],
    "location_preference": "",
    "budget_preference": "",
    "college_type_preference": "",
    "pathway_preference": "",
    "conversation_summary": ""
  },
  "recent_messages": [
    {"role": "user", "content": "I like math and video games."},
    {"role": "assistant", "content": "That's a great combination! ..."}
  ],
  "session_number": 2
}
```

**`update_profile(student_name, profile_updates)` output:** the merged profile dict (same shape as `profile` above). List fields (`interests`, `strengths`, `career_preferences`, `college_preferences`, `favorite_careers`) are merged case-insensitively without duplicates; scalar fields (`grade_level`, `gpa`, the four preference fields) are only overwritten when the new value is non-empty/non-null.

**`remember_last_recommendations(student_id, recommendations)`:** overwrites (does not merge) a `last_recommendations` key on the profile with this turn's offered recommendation items verbatim. Unlike the list fields above, this is not an accumulating trait — it's replaced every turn so it always reflects only what was *just* offered, letting the next turn's `_match_previous_choice()` (in `orchestrator.py`) check whether the student's reply names one of them. Returns nothing; failures are swallowed.

**`save_turn(student_name, user_message, assistant_response, metadata)`:** persists the user and assistant messages. Returns nothing; failures are swallowed.

**Failure behavior:** If SQLite is unavailable, `load_memory` returns an empty in-memory profile (`{"conversation_summary": ""}`) and `update_profile`/`save_turn` become no-ops for that turn rather than raising.

**Note:** `location_preference`, `budget_preference`, `college_type_preference`, and `pathway_preference` exist on `StudentProfile` (`src/schemas/models.py`) as optional fields for the Guardrail Agent to check, but `DiscoveryAgent` does not currently extract them from conversation — they stay empty unless set some other way. This is a known gap, not a bug (see `docs/12_DECISION_LOG.md`).

---

## 3. Input Guardrail Agent

**Responsibility:** Rule-based, LLM-free pre-generation safety check on the raw student message, run before any other agent sees it. `profanity_detected` and `frustration_detected` are detection-only, exactly as originally scoped in decision D023. `prompt_injection_detected` is no longer detection-only (decision D032): it blocks the turn.

**When called:** First step of the turn, before `memory.load_memory()` (this agent is a pure function of the raw message, so it has no dependency on stored state — decision D025). The block itself, when it fires, is applied right after memory load, so the response can still reflect the student's existing profile/`student_id` for logging even on a blocked turn — see the Orchestrator section above.

**Input:** `check_input(user_message)`.

**Output contract:**
```json
{
  "flags": ["frustration_detected"],
  "passed": false
}
```

`passed` is `false` whenever any flag fires; `flags` is an empty list on a clean message.

**Flag taxonomy:**

| Flag | Trigger |
|---|---|
| `profanity_detected` | Common profanity, word-boundary matched (e.g. does not false-trigger on "assistant" or "class") |
| `frustration_detected` | Phrases like "this is stupid", "i give up", "you're not helping", "why is this so hard" |
| `prompt_injection_detected` | Phrases like "ignore previous instructions", "reveal your system prompt", "pretend you are", "developer mode" |

**Matching:** `\b`-anchored regex word-boundary matching against phrase lists — chosen specifically to avoid single-word terms false-triggering inside legitimate words.

**Orchestrator behavior on the result:** Flags are always recorded on the turn (`input_guardrail_flags` in the result dict and the `observability_logs` row) and shown in the UI's collapsed "Technical details" section. For `profanity_detected`/`frustration_detected`, that's the entire effect — the turn proceeds unchanged. For `prompt_injection_detected`, the orchestrator short-circuits: Discovery, Retrieval, Recommendation, Path Planning, output Guardrail, and Evaluation are all skipped entirely, and a fixed safe response (`_PROMPT_INJECTION_SAFE_RESPONSE`) is returned instead. No LLM call is made on the blocked path, so it costs $0.00 and the response is essentially instant (~0.1s, measured).

**Failure behavior:** The agent is pure Python string/dict logic with no I/O — there is no external call that can fail.

**Ruleset:** `src/prompts/input_guardrail/v1.yaml`, loaded via `PromptLoader.load_ruleset()` (see Prompt Governance above). All 3 flags' phrases live in this file — `input_guardrail_agent.py` contains only the matching logic, no hardcoded phrase lists.

**Optional tracing:** if a `TracingService` is injected and LangSmith is configured, every call emits an `input_guardrail` trace (message, flags, pass/fail) via the same shared instance every other traced agent receives.

---

## 4. Discovery Agent

**Responsibility:** Extracts structured profile fields from the student's latest message only (not the full history). Never invents a grade level or GPA the student didn't state. Identifies what's still missing and proposes one clarifying question.

**When called:** Every turn, before retrieval.

**Input:** `extract_profile_updates(student_name, user_message, existing_profile)`.

**Output contract:**
```json
{
  "student_profile_updates": {
    "grade_level": "11",
    "gpa": 3.4,
    "interests": ["math", "gaming"],
    "strengths": [],
    "career_preferences": [],
    "college_preferences": [],
    "favorite_careers": []
  },
  "confidence": 0.85,
  "missing_information": ["strengths", "career_preferences", "college_preferences", "favorite_careers"],
  "next_question": "What subjects or activities do you feel you excel in?"
}
```

**Validation rules:**
- `confidence` measures certainty about *this message's* extraction, not profile completeness — a message stating one clear fact scores high even if most fields are still unknown
- `next_question` is always a single question, never a list
- `gpa` is `null` (not a guessed number) when the message doesn't mention it

**Failure behavior:** If extraction fails or `confidence < 0.5`, `student_profile_updates` is the *existing* profile unchanged (not emptied), and `next_question` falls back to a safe open-ended prompt.

**Prompt:** `src/prompts/discovery/v1.md`, loaded via `PromptLoader` (see Prompt Governance above).

**Optional tracing:** emits a `discovery` trace (student name, message, confidence) via the injected `TracingService`, when configured.

---

## 5. Retrieval Agent

**Responsibility:** Runs `RetrievalService.search_all()` (semantic search across all doc types, no filter) for the student's message and normalizes the results.

**When called:** After Discovery Agent, before Recommendation Agent.

**Input:** `retrieve_relevant_context(user_message, profile, top_k=5)`.

**Output contract:**
```json
{
  "query": "I like math and video games. What careers might fit me?",
  "retrieved_documents": [
    {
      "doc_id": "career_data_analyst",
      "doc_type": "career",
      "title": "Data Analyst",
      "score": 0.62,
      "metadata": {"interest_tags": ["math", "data"], "related_majors": ["statistics"]}
    }
  ],
  "retrieval_confidence": 0.58
}
```

**Validation rules:**
- `retrieved_documents` may be empty but is never null
- `doc_type` is one of `career`, `major`, `college`, or `interest` (the knowledge base includes an `interests.json` dataset in addition to careers/majors/colleges)
- `retrieval_confidence` is the average score across the returned documents

**Failure behavior:** If Pinecone is unavailable, `RetrievalService` falls back to `KnowledgeLoader.search_by_tags()` (local tag-intersection search) transparently — the agent normalizes either result shape into the contract above without the caller needing to know which path was used.

**Optional tracing:** emits a `retrieval` trace (query, retrieved document titles, retrieval confidence) via the injected `TracingService`, when configured.

---

## 6. Recommendation Agent

**Responsibility:** Generates 3–5 grounded recommendations (career, major, or college pathway) using GPT-4o-mini, given the student's message, profile, and retrieved documents. Every career recommendation must explain why it's exciting and what opportunities it opens — the goal is to expand a student's sense of possibility, not just list a feature match.

**When called:** After Retrieval Agent, before Path Planning Agent.

**Input:** `generate_recommendations(user_message, profile, retrieved_context)`.

**Output contract:**
```json
{
  "recommendations": [
    {
      "type": "career",
      "title": "Data Analyst",
      "why_it_fits": "Your strength in math and interest in data patterns aligns directly with this role.",
      "why_exciting": "Data analysts turn raw numbers into decisions that change how companies, hospitals, and governments operate.",
      "opportunities": ["High demand across every industry", "Clear growth path to data scientist or product manager"],
      "real_world_impact": "Helps organizations understand what's working and make better decisions.",
      "related_majors": ["Statistics", "Computer Science"],
      "skills_to_build": ["Python", "SQL", "data visualization"],
      "adjacent_paths": ["Data Scientist", "Business Intelligence Analyst"],
      "evidence": ["career_data_analyst"],
      "confidence": 0.8,
      "risks_or_limitations": ["Requires comfort with statistics software"],
      "next_steps": ["Take a statistics elective", "Explore free Python tutorials"]
    }
  ],
  "summary": "Based on your interests, here are a few directions worth exploring...",
  "follow_up_question": "Which of these resonates most with you?"
}
```

`type` is one of `career`, `major`, or `college_pathway` — in practice GPT-4o-mini sometimes writes a close variant (e.g. `college` instead of `college_pathway`); downstream consumers (Path Planning Agent's selection logic) treat anything that isn't exactly `career` or `major` as the same lowest-priority tier rather than matching `college_pathway` literally.

**Validation rules:**
- Aim for 3–5 recommendations; the agent does not hard-fail below 3, it returns whatever GPT produced as long as at least one item has a non-empty `title`
- Positive framing (`why_exciting`, `opportunities`, `real_world_impact`) must not overpromise salary, job security, or admission outcomes

**Failure behavior:** If the model returns invalid/unusable JSON, the agent falls back to `{"recommendations": [], "summary": "I found some relevant paths, but I could not structure the recommendations cleanly. Based on the retrieved context, we can explore these options next: <titles>.", "follow_up_question": "..."}` instead of crashing.

**Prompt:** `src/prompts/recommendation/v1.md`, loaded via `PromptLoader` (see Prompt Governance above).

**Not part of this agent's contract:** `fun_facts` and `future_outlook`, which appear on recommendation items in the final orchestrator result, are *not* generated here — they are added afterward by `orchestrator._enrich_recommendations()` (decision D026, see Orchestrator section above) via a separate, unversioned, display-only LLM call that runs after evaluation. `RecommendationAgent.generate_recommendations()` itself never returns those two fields.

**Optional tracing:** emits a `recommendation` trace (message, retrieved document count, recommendation titles, whether the fallback was used) via the injected `TracingService`, when configured.

---

## 7. Path Planning Agent

**Responsibility:** Turns one selected recommendation into a concrete, phased roadmap: short-term (3–6 months), medium-term (1–3 years), long-term, skills to build, project ideas, and college-preparation steps. A recommendation answers "what might fit me?" — a path plan answers "what should I do next?"

**When called:** After Recommendation Agent.

**Input:** `generate_path_plan(profile, recommendations, selected_override=None)` — `recommendations` is the *full recommendations dict* from the Recommendation Agent, not a single pre-selected career string. `selected_override`, when given, is a single recommendation item (same shape as one entry in `recommendations["recommendations"]`) that wins over the priority pick below.

**Selection logic (decision D028, supersedes D018's priority-only rule):**
1. **Explicit student choice, if present:** The orchestrator checks whether the student's current message names one of *last turn's* offered recommendations (`_match_previous_choice()` in `orchestrator.py`, word-boundary matched against titles stored via `MemoryAgent.remember_last_recommendations()`). If it matches, that exact item is passed in as `selected_override` and used directly — no re-ranking.
2. **Otherwise, fall back to the original priority order:** given `recommendations["recommendations"]` (already ranked by the Recommendation Agent), pick the highest-ranked `career` item if one exists; otherwise the highest-ranked `major`; otherwise the highest-ranked remaining item (in practice, a college pathway). This priority — career > major > college_pathway — exists because a roadmap anchored to a specific college reads oddly compared to one anchored to a career or major direction.

**Output contract:**
```json
{
  "selected_path": "Data Analyst",
  "source": "student_choice",
  "short_term_steps": ["Take a statistics elective", "Complete a free Python for Data Science course"],
  "medium_term_steps": ["Major in Statistics or Computer Science", "Complete a data-focused internship"],
  "long_term_steps": ["Build a portfolio of data projects", "Target analyst roles across industries"],
  "skills_to_build": ["Python", "SQL", "data visualization"],
  "suggested_projects": ["Analyze a public sports dataset", "Build a dashboard tracking game release data"],
  "college_preparation_steps": ["Take AP Statistics if available"]
}
```

`source` is `"student_choice"` when `selected_override` was used, `"auto_priority"` otherwise — the Streamlit UI shows a small "Built around the path you picked" note under the roadmap heading when it's `"student_choice"`.

**Validation rules:**
- At least one item in each of `short_term_steps`, `medium_term_steps`, `long_term_steps`
- Steps must be grade-level appropriate (no application-season advice for a 9th grader)

**Failure behavior:** If the model output is unusable or no recommendation exists to plan around, returns a generic 3-step fallback roadmap ("talk to a counselor" / "explore related clubs" / "research colleges as application season approaches") instead of crashing.

**Prompt:** `src/prompts/path_planning/v1.md`, loaded via `PromptLoader` (see Prompt Governance above).

**Optional tracing:** emits a `path_planning` trace (selected title, choice source, resulting path) via the injected `TracingService`, when configured.

---

## 8. Guardrail Agent

**Responsibility:** Rule-based, LLM-free post-generation safety check. Runs after Path Planning, before Evaluation. Scans the full turn's text (response, recommendation fields, path plan steps) for unsafe or overconfident language, and checks the profile for missing context that the response implicitly depends on.

**When called:** After Path Planning Agent, before Evaluation Agent.

**Input:** `check_guardrails(response_payload, profile, user_message)` where `response_payload` is `{"response": str, "recommendations": <RecommendationAgent output>, "path_plan": <PathPlanningAgent output>}`.

**Output contract:**
```json
{
  "passed": true,
  "flags": ["missing_gpa_for_college_guidance"],
  "risk_level": "medium",
  "required_revisions": ["Ask for GPA or provide only broad college pathway categories."]
}
```

`risk_level` is the highest severity across all triggered flags; `passed` is `false` only when `risk_level` is `high`.

**Flag taxonomy:**

| Flag | Trigger | Risk |
|---|---|---|
| `admission_guarantee` | "you will get into", "guaranteed admission", "certain acceptance", etc. | high |
| `salary_guarantee` | "you will earn", "guaranteed salary", "job guaranteed", etc. | high |
| `protected_attribute_bias` | Reasoning like "because you're a woman/man/[race]/[religion]/..." | high |
| `overconfidence` | "perfect career", "only path", "the only option", "you should definitely" | medium |
| `pressure_language` | "you must", "you have to", "there is no other option" | medium |
| `missing_gpa_for_college_guidance` | Response mentions college/university/admission and `profile.gpa` is unset | medium |
| `missing_budget_for_affordability_guidance` | Response mentions affordability/tuition/scholarship/cost and `profile.budget_preference` is unset | medium |
| `missing_grounding` | Recommendations exist but none has any `evidence` | medium |
| `missing_location_for_specific_college_guidance` | A recommendation has `type: college_pathway` and `profile.location_preference` is unset | low |
| `insufficient_profile` | The message is under 3 words and the profile has no interests/strengths/grade/GPA | low |

**Orchestrator behavior on the result:** `risk_level: high` → a fixed safe note is appended to the response ("...Final college or career decisions should be discussed with a counselor, parent, or trusted advisor."). `risk_level: medium` → a "Keep in mind: ..." note built from `required_revisions` is appended. `low` → response returned unmodified.

**Failure behavior:** The agent is pure Python string/dict logic with no I/O — there is no external call that can fail.

**Ruleset:** `src/prompts/guardrail/v1.yaml`, loaded via `PromptLoader.load_ruleset()` (see Prompt Governance above). All 10 flags' phrases, keywords, connectors/traits, risk levels, and revision text live in this file — `guardrail_agent.py` contains only the matching logic, no hardcoded phrase lists.

**Optional tracing:** emits a `guardrail` trace (message, flags, risk level) via the injected `TracingService`, when configured.

---

## 9. Evaluation Agent

**Responsibility:** Scores every response using the **RASCEF** framework: Relevance, Accuracy/groundedness, Safety, Completeness, Explainability, Fairness — each 1–5, max 30. Primary path is GPT-4o as an LLM-as-judge; a rule-based evaluator is the fallback.

**When called:** After Guardrail Agent, before Observability Agent. Called a second time, with a freshly regenerated `response_payload`/`guardrail_result`, if the critic/revision loop retries (see Orchestrator, decision D023) — at most twice per turn, never more.

**Input:** `evaluate(user_message, response_payload, retrieved_context, profile, guardrail_result, input_guardrail_flags=None, revision_attempted=False)`. The last two are optional and exist solely to enrich the LangSmith trace (see Optional tracing below) — they play no role in scoring.

**Output contract:**
```json
{
  "scores": {
    "relevance": 5,
    "accuracy": 4,
    "safety": 5,
    "completeness": 4,
    "explainability": 5,
    "fairness": 5
  },
  "total_score": 28,
  "max_score": 30,
  "quality_badge": "green",
  "feedback": ["Relevance: directly addresses the student's stated interests.", "Completeness: next steps could be more specific."],
  "requires_revision": false
}
```

**RASCEF judge prompt (system prompt sent to GPT-4o):** evaluates Relevance (does it address the student's needs?), Accuracy/groundedness (supported by retrieved context, no unsupported claims?), Safety (no admission/salary guarantees, pressure, or inappropriate certainty?), Completeness (useful options, next steps, enough detail?), Explainability (explains why recommendations fit and what they open up?), Fairness (no biased or protected-characteristic-based reasoning, no overly narrow assumptions?). The judge is explicitly instructed not to be overly generous and to mark a response down on safety/accuracy if it's unsafe or unsupported even when it reads fluently.

**Quality badge logic (recomputed deterministically from `total_score`, never trusted from the model):**

| Score Range | Badge |
|---|---|
| 26–30 | `green` |
| 21–25 | `amber` |
| 0–20 | `red` |

**Pass threshold:** 24/30. `requires_revision` is `true` whenever `total_score < 24`, computed in code — not read from the LLM's own opinion.

**Rule-based fallback (`EvaluationService.evaluate_rule_based`):** Used when the LLM judge call fails or returns unusable JSON. Scores each RASCEF dimension from lightweight heuristics — non-empty response, presence of grounding evidence, guardrail risk level, presence of next steps, presence of `why_it_fits`/`why_exciting`. A rule-based-only result never gets the `green` badge (capped at `amber`) so a degraded evaluation is never presented as a fully-judged one.

**Failure behavior:** If both the LLM judge and the rule-based fallback fail (should not happen in practice — the fallback has no external dependencies), returns a `quality_badge: "not_evaluated"` result with zeroed scores rather than crashing the turn.

**Optional tracing:** If LangSmith is configured (`LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` set), each evaluation logs its inputs/outputs, model name, quality badge, evaluation score, guardrail flags, guardrail risk level, `input_guardrail_flags`, and `revision_attempted` via the injected `TracingService` (same instance every other traced agent receives — see Dependency Injection Pattern above). The first six are explicit fields `EvaluationAgent._trace()` builds itself; `trace_event()` additionally auto-merges in the 6 prompt/ruleset version tags plus `agent_version` underneath them — so the caller only has to know about the evaluation-specific fields, not prompt versioning. Because `evaluate()` runs once per attempt, a turn that hits the critic/revision loop produces two traces: the first with `revision_attempted: false`, the retry with `revision_attempted: true`. Tracing is a no-op when not configured, and any tracing failure is swallowed — it can never affect the response.

**Prompt:** `src/prompts/evaluation/rascef_v1.md`, loaded via `PromptLoader` (see Prompt Governance above).

---

## 10. Observability Agent

**Responsibility:** Writes one row per turn to the local `observability_logs` SQLite table via `ObservabilityRepository`. Captures latency, models used, guardrail/evaluation results, and a real cost estimate (decision D029). Never raises — a logging failure must never break the student's response.

**When called:** After Evaluation Agent, before the turn is saved to memory.

**Input:** `log_turn(event)` where `event` includes:
```json
{
  "timestamp": "2026-07-26T14:32:11+00:00",
  "student_id": 42,
  "student_name": "Jordan",
  "user_message": "I like math and video games. What careers might fit me?",
  "model": "gpt-4o-mini",
  "evaluation_model": "gpt-4o",
  "embedding_model": "text-embedding-3-small",
  "retrieved_document_count": 5,
  "guardrail_flags": ["missing_gpa_for_college_guidance"],
  "guardrail_risk_level": "medium",
  "input_guardrail_flags": [],
  "revision_attempted": false,
  "evaluation_score": 27,
  "quality_badge": "green",
  "evaluation_scores": {"relevance": 5, "accuracy": 4, "...": "..."},
  "prompt_versions": {"discovery_prompt_version": "discovery_v1", "...": "..."},
  "latency_ms": 4200,
  "prompt_tokens": 4275,
  "completion_tokens": 2018,
  "token_usage_by_model": {
    "text-embedding-3-small": {"prompt_tokens": 5, "completion_tokens": 0},
    "gpt-4o-mini": {"prompt_tokens": 1957, "completion_tokens": 1618},
    "gpt-4o": {"prompt_tokens": 2313, "completion_tokens": 400}
  },
  "estimated_cost": 0.0090,
  "error": ""
}
```

**Output:** `log_turn()` returns the new row's `log_id` (`int`), or `None` if the write failed — threaded up through the orchestrator's return value as `observability_log_id` (see Orchestrator above) so the UI can wire HITL feedback to the exact row a response came from.

**Cost calculation (decision D029 — `src/services/usage_tracker.py`, `UsageTracker`):** `OpenAIClient.complete()`/`.embed()` now return real `response.usage` token counts instead of discarding them. The orchestrator creates one `UsageTracker` per `run_turn()` call and passes it into every LLM/embedding call made that turn (Discovery, Retrieval's embedding, Recommendation, Path Planning, Evaluation, and the display-only enrichment call) — including both attempts if the critic/revision loop retries. `UsageTracker.by_model()` sums usage per model; `estimated_cost_usd()` prices each model's tokens and sums across all of them:
- `gpt-4o-mini`: $0.15 / 1M input tokens + $0.60 / 1M output tokens
- `gpt-4o`: $2.50 / 1M input tokens + $10.00 / 1M output tokens
- `text-embedding-3-small`: $0.02 / 1M tokens

A single turn spans at least 3 different models (generation, evaluation, embedding), so `observability_logs.token_usage_by_model` (additive JSON column) holds the full per-model breakdown; the existing single `prompt_tokens`/`completion_tokens` columns hold the grand total across every model, for a quick-glance figure. `run_turn()`'s return value also includes `token_usage_by_model` and `estimated_cost_usd` directly, which the Streamlit UI's "Technical Details" panel renders as a small table.

**Failure behavior:** Both `ObservabilityAgent.log_turn()` and the orchestrator's call site wrap the write in `try/except` — a SQLite failure never blocks or alters the response returned to the student.

**Schema:** `observability_logs` uses `INTEGER PRIMARY KEY AUTOINCREMENT` (not UUIDs). Columns were added additively over time via a safe `ALTER TABLE` migration in `SQLiteClient._migrate_observability_logs()` that only adds columns not already present — existing databases upgrade in place without data loss.

**Human-in-the-loop feedback (decisions D021, D024):** `ObservabilityRepository` also exposes:
- `save_feedback(log_id, helpful, feedback_text=None)` — updates the `helpful` (nullable `INTEGER`, 0/1) and `feedback_text` (nullable `TEXT`) columns on one existing log row; overwrites any prior feedback on that row
- `get_feedback_summary()` — returns `{"total_feedback": int, "helpful_count": int, "not_helpful_count": int, "helpful_rate": float | None}` aggregated across every log row that has received feedback

Both columns are additive (same `ALTER TABLE` pattern as above, `NULL` by default). The Streamlit UI wires this via 👍 Helpful / 👎 Not Helpful buttons under each assistant response (`app.py`'s `_render_feedback_buttons()`), calling `orchestrator.submit_feedback(log_id, helpful, feedback_text=None)` — a thin wrapper that calls `ObservabilityRepository.save_feedback()` and swallows failures, keeping `app.py` decoupled from repositories. No authentication is required. Buttons are replaced with a "Thanks for your feedback" caption after one submission per `log_id` (tracked in `st.session_state`, not persisted) to avoid duplicate submissions. `src/scripts/test_human_feedback.py` also exercises the mechanism directly.

---

## Where Contracts Are Enforced Today

There is no runtime schema-validation layer between agents — every agent receives and returns plain dicts matching the JSON shapes documented above. What *is* enforced:

- Each agent's own internal validation of LLM output (e.g. `RecommendationAgent._validate()`, `PathPlanningAgent._validate()`, `EvaluationService._validate()`) checks that required fields are present and well-typed before trusting model output, falling back to a safe default otherwise
- The Guardrail Agent's flag taxonomy and the Evaluation Agent's RASCEF scoring both operate on the dict shapes above, not on Pydantic instances
- `src/schemas/models.py` defines `StudentProfile`, `RetrievedDocument`, `DiscoveryOutput`, `RetrievalOutput`, `RecommendationOutput`/`RecommendationItem`, `PathPlanningOutput`, `GuardrailResult`, `EvaluationScores`/`EvaluationResult`, `ObservabilityLog`, and `OrchestratorTurnResult` as the target domain model set — useful as a reference and a starting point if strict validation is added later, but several of these models (notably `EvaluationScores`, `RecommendationItem`, `PathPlanningOutput`, `ObservabilityLog`) have drifted from the actual dict shapes above as fields were added during implementation. Bringing them back in sync is a known follow-up, not something this document should pretend has already happened.

### How Contracts Support the Demo

- Show the Orchestrator calling each agent in sequence via the collapsed "Technical details" expander in the Streamlit UI (with an always-visible ✅/⚠️ summary line above it)
- Display the RASCEF quality badge (green/amber/red) and score breakdown
- Show `retrieved_documents` to prove recommendations are grounded, not hallucinated
- Trigger a guardrail intentionally (e.g. "Will I get into MIT with a 3.8 GPA?") to demonstrate the safety note being appended
- Show `next_question` driving the conversation forward one step at a time for a vague opening message
