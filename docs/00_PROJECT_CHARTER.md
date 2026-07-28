# PathFinder AI — Project Charter

## 1. Project Name

PathFinder AI

---

## 2. Product Goal

PathFinder AI is a chat-first career discovery and college pathway guidance platform for high school students, parents, and school counselors.

---

## 3. Primary Problem

Many high school students are unsure what careers exist beyond the familiar defaults, what college majors connect to those careers, which colleges support those paths, and what concrete steps they should take given their current academic profile.

---

## 4. Target Users

- **Primary:** High school students — those applying to colleges and those unsure about careers or majors
- **Secondary:** Parents and school counselors

---

## 5. Core Product Capabilities

- Conversational career discovery
- Career option explanation with positive opportunity framing
- Major guidance connected to career paths
- College pathway guidance tiered by GPA (reach / target / likely)
- GPA-aware, honest guidance
- Personalized next-step roadmap
- Memory across sessions — returning students continue, not restart

---

## 6. AI System Capabilities

- Multi-agent orchestration (10 agents coordinated by an Orchestrator)
- Pinecone RAG with OpenAI embeddings (careers, majors, colleges, interests)
- SQLite persistent memory (profile merges across turns and sessions)
- Typed dict contracts between agents (documented in `docs/09_Agent_Contracts.md`; `src/schemas/models.py` holds the reference Pydantic domain models, not runtime-enforced today)
- Rule-based, pre-generation input guardrails (profanity/frustration/prompt-injection flags — detection only) and post-generation guardrails (10 flags) — see `docs/09_Agent_Contracts.md`
- RASCEF evaluation (Relevance, Accuracy, Safety, Completeness, Explainability, Fairness) via GPT-4o LLM-as-judge, with a rule-based fallback and a single automatic critic/revision retry when the score is below threshold
- Human-in-the-loop 👍/👎 feedback on every response, no authentication required
- Per-turn observability logging to SQLite, with optional LangSmith tracing
- Real per-turn cost tracking, broken down per model (`UsageTracker`, decision D029 — see `docs/99_REFERENCE.md`)

---

## 7. Locked Technical Decisions

| Decision | Choice |
|---|---|
| Generation model | GPT-4o-mini |
| Evaluation model | GPT-4o (optional, sampled) |
| Embedding model | OpenAI `text-embedding-3-small` |
| Vector database | Pinecone |
| Memory database | SQLite |
| UI framework | Streamlit |
| Language | Python 3.13 |
| Windows venv | `.venv_win` |
| Linux / WSL venv | `.venv_linux` (reserved) |

These decisions are final for the MVP. Changes require an entry in `docs/12_DECISION_LOG.md`.

---

## 8. In Scope

- Careers, majors, and colleges knowledge base (local JSON + Pinecone)
- RAG retrieval via Pinecone with local JSON fallback
- Multi-agent orchestration flow
- SQLite memory: student profile and conversation summary
- GPA-aware guidance with reach / target / likely framing
- Post-generation guardrail checks
- RASCEF evaluation scoring (6 dimensions, 1–5 each)
- Per-call observability logging (SQLite; optional LangSmith tracing)
- Demo scenarios (`docs/11_Test_Scenarios_and_Golden_Dataset.md`)

---

## 9. Out of Scope

- Scholarships and FAFSA guidance
- SAT / ACT score prediction or analysis
- Parent-facing portal
- Counselor-facing dashboard
- Real-time college admission APIs
- Application tracking or deadline reminders
- Personal statement or essay review
- Production authentication or user account management

---

## 10. Capstone Story

Do not frame this as a chatbot.

Frame it as:

> PathFinder AI is a career discovery and college pathway guidance platform that demonstrates practical agentic AI patterns: RAG with Pinecone and OpenAI embeddings, SQLite persistent memory, multi-agent orchestration, post-generation guardrails, structured evaluation with LLM-as-judge, per-call observability logging, and cost-aware model selection. The high school student guidance domain is the use case — the AI system design patterns are the demonstration.

---

## Engineering Principles

- Follow SOLID principles where practical: single responsibility per agent, open for extension, closed to modification of internals
- Keep agents focused on single responsibilities — no agent does retrieval AND generation AND logging
- Separate UI, orchestration, agents, services, repositories, infrastructure, and schemas into distinct layers
- Avoid direct OpenAI, Pinecone, and SQLite calls inside agents — use a service or repository abstraction instead
- Keep code testable: agents receive their dependencies via constructor injection, not by importing infrastructure directly

These principles are locked as decision D012 in `docs/12_DECISION_LOG.md`.

---

## 11. Token Optimization Rule

For future Claude Code sessions:

1. Read `docs/99_REFERENCE.md` first — it contains the compact project summary and is optimized for low token usage.
2. Load only the specific design document needed for the current task.
3. Do not read every documentation file unless explicitly doing an architecture review.
4. Use `docs/12_DECISION_LOG.md` to check whether a decision has already been made before proposing a change.
