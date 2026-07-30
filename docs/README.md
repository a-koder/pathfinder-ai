# PathFinder AI — Documentation Index

This is the map for every doc in `docs/`. Start here, then dive into whatever topic you
need from the table below.

---

## By Topic

| Topic | Primary Doc(s) | What's There |
|---|---|---|
| **Problem Statement** | [`01_Product_Overview.md`](01_Product_Overview.md) | Why this exists — the 400:1 counselor ratio, generic career quizzes, GPA guidance arriving too late, written as a PRFAQ |
| **Solution Overview** | [`01_Product_Overview.md`](01_Product_Overview.md), [`07_Capstone_Requirements_Mapping.md`](07_Capstone_Requirements_Mapping.md) | What PathFinder AI actually does, target users, MVP scope and boundaries |
| **Architecture** | [`04_Architecture.md`](04_Architecture.md), [`08_Diagrams.md`](08_Diagrams.md) | Clean Architecture's 6 layers, SOLID mapping, dependency flow, full per-turn data flow diagram, agent inventory |
| **AI Concepts Used** | [`07_Capstone_Requirements_Mapping.md`](07_Capstone_Requirements_Mapping.md) ("Final Capstone Story"), [`14_Presentation_Deck.md`](14_Presentation_Deck.md) ("AI Concepts, Named" slide) | The named pattern list: multi-agent orchestration, RAG, memory, guardrails, evaluation, observability, prompt governance, structured outputs |
| **Multi-Agent Design** | [`09_Agent_Contracts.md`](09_Agent_Contracts.md) | Persona, plus the full input/output contract, validation rules, and failure behavior for all 11 agents |
| **RAG Pipeline** | [`13_RAG_Implementation.md`](13_RAG_Implementation.md), [`08_Diagrams.md`](08_Diagrams.md) §2 | Pinecone indexing strategy, metadata filtering, embedding model choice, local-fallback design |
| **Memory** | Root [`README.md`](../README.md) "Memory" section, [`08_Diagrams.md`](08_Diagrams.md) §3, [`09_Agent_Contracts.md`](09_Agent_Contracts.md) §2 | SQLite schema (`students`, `profiles`, `messages`, `conversation_summaries`, `observability_logs`), incremental profile-merge rules |
| **Guardrails** | [`09_Agent_Contracts.md`](09_Agent_Contracts.md) §3 (Input) and §9 (Output) | Full flag taxonomy for both guardrails, risk levels, what's detection-only vs. what changes the response |
| **Intent Routing** | Root [`README.md`](../README.md) "Intent Routing" section, [`09_Agent_Contracts.md`](09_Agent_Contracts.md) §4 | The four intents (explore/roadmap/related_topic/general_chat), anchor resolution, why it replaced `_match_previous_choice()` (decision D034) |
| **Evaluation** | [`09_Agent_Contracts.md`](09_Agent_Contracts.md) §10, [`11_Test_Scenarios_and_Golden_Dataset.md`](11_Test_Scenarios_and_Golden_Dataset.md) | RASCEF's 6 dimensions, pass threshold, LLM-as-judge + rule-based fallback, golden test scenarios |
| **Observability** | [`09_Agent_Contracts.md`](09_Agent_Contracts.md) §11 | Per-turn logging schema, real per-model cost tracking, HITL feedback capture, optional LangSmith tracing |
| **Future Roadmap** | [`19_Future_Vision.md`](19_Future_Vision.md) | MCP integrations, provider-agnostic LLM support, deeper LangSmith usage, agent-to-agent interop (only if a real need shows up), and more — each tied to a concrete extension point in the current code |

---

## Full Document List (numeric order)

| # | Doc | Purpose |
|---|---|---|
| — | [`README.md`](../README.md) (root) | Setup, run instructions, feature summary — the practical "how do I run this" doc |
| 01 | [`01_Product_Overview.md`](01_Product_Overview.md) | Problem, users, and scope, written as a Press Release / FAQ |
| 04 | [`04_Architecture.md`](04_Architecture.md) | Clean Architecture layers, SOLID, dependency flow, full turn-by-turn data flow, agent inventory |
| 07 | [`07_Capstone_Requirements_Mapping.md`](07_Capstone_Requirements_Mapping.md) | Maps the product to capstone requirements; knowledge base schema; the capstone framing |
| 08 | [`08_Diagrams.md`](08_Diagrams.md) | Architecture and sequence diagrams |
| 09 | [`09_Agent_Contracts.md`](09_Agent_Contracts.md) | Authoritative per-agent input/output contracts, validation rules, failure behavior |
| 11 | [`11_Test_Scenarios_and_Golden_Dataset.md`](11_Test_Scenarios_and_Golden_Dataset.md) | Mock student profiles and manual-review scenarios for prompt tuning |
| 12 | [`12_DECISION_LOG.md`](12_DECISION_LOG.md) | Every architecture/product decision, alternatives considered, and why |
| 13 | [`13_RAG_Implementation.md`](13_RAG_Implementation.md) | Full RAG design and ingestion detail |
| 14 | [`14_Presentation_Deck.md`](14_Presentation_Deck.md) | Marp-flavored capstone slide deck, speaker notes, demo script |
| 19 | [`19_Future_Vision.md`](19_Future_Vision.md) | Realistic next steps beyond the MVP, each tied to an existing extension point |

**Numbering gaps:** reserved, unused. Not a sign of missing docs — just room for future additions without renumbering anything.
