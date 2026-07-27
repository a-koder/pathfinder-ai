# PathFinder AI — AI System Design

## 1. System Purpose

PathFinder AI is not a chatbot. It is a small, purposefully designed **agentic AI system** demonstrated through a high school student career and college guidance use case.

### What It Does for Students

- Surfaces careers students may not know exist — beyond the obvious doctor/lawyer/engineer defaults
- Connects careers to relevant college majors with explanations of why they fit
- Provides GPA-aware college pathway guidance framed as reach / target / likely — not certainty
- Builds a personalized next-step roadmap based on the student's actual profile
- Persists memory across sessions so returning students continue, not restart

### What It Does for the Builder

This project is also a **hands-on learning platform** for practical AI engineering. Each component of PathFinder AI maps to a real pattern used in production agentic systems:

| Pattern | Where It Appears in PathFinder AI |
|---|---|
| Agent orchestration | Orchestrator controls flow, delegates to specialized agents |
| Memory design | SQLite stores student profile, history, and evolving preferences |
| Guardrails | Guardrail Agent prevents unsafe or overconfident claims |
| Evaluation | Evaluation Agent scores response quality on defined dimensions |
| Observability | Every LLM call is logged with tokens, cost, latency, and scores |
| Cost optimization | GPT-4o-mini for most calls; GPT-4o reserved for evaluation only |
| Prompt engineering | Dynamic system prompts inject student context per turn |
| Grounded recommendations | Career and major data served from local knowledge base, not hallucinated |

---

## 2. Final MVP Architecture

The request flow for every student message:

```
Student
  └─► Streamlit Chat UI
        └─► Orchestrator
              ├─► Memory Lookup         (load student profile + history)
              ├─► Discovery Agent       (understand student; build profile)
              ├─► Career Recommendation Agent  (match profile → careers)
              ├─► Path Planning Agent   (careers → majors → roadmap)
              ├─► Guardrail Checks      (safety, honesty, scope)
              ├─► Evaluation Checks     (quality score per response)
              ├─► Final Response        (sent to Streamlit UI)
              ├─► Memory Update         (save profile changes, messages)
              └─► Observability Logs    (tokens, cost, latency, scores)
```

**MVP realism note:** For the 1–2 week capstone, most agents are implemented as prompt sections within a single LLM call, not as separate API calls. The orchestrator coordinates them logically. Separate LLM calls are only used for evaluation when explicitly needed.

---

## 3. Core Components

### 3.1 Streamlit UI
- Chat-first interface — no forms, no dropdowns, just conversation
- Student enters their name at the start of every session
- Orchestrator uses the name to look up returning students in SQLite
- Chat history is displayed in the session window
- Roadmap summary can be rendered as a formatted block on request

### 3.2 Orchestrator
- Central controller — nothing runs without going through it
- On each turn:
  1. Loads student profile and recent messages from SQLite
  2. Determines which agent logic to activate (discovery, recommendation, planning)
  3. Builds the full system prompt dynamically with student context injected
  4. Calls the LLM and receives the response
  5. Runs guardrail checks on the output
  6. Runs evaluation scoring on the output
  7. Saves the updated profile and message to SQLite
  8. Writes an observability log entry
  9. Returns the final response to Streamlit

### 3.3 Memory Layer
- SQLite database stored at `data/memory.db`
- Four tables: `students`, `messages`, `profiles`, `observability_logs`
- Student profile is stored as a JSON blob — updated incrementally across sessions
- New interests are appended, not overwritten
- Conversation history provides the LLM with continuity across turns
- See Section 5 for full schema and profile structure

### 3.4 Career Knowledge Base
- Local files only — no real-time API calls in MVP
- `data/careers.json` — curated list of ~25–30 careers with descriptions, interest tags, and related majors
- `data/majors.json` — college majors with descriptions and typical career outcomes
- `data/colleges.md` — plain-text GPA-tier guidance (High / Mid / Open access)
- Relevant excerpts are injected into the system prompt when recommendations are needed
- The LLM reasons over this data — it does not fabricate careers or majors

### 3.5 LLM Layer
- **Primary model:** OpenAI `gpt-4o-mini` — used for all normal conversation, profile extraction, career recommendations, and path planning. Low cost, sufficient capability for structured guidance tasks.
- **Secondary model:** OpenAI `gpt-4o` — used optionally for evaluation (LLM-as-judge scoring) when a higher-quality assessment is needed. Not called on every turn.
- **Claude (via Claude Code):** Used for system design, documentation, code review, and development assistance — not the runtime model for the student-facing app.
- API key managed via environment variable (`OPENAI_API_KEY`) loaded from a `.env` file at startup.

---

## 4. Agent Responsibilities

### 4.1 Discovery Agent
**Goal:** Understand who the student is before making any recommendations.

- Asks open-ended questions about interests, activities, strengths, and dislikes
- Asks one question per turn — never lists multiple questions in a single response
- Asks about grade level and GPA casually and constructively
- Builds a structured student profile incrementally over the conversation
- Does not surface career recommendations until at least 2–3 profile fields are known

**Activation:** Always active in the first session; also activated when the profile is sparse.

### 4.2 Career Recommendation Agent
**Goal:** Surface relevant, non-obvious careers grounded in the student's profile.

- Matches student interests and strengths to careers in the local knowledge base
- Prioritizes careers the student is unlikely to have considered independently
- Provides at minimum 3 career suggestions with: career name, brief description, why it fits this student
- Does not recommend careers that contradict stated dislikes
- Uses the career knowledge base — does not invent careers from general LLM knowledge

**Activation:** When the student asks about careers, expresses uncertainty about direction, or profile has enough data.

### 4.3 Path Planning Agent
**Goal:** Convert career interest into an actionable roadmap.

- Maps each career to 1–2 relevant college majors
- Describes what students in that major study and where graduates typically work
- Suggests relevant high school activities, projects, or skills to develop
- Provides college pathway guidance (reach / target / likely) based on GPA
- Produces a structured next-step summary the student can act on

**Activation:** When a student expresses interest in a specific career or asks "what should I do next?"

### 4.4 Guardrail Agent
**Goal:** Ensure all responses are honest, safe, and within scope.

Checks applied before every response is returned:

- No guarantee of college admission — any phrasing like "you will get in" is blocked
- GPA guidance is always framed as reach / target / likely, never as certainty
- Salary or job outcome claims must be grounded in the knowledge base — no fabricated statistics
- No recommendations based on protected characteristics (race, gender, religion, etc.)
- Do not pressure the student toward a single path — always preserve optionality
- When the student's profile is incomplete, ask for clarification rather than guessing
- Out-of-scope questions (scholarships, financial aid, applications, essays) are redirected constructively
- Recommend consulting a real counselor or parent for final decisions

**Activation:** Always — runs as a post-generation check on every response.

### 4.5 Evaluation Agent
**Goal:** Score each response for quality across defined dimensions.

- Scores the response before it is returned to the student
- Logs the score to `observability_logs` for monitoring
- Flags responses that fall below the pass threshold
- Used to identify prompt weaknesses and improve system quality over time

See Section 7 for full scoring dimensions and methodology.

**Activation:** Every turn in full evaluation mode; rule-based checks always run; LLM-as-judge reserved for periodic sampling or low-scoring responses.

### 4.6 Memory Agent
**Goal:** Keep the student's profile current and useful across sessions.

- Reads the student profile from SQLite at the start of each turn
- After each turn, extracts profile updates from the conversation (new interests, updated GPA, career selections)
- Merges new fields into the existing profile — appends, does not overwrite
- Saves the full message (user + assistant) to the `messages` table
- Updates `conversation_summary` field periodically so returning sessions have concise context
- Enables returning students to continue without repeating themselves

**Activation:** Every turn — reads at start, writes at end.

---

## 5. Memory Design

### SQLite Tables

**`students`**
Stores one row per student.

| Field | Type | Purpose |
|---|---|---|
| student_id | TEXT (UUID) | Unique identifier |
| name | TEXT | Used for recognition at login |
| created_at | DATETIME | First session timestamp |
| last_seen_at | DATETIME | Most recent session timestamp |
| session_count | INTEGER | Total number of sessions |

**`messages`**
Stores every conversation turn.

| Field | Type | Purpose |
|---|---|---|
| message_id | TEXT (UUID) | Unique message ID |
| student_id | TEXT | Foreign key to students |
| session_number | INTEGER | Which session this message belongs to |
| role | TEXT | "user" or "assistant" |
| content | TEXT | Full message text |
| timestamp | DATETIME | When the message was sent |

**`profiles`**
Stores the evolving student profile as a JSON blob.

| Field | Type | Purpose |
|---|---|---|
| student_id | TEXT | Foreign key to students |
| profile_json | TEXT | Full profile as JSON string |
| updated_at | DATETIME | Last profile update timestamp |

**`observability_logs`**
Stores one row per LLM call.

| Field | Type | Purpose |
|---|---|---|
| log_id | TEXT (UUID) | Unique log ID |
| student_id | TEXT | Which student triggered this call |
| timestamp | DATETIME | When the call was made |
| agent | TEXT | Which agent/component made the call |
| model | TEXT | Model used (e.g., gpt-4o-mini) |
| prompt_tokens | INTEGER | Input token count |
| completion_tokens | INTEGER | Output token count |
| estimated_cost_usd | REAL | Calculated cost for this call |
| latency_ms | INTEGER | Round-trip time in milliseconds |
| eval_score | INTEGER | Evaluation score (out of 30) |
| guardrail_flags | TEXT | JSON list of any triggered flags |
| error | TEXT | Error message if call failed |

### Student Recognition (MVP)
- Student enters their name at the start of each session
- Orchestrator queries `students` table by name (case-insensitive)
- If found: load profile and last 10 messages as context for the LLM
- If not found: create a new student record and start Discovery phase
- **Production note:** Name-based lookup is MVP-only. A real system requires authentication (email + password or SSO) to prevent profile collisions and protect student data.

### Evolving Profile JSON

Stored in the `profiles.profile_json` field. Updated after each turn.

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
  "college_preferences": [],
  "conversation_summary": ""
}
```

Fields are appended incrementally — a second session that mentions a new interest adds it to the list rather than replacing it.

---

## 6. Guardrail Strategy

Guardrails are not optional polish — they are a core component of a responsible AI system, especially one interacting with minors about major life decisions.

**What PathFinder AI will never do:**

- Guarantee or predict college admission — responses must use "likely," "possible," "worth considering," not "you will get in"
- State exact salary or job outcome figures unless they appear verbatim in the local knowledge base
- Make recommendations based on race, gender, religion, nationality, or other protected characteristics
- Pressure the student toward a single path — always present options, not mandates
- Fabricate career, major, or college information not present in the knowledge base
- Act as a mental health resource — redirect to a school counselor if distress is detected

**What PathFinder AI will always do:**

- Label college options as reach / target / likely based on GPA range, never as certainty
- Ask for clarifying information when the student profile is too sparse to recommend well
- Acknowledge the limits of AI guidance and recommend real counselors or parents for final decisions
- Include a confidence note when recommendation grounding is thin
- Redirect out-of-scope questions constructively (e.g., "I focus on careers and majors — for scholarship info, your school counselor is a great resource")

**Implementation:** Guardrail checks are applied as a post-generation review step in the orchestrator. A small set of rule-based string checks runs on every response. A flagged response is either rewritten with a softer prompt or returned with an appended disclaimer.

---

## 7. Evaluation Strategy

Evaluation answers the question: *Is the system actually giving good guidance?*

Without evaluation, you are shipping a prompt and hoping for the best. With even lightweight evaluation, you can measure, compare, and improve.

### Dimensions and Scoring

Each response is scored on 6 dimensions, 1–5 each. Maximum score: 30.

| Dimension | What It Measures | Example of a Low Score |
|---|---|---|
| Relevance | Does the response address what the student asked? | Career suggestions unrelated to stated interests |
| Groundedness | Are claims supported by local data, not invented? | Salary figure not found in knowledge base |
| Personalization | Does the response reflect this student's specific profile? | Generic advice that ignores stated GPA or interests |
| Actionability | Does the student know what to do next? | "You should think about your future" with no concrete step |
| Safety | Does the response avoid overconfident or harmful claims? | "You will definitely get into this school" |
| Clarity | Is the response readable and jargon-free for a high schooler? | Dense paragraph with no structure |

**Pass threshold:** 24/30. Responses below this threshold are flagged in `observability_logs`.

### Evaluation Methods

**1. Rule-based checks (always run, zero cost)**
- Did the response include at least 3 career options when recommendations were requested?
- Did each career include a reason why it fits this student?
- Did the response avoid phrases like "you will get in" or "guaranteed"?
- Was GPA guidance labeled as reach / target / likely?
- Did the response include at least one next step?
- Was the response under 300 words (appropriate length for a chat turn)?

**2. LLM-as-judge (optional, GPT-4o)**
- A second LLM call scores the response against the 6 dimensions
- Uses a structured scoring prompt — returns a JSON object with scores and brief reasoning
- Reserved for periodic sampling (e.g., every 5th response) or when rule-based checks flag a low score
- Adds ~$0.01–0.05 per scored response; use deliberately

**3. Manual review with mock profiles (pre-launch)**
- Create 5–10 fictional student profiles covering: high/mid/low GPA, different interests, different grade levels
- Run each through the full conversation flow
- Score manually against the 6 dimensions
- Use findings to tighten prompts before demo

---

## 8. Observability Strategy

Every LLM call writes a row to `observability_logs`. This is not logging for its own sake — it is the instrumentation that makes the system understandable and improvable.

### What Is Tracked Per Call

| Field | Why It Matters |
|---|---|
| Timestamp | Sequence and timing of agent activity |
| Student name | Correlate logs to a specific user journey |
| Agent / component | Which part of the system made this call |
| Model used | Verify cost-tier decisions are being respected |
| Prompt tokens | Input cost driver — flag bloated prompts |
| Completion tokens | Output cost driver — flag runaway responses |
| Estimated cost (USD) | Running total per student, per session |
| Latency (ms) | User experience — slow calls degrade trust |
| Evaluation score | Quality signal — identify weak response patterns |
| Guardrail flags | Safety signal — which rules are triggering and how often |
| Error messages | Debugging — API failures, parsing errors, empty responses |

### Why This Matters for Engineering Leadership

- **Cost control:** Token usage and estimated cost per session surfaces the real cost of serving each student. This is the data needed to make model-tier decisions confidently.
- **Quality monitoring:** Evaluation scores over time reveal whether prompt changes improved or degraded response quality — without relying on intuition.
- **Debugging:** When a student gets a bad response, the log shows exactly which agent was called, what model was used, what tokens were consumed, and what guardrail flags fired.
- **User experience:** Latency tracking identifies which components are slow. A 10-second response kills the chat experience.
- **Responsible AI governance:** Guardrail flag frequency shows how often the system is being pushed toward unsafe or out-of-scope territory. This is the audit trail that responsible AI requires.

---

## 9. Cost Optimization Strategy

Running an LLM-powered app has real costs. Building cost-awareness in from the start is an engineering discipline, not an afterthought.

### Model Selection Policy

| Use case | Model | Reason |
|---|---|---|
| Normal conversation | `gpt-4o-mini` | Sufficient reasoning quality at ~10x lower cost than GPT-4o |
| Career recommendations | `gpt-4o-mini` | Structured task; mini handles it reliably |
| Path planning | `gpt-4o-mini` | Same — structured output from good prompts |
| LLM-as-judge evaluation | `gpt-4o` | Higher-quality judgment; called selectively, not every turn |
| Design, docs, code review | Claude (Claude Code) | Development tool — not the runtime model |

### Prompt and Call Efficiency

- **No unnecessary second LLM calls** — profile extraction is included in the main system prompt, not a separate API call
- **Local knowledge base first** — career and major data is injected as context, not retrieved via embeddings or a separate search call
- **Cache career knowledge** — load `careers.json` and `majors.json` once at startup; do not reload per request
- **Compact prompts** — system prompt is built from modular sections; only inject the sections relevant to the current agent logic
- **Load only recent history** — inject the last 10 messages as context, not the full conversation history

### Cost Monitoring

- Every call logs `prompt_tokens`, `completion_tokens`, and `estimated_cost_usd` to `observability_logs`
- Token costs: GPT-4o-mini is approximately $0.15/1M input tokens, $0.60/1M output tokens (as of 2025)
- A 10-turn student session should cost well under $0.05 at these rates
- Cost anomalies (single call > $0.10) surface immediately in logs and should be investigated

---

## 10. Implementation Phases

### Phase 1 — Foundation (Days 1–2)
- Documentation complete ✓
- Project structure scaffolded (folders, `requirements.txt`, stub files)
- Streamlit shell running with a basic chat loop
- `.env` file and API key loading in place

### Phase 2 — Memory (Days 3–4)
- SQLite database initialized with all 4 tables
- Student profile read/write working
- Message history saved per session
- Returning student recognized by name and greeted with context

### Phase 3 — Career Data and Recommendations (Days 5–7)
- `careers.json` and `majors.json` populated with 25–30 curated entries
- `colleges.md` written with 3-tier GPA guidance
- Discovery Agent logic in system prompt — profile extraction working
- Career Recommendation Agent returning grounded suggestions
- Path Planning Agent producing roadmap summaries on request

### Phase 4 — Guardrails and Evaluation (Days 8–9)
- Guardrail checks implemented as post-generation review
- Rule-based evaluation checks running on every response
- Scores logged to `observability_logs`
- LLM-as-judge wired up and tested on 3–5 sample responses

### Phase 5 — Observability and Demo Polish (Days 10–12)
- Full observability logging working end-to-end
- Cost estimation calculated and logged per call
- 5–10 mock student profiles tested manually
- Response quality reviewed and prompts tightened
- Streamlit UI cleaned up for demo presentation
- Roadmap summary rendering polished

---

## 11. Capstone Story

The final presentation should not say:

> "I built a chatbot that recommends careers."

It should say:

> "I designed and implemented a small agentic AI system with memory, guardrails, evaluation, observability, cost-aware model selection, and grounded recommendations using a local knowledge base. High school student career and college guidance is the domain — it is the use case that makes the AI engineering patterns visible and testable."

### The Patterns This Project Demonstrates

| AI Engineering Pattern | PathFinder AI Implementation |
|---|---|
| Agent orchestration | Orchestrator coordinates 6 logical agents in a defined flow |
| Dynamic prompt construction | System prompt assembled per turn from profile + history + knowledge |
| Persistent memory | SQLite stores profile and history across sessions |
| Grounded generation (RAG lite) | Local JSON/Markdown knowledge base injected into prompt context |
| Guardrails | Post-generation checks enforce safety and honesty rules |
| Evaluation | 6-dimension scoring with rule-based and LLM-as-judge methods |
| Observability | Per-call logging of tokens, cost, latency, scores, and flags |
| Cost optimization | Model tier selection policy; prompt efficiency practices |

Each of these patterns appears in every serious production agentic system. PathFinder AI is the prototype that makes them concrete, testable, and explainable.
