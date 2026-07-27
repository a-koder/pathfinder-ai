# PathFinder AI — Architecture and Sequence Diagrams

## 1. Why These Diagrams Matter

PathFinder AI is both a **career guidance product** and a **capstone AI system**. These diagrams serve two audiences:

- **Product audience** (students, parents, counselors, evaluators): Shows what the system does and how it flows
- **Technical audience** (capstone reviewers, engineering peers): Shows that the system implements real AI engineering patterns — RAG, memory, guardrails, evaluation, observability, and cost tracking

Use these diagrams in the capstone presentation to move from "I built a chatbot" to "I designed and implemented a multi-agent AI system."

---

## 2. High-Level System Architecture

**What this shows:** The full system layered top to bottom — from the student interface down through orchestration, retrieval, agents, safety checks, and memory. Each layer has a distinct responsibility.

```mermaid
flowchart TD
    U["Student / Parent / Counselor"]
    UI["Streamlit Chat UI"]
    IGA["Input Guardrail Agent\n(profanity / frustration / prompt-injection)"]
    MA["Memory Agent\n(load)"]

    subgraph Parallel ["Runs Concurrently — Both Depend Only On Memory Load"]
        direction LR
        DA["Discovery Agent"]
        RETA["Retrieval Agent"]
    end

    MERGE["Memory Agent\n(merge + persist profile)"]
    RA["Recommendation Agent"]

    subgraph PostGen ["Runs After Recommendation"]
        direction LR
        PPA["Path Planning Agent"]
        GA["Guardrail Agent\n(output safety check)"]
    end

    EA["Evaluation Agent\n(RASCEF score)"]
    REV{"Score < 24?\nCritic / Revision Loop\n(max 1 retry)"}
    FR["Response → Streamlit UI"]

    subgraph Obs ["Observability"]
        OL["observability_logs\n(SQLite)"]
        LS["LangSmith\n(optional tracing)"]
        HITL["HITL Feedback\n👍 / 👎"]
    end

    subgraph RAG ["Retrieval Layer"]
        EMB["OpenAI Embeddings"]
        PC["Pinecone Vector Search"]
        KB["Career / Major / College Knowledge Base"]
    end

    MEM["SQLite\nStudent Profile + History"]

    U --> UI --> IGA --> MA
    MA <--> MEM
    MA --> Parallel
    RETA --> RAG
    EMB <--> PC <--> KB
    Parallel --> MERGE <--> MEM
    MERGE --> RA --> PostGen
    PostGen --> EA --> REV
    REV -- "yes, retry once" --> RA
    REV -- "no / already retried" --> FR
    FR --> UI
    EA --> Obs
    OL --> HITL
```

**Layer summary:**
- **Streamlit UI** — Chat interface; no business logic lives here
- **Orchestrator** — Central controller; coordinates all 10 agents in sequence (with one concurrent step) per turn
- **Input Guardrail Agent** — Pre-generation, rule-based check on the raw message (profanity/frustration/prompt-injection); detection only, never blocks
- **Memory Agent** — Reads student profile and history at turn start; merges and persists updates after Discovery; writes the turn at turn end
- **Discovery Agent** and **Retrieval Agent** — Run concurrently on worker threads: Discovery extracts interests/GPA/grade/dislikes from the message; Retrieval builds a semantic query, embeds it, and fetches top-k docs from Pinecone. Neither depends on the other's output
- **Recommendation Agent** — Generates grounded career, major, and college pathway response using retrieved context
- **Path Planning Agent** and **Guardrail Agent** — Path Planning builds the phased roadmap; the Guardrail Agent runs a rule-based post-generation safety check (10 flags)
- **Evaluation Agent** — Scores the response on the 6 RASCEF dimensions; scores below 24/30 trigger one automatic regenerate-and-recheck retry (the critic/revision loop), never more than one
- **Observability** — Every turn logs to SQLite (`observability_logs`), optionally traces to LangSmith, and exposes 👍/👎 HITL feedback wired to that same log row

---

## 3. End-to-End Sequence Diagram

**What this shows:** The exact sequence of events for a single conversation turn — which component calls which, in what order, and what flows back to the student.

```mermaid
sequenceDiagram
    actor S as Student
    participant UI as Streamlit UI
    participant ORC as Orchestrator
    participant IGA as Input Guardrail Agent
    participant MA as Memory Agent
    participant DA as Discovery Agent
    participant RETA as Retrieval Agent
    participant EMB as OpenAI Embeddings
    participant PC as Pinecone
    participant RA as Recommendation Agent
    participant PPA as Path Planning Agent
    participant GA as Guardrail Agent
    participant EA as Evaluation Agent
    participant OL as Observability Logger
    participant LS as LangSmith (optional)

    S->>UI: Sends message
    UI->>ORC: Forwards message + session state

    ORC->>IGA: Check raw message (profanity / frustration / prompt injection)
    IGA-->>ORC: Flags (detection only, never blocks)

    ORC->>MA: Load student profile and conversation summary
    MA-->>ORC: Profile JSON + last 10 messages

    par Discovery and Retrieval run concurrently
        ORC->>DA: Update student understanding
        DA-->>ORC: Updated profile fields (interests, GPA, grade)
    and
        ORC->>RETA: Build retrieval query from message
        RETA->>EMB: Embed retrieval query
        EMB-->>RETA: Query vector
        RETA->>PC: Search top-k relevant documents
        PC-->>RETA: Career / Major / College context
        RETA-->>ORC: Retrieved documents
    end

    ORC->>MA: Merge profile updates + persist
    MA-->>ORC: Merged profile

    ORC->>RA: Generate grounded response
    Note over ORC,RA: System prompt includes profile + retrieved context + history
    RA-->>ORC: Draft recommendations

    ORC->>PPA: Build phased roadmap for top recommendation
    PPA-->>ORC: Roadmap

    ORC->>GA: Check response for unsafe claims
    GA-->>ORC: Guardrail flags (if any)

    ORC->>EA: Score response quality (RASCEF)
    EA-->>ORC: Dimension scores (out of 30)
    EA->>LS: Trace (prompt versions, score, badge, guardrail + input guardrail flags)

    alt total_score < 24 (critic / revision loop, max 1 retry)
        ORC->>RA: Regenerate recommendation
        RA-->>ORC: New draft
        ORC->>PPA: Regenerate roadmap
        PPA-->>ORC: New roadmap
        ORC->>GA: Re-check response
        GA-->>ORC: Guardrail flags (if any)
        ORC->>EA: Re-score (max one retry, accepted either way)
        EA-->>ORC: Final scores
        EA->>LS: Trace (revision_attempted: true)
    end

    ORC->>OL: Record latency, scores, flags, prompt versions
    OL-->>ORC: log_id

    ORC->>MA: Save message + update profile
    MA-->>ORC: Confirmed

    ORC->>UI: Return final response + trace + log_id
    UI->>S: Display response in chat

    opt Student rates the response
        S->>UI: 👍 / 👎
        UI->>ORC: submit_feedback(log_id, helpful)
        ORC->>OL: save_feedback(log_id, helpful)
    end
```

---

## 4. RAG Pipeline Diagram

**What this shows:** How the knowledge base is converted into searchable vectors (indexing) and how student queries retrieve relevant content at runtime (query). This is the core of grounded, non-hallucinated recommendations.

```mermaid
flowchart LR
    subgraph Index ["Indexing Flow — One-Time Setup"]
        direction TB
        C["careers.json"]
        M["majors.json"]
        CL["colleges.json"]
        DB["Document Builder\nFormat text for embedding"]
        EMB1["OpenAI text-embedding-3-small"]
        PI["Pinecone Index\nWith metadata: doc_type, title, tags, gpa_band"]

        C --> DB
        M --> DB
        CL --> DB
        DB --> EMB1 --> PI
    end

    subgraph Query ["Query Flow — Per Conversation Turn"]
        direction TB
        Q1["Student Question"]
        Q2["Student Profile\nInterests, GPA, Grade"]
        QB["Query Builder\nCombine question + profile"]
        EMB2["OpenAI text-embedding-3-small"]
        PS["Pinecone Semantic Search\ntop-k with optional doc_type filter"]
        RC["Retrieved Context\nTop-k careers, majors, colleges"]
        LLM["GPT-4o-mini\nGenerates grounded response"]

        Q1 --> QB
        Q2 --> QB
        QB --> EMB2 --> PS --> RC --> LLM
    end
```

**Why this matters:** Without RAG, the LLM recommends careers from its training data — generic, unverifiable, and potentially hallucinated. With Pinecone retrieval, every recommendation is traceable to a specific document in the knowledge base. The system cannot recommend a career that does not exist in the curated dataset.

---

## 5. Memory Model Diagram

**What this shows:** The SQLite schema — five tables and how they relate to a single student. Memory is what transforms a one-time chatbot into a persistent counselor.

```mermaid
erDiagram
    STUDENTS {
        string student_id PK
        string name
        datetime created_at
        datetime last_seen_at
        int session_count
    }

    PROFILES {
        string student_id FK
        string grade_level
        string gpa
        string interests_json
        string strengths_json
        string favorite_careers_json
        string college_preferences_json
        datetime updated_at
    }

    MESSAGES {
        string message_id PK
        string student_id FK
        string role
        string content
        datetime created_at
    }

    CONVERSATION_SUMMARIES {
        string summary_id PK
        string student_id FK
        string summary
        datetime updated_at
    }

    OBSERVABILITY_LOGS {
        int log_id PK
        int student_id FK
        string model
        float estimated_cost_usd
        int latency_ms
        int eval_score
        string quality_badge
        string guardrail_flags
        string input_guardrail_flags
        bool revision_attempted
        string prompt_versions
        bool helpful
        string feedback_text
        datetime timestamp
    }

    STUDENTS ||--|| PROFILES : "has one"
    STUDENTS ||--o{ MESSAGES : "sends many"
    STUDENTS ||--o{ CONVERSATION_SUMMARIES : "has many"
    STUDENTS ||--o{ OBSERVABILITY_LOGS : "generates many"
```

**Key design decisions:**
- Profile is stored as JSON blobs — flexible enough to evolve without schema migrations
- Messages are stored individually — enables conversation replay and context injection
- Summaries are session-level — used to brief the LLM without injecting the full message history
- Observability logs are tied to the student — enables per-student cost and quality analysis

---

## 6. Agent Responsibility Diagram

**What this shows:** What each agent is responsible for and how they are coordinated. The Orchestrator is the hub — no agent runs independently.

```mermaid
flowchart TD
    ORC["Orchestrator\nCoordinates all 10 agents in sequence\n(with one concurrent step)"]

    subgraph IGA_box ["Input Guardrail Agent"]
        IGA1["Detect profanity"]
        IGA2["Detect frustration"]
        IGA3["Detect prompt-injection attempts"]
        IGA4["Detection only - never blocks the message"]
    end

    subgraph MA_box ["Memory Agent"]
        MA1["Read profile and history at turn start"]
        MA2["Merge and persist profile after Discovery"]
        MA3["Write message at turn end"]
    end

    subgraph DA_box ["Discovery Agent"]
        DA1["Extract interests, strengths, GPA, grade level"]
        DA2["Never invents GPA or grade level"]
        DA3["Runs concurrently with Retrieval"]
    end

    subgraph RETA_box ["Retrieval Agent"]
        RETA1["Build semantic query from the message"]
        RETA2["Generate OpenAI embedding for query"]
        RETA3["Fetch top-k career / major / college docs from Pinecone"]
        RETA4["Runs concurrently with Discovery"]
    end

    subgraph RA_box ["Recommendation Agent"]
        RA1["Generate response grounded in retrieved context"]
        RA2["Cover careers, majors, and college pathway guidance"]
        RA3["Explain why each recommendation fits this student"]
    end

    subgraph PPA_box ["Path Planning Agent"]
        PPA1["Build a phased roadmap for the top recommendation"]
        PPA2["Short-term, medium-term, long-term steps"]
    end

    subgraph GA_box ["Guardrail Agent"]
        GA1["Block admission / salary guarantees"]
        GA2["Prevent protected-attribute bias"]
        GA3["Flag missing GPA / budget / location context"]
        GA4["Flag ungrounded recommendations"]
    end

    subgraph EA_box ["Evaluation Agent"]
        EA1["RASCEF: relevance, accuracy, safety"]
        EA2["RASCEF: completeness, explainability, fairness"]
        EA3["Flag responses below 24 out of 30"]
        EA4["Trigger the critic/revision retry (max 1)"]
    end

    subgraph OBS_box ["Observability Agent"]
        OBS1["Log every turn to SQLite"]
        OBS2["Return log_id for HITL feedback"]
        OBS3["Optional LangSmith trace"]
    end

    ORC --> IGA_box
    ORC --> MA_box
    ORC --> DA_box
    ORC --> RETA_box
    ORC --> RA_box
    ORC --> PPA_box
    ORC --> GA_box
    ORC --> EA_box
    ORC --> OBS_box
```

---

## 7. Guardrail and Evaluation Flow

**What this shows:** What happens after the LLM generates a response and before it reaches the student. Safety checks and quality scoring are not optional — they run on every turn.

```mermaid
flowchart TD
    MSG["Raw Student Message"]
    IG{"Input Guardrail\nprofanity / frustration /\nprompt-injection?"}
    GEN["Recommendation + Path Planning\nfrom GPT-4o-mini"]

    subgraph Guardrails ["Output Guardrail — 10 Rule-Based Flags"]
        G1["High risk: admission_guarantee,\nsalary_guarantee, protected_attribute_bias"]
        G2["Medium risk: overconfidence, pressure_language,\nmissing_gpa/budget context, missing_grounding"]
        G3["Low risk: missing_location_for_college,\ninsufficient_profile"]
    end

    subgraph Evaluation ["RASCEF Evaluation Scoring — 6 Dimensions, 1-5 each"]
        E1["Relevance"]
        E2["Accuracy / groundedness"]
        E3["Safety"]
        E4["Completeness"]
        E5["Explainability"]
        E6["Fairness"]
        TOTAL["Total Score out of 30"]
    end

    PASS["Pass — Score >= 24\nReturn response to student"]
    RETRY{"Score < 24?\nRevise once\n(max 1 retry)"}
    STILLLOW["Still < 24 after retry\nReturn anyway, with a\n'needs more info' note"]

    MSG --> IG
    IG -- "flags recorded, never blocks" --> GEN
    GEN --> Guardrails
    G1 -- "high risk" --> SAFENOTE["Safe note appended\n(never withheld)"]
    G2 -- "medium risk" --> LIMNOTE["'Keep in mind' note appended"]
    G3 -- "low risk" --> Evaluation
    SAFENOTE --> Evaluation
    LIMNOTE --> Evaluation

    E1 & E2 & E3 & E4 & E5 & E6 --> TOTAL
    TOTAL --> RETRY
    RETRY -- "No" --> PASS
    RETRY -- "Yes, first attempt" --> GEN
    RETRY -- "Yes, already retried once" --> STILLLOW
```

**Scoring threshold:** 24 out of 30, computed deterministically from `total_score` (never trusted from the model). A response below threshold triggers exactly one regenerate-and-recheck retry (the critic/revision loop); if it is still below threshold after that retry, it is returned anyway with a "needs more information" note rather than withheld or retried further. Every attempt — including the retry — is logged to `observability_logs` and, if configured, traced to LangSmith.

---

## 8. Observability and Cost Tracking Diagram

**What this shows:** What is captured for every API call and where it goes. This is the instrumentation layer that makes the system understandable, debuggable, and cost-controllable.

```mermaid
flowchart TD
    CALL["Each Conversation Turn\nOrchestrator.run_turn()"]

    subgraph Meta ["Captured Metadata"]
        M1["Model names\ngeneration / evaluation / embedding"]
        M2["Prompt versions\ndiscovery, recommendation, path_planning,\nrascef, guardrail, input_guardrail"]
        M3["Estimated cost USD\ncalculated from token counts - currently\nalways $0.00, token usage not yet wired up"]
        M4["Latency ms\nRound-trip time for the full turn"]
        M5["Retrieved document count\nFrom Pinecone"]
        M6["Input guardrail flags\nprofanity / frustration / prompt-injection"]
        M7["Output guardrail flags + risk level"]
        M8["Evaluation score, quality badge,\nRASCEF dimension breakdown"]
        M9["revision_attempted\ntrue if the critic/revision retry fired"]
    end

    LOG["observability_logs Table\nOne row per turn, returns log_id"]
    LS["LangSmith\n(optional - same metadata, per evaluation call)"]
    HITL["HITL Feedback\n👍 / 👎 linked to log_id"]

    subgraph Uses ["Why This Matters"]
        U1["Cost control\nPer-session and per-student spend"]
        U2["Debugging\nTrace bad responses to their source"]
        U3["Quality monitoring\nEval score trends, revision-retry frequency"]
        U4["Responsible AI\nGuardrail + input guardrail frequency audit trail"]
        U5["Production readiness\nLatency and failure rate tracking"]
    end

    CALL --> Meta --> LOG --> Uses
    Meta --> LS
    LOG --> HITL
```

**From an Engineering Manager perspective:** Observability is the difference between a system you trust and a system you hope works. Every logged field has a specific operational use case — prompt versions let you attribute a quality regression to a specific prompt change, latency flags UX regressions, guardrail frequency reveals misuse patterns, `revision_attempted` frequency reveals how often the critic loop is doing real work, and eval score trends reveal prompt drift before users notice it. Cost tracking is implemented but currently always reports $0.00 — `OpenAIClient` doesn't yet surface token usage (a documented, non-blocking limitation).

---

## 9. Prompt Governance Architecture

**What this shows:** Every LLM-facing prompt is a versioned file on disk, not a hardcoded string — this is what makes prompt iteration safe and auditable (decision D020 in `docs/12_DECISION_LOG.md`).

```mermaid
flowchart TD
    subgraph Files ["Prompt Files — src/prompts/<category>/<version>"]
        F1["discovery/v1.md"]
        F2["recommendation/v1.md"]
        F3["path_planning/v1.md"]
        F4["evaluation/rascef_v1.md"]
        F5["guardrail/v1.yaml"]
        F6["input_guardrail/v1.yaml"]
    end

    LOADER["Prompt Loader\nsrc/services/prompt_loader.py\nload_prompt() / load_ruleset()\nfunctools.lru_cache, path resolved\nfrom the loader's own file location"]

    subgraph Agents ["Agents"]
        A1["Discovery Agent"]
        A2["Recommendation Agent"]
        A3["Path Planning Agent"]
        A4["Evaluation Agent\n(RASCEF judge)"]
        A5["Guardrail Agent\n(rule-based, no LLM)"]
        A6["Input Guardrail Agent\n(rule-based, no LLM)"]
    end

    LLM["OpenAI LLMs\ngpt-4o-mini generation\ngpt-4o evaluation judge"]
    META["config.prompt_version_metadata()\nAttached to every orchestrator result,\nobservability log row, and LangSmith trace"]

    F1 --> LOADER --> A1 --> LLM
    F2 --> LOADER --> A2 --> LLM
    F3 --> LOADER --> A3 --> LLM
    F4 --> LOADER --> A4 --> LLM
    F5 --> LOADER --> A5
    F6 --> LOADER --> A6

    A1 & A2 & A3 & A4 & A5 & A6 --> META
```

**Active versions today:** `discovery_v1`, `recommendation_v1`, `path_planning_v1`, `rascef_v1` (evaluation), `guardrail_v1`, `input_guardrail_v1`. Each is independently configured via `.env` (`DISCOVERY_PROMPT_VERSION`, `RECOMMENDATION_PROMPT_VERSION`, `PATH_PLANNING_PROMPT_VERSION`, `EVALUATION_PROMPT_VERSION`, `GUARDRAIL_RULESET_VERSION`, `INPUT_GUARDRAIL_RULESET_VERSION`) — bumping a prompt to a new version means adding a new file and changing one env var, no code change, and the previous version stays on disk for comparison or rollback.

**Why this matters for the capstone:** Prompt governance is what separates "I tuned a prompt until it worked" from "I can prove which prompt version produced which response, and roll back safely." The version tags aren't just logged — they're attached to every LangSmith trace, so a reviewer can filter by prompt version and see exactly how output quality changed between iterations.

---

## 10. Deployment and Environment Diagram

**What this shows:** How the development environment is structured, what secrets are managed, and which external services the app depends on.

```mermaid
flowchart TD
    DEV["Developer Machine\nWindows 11"]

    subgraph Local ["Local Environment"]
        WIN[".venv_win\nPython venv for Windows development\nAll dependencies installed here"]
        LIN[".venv_linux\nReserved for Linux / WSL experiments\nNot used in active dev"]
        ENV[".env file\nAPI keys and config\nNever committed to git"]
        GIT[".gitignore\nExcludes .venv_win, .venv_linux, .env, data/memory.db"]
    end

    APP["Streamlit App\nlocalhost:8501\nsrc/app.py"]
    DB["SQLite Database\ndata/memory.db\nLocal only"]

    subgraph External ["External APIs"]
        OAI["OpenAI API\nGPT-4o-mini for generation\ntext-embedding-3-small for vectors\nGPT-4o optional for evaluation"]
        PCC["Pinecone Cloud\nVector index\nCareer, major, college embeddings"]
    end

    DEV --> Local
    WIN --> APP
    ENV --> APP
    APP --> DB
    APP --> OAI
    APP --> PCC
```

**Environment notes:**
- `.venv_win` is the active virtual environment for Windows development — activate with `.venv_win\Scripts\activate`
- `.venv_linux` is reserved for future Linux or WSL work — kept separate to avoid dependency conflicts
- `.env` stores `OPENAI_API_KEY`, `PINECONE_API_KEY`, and `PINECONE_INDEX_NAME` — loaded at startup via `python-dotenv`
- `.gitignore` must explicitly exclude `.venv_win/`, `.venv_linux/`, `.env`, and `data/memory.db` before the first commit

---

## 11. Suggested Presentation Story

Use this speaking sequence when presenting the diagrams. Each step maps to one diagram above.

**Step 1 — Open with the product problem** *(no diagram needed)*
> "High school students face major decisions about careers and college with very little personalized support. School counselors are stretched across hundreds of students. Career quizzes give generic results. PathFinder AI is a conversational AI counselor that meets students where they are."

**Step 2 — Show the system architecture** *(Diagram 2)*
> "Here is the full system. A student types a message into the Streamlit chat interface. The Orchestrator takes over — it loads the student's memory, calls the right agents, retrieves relevant knowledge, checks the response for safety, scores it for quality, and logs everything. The student only sees the final, grounded response."

**Step 3 — Show the RAG pipeline** *(Diagram 4)*
> "The knowledge base contains curated careers, majors, and college pathways. At setup, every document is embedded using OpenAI and stored in Pinecone. At runtime, the student's interests and question are embedded and used to search Pinecone semantically. The top results are injected into the prompt — so every recommendation is grounded in real data, not hallucination."

**Step 4 — Show the memory model** *(Diagram 5)*
> "Memory is what transforms a one-time chatbot into a persistent counselor. The student profile evolves across sessions — interests, GPA, and favorite careers are updated incrementally. A returning student is recognized by name, greeted with context, and never asked to repeat themselves."

**Step 5 — Show guardrails, evaluation, and the revision loop** *(Diagrams 2 and 7)*
> "Every message is checked twice: an input guardrail flags profanity, frustration, or prompt-injection attempts before the student's message is even processed, and an output guardrail catches unsafe claims after generation — no admission guarantees, no fabricated salary figures, no protected-attribute bias. Evaluation scoring gives each response a RASCEF quality score across six dimensions — Relevance, Accuracy, Safety, Completeness, Explainability, Fairness. If the score comes in below 24 out of 30, the system automatically regenerates the response once and re-checks it — a critic/revision loop, capped at a single retry, so quality control is not just a report card, it's a second chance."

**Step 6 — Show prompt governance** *(Diagram 9)*
> "Every prompt this system sends to an LLM lives in a versioned file, not a hardcoded string. That means every response can be traced back to the exact prompt version that produced it, prompts can be improved without touching code, and a bad version can be rolled back instantly."

**Step 7 — Show observability, feedback, and cost** *(Diagram 8)*
> "Every turn is logged — model, latency, retrieved document count, guardrail flags, evaluation score, and prompt versions. Students can also rate any response with a thumbs up or down, linked directly to that log row. This is how you run an AI system responsibly — not by hoping it works, but by measuring it and listening to feedback."

**Step 8 — Close with the capstone framing** *(no diagram needed)*
> "This is not a chatbot. It is a multi-agent AI system with RAG, memory, layered guardrails, LLM-as-judge evaluation with an automatic revision loop, governed and versioned prompts, observability, and human-in-the-loop feedback — demonstrated through a real use case that matters to real students."

---

## 12. Diagram Usage Notes

### Where Each Diagram Belongs

| Diagram | BRD / PRD | Architecture Doc | Presentation | README | Demo Walkthrough |
|---|---|---|---|---|---|
| 2. High-Level Architecture | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3. Sequence Diagram | | ✓ | ✓ | | ✓ |
| 4. RAG Pipeline | | ✓ | ✓ | | ✓ |
| 5. Memory Model | | ✓ | ✓ | | |
| 6. Agent Responsibilities | | ✓ | ✓ | | |
| 7. Guardrail and Evaluation | ✓ | ✓ | ✓ | | |
| 8. Observability and Cost | | ✓ | ✓ | | ✓ |
| 9. Prompt Governance Architecture | | ✓ | ✓ | ✓ | |
| 10. Deployment / Environment | | | | ✓ | |

### How to Render These Diagrams

Mermaid diagrams in this file can be rendered using any of the following:

- **GitHub** — Mermaid is natively rendered in `.md` files on GitHub
- **VS Code** — Install the "Markdown Preview Mermaid Support" extension; use `Ctrl+Shift+V` to preview
- **Mermaid Live Editor** — Paste diagram code at `mermaid.live` for instant rendering and export
- **Notion** — Paste as a code block with language set to `mermaid`
- **Obsidian** — Native Mermaid support in preview mode
- **Docusaurus / MkDocs** — Both support Mermaid with a plugin; useful if docs are published

### Diagram Maintenance

- Update diagrams when the architecture changes — stale diagrams are worse than no diagrams
- The sequence diagram (Section 3) and the guardrail flow (Section 7) are most likely to evolve as implementation details are finalized
- The memory model diagram (Section 5) should stay in sync with `src/infrastructure/sqlite_client.py`'s schema (`create_tables()` and `_OBSERVABILITY_LOG_ADDITIVE_COLUMNS`)
- The prompt governance diagram (Section 9) should stay in sync with `config.prompt_version_metadata()` whenever a new prompt category is added
- Diagram source lives here in `docs/08_Diagrams.md` — treat it as the single source of truth for visual architecture
