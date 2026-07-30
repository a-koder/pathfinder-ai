# PathFinder AI — Documentation Index

This is the map for every doc in `docs/`. Start here, then dive into whatever topic you
need from the table below.

---

## By Topic

| Topic | Primary Doc(s) | What's There |
|---|---|---|
| **Problem Statement** | [`01_Vision.md`](01_Vision.md), [`02_BRD.md`](02_BRD.md) | Why this exists — the 400:1 counselor ratio, generic career quizzes, GPA guidance arriving too late |
| **Solution Overview** | [`03_PRD.md`](03_PRD.md), [`07_Capstone_Mapping_and_Implementation_Plan.md`](07_Capstone_Mapping_and_Implementation_Plan.md) §1 | What PathFinder AI actually does, target users, MVP scope and boundaries |
| **Architecture** | [`04_Architecture.md`](04_Architecture.md), [`08_Diagrams.md`](08_Diagrams.md) | Clean Architecture's 6 layers, SOLID mapping, dependency flow, full per-turn data flow diagram |
| **AI Concepts Used** | [`07_Capstone_Mapping_and_Implementation_Plan.md`](07_Capstone_Mapping_and_Implementation_Plan.md) §13, [`14_Presentation_Deck.md`](14_Presentation_Deck.md) ("AI Concepts, Named" slide) | The named pattern list: multi-agent orchestration, RAG, memory, guardrails, evaluation, observability, cost optimization, prompt engineering, structured outputs |
| **Multi-Agent Design** | [`05_Agent_Design.md`](05_Agent_Design.md), [`09_Agent_Contracts.md`](09_Agent_Contracts.md) | Persona/conversation strategy, plus the full input/output contract, validation rules, and failure behavior for all 10 agents |
| **RAG Pipeline** | [`13_RAG_Implementation.md`](13_RAG_Implementation.md) | Pinecone indexing strategy, metadata filtering, embedding model choice, local-fallback design |
| **Memory** | [`04_Architecture.md`](04_Architecture.md) "Memory" (via root `README.md`), [`07_Capstone_Mapping_and_Implementation_Plan.md`](07_Capstone_Mapping_and_Implementation_Plan.md) §7 | SQLite schema (`students`, `profiles`, `messages`, `conversation_summaries`, `observability_logs`), incremental profile-merge rules |
| **Guardrails** | [`09_Agent_Contracts.md`](09_Agent_Contracts.md) §3 (Input) and §8 (Output) | Full flag taxonomy for both guardrails, risk levels, what's detection-only vs. what changes the response |
| **Evaluation** | [`09_Agent_Contracts.md`](09_Agent_Contracts.md) §9, [`11_Test_Scenarios_and_Golden_Dataset.md`](11_Test_Scenarios_and_Golden_Dataset.md) | RASCEF's 6 dimensions, pass threshold, LLM-as-judge + rule-based fallback, golden test scenarios |
| **Observability** | [`09_Agent_Contracts.md`](09_Agent_Contracts.md) §10 | Per-turn logging schema, real per-model cost tracking, HITL feedback capture, optional LangSmith tracing |
| **Future Roadmap** | [`19_Future_Vision.md`](19_Future_Vision.md) | MCP integrations, provider-agnostic LLM support, deeper LangSmith usage, agent-to-agent interop (only if a real need shows up), and more — each tied to a concrete extension point in the current code |

---

## Full Document List (numeric order)

| # | Doc | Purpose |
|---|---|---|
| — | [`README.md`](../README.md) (root) | Setup, run instructions, feature summary — the practical "how do I run this" doc |
| 00 | [`00_PROJECT_CHARTER.md`](00_PROJECT_CHARTER.md) | Project mandate, sponsor, success criteria |
| 01 | [`01_Vision.md`](01_Vision.md) | Problem statement and product vision |
| 02 | [`02_BRD.md`](02_BRD.md) | Business requirements |
| 03 | [`03_PRD.md`](03_PRD.md) | Product requirements, personas, MVP scope |
| 04 | [`04_Architecture.md`](04_Architecture.md) | Clean Architecture layers, SOLID, dependency flow, full turn-by-turn data flow, agent inventory |
| 05 | [`05_Agent_Design.md`](05_Agent_Design.md) | Conversational persona and strategy design |
| 06 | [`06_AI_System_Design.md`](06_AI_System_Design.md) | System-level AI design and pattern rationale |
| 07 | [`07_Capstone_Mapping_and_Implementation_Plan.md`](07_Capstone_Mapping_and_Implementation_Plan.md) | Maps the product to capstone requirements; knowledge base design; phase-by-phase build plan |
| 08 | [`08_Diagrams.md`](08_Diagrams.md) | Architecture and sequence diagrams |
| 09 | [`09_Agent_Contracts.md`](09_Agent_Contracts.md) | Authoritative per-agent input/output contracts, validation rules, failure behavior |
| 10 | [`10_Error_Handling_and_Fallbacks.md`](10_Error_Handling_and_Fallbacks.md) | Failure-scenario table — detection, fallback, user-facing message per scenario |
| 11 | [`11_Test_Scenarios_and_Golden_Dataset.md`](11_Test_Scenarios_and_Golden_Dataset.md) | Mock student profiles and manual-review scenarios for prompt tuning |
| 12 | [`12_DECISION_LOG.md`](12_DECISION_LOG.md) | Every architecture/product decision, alternatives considered, and why |
| 13 | [`13_RAG_Implementation.md`](13_RAG_Implementation.md) | Full RAG design and ingestion detail |
| 14 | [`14_Presentation_Deck.md`](14_Presentation_Deck.md) | Marp-flavored capstone slide deck, speaker notes, demo script |
| 19 | [`19_Future_Vision.md`](19_Future_Vision.md) | Realistic next steps beyond the MVP, each tied to an existing extension point |
| 25 | [`25_Capstone_Review.md`](25_Capstone_Review.md) | Honest self-assessment: strengths, weaknesses, gaps, rubric estimate |

**Numbering gap (15–18, 20–24, 99):** reserved, unused. Not a sign of missing docs — just room for future additions without renumbering anything.

---

## Known Documentation Gaps

- `docs/10_Error_Handling_and_Fallbacks.md` describes some fallback behavior (e.g. OpenAI call retries with backoff, a startup config-check banner) that isn't actually implemented in `src/` today — it reads as the original design intent rather than a verified account of current behavior. See `docs/25_Capstone_Review.md` for the full list of doc/code drift points.
- `src/schemas/models.py`'s Pydantic models have drifted from the actual dict shapes agents pass around (noted directly in `docs/09_Agent_Contracts.md` and `docs/04_Architecture.md` — not hidden, just unresolved).
