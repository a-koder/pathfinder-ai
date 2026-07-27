# PathFinder AI — Capstone Mapping and Implementation Plan

## 1. Final Project Framing

PathFinder AI is a **chat-first career guidance and college pathway platform** for high school students, parents, and school counselors.

### What It Does for Students

- Surfaces careers students may not know exist — beyond the familiar defaults
- Explains what college majors connect to those careers and why
- Provides college pathway guidance grounded in GPA and academic profile
- Frames options as reach / target / likely — not guarantees
- Builds a personalized next-step roadmap students can act on
- Persists memory across sessions so returning students continue, not restart

### What It Demonstrates as a Capstone

The same system intentionally implements the core patterns of a production agentic AI application:

| Capstone Pattern | Role in PathFinder AI |
|---|---|
| Agent orchestration | Orchestrator coordinates specialized agents in a defined flow |
| RAG (Retrieval-Augmented Generation) | Pinecone retrieves relevant careers, majors, and colleges per query |
| Memory | SQLite stores student profile and conversation history across sessions |
| Guardrails | Post-generation checks enforce honesty, safety, and scope rules |
| Evaluation | Each response is scored on 6 quality dimensions |
| Observability | Every LLM call is logged with tokens, cost, latency, and scores |
| Cost optimization | GPT-4o-mini for generation; GPT-4o reserved for evaluation only |
| Prompt engineering | Dynamic system prompt assembles student context per turn |

---

## Career Positivity and Student Motivation

PathFinder AI should not only match students to careers. It should help students feel curious and motivated about paths they may not have considered.

Many students arrive uncertain or discouraged. The system should expand possibilities while remaining honest about effort, skills, and limitations.

Each career recommendation must explain:

- **Why the career may be exciting** — what draws people to this work, not just what skills it requires
- **What opportunities it opens** — industries, growth paths, adjacent roles, and long-term directions
- **What real-world impact it has** — how this work affects companies, communities, or people's lives
- **What related paths exist** — adjacent careers a student can explore if the primary option doesn't fit
- **What first step the student can take** — a concrete, grade-level-appropriate action they can do now

**Constraint:** Positive framing must be grounded in the knowledge base. It must not overpromise salary, job security, admission outcomes, or career guarantees. Inspiration is earned through honest excitement — not inflated claims.

This is captured in the Recommendation Agent contract in `docs/09_Agent_Contracts.md` and the career data schema in Section 4 of this document.

---

## 2. Capstone Requirement Mapping

| Capstone / AI System Requirement | How PathFinder AI Addresses It | Implementation Artifact | Demo Evidence |
|---|---|---|---|
| Real-world problem | High school students lack structured, personalized career and college guidance | `docs/01_Vision.md`, `docs/02_BRD.md` | Student conversation showing non-obvious career discovery |
| Target users | High school students (primary); parents and counselors (secondary) | `docs/03_PRD.md` personas | Live demo with a realistic student profile |
| Multi-agent design | Discovery, Memory, Retrieval, Recommendation, Guardrail, and Evaluation agents coordinated by Orchestrator | `src/agents/orchestrator.py` | Show agent flow log for a single conversation turn |
| RAG / grounded retrieval | Pinecone stores embeddings of careers, majors, and colleges; retrieved context grounds every recommendation | `src/retrieval/pinecone_client.py`, `data/` | Show retrieved documents injected into prompt context |
| Memory | SQLite stores student profile, conversation history, and session summaries | `src/memory/database.py` | Return as a prior student and show context pickup |
| Guardrails | Post-generation checks block guaranteed admission claims, salary fabrications, and protected-category bias | `src/guardrails/checks.py` | Trigger a guardrail intentionally and show the flag in logs |
| Evaluation | 6-dimension scoring (1–5 each); rule-based + optional LLM-as-judge | `src/evaluation/scorer.py` | Show evaluation scores in `observability_logs` |
| Observability | Per-call logging: model, tokens, cost, latency, eval score, guardrail flags | `src/observability/logger.py` | Display log table for a full session |
| Cost monitoring | `estimated_cost_usd` logged per call; model tier policy documented | `observability_logs` table | Show per-session cost breakdown |
| Structured outputs | Student profile stored as structured JSON; Pinecone metadata typed by document category | `src/schemas/models.py` | Show profile JSON evolving across turns |
| Demo scenario | 2–3 scripted student journeys covering: undecided student, grade 12 applicant, returning student | `docs/demo_scenarios.md` (Phase 10) | Live walkthrough of at least one end-to-end scenario |
| Documentation | Vision, BRD, PRD, Architecture, Agent Design, AI System Design, this document | `docs/` folder | Present docs as evidence of design-first thinking |
| Responsible AI considerations | Guardrails, GPA framing, no protected-category bias, counselor referral, confidence limits | `docs/06_AI_System_Design.md`, `src/guardrails/` | Guardrail section of presentation |

---

## 3. Final Architecture

The complete request flow for every student message:

```
Student
  └─► Streamlit Chat UI
        └─► Orchestrator
              ├─► Memory Agent
              │     └─► Load student profile + conversation summary from SQLite
              │
              ├─► Discovery Agent
              │     └─► Update student understanding from current message
              │
              ├─► Retrieval Agent
              │     ├─► Build retrieval query from student profile + message
              │     ├─► Generate OpenAI embedding for query
              │     └─► Retrieve top-k career / major / college documents from Pinecone
              │
              ├─► Recommendation Agent
              │     └─► Generate grounded response using retrieved context
              │         (career suggestions, major guidance, college pathway)
              │
              ├─► Guardrail Agent
              │     └─► Check for unsafe, overconfident, or out-of-scope claims
              │
              ├─► Evaluation Agent
              │     └─► Score response on 6 quality dimensions
              │
              ├─► Observability Logger
              │     └─► Write tokens, cost, latency, scores, flags to SQLite
              │
              ├─► Final Response → Streamlit UI
              │
              └─► Memory Agent
                    └─► Save message, update profile, update conversation summary
```

**Agent summary:**

| Agent | Responsibility | File |
|---|---|---|
| Memory Agent | Load and save student profile + conversation history | `src/agents/memory_agent.py` |
| Discovery Agent | Extract interests, GPA, grade, dislikes from conversation | `src/agents/discovery_agent.py` |
| Retrieval Agent | Build query, embed, retrieve top-k docs from Pinecone | `src/agents/retrieval_agent.py` |
| Recommendation Agent | Generate grounded career / major / college response | `src/agents/recommendation_agent.py` |
| Guardrail Agent | Post-generation safety and honesty checks | `src/agents/guardrail_agent.py` |
| Evaluation Agent | Score response quality across 6 dimensions | `src/agents/evaluation_agent.py` |
| Orchestrator | Coordinate all agents in sequence per turn | `src/agents/orchestrator.py` |

**MVP realism note:** For the 1–2 week capstone, each agent is a lightweight class with a single method. Discovery, Recommendation, Guardrail, and Evaluation logic run within the same LLM call or as post-generation functions — not as separate API calls per agent. Separate LLM calls are used only for: (1) the main generation call and (2) optional LLM-as-judge evaluation on sampled responses.

---

## 4. Knowledge Base Design

The knowledge base contains three root datasets. These are the foundation of every recommendation in the system. They are curated locally for MVP — no live APIs required.

### 4.1 Careers

Stored in `data/careers.json`. Each career document is embedded and indexed in Pinecone.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (e.g., `career_ux_researcher`) |
| `title` | string | Career name (e.g., "UX Researcher") |
| `description` | string | 2–3 sentence plain-language description |
| `interest_tags` | list[string] | Interests that make this career a good fit (e.g., `["design", "psychology", "tech"]`) |
| `strength_tags` | list[string] | Academic or personal strengths that align (e.g., `["communication", "analysis"]`) |
| `related_majors` | list[string] | Major IDs or names that lead to this career |
| `skills` | list[string] | Core skills used in this role |
| `sample_projects` | list[string] | Concrete examples a high schooler can relate to |
| `future_outlook` | string | Brief note on job growth or industry direction |
| `why_exciting` | string | One compelling sentence for a student who hasn't heard of this career |

### 4.2 Majors

Stored in `data/majors.json`. Each major document is embedded and indexed in Pinecone.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (e.g., `major_cognitive_science`) |
| `name` | string | Major name (e.g., "Cognitive Science") |
| `description` | string | What students study in this major |
| `related_careers` | list[string] | Career IDs or names this major leads to |
| `recommended_subjects` | list[string] | High school subjects that prepare students for this major |
| `skills_built` | list[string] | Skills developed through this program |
| `typical_degree_types` | list[string] | (e.g., `["Bachelor's", "Master's"]`) |

### 4.3 Colleges

Stored in `data/colleges.json`. Each college document is embedded and indexed in Pinecone.

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique identifier (e.g., `college_uc_san_diego`) |
| `name` | string | College name |
| `location` | string | City, State |
| `college_type` | string | (e.g., "Public Research University", "Liberal Arts College") |
| `sample_programs` | list[string] | Notable programs relevant to common student profiles |
| `gpa_band` | string | Typical admitted GPA range (e.g., `"3.5–4.0"`) |
| `pathway_notes` | string | 1–2 sentences on what type of student fits well |
| `affordability_notes` | string | General note on in-state tuition, financial aid reputation |
| `fit_tags` | list[string] | Student profile tags that match this college (e.g., `["STEM", "large campus", "research opportunities"]`) |

**MVP note:** Start with 25–30 careers, 20–25 majors, and 20–30 curated college examples. Depth and coverage can be expanded in later iterations. Quality of data matters more than quantity for the prototype.

---

## 5. Pinecone RAG Design

### Why Pinecone

Semantic search over the knowledge base lets the system find relevant careers, majors, and colleges based on meaning — not keyword matching. A student who says "I like figuring out why people do things" should surface psychology, UX research, and behavioral economics even without using those exact words.

### Indexing Strategy

- Each career, major, and college document is converted to a plain-text embedding document
- The text combines the most semantically rich fields: title, description, interest tags, skills, pathway notes
- OpenAI `text-embedding-3-small` generates the embedding vector (1536 dimensions, low cost)
- Each vector is stored in Pinecone with structured metadata for filtered retrieval

**Pinecone metadata schema per document:**

```json
{
  "doc_type": "career | major | college",
  "title": "UX Researcher",
  "tags": ["design", "psychology", "user research"],
  "gpa_band": "3.0–3.8",
  "related_majors": ["cognitive_science", "hci", "psychology"],
  "source_file": "data/careers.json"
}
```

### Query Strategy

At retrieval time, the orchestrator builds a query string from:
- Student's stated interests and strengths
- Current student question or message
- GPA (if known) — used in metadata filtering for college documents

The query string is embedded using `text-embedding-3-small` and sent to Pinecone. Retrieval returns the top-k most semantically relevant documents.

**Retrieval parameters:**
- `top_k`: 5–8 documents per query (tunable)
- Metadata filter: `doc_type` can be restricted to `career`, `major`, or `college` when the question is type-specific
- Retrieved documents are formatted as a context block injected into the system prompt

### What Gets Retrieved

| Student Question Type | Pinecone Filter | Expected Returns |
|---|---|---|
| "What careers fit me?" | `doc_type: career` | 5 career documents matching interests |
| "What should I major in for game design?" | `doc_type: major` | Top majors related to game design |
| "What colleges fit a 3.2 GPA with CS interest?" | `doc_type: college` + GPA filter | Colleges in the matching GPA band |
| Open/mixed question | No filter | Mix of careers, majors, colleges |

---

## 6. Retrieval Flow

Step-by-step flow for every student conversation turn:

1. **Student message received** via Streamlit chat input
2. **Memory layer loads** existing student profile JSON and conversation summary from SQLite
3. **Discovery Agent** reads the current message and updates its understanding of the student — extracts or confirms interests, GPA, grade level, dislikes
4. **Orchestrator builds retrieval query** by combining: student interests + strengths + current question + relevant profile fields
5. **OpenAI embedding is generated** for the retrieval query using `text-embedding-3-small`
6. **Pinecone returns top-k documents** — careers, majors, and/or colleges semantically relevant to the query
7. **Recommendation Agent generates a grounded response** using: system prompt + student profile context + retrieved documents + conversation history
8. **Guardrail Agent checks** the generated response for unsafe claims, overconfident language, out-of-scope content, and GPA framing
9. **Evaluation Agent scores** the response across 6 quality dimensions; flags responses below threshold
10. **Observability logger records** the full call: timestamp, student name, model used, embedding model, prompt tokens, completion tokens, estimated cost (USD), latency (ms), retrieved document count, guardrail flags, evaluation score, errors
11. **Memory is updated**: new message saved to `messages`, student profile merged with any new profile fields, conversation summary updated if session has crossed a threshold

---

## 7. Memory Design

### SQLite Tables

**`students`** — One row per student
- `student_id` (TEXT, UUID) — primary key
- `name` (TEXT) — used for session recognition
- `created_at` (DATETIME) — first session
- `last_seen_at` (DATETIME) — most recent session
- `session_count` (INTEGER) — total sessions

**`profiles`** — One row per student; updated incrementally
- `student_id` (TEXT) — foreign key
- `profile_json` (TEXT) — full profile as JSON blob
- `updated_at` (DATETIME) — last write timestamp

**`messages`** — One row per conversation turn
- `message_id` (TEXT, UUID)
- `student_id` (TEXT) — foreign key
- `session_number` (INTEGER)
- `role` (TEXT) — "user" or "assistant"
- `content` (TEXT) — full message text
- `timestamp` (DATETIME)

**`conversation_summaries`** — One row per session; written at session close
- `summary_id` (TEXT, UUID)
- `student_id` (TEXT) — foreign key
- `session_number` (INTEGER)
- `summary_text` (TEXT) — LLM-generated summary of key points from the session
- `created_at` (DATETIME)

**`observability_logs`** — One row per LLM or embedding API call
- `log_id` (TEXT, UUID)
- `student_id` (TEXT)
- `timestamp` (DATETIME)
- `agent` (TEXT) — which component made this call
- `model` (TEXT) — e.g., `gpt-4o-mini`
- `embedding_model` (TEXT) — e.g., `text-embedding-3-small`
- `prompt_tokens` (INTEGER)
- `completion_tokens` (INTEGER)
- `estimated_cost_usd` (REAL)
- `latency_ms` (INTEGER)
- `retrieved_doc_count` (INTEGER)
- `guardrail_flags` (TEXT) — JSON list
- `eval_score` (INTEGER) — total out of 30
- `error` (TEXT)

### Evolving Profile JSON

```json
{
  "student_name": "",
  "grade_level": "",
  "gpa": "",
  "interests": [],
  "strengths": [],
  "dislikes": [],
  "career_preferences": [],
  "favorite_careers": [],
  "preferred_majors": [],
  "college_preferences": [],
  "prior_recommendations": [],
  "conversation_summary": ""
}
```

Fields are merged, not overwritten. A returning student's second session appends new interests rather than replacing prior ones.

### Student Recognition

- **MVP:** Student enters their name at the start of each session. Orchestrator looks up by name (case-insensitive) in the `students` table.
- **Production:** Name-based lookup is not secure for real student data. Production requires email-based login or SSO with access controls.

---

## 8. Guardrail Strategy

Guardrails are applied as post-generation checks before every response is returned to the student. These are not optional — they are a core responsibility of any AI system making claims that affect major life decisions.

**What PathFinder AI will never do:**

- Guarantee or predict college admission — blocked phrases include "you will get in," "guaranteed acceptance," "certain to be admitted"
- State salary figures or job outcome statistics unless they appear verbatim in the knowledge base
- Make recommendations based on race, gender, religion, nationality, or any other protected characteristic
- Push a student toward a single career or college path — recommendations always present multiple options
- Answer questions about scholarships, financial aid, FAFSA, SAT/ACT scores, or essay review (redirect constructively)
- Fabricate career, major, or college information not present in the retrieved context

**What PathFinder AI will always do:**

- Frame college options as **reach / target / likely** based on the student's GPA band — never as certainty
- Ask clarifying questions when the student profile is too sparse to make a reliable recommendation
- Acknowledge the limits of AI guidance and recommend consulting a real school counselor or parent for final decisions
- Include a confidence note when the retrieved context is thin or the student's profile is incomplete
- Label responses appropriately when the system cannot fully ground a claim

**Implementation:** A set of rule-based string checks runs on every generated response. Flagged responses are returned with an appended disclaimer or rewritten with a safer prompt. All flags are logged in `observability_logs`.

---

## 9. Evaluation Strategy

Evaluation measures whether the system is giving genuinely useful guidance — not just fluent text.

### Evaluation Dimensions

Each response is scored 1–5 on 6 dimensions. Maximum total: 30.

| Dimension | What It Measures | Low Score Example |
|---|---|---|
| Relevance | Does the response address what the student actually asked? | Career suggestions that ignore the student's stated question |
| Groundedness | Are claims supported by retrieved documents, not hallucinated? | Salary figure or college fact not found in any retrieved document |
| Personalization | Does the response reflect this specific student's profile? | Generic advice that could apply to any student |
| Actionability | Does the student know what to do next? | "Think about your future" with no concrete step |
| Safety | Does the response avoid overconfident or harmful claims? | "You'll definitely get into this school with a 3.5 GPA" |
| Clarity | Is the response readable and jargon-free for a high schooler? | Dense academic prose with no structure |

**Pass threshold:** 24 / 30. Responses below this score are flagged in `observability_logs` for review.

### Evaluation Methods

**1. Rule-based checks (always run, zero additional cost)**
- Did the response include at least 3 career/major/college options when a recommendation was requested?
- Did each career suggestion include a reason why it fits this specific student?
- Did the response avoid guaranteed admission language?
- Was GPA guidance framed as reach / target / likely?
- Did the response include at least one concrete next step?
- Were retrieved documents used (not ignored) in the response?

**2. LLM-as-judge using GPT-4o (selective)**
- A second LLM call sends the student message, retrieved context, and generated response to GPT-4o
- GPT-4o returns a structured JSON object: dimension scores + brief reasoning per dimension
- Reserved for: every Nth response (configurable), or any response that fails a rule-based check
- Adds ~$0.01–0.05 per evaluation call — use deliberately, log every use

**3. Manual review with mock student profiles (pre-demo)**
- Create 5–10 fictional student profiles covering: high / mid / low GPA, varied interests, grades 9–12
- Run each through the full conversation flow end-to-end
- Score responses manually against all 6 dimensions
- Use findings to tighten system prompt and guardrail rules before the final demo

---

## 10. Observability and Cost Tracking

### What Is Logged Per LLM or Embedding Call

| Field | Why It Matters |
|---|---|
| `timestamp` | Sequence and timing; correlate events across a session |
| `student_name` | Trace logs back to a specific user journey |
| `agent` | Identify which component made the call (Orchestrator, Evaluation, etc.) |
| `model` | Verify model-tier decisions are being followed |
| `embedding_model` | Track embedding cost separately from generation cost |
| `prompt_tokens` | Primary input cost driver; flag bloated prompts |
| `completion_tokens` | Output cost driver; flag unexpectedly long responses |
| `estimated_cost_usd` | Real cost per call; accumulate per session and per student |
| `latency_ms` | User experience signal; slow calls degrade trust in a chat app |
| `retrieved_doc_count` | Confirm retrieval is working; 0 retrieved = grounding failure |
| `guardrail_flags` | Safety audit trail; shows which rules trigger most often |
| `eval_score` | Quality trend; track whether prompt changes improve or degrade scores |
| `error` | Debugging; API failures, parsing errors, empty retrievals |

### Why This Matters for Engineering Leadership

- **Cost control:** Token and cost logging per session produces the data needed to make model-tier decisions with evidence, not intuition. A session that costs $0.50 instead of $0.05 has a detectable cause.
- **Quality monitoring:** Evaluation score trends across sessions reveal whether the system is improving or drifting — without relying on gut feel.
- **Debugging:** When a student receives a bad or irrelevant response, the observability log shows the full chain: which agent ran, what model was called, what was retrieved, what was flagged.
- **Responsible AI governance:** Guardrail flag frequency is the audit trail that demonstrates the system is actively enforcing safety rules — not just claiming to.
- **Engineering credibility:** An EM who can instrument, measure, and interpret an AI system's behavior is operating at a different level than one who can only prompt it.

---

## 11. Implementation Phases

### Phase 1 — Foundation
**Goal:** Project structure reflecting Clean Architecture is in place, virtual environment is configured for the correct platform, `.gitignore` is committed, and a working Streamlit shell is running locally.

**Architecture layers scaffolded in this phase:**

| Layer | Folder | Purpose |
|---|---|---|
| Presentation | `src/app.py` | Streamlit UI — no business logic |
| Application | `src/agents/` | Agent use cases — stub classes only |
| Service | `src/services/` | Service stubs — no real API calls yet |
| Repository | `src/repositories/` | Repository stubs — no real SQL yet |
| Infrastructure | `src/infrastructure/` | Client stubs — no real SDK calls yet |
| Domain | `src/schemas/models.py` | Pydantic models — all agent contracts |

**Files touched:**
- `.gitignore`
- `requirements.txt`
- `.env.example`
- `src/config.py` (loads environment variables; exposes `has_openai_key()`, `has_pinecone_key()`)
- `src/app.py` (Streamlit shell; calls `Orchestrator.run()`)
- `src/schemas/models.py` (all Pydantic domain models)
- `src/agents/orchestrator.py`, `discovery_agent.py`, `memory_agent.py`, `retrieval_agent.py`, `recommendation_agent.py`, `path_planning_agent.py`, `guardrail_agent.py`, `evaluation_agent.py`, `observability_agent.py` (stub classes with constructor injection)
- `src/services/llm_service.py`, `embedding_service.py`, `retrieval_service.py`, `prompt_service.py` (stubs)
- `src/repositories/student_repository.py`, `profile_repository.py`, `message_repository.py`, `observability_repository.py` (stubs)
- `src/infrastructure/openai_client.py`, `pinecone_client.py`, `sqlite_client.py`, `knowledge_loader.py` (stubs)

**Note:** The initial `src/memory/`, `src/retrieval/`, `src/guardrails/`, `src/evaluation/`, and `src/observability/` stub folders created before this design decision are superseded by the Clean Architecture layout above. They will be removed as part of this phase.

**Virtual environment setup:**

Windows (primary development environment):
```
python -m venv .venv_win
.venv_win\Scripts\activate
pip install -r requirements.txt
```

Linux or WSL (reserved for future use):
```
python -m venv .venv_linux
source .venv_linux/bin/activate
pip install -r requirements.txt
```

Use `.venv_win` for all active Windows development. Do not activate `.venv_linux` on Windows — it is reserved for Linux or WSL contexts only.

**`.gitignore` — must be created before the first commit:**
```
# Virtual environments
.venv_win/
.venv_linux/

# Secrets
.env

# Python cache
__pycache__/
*.pyc

# Local database
data/memory.db
```

**Verification:**
- `.gitignore` is present and contains all required entries before any other files are committed
- `.venv_win` is created and activated; `pip list` shows installed packages
- `streamlit run src/app.py` opens a chat UI in the browser
- Sending a message returns a hardcoded placeholder response
- No errors on startup; `.env` loads correctly
- `git status` does not show `.venv_win/`, `.env`, or `__pycache__/` as tracked files

---

### Phase 2 — SQLite Memory
**Goal:** Student profiles and conversation history persist across sessions via the Repository pattern.

**Files touched:**
- `src/infrastructure/sqlite_client.py` (connection management; schema creation for all 5 tables)
- `src/repositories/student_repository.py` (`create_or_get`, `update_last_seen`)
- `src/repositories/profile_repository.py` (`get`, `upsert`)
- `src/repositories/message_repository.py` (`save`, `get_recent`)
- `src/agents/memory_agent.py` (wires repositories; implements `load` and `save`)

**Design note:** Agents call `MemoryAgent` — they never import from `repositories/` or `infrastructure/` directly. All SQL lives in repositories. All SDK calls live in `sqlite_client.py`.

**Verification:**
- New student record created on first session
- Profile JSON saved and retrievable by name
- Messages saved per session; `get_recent` returns correct ordering
- Returning student lookup returns prior profile without asking again
- No SQL written outside of `src/repositories/`

---

### Phase 3 — Knowledge Base Data
**Goal:** Career, major, and college datasets exist as curated local JSON files.

**Files touched:**
- `data/careers.json` (25–30 entries, all fields populated)
- `data/majors.json` (20–25 entries)
- `data/colleges.json` (20–30 entries)

**Verification:**
- All JSON files are valid and parseable
- Each document contains all required fields
- At least 3 career-to-major relationships are correct and cross-referenced
- College GPA bands are accurate and usable for reach / target / likely classification

---

### Phase 4 — OpenAI Embeddings and Pinecone Ingestion
**Goal:** Knowledge base documents are embedded and stored in Pinecone via the infrastructure layer.

**Files touched:**
- `src/infrastructure/knowledge_loader.py` (load and parse `careers.json`, `majors.json`, `colleges.json`)
- `src/infrastructure/openai_client.py` (implement embedding call via OpenAI SDK)
- `src/infrastructure/pinecone_client.py` (implement index init, upsert, and query via Pinecone SDK)
- `src/services/embedding_service.py` (calls `OpenAIClient`; handles retries; returns vector)
- `scripts/ingest.py` (one-time script: loads knowledge base, embeds, upserts to Pinecone)

**Design note:** `scripts/ingest.py` uses `KnowledgeLoader` and `PineconeClient` directly — it is an ops script, not part of the agent flow. The `EmbeddingService` and `PineconeClient` used at runtime are the same classes.

**Verification:**
- `python scripts/ingest.py` populates the Pinecone index without errors
- Each vector has correct metadata (`doc_type`, `title`, `tags`, `gpa_band`)
- Pinecone console shows expected vector count
- Re-running ingest is idempotent (upsert by `id`, no duplicates)
- No Pinecone or OpenAI SDK calls outside `src/infrastructure/`

---

### Phase 5 — Retrieval Function
**Goal:** Given a student profile and message, retrieve semantically relevant documents from Pinecone via the service layer.

**Files touched:**
- `src/services/retrieval_service.py` (builds query string; calls `EmbeddingService`; calls `PineconeClient`; falls back to `KnowledgeLoader` tag-match on failure)
- `src/agents/retrieval_agent.py` (calls `RetrievalService`; returns `RetrievalOutput`)

**Design note:** `RetrievalAgent` depends on `RetrievalService` injected at construction. It does not import `PineconeClient` or `OpenAIClient`. The fallback logic (local JSON) lives in `RetrievalService`, not in the agent.

**Verification:**
- "I like helping people and I'm interested in biology" returns relevant career documents
- `doc_type: college` filter returns only college documents
- Retrieved document count appears in observability log
- Pinecone failure triggers local JSON fallback without crashing
- No Pinecone or OpenAI imports in `src/agents/`

---

### Phase 6 — Conversational Recommendation Agent
**Goal:** The system holds a full guided conversation and returns grounded career, major, and college recommendations. All agents are wired through the service layer.

**Files touched:**
- `src/infrastructure/openai_client.py` (implement chat completion call)
- `src/services/llm_service.py` (wraps `OpenAIClient`; handles retries; accepts model parameter for mini vs. full)
- `src/services/prompt_service.py` (assembles system prompt from profile + retrieved context + history)
- `src/agents/discovery_agent.py` (calls `LLMService` with extraction prompt; returns `DiscoveryOutput`)
- `src/agents/recommendation_agent.py` (calls `PromptService` then `LLMService`; returns `RecommendationOutput`)
- `src/agents/orchestrator.py` (instantiates all services and agents; wires full turn flow)

**Design note:** All agents receive services via `Orchestrator.__init__()` — no agent creates its own `OpenAIClient`. The `LLMService` accepts a `model` parameter so the same service instance handles both GPT-4o-mini (normal) and GPT-4o (evaluation).

**Verification:**
- Student can have a 5-turn conversation and receive at least 3 grounded career suggestions
- Each suggestion references a career that exists in the knowledge base
- Retrieved documents appear in the generated response
- Returning student is greeted with prior context from memory
- No `openai` or `pinecone` imports anywhere in `src/agents/`

---

### Phase 7 — Guardrail Checks
**Goal:** All responses are checked for unsafe claims before being returned. Guardrail logic lives in the agent layer — no LLM call required.

**Files touched:**
- `src/agents/guardrail_agent.py` (rule-based string checks; returns `GuardrailResult` with flags and `risk_level`)

**Design note:** `GuardrailAgent` has no service or infrastructure dependencies — it is pure logic operating on a string. This is the cleanest example of Single Responsibility: one class, one method, one concern, zero external calls.

**Verification:**
- Guaranteed admission language is caught and flagged with `risk_level: high`
- GPA-related response without reach/target/likely framing is flagged
- Guardrail flags appear in `ObservabilityLog` after each turn
- No false positives on safe, honest responses

---

### Phase 8 — Evaluation Scoring
**Goal:** Every response is scored on 6 dimensions; low scores produce an amber or red quality badge.

**Files touched:**
- `src/agents/evaluation_agent.py` (rule-based checks always; calls `LLMService` with `gpt-4o` for sampled LLM-as-judge scoring)

**Design note:** `EvaluationAgent` reuses the injected `LLMService` with `model=EVAL_MODEL` — the same service abstraction used for generation, different model parameter. No new infrastructure dependency is needed.

**Verification:**
- All 6 rule-based checks run on every response
- Score is computed and stored via `ObservabilityRepository`
- A deliberately weak response scores below 24 (amber/red badge)
- A strong response scores 24+ consistently (green badge)
- LLM-as-judge call uses `gpt-4o`, logged separately in `observability_logs`

---

### Phase 9 — Observability and Cost Logging
**Goal:** Full call metadata is written to `observability_logs` on every LLM and embedding call via the repository layer.

**Files touched:**
- `src/repositories/observability_repository.py` (implement `write(log)` against SQLite)
- `src/agents/observability_agent.py` (calls `ObservabilityRepository`; computes `estimated_cost_usd`)

**Design note:** Cost calculation lives in `ObservabilityAgent`, not in `LLMService`. The service layer is responsible for calling the API — the agent layer is responsible for what to do with the result (including recording it). This keeps cost logic testable without API calls.

**Cost constants (per model, as of 2026):**
- `gpt-4o-mini`: $0.15 / 1M input tokens, $0.60 / 1M output tokens
- `gpt-4o`: $2.50 / 1M input tokens, $10.00 / 1M output tokens
- `text-embedding-3-small`: $0.02 / 1M tokens

**Verification:**
- Every conversation turn produces at least one log row in `observability_logs`
- `estimated_cost_usd` is non-zero and in a plausible range
- `latency_ms` is captured accurately
- A full session can be queried and summarized as a per-student cost report
- No cost or logging logic in `src/services/` or `src/infrastructure/`

---

### Phase 10 — Demo Scenarios and Final README
**Goal:** The system is demo-ready with scripted scenarios and clear documentation.

**Files touched:**
- `docs/demo_scenarios.md` (2–3 scripted student journeys with expected outputs)
- `README.md` (setup instructions, how to run, how to demo)

**README must include:**
- Virtual environment setup for Windows: `python -m venv .venv_win` then `.venv_win\Scripts\activate`
- Virtual environment setup for Linux / WSL: `python -m venv .venv_linux` then `source .venv_linux/bin/activate`
- Note that `.venv_win` is used for Windows development; `.venv_linux` is reserved for Linux contexts
- Steps to copy `.env.example` to `.env` and populate API keys
- How to run the ingest script to populate Pinecone before first use
- How to launch the app: `streamlit run src/app.py`

**Verification:**
- All 3 demo scenarios run end-to-end without errors
- Setup instructions work from a clean environment using `.venv_win` on Windows
- The full request flow (retrieval → generation → guardrail → evaluation → logging) is observable in a single demo turn
- `git status` on a clean clone shows no untracked secrets, cache files, or virtual environment folders

---

## 12. MVP Boundaries

### In Scope

- Chat-first conversational guidance interface
- Career discovery grounded in curated knowledge base
- Major recommendations connected to careers
- College pathway guidance tiered by GPA (reach / target / likely)
- GPA-aware, honest recommendations
- SQLite memory: student profile and conversation history
- Pinecone RAG: OpenAI embeddings over careers, majors, and colleges
- Discovery Agent, Recommendation Agent, and Path Planning Agent
- Guardrail checks on every response
- Evaluation scoring per response
- Observability logging: tokens, cost, latency, scores, flags
- Cost tracking and model tier policy

### Out of Scope

- Scholarship or financial aid matching
- FAFSA guidance
- Parent-facing portal or view
- Counselor-facing dashboard or student roster
- Real-time college admission data or APIs
- SAT / ACT score prediction or analysis
- College application tracking or deadline reminders
- Personal statement or essay review
- Production authentication or user account management
- Multi-user access controls
- Deployment to cloud infrastructure

---

## 13. Final Capstone Story

Do not say:

> "I built a chatbot that recommends careers."

Say:

> "I built PathFinder AI — a career discovery and college pathway guidance platform for high school students. The system demonstrates production-grade agentic AI patterns: RAG with Pinecone and OpenAI embeddings, SQLite memory for persistent student profiles, a multi-agent orchestration flow, post-generation guardrails, structured evaluation with LLM-as-judge, per-call observability logging, and cost-aware model selection. The high school student guidance domain is the use case — the AI system design patterns are the demonstration."

### The Patterns This Project Makes Concrete

| AI Engineering Pattern | PathFinder AI Evidence |
|---|---|
| Multi-agent orchestration | 6 agents coordinated by a central orchestrator in a defined request flow |
| RAG with vector search | Pinecone indexes 75+ curated documents; retrieved context grounds every recommendation |
| Semantic retrieval | OpenAI `text-embedding-3-small` enables interest-based career matching beyond keyword search |
| Persistent memory | SQLite stores evolving student profile and full conversation history across sessions |
| Guardrails | Post-generation rule checks enforce honesty, safety, and scope on every response |
| Evaluation | 6-dimension scoring with rule-based checks and optional LLM-as-judge; scores logged per call |
| Observability | Token counts, latency, cost, eval score, and guardrail flags written per API call |
| Cost optimization | GPT-4o-mini for all generation; GPT-4o reserved for evaluation; cost logged and reviewable |
| Prompt engineering | System prompt assembled dynamically per turn from student profile + retrieved context |
| Structured outputs | Profile stored as typed JSON; Pinecone metadata typed by document category |
