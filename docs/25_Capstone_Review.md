# PathFinder AI — Capstone Review

An honest self-assessment, not a marketing pass. Every claim below is grounded in the actual
code, `docs/12_DECISION_LOG.md`, or a live test run from this review session — nothing here
is aspirational. Where something is genuinely strong, it's stated plainly; where something
is weak or missing, likewise.

---

## Strengths

**The multi-agent pipeline is real, not decorative.** 10 agents, each a small class with one
public method, wired by explicit constructor injection (no DI framework, no agent framework —
`docs/12_DECISION_LOG.md` D023/D025). The Orchestrator's sequence — input guardrail → memory
load → discovery ‖ retrieval (concurrent) → recommendation → path planning → guardrail →
evaluation → bounded one-retry revision loop → observability → memory save — is verifiable in
code (`src/agents/orchestrator.py`), not just described in a slide. A live run of
`test_full_workflow.py` during this session produced 7/7 passing scenarios with real RASCEF
scores (27–30/30, all green) and a correctly-firing/correctly-clearing GPA guardrail across
turns — this isn't a claim, it happened during this review.

**RAG is genuinely grounded, with a real fallback.** 170 curated documents across 4 datasets,
embedded with `text-embedding-3-small`, retrieved via Pinecone with `doc_type` metadata
filtering, and a working local tag-match fallback (`KnowledgeLoader.search_by_tags()`) if
Pinecone is unreachable — verified in `src/services/retrieval_service.py`, not just asserted.

**Output guardrails have real teeth.** Unlike many capstone "guardrail" implementations that
only log a flag, PathFinder AI's output guardrail actually changes what the student sees: a
`high`-risk flag permanently appends a safety note to the stored response, `medium`-risk flags
render a live "keep in mind" UI note, and the guardrail result feeds directly into RASCEF
scoring. This was confirmed by direct code read, not assumed from documentation.

**Evaluation is a real LLM-as-judge with a disciplined fallback.** RASCEF (6 dimensions, GPT-4o
judge, 24/30 pass threshold) with a rule-based fallback that is deliberately capped at `amber`
even when its raw heuristic score would be `green` — a small but telling design choice that
shows awareness of not overstating confidence in a degraded evaluation path.

**Cost tracking is real, not a placeholder.** Decision D029 replaced an earlier `$0.00`
scaffolding stage (D019) with actual `response.usage` token counts threaded through every
LLM/embedding call via `UsageTracker`, broken down per model. This is a rare thing to see
actually finished in a capstone rather than left as a TODO.

**The decision log is a genuine engineering artifact.** 29 decisions (D001–D029), each with
alternatives considered and why they lost — e.g., D018's career > major > college_pathway
roadmap-anchoring rule, or D023's explicit rejection of blocking-on-input-guardrail-flags
("avoids false-positive lockouts"). This is the single strongest piece of evidence that
engineering judgment, not just implementation, happened here.

**Documentation is unusually complete and self-aware.** `docs/09_Agent_Contracts.md` documents
every agent's contract, validation rules, and failure behavior in enough detail to actually be
authoritative — and it says so explicitly where something *hasn't* kept up (e.g., "several
[Pydantic models] have drifted from the actual dict shapes... bringing them back in sync is a
known follow-up, not something this document should pretend has already happened"). That
sentence is a good sign, not a bad one — it means the docs can be trusted when they say
something works.

---

## Weaknesses

**No automated test suite.** All 13 verification scripts in `src/scripts/` are standalone,
run manually, against live OpenAI/Pinecone APIs — real cost and real latency per run, no CI
gate, no offline/mocked fast path, and results depend on API availability at the moment you
run them. This is the single most-repeated "known limitation" across the docs, which is
honest, but it means there is no regression safety net between sessions today.

**Input guardrails are detection-only with no enforcement path.** Confirmed directly in
`input_guardrail_agent.py` and `orchestrator.py`: flags are computed, logged, and traced — and
never block, rewrite, or otherwise change a turn. This was a deliberate D023 decision, and
defensible for a prototype, but it means a student can send a prompt-injection attempt today
and the system behaves identically to if they hadn't. Worth stating precisely rather than
letting "we have guardrails" imply more than it does.

**Two guardrail checks are effectively dead code today.** `missing_budget_for_affordability_guidance`
and `missing_location_for_specific_college_guidance` both key off profile fields
(`budget_preference`, `location_preference`) that `DiscoveryAgent` never actually extracts from
conversation (confirmed in `docs/09_Agent_Contracts.md`'s Memory Agent note and
`docs/04_Architecture.md`'s Known Limitations). The flags can only fire in the direction of
"missing" — they can never be satisfied, because nothing ever populates those fields. This
isn't a bug so much as an unfinished loop: the check exists, the data source doesn't.

**No `out_of_scope` guardrail.** Scholarship, FAFSA, SAT/ACT, and essay-review questions are
explicitly out of MVP scope per `docs/01_Vision.md`, but nothing actually intercepts them —
they reach the Recommendation Agent, which will attempt a weak, ungrounded answer rather than
redirecting. Documented as a known gap in `docs/04_Architecture.md`, not hidden, but worth
surfacing directly since "guardrails cover scope" is an easy claim to overstate.

**`docs/10_Error_Handling_and_Fallbacks.md` is partially aspirational, not verified.** Direct
code check during this review: `openai_client.py` has no retry logic at all (the doc claims
"retry up to 2 times with 2s backoff"), and `has_openai_key()`/`has_pinecone_key()` are only
ever called from `src/scripts/`, never from `app.py` — the documented "config warning at
startup" doesn't exist in the running app. This is a real doc/code gap, not previously flagged
anywhere else in the docs, and worth fixing or explicitly caveating before anyone treats that
document as ground truth.

**No production-readiness path.** Name-based student "authentication" (case-insensitive
lookup, no password, no session security), single-machine SQLite, no deployment target — all
explicitly acknowledged as MVP-only, which is appropriate for a capstone, but worth being
ready to say plainly rather than defensively if asked.

**`feedback_text` is backend-only.** The free-text HITL comment column exists and is exercised
by `test_human_feedback.py`, but has no UI entry point — only the 👍/👎 buttons are wired. A
small, honest gap between what the schema supports and what a student can actually do.

---

## Remaining Gaps (lower severity, worth knowing)

- `src/schemas/models.py` domain models have drifted from the dict shapes agents actually pass — no runtime validation layer enforces contracts at agent boundaries today.
- No agent-to-agent (A2A) protocol, no MCP integrations, no provider-agnostic LLM support yet — all correctly scoped as future work in `docs/19_Future_Vision.md`, not gaps in the current MVP's own goals.
- Observability has no visualization layer — the data (`observability_logs`) is rich, but only queryable directly today.
- Prompt/ruleset versioning infrastructure exists and works (D020), but only one version (`v1`) of each prompt has ever shipped — the rollback story is real but untested against an actual second version.

---

## Rubric Score Estimate

A reasoned estimate against the categories an EM-track AI capstone rubric would plausibly use —
**my own estimate, not a real grader's**, offered to calibrate expectations, not as a guarantee:

| Category | Assessment | Rationale |
|---|---|---|
| Multi-Agent Design | **Strong** | Real orchestrator, 10 bounded agents, documented contracts, concurrency where it's actually safe (D025) |
| RAG | **Strong** | Real vector search, metadata filtering, working local fallback, grounding evidence surfaced per recommendation |
| Guardrails | **Solid, with an honest asterisk** | Output guardrails have real enforcement; input guardrails are detection-only by deliberate design; two flags are currently unreachable due to missing profile extraction |
| Evaluation | **Strong** | Real LLM-as-judge, deterministic badge recomputation, a fallback that doesn't overstate its own confidence |
| Structured Outputs | **Solid** | Well-defined JSON contracts everywhere; the gap is the domain-model/dict-shape drift and no runtime validation layer |
| Observability | **Strong for logging, weak for visualization** | Real per-model cost, full per-turn metadata, optional LangSmith — but no dashboard, queryable only via raw SQL/scripts today |
| Operationalization | **Weak** | No CI, no automated tests, no deployment story — all explicitly acknowledged, which helps, but doesn't change the underlying gap |
| Improvement Loop | **Solid** | Prompt versioning + decision log + HITL feedback capture all exist and connect to each other; the loop is real but has only been exercised manually, once |

**Overall:** this reads as a strong engineering-discipline capstone — the architecture,
contracts, and decision trail are more rigorous than most prototypes at this stage — held back
mainly by the lack of automated testing/CI (Operationalization) and a couple of guardrail
checks that can't actually fire yet. Both are fixable without new agents or a rewrite.

---

## Recommended Talking Points

1. **Lead with the decision log, not the demo.** D023 (why input guardrails don't block),
   D018/D028 (roadmap-anchoring logic evolving twice as real gaps were found), and D029 (fixing
   the `$0.00` cost placeholder) show iterative engineering judgment — that's a stronger signal
   than any single feature.
2. **Say the input-guardrail limitation out loud, framed as a choice.** "Detection-only was a
   deliberate tradeoff to avoid false-positive lockouts, documented in D023" lands very
   differently than being asked "wait, does this actually block anything?" and hedging.
3. **Don't claim budget/location guardrails work end-to-end.** They're real, tested code paths
   for the "missing" direction, but say plainly that `DiscoveryAgent` doesn't populate those
   fields yet — it's a known, scoped gap, not a hidden one.
4. **Own the no-pytest-suite gap directly and pair it with what does exist**: 13 scripts
   exercising real agents against live APIs, run today with a 7/7 pass rate as part of this
   review. "No CI yet" is a materially different statement than "untested."
5. **Use the cost-tracking story (D019 → D029) as a concrete example of shipping scaffolding
   honestly, then finishing it** — it's a good answer to "how do you handle technical debt?"
6. **If asked about `docs/10_Error_Handling_and_Fallbacks.md`'s retry/config-check claims**,
   don't defend them — they don't match the current code, and saying so directly is stronger
   than being caught by a follow-up question that reads the file.
