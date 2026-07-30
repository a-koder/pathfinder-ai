# PathFinder AI — Capstone Requirements Mapping

## Career Positivity and Student Motivation

PathFinder AI shouldn't just match students to careers — it should help them feel curious and motivated about paths they hadn't considered. A lot of students show up uncertain or a little discouraged, so the system is built to expand what feels possible while staying honest about effort, skills, and limitations.

Every career recommendation has to explain:

- **Why the career may be exciting** — what draws people to this work, not just the skills it requires
- **What opportunities it opens** — industries, growth paths, adjacent roles, long-term directions
- **What real-world impact it has** — how the work affects companies, communities, or people's lives
- **What related paths exist** — adjacent careers worth exploring if the primary option doesn't fit
- **What first step the student can take** — something concrete and grade-level-appropriate they can do now

The constraint that keeps this honest: positive framing has to be grounded in the knowledge base. It can't overpromise salary, job security, or admission outcomes. Inspiration is earned through honest excitement, not inflated claims — this is enforced directly by the Guardrail Agent and reflected in the Recommendation Agent's prompt (see `docs/09_Agent_Contracts.md`).

---

## Capstone Requirement Mapping

| Requirement | How PathFinder AI Addresses It | Implementation Artifact | Demo Evidence |
|---|---|---|---|
| Real-world problem | High school students lack structured, personalized career and college guidance | `docs/01_Product_Overview.md` | Student conversation showing non-obvious career discovery |
| Target users | High school students (primary); parents and counselors (secondary) | `docs/01_Product_Overview.md` | Live demo with a realistic student profile |
| Multi-agent design | 10 agents (Memory, Input Guardrail, Discovery, Retrieval, Recommendation, Path Planning, Guardrail, Evaluation, Observability, and the Orchestrator that coordinates them) | `src/agents/orchestrator.py`, `docs/09_Agent_Contracts.md` | Technical Details panel showing the agent flow for a single turn |
| RAG / grounded retrieval | Pinecone stores embeddings of careers, majors, colleges, and interest areas; retrieved context grounds every recommendation | `src/infrastructure/pinecone_client.py`, `src/services/retrieval_service.py`, `data/` | Retrieved documents shown in the trace panel |
| Memory | SQLite stores student profile, conversation history, and session metadata across visits | `src/agents/memory_agent.py`, `src/repositories/` | Return as a returning student and show context pickup |
| Guardrails | Pre-generation input checks (detection-only) plus post-generation checks blocking admission/salary guarantees and protected-attribute bias | `src/agents/guardrail_agent.py`, `src/agents/input_guardrail_agent.py` | Trigger a guardrail live and show the flag + note |
| Evaluation | RASCEF — 6 dimensions, GPT-4o LLM-as-judge with a rule-based fallback, bounded one-retry revision loop | `src/agents/evaluation_agent.py`, `src/services/evaluation_service.py` | Quality badge + score breakdown in the trace panel |
| Observability | Per-turn logging: model, tokens, real per-model cost, latency, eval score, guardrail flags | `src/agents/observability_agent.py` | Session log table |
| Cost monitoring | `estimated_cost_usd` computed from real token usage per call, logged per turn | `src/services/usage_tracker.py`, `observability_logs` table | Per-turn cost breakdown shown in the UI |
| Structured outputs | Student profile and every agent's input/output stored as typed JSON | `docs/09_Agent_Contracts.md` | Profile JSON evolving across turns |
| Demo scenario | Scripted student journeys covering discovery, GPA-aware guidance, and a returning student | `docs/11_Test_Scenarios_and_Golden_Dataset.md` | Live walkthrough of at least one end-to-end scenario |
| Documentation | Product overview, architecture, agent contracts, decision log, this document | `docs/` folder | Docs presented as evidence of design-first thinking |
| Responsible AI considerations | Guardrails, GPA-honest framing, no protected-category bias, counselor referral on high-risk responses | `src/agents/guardrail_agent.py`, `docs/09_Agent_Contracts.md` | Guardrail section of the presentation |

---

## Knowledge Base Design

The knowledge base has four root datasets, curated locally — no live external APIs. They're the foundation of every recommendation in the system.

### Careers

Stored in `data/careers.json`. Each document is embedded and indexed in Pinecone.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (e.g., `career_ux_researcher`) |
| `title` | string | Career name (e.g., "UX Researcher") |
| `description` | string | 2–3 sentence plain-language description |
| `interest_tags` | list[string] | Interests that make this career a good fit |
| `strength_tags` | list[string] | Academic or personal strengths that align |
| `related_majors` | list[string] | Major IDs or names that lead to this career |
| `skills` | list[string] | Core skills used in this role |
| `sample_projects` | list[string] | Concrete examples a high schooler can relate to |
| `future_outlook` | string | Brief note on job growth or industry direction |
| `why_exciting` | string | One compelling sentence for a student who hasn't heard of this career |

### Majors

Stored in `data/majors.json`.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (e.g., `major_cognitive_science`) |
| `name` | string | Major name |
| `description` | string | What students study in this major |
| `related_careers` | list[string] | Career IDs or names this major leads to |
| `recommended_subjects` | list[string] | High school subjects that prepare students for this major |
| `skills_built` | list[string] | Skills developed through this program |
| `typical_degree_types` | list[string] | e.g., `["Bachelor's", "Master's"]` |

### Colleges

Stored in `data/colleges.json`.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier |
| `name` | string | College name |
| `location` | string | City, State |
| `college_type` | string | e.g., "Public Research University" |
| `sample_programs` | list[string] | Notable programs relevant to common student profiles |
| `gpa_band` | string | Typical admitted GPA range |
| `pathway_notes` | string | 1–2 sentences on what type of student fits well |
| `affordability_notes` | string | General note on in-state tuition, financial aid reputation |
| `fit_tags` | list[string] | Student profile tags that match this college |

### Interests

Stored in `data/interests.json` — a fourth dataset added after the original design, mapping broad interest areas to relevant careers and majors, used when a student's message is exploratory rather than career-specific.

---

## Final Capstone Story

Not: *"I built a chatbot that recommends careers."*

Instead: *"I built PathFinder AI — a career discovery and college pathway guidance platform for high school students. The system demonstrates production-grade agentic AI patterns: RAG with Pinecone and OpenAI embeddings, SQLite memory for persistent student profiles, a 10-agent orchestration flow, layered input and output guardrails, RASCEF evaluation with LLM-as-judge and a bounded revision loop, per-turn observability with real cost tracking, and versioned, governed prompts. The high school student guidance domain is the use case; the AI system design patterns are the demonstration."*

### The Patterns This Project Makes Concrete

| AI Engineering Pattern | PathFinder AI Evidence |
|---|---|
| Multi-agent orchestration | 10 agents coordinated by a central orchestrator, with concurrency where it's safe (Discovery ‖ Retrieval) |
| RAG with vector search | Pinecone indexes 170 curated documents across careers, majors, colleges, and interests |
| Semantic retrieval | OpenAI `text-embedding-3-small` enables interest-based matching beyond keyword search |
| Persistent memory | SQLite stores an evolving student profile and full conversation history across sessions |
| Guardrails | Input-side detection plus post-generation rule checks that actually change what the student sees |
| Evaluation | RASCEF — 6-dimension LLM-as-judge scoring with a rule-based fallback and one bounded auto-retry |
| Observability | Real per-model token cost, latency, eval score, and guardrail flags logged per turn |
| Prompt governance | Every prompt is a versioned file, swappable via one env var, with no code change |
| Structured outputs | Every agent's input/output is a documented, typed JSON contract |
