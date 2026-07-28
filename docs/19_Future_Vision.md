# PathFinder AI — Future Vision

## Purpose

This document lists realistic next steps beyond the current MVP — extensions of what already exists, not speculative features. Each item below builds on a concrete piece of the current architecture (referenced inline) rather than proposing something disconnected from it. Nothing here is scoped, scheduled, or committed; treat it as a roadmap of *plausible* directions, to be turned into real decisions (and added to `docs/12_DECISION_LOG.md`) if and when they're pursued.

For what's explicitly out of scope for the MVP today, see `docs/01_Vision.md`'s "Out of Scope (MVP)" section — several items below (scholarships, real-time college data) are the natural next step past that boundary.

---

## MCP Integrations

**Today:** External lookups (Pinecone search, OpenAI calls) are each wrapped behind a single service class (`RetrievalService`, `LLMService`) that agents depend on through an injected interface — the Clean Architecture pattern already used throughout `src/services/` and `src/infrastructure/`.

**Next step:** Expose scholarship, college-data, and course-provider lookups (below) as MCP tools rather than one-off service integrations. MCP's client-server tool-calling model fits this codebase's existing dependency-injection pattern almost directly — an `MCPToolService` would sit in the same service layer as `RetrievalService` today, and agents would call it the same way they call any other service, without knowing or caring which MCP server is behind a given tool. This also means new external data sources could be added by connecting a new MCP server, not by writing a new bespoke integration each time.

## Scholarship APIs

**Today:** Explicitly out of scope for the MVP (`docs/01_Vision.md`) — PathFinder AI has no scholarship data or matching logic at all.

**Next step:** A scholarship-matching capability, likely as its own MCP-exposed tool or dedicated service, that the Recommendation Agent or Path Planning Agent could query once a student's profile (GPA, interests, budget preference) is established. This is a natural extension of the existing `budget_preference` guardrail check (`missing_budget_for_affordability_guidance`), which today only detects the *absence* of budget context — a scholarship integration would let the system act on it.

## College APIs

**Today:** College data is a static, curated dataset (`data/colleges.json`, 27 entries) — embedded once and served through the same RAG pipeline as careers and majors (`docs/13_RAG_Implementation.md`). Real-time admissions data, deadlines, or acceptance-rate APIs were explicitly excluded from MVP scope.

**Next step:** Layer a live college-data API (admissions statistics, deadlines, program updates) behind the same `RetrievalService`/`doc_type: college` pattern already in place, so real-time facts augment — rather than replace — the curated, editorially-controlled college dataset. Keeping the curated dataset as the grounding source and using a live API only for time-sensitive facts (deadlines, current tuition) avoids re-introducing the hallucination risk RAG was built to prevent.

## Course Providers

**Today:** `path_plan.college_preparation_steps` and `suggested_projects` are LLM-generated text suggestions (`src/agents/path_planning_agent.py`) — general advice like "take AP Statistics," not links to an actual course a student can enroll in.

**Next step:** Connect course-provider catalogs (AP course databases, Coursera/edX-style platforms, or a school's own course catalog) so `PathPlanningAgent`'s suggestions can resolve to a real, enrollable course rather than a generic recommendation. This is a content-grounding upgrade to an existing agent output field, not a new agent.

## Career Market Data

**Today:** Career descriptions, growth framing, and "why exciting" content in `data/careers.json` are static and editorially written, refreshed only when the dataset is manually updated.

**Next step:** Ground the Recommendation Agent's `future_outlook` field (currently generated fresh each turn by a display-only enrichment call, see decision D026) in real labor-market data — sources like O*NET or BLS-style employment/outlook datasets — so "growing field" framing reflects actual current data instead of the model's general knowledge. This would also strengthen the Guardrail Agent's ability to catch overconfident career claims, since real market data gives it something concrete to check against.

## Advanced Analytics

**Today:** `observability_logs` (SQLite) already captures per-turn latency, guardrail flags, RASCEF scores, prompt versions, and real per-model token cost (decision D029) — but the only consumer today is `ObservabilityRepository.get_feedback_summary()` (a single aggregate) and the manual test scripts.

**Next step:** Build real aggregate analytics on top of data that's already being captured: quality-score trends over time, guardrail-flag frequency by category, cost-per-session and cost-per-student, and revision-loop trigger rate. This is a reporting/query layer on existing data, not a new instrumentation effort.

## Real-Time Observability Dashboards

**Today:** Observability data is queryable only via direct SQLite access or the manual `src/scripts/test_observability.py` script; there is no visualization layer, and LangSmith tracing (when enabled) is the only place data is viewed outside the raw table.

**Next step:** A live dashboard (a new Streamlit page reading from `ObservabilityRepository`, or a proper BI tool pointed at `data/memory.db`) surfacing the same fields already logged: quality-badge distribution, guardrail-flag rates, latency percentiles, and running cost. Since every field this would need is already captured per turn, this is purely a visualization project, not a data-collection one.

## More Sophisticated HITL Workflows

**Today:** Human-in-the-loop feedback is a single 👍/👎 per response, wired to `ObservabilityRepository.save_feedback()` and shown once per `log_id` per browser session (decision D024). `feedback_text` (free-text comment) exists as a column but has no UI entry point yet — it's reachable only by calling the repository directly.

**Next step:** Layered feedback beyond a single binary signal — e.g. per-recommendation feedback (which of the 3 cards actually landed), a free-text comment box wired to the already-existing `feedback_text` column, or a counselor/parent review queue for flagged (high-risk guardrail) responses. Each of these extends a mechanism that already exists end-to-end in the database; none require new schema design from scratch.
