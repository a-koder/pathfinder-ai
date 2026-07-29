---
marp: true
theme: gaia
paginate: true
size: 16:9
---

<!--
HOW TO USE THIS FILE - this file is two things in one:
1. A Marp slide deck (slides 1-13 below). Open it in VS Code with the free "Marp for VS
   Code" extension for a live preview, or render it with marp-cli:
   npx @marp-team/marp-cli docs/14_Presentation_Deck.md --pptx  (also supports --pdf, --html)
   It's still plain markdown underneath - edit it in any text editor.
2. A reference appendix (after slide 13) with the storyboard, demo script, visual-asset
   map, and a recommendation on cutting slides for time - clearly marked "Appendix - not
   for the 10-minute talk," meant to be skipped past when actually presenting.
Grounded in the actual pathfinder-ai codebase as of 2026.07.28 - no invented features.
Screenshots referenced below are real, captured live and saved to docs/assets/deck/.
-->

<!-- _class: lead -->

# 🚀 PathFinder AI
### Explore Possibilities. Discover Your Path.

**A Multi-Agent AI Career Counselor for High School Students**

Anurag Kabra · Capstone Project

<!--
Speaker notes (30-45s):
Hi, I'm Anurag. Over the next 10 minutes I'll show you PathFinder AI — a career and college
guidance counselor built as a multi-agent AI system, not a single prompt in a chat window.
It's for high school students who don't know what careers exist beyond doctor, lawyer, or
engineer, and it's built to demonstrate real production AI patterns: memory, retrieval,
safety guardrails, automated quality evaluation, and observability, all working together.
Let's start with the problem it's solving.
Transition: "So why does a student need this in the first place?"
-->

---

# The Problem

- School counselors: **400+ students each** on average — no room for 1:1 guidance
- Most students don't know careers exist beyond the obvious ones
- Career aptitude quizzes give generic results with **no follow-through**
- GPA reality often goes unaddressed until application season — too late to act on

**Personalized career guidance doesn't scale with people alone.**

<!--
Speaker notes (40-50s):
These aren't abstract numbers — a 400-to-1 counselor ratio means most students get maybe
one short conversation a year about their future, if that. Career quizzes hand back a
generic label like "Investigative type" and nothing actionable. And GPA-aware guidance —
the thing that actually determines what's realistic — usually shows up for the first time
during application season, when it's too late to course-correct. The gap isn't information,
it's personalized, ongoing conversation. That's exactly what an AI counselor can offer if
it's built right — which is the point of the rest of this talk.
Transition: "So what did we actually build?"
-->

---

# The Solution

**PathFinder AI** — a chat-first AI counselor that:

- **Remembers** each student across visits, not just within one session
- **Grounds** every recommendation in a real, curated knowledge base
- **Checks its own answers** for safety and quality before responding
- Turns "what fits me?" into a **concrete next-step roadmap**

10 specialized agents. One conversation.

<!--
Speaker notes (40-50s):
PathFinder AI is chat-first — a student just talks about what they're into. Under the hood,
it's not one prompt; it's 10 specialized agents coordinating on every single message: one
extracts profile facts, one retrieves grounded knowledge, one generates recommendations, one
builds a roadmap, two run safety/quality checks, and more. The student never sees that
complexity — they just see a counselor that remembers them, doesn't make things up, and
gives them something concrete to do next. Let's look at how that's actually built.
Transition: "Here's the architecture behind that."
-->

---

![bg right:38%](assets/deck/10_architecture_at_a_glance.jpg)

## Architecture, End to End

Clean Architecture, 6 layers:

**Presentation → Agents → Services → Repositories → Infrastructure → Domain**

- SOLID — every dependency injected, nothing hardwired
- Agents never touch a database or SDK directly

<!--
Speaker notes (40-50s):
This is a production-style layered architecture, not a script. The Streamlit UI knows
nothing about OpenAI or SQLite — it only talks to an Orchestrator. Agents depend on
service abstractions injected at construction time, so an agent's LLM call could be swapped
from GPT-4o-mini to another provider without touching agent code. That's dependency
inversion in practice, not just a slide term. On the right is the actual turn-by-turn flow —
every one of the 10 agents in call order, which is what we'll walk through next.
Transition: "Let's zoom into what happens on a single message."
-->

---

# One Conversation Turn

**Input Guardrail → Memory Load → Discovery ‖ Retrieval → Recommendation → Path Planning → Guardrail → Evaluation → (retry once, if needed) → Observability → Memory Save**

- Discovery and Retrieval run **concurrently** — independent work, no wasted latency
- A low quality score triggers **one** automatic regenerate-and-recheck, never more

<!--
Speaker notes (35-45s):
Every message goes through this exact sequence. Discovery (extracting interests, GPA,
grade level) and Retrieval (semantic search) don't depend on each other, so they run on
separate threads concurrently — shaving real latency off every turn for zero behavior
change. If the quality score comes back low, the system regenerates once automatically —
a bounded critic loop, not an infinite retry. This sequence is what makes PathFinder AI
verifiably multi-agent, not one big prompt with section headers.
Transition: "None of this matters if the recommendations aren't grounded in something real."
-->

---

## Grounded, Not Guessed

- **170 curated documents**: 54 careers, 44 majors, 27 colleges, 45 interest areas
- Embedded with OpenAI (`text-embedding-3-small`), searched via **Pinecone**
- Metadata-filtered by `doc_type` and `gpa_band` — one index, one namespace
- Falls back to local tag search if Pinecone is unreachable

**Every recommendation traces to a real document — never invented.**

<!--
Speaker notes (35-45s):
This is the RAG layer, and it's the difference between a career counselor and a career
hallucinator. Every career, major, and college in this system comes from a curated
dataset — not the model's training data. A student's message gets embedded and searched
semantically against that dataset, filtered by document type, or by GPA band when we're
talking about colleges. If Pinecone is ever unreachable, it degrades gracefully to a local
tag-based search instead of failing outright. Nothing gets recommended that isn't backed
by an actual document.
Transition: "Grounding handles accuracy — now let's talk about safety."
-->

---

![bg right:38%](assets/deck/08_scenario2_guardrail_note_amber.jpg)

## Responsible AI, By Design

- **Input guardrails**: profanity, frustration, prompt-injection — detect only
- **Output guardrails**: 10 rules — no admission/salary guarantees, no bias
- **RASCEF**: 6-dimension LLM-as-judge score, every turn
- **Revision loop**: auto-regenerates once if quality falls short

<!--
Speaker notes (45-55s):
Safety runs twice — before generation and after. Before: a rule-based check flags
profanity, frustration, or prompt-injection attempts, purely for visibility, it never
blocks the student. After: 10 rule-based flags catch things like admission guarantees,
salary promises, or missing GPA context before college advice — you can see that exact
note live on the right, flagged in amber. Then RASCEF — Relevance, Accuracy, Safety,
Completeness, Explainability, Fairness — scores the response out of 30 using GPT-4o as a
judge, with a rule-based fallback if that call fails. Below 24 out of 30, it regenerates
once automatically before the student ever sees it.
Transition: "All of that needs to be traceable — that's where prompt governance and
observability come in."
-->

---

![bg right:38%](assets/deck/06_rascef_evaluation_score.jpg)

## Governed and Observed

- Every prompt is a **versioned file**, never hardcoded
- Swap versions via one env var — no code change, instant rollback
- Every turn logs latency, flags, score, and **real per-model cost**
- Optional LangSmith tracing; 👍/👎 tied to the exact log row

<!--
Speaker notes (40-50s):
Two things reviewers usually ask about: can you explain why a response changed, and what
does this actually cost? Every prompt — discovery, recommendation, path planning, the
RASCEF judge — lives in a versioned file, so a prompt edit is a new file, not an
overwritten one, and it's fully rollback-able. And on the right, that's a real per-turn
cost breakdown — not a placeholder. It sums actual token usage across every model called
that turn, including a retry, broken down per model. Every turn also logs to SQLite, and a
student's thumbs up or down links straight back to that exact log row.
Transition: "So what does that actually feel like for a student?"
-->

---

![bg right:38%](assets/deck/09_scenario3_returning_student_memory.jpg)

## What Makes It Feel Like a Counselor

- **Memory** — returning students pick up right where they left off
- **Choice-aware roadmaps** — anchored to what the student actually picked
- **Human feedback** — 👍/👎 on every response
- **Grounded picks** — with fun facts and a future outlook

<!--
Speaker notes (35-45s):
This is the payoff of everything so far. On the right — that's a real returning student.
Same name, new session, and PathFinder AI already knows their interests and picks the
conversation back up. The roadmap step is similarly responsive: if a student answers "which
of these resonates with you" by naming one of the options, the roadmap is built around
that specific choice — not just whichever option an internal priority order would have
picked. That's the difference between a static recommender and something that actually
listens.
Transition: "Before the demo, here's the plain list of AI concepts all of that represents."
-->

---

## AI Concepts, Named

- **Multi-agent orchestration** — 10 agents, one central Orchestrator, no peer-to-peer agent calls
- **RAG** (Retrieval-Augmented Generation) — Pinecone + OpenAI embeddings ground every claim
- **Persistent memory** — SQLite profile + conversation history survive across sessions
- **Guardrails** — rule-based input/output safety checks, every single turn
- **Evaluation** — RASCEF, 6-dimension LLM-as-judge scoring, bounded auto-retry
- **Observability & cost tracking** — per-call tokens, latency, real cost, all logged
- **Prompt engineering & versioning** — prompts as versioned files, swappable via env var
- **Structured outputs** — Pydantic-typed profile, retrieval metadata throughout

*Not used (yet): peer-to-peer agent-to-agent messaging (e.g. an A2A protocol) — coordination is intentionally orchestrator-hub today. See "What's Next" for when that changes.*

<!--
Speaker notes (30-40s):
Everything in the last five slides maps to a named pattern, so here's the checklist plainly:
multi-agent orchestration, RAG, memory, guardrails, evaluation, observability, prompt
versioning, structured outputs. One honest clarification since it's a common question —
agents don't message each other directly. Everything is coordinated through one central
Orchestrator, hub-and-spoke, not a peer-to-peer agent-to-agent protocol. That's deliberate,
not a gap — I'd only add real A2A-style messaging if a genuine cross-system need for it
showed up, which is covered on the roadmap slide later.
Transition: "Let's stop talking about it and just show you."
-->

---

<!-- _class: lead -->

# Live Demo

1. **"I like gaming, storytelling, and technology."**
2. **"I want college recommendations but don't know my GPA."**
3. A returning student, remembered.

<!--
Speaker notes (5-10s, then switch to the browser):
Three quick scenarios: a fresh discovery conversation, a guardrail firing live on a
GPA-sensitive question, and a returning student being recognized instantly. Full script
for each is in the appendix at the end of this file. Switch to the browser now.
Transition (after demo): "Let's close with where this stands and what's next."
-->

---

# Where It Stands

- Verified with **13 scripted end-to-end/integration tests** across every agent
- RASCEF pass threshold: **24/30** — auto-retry below that, always logged either way
- **29 documented architecture decisions** (`D001`–`D029`), each with alternatives considered
- Known gap, stated plainly: no automated `pytest` suite yet — verification is manual-script-based

<!--
Speaker notes (30-40s):
A few honest numbers instead of a vibe: 13 scripted tests cover the full workflow, the
revision loop, human feedback, prompt versioning, and observability, run against live
APIs rather than mocks. Every architecture and product decision — 29 of them — is logged
with what alternative was considered and why it lost, which is what makes this auditable
rather than "trust me." And I'll say the quiet part out loud: there's no automated pytest
suite yet, verification today is manual-script-based. That's a real gap, not glossed over.
Transition: "Which is a good bridge to what's actually next."
-->

---

# What's Next

- **MCP-based integrations** — scholarships, colleges, and course providers as callable tools
- **Provider-agnostic LLM support** — compare OpenAI, Anthropic, etc. without touching agent code
- **Deeper LangSmith usage** — dataset-based eval against golden scenarios, not just live tracing
- **Agent-to-agent (A2A) interop** — only at a real cross-system boundary, if one shows up

Full detail (plus career market data, an observability dashboard, and richer HITL): `docs/19_Future_Vision.md`

<!--
Speaker notes (25-35s):
None of this is speculative technology — it's the next layer on top of what's already
working. MCP is a natural fit since every external lookup PathFinder AI would need —
scholarships, college data, course catalogs — is exactly the kind of tool-calling MCP is
designed for. Provider-agnostic LLM support and deeper LangSmith usage are both service-layer
extensions of things that already exist, not new architecture. And to be direct about
agent-to-agent protocols like A2A: I'm deliberately not adding peer-to-peer agent messaging
inside this system for its own sake — the orchestrator-hub model is intentional and stays
unless a real cross-system need for it shows up. Full writeup is in the Future Vision doc.
Thank you — happy to take questions.
-->

---

<!-- _class: lead -->

# Appendix
### (reference material — not part of the 10-minute talk)

Storyboard · Visual Asset Map · Demo Script · Slide-Cut Recommendation

---

## Appendix A — Presentation Storyboard

| # | Slide Title | Objective | Key Message |
|---|---|---|---|
| 1 | PathFinder AI (Title) | Open with identity and credibility | This is a real multi-agent AI system, not a chatbot demo |
| 2 | The Problem | Establish the human stakes before any tech | Career guidance doesn't scale with people alone |
| 3 | The Solution | Name what was built, in plain language | One conversation, 10 coordinating agents, memory + grounding + safety |
| 4 | Architecture, End to End | Show engineering discipline | Clean Architecture, SOLID, dependency inversion — not a script |
| 5 | One Conversation Turn | Show the exact agent sequence | Concurrency where safe, one bounded retry, never more |
| 6 | Grounded, Not Guessed | Prove recommendations aren't hallucinated | 170 real documents, semantic search, graceful fallback |
| 7 | Responsible AI, By Design | Address safety head-on | Guardrails run before *and* after generation, plus a self-correcting score |
| 8 | Governed and Observed | Show operational maturity | Versioned prompts, real per-turn cost, full traceability |
| 9 | What Makes It Feel Like a Counselor | Bring it back to the student experience | Memory and choice-aware roadmaps, not a static quiz |
| 10 | AI Concepts, Named | Make the pattern checklist explicit for evaluators | Every pattern named plainly, including what's deliberately not there |
| 11 | Live Demo | Prove it, don't just claim it | Three real scenarios, live |
| 12 | Where It Stands | Build trust with honest numbers | Tested, documented, and honest about the one known gap |
| 13 | What's Next | End forward-looking, not defensive | Realistic next layer, not vague ambition |

---

## Appendix B — Visual Asset Map

| Slide | Existing diagram to reuse | Screenshot (in `docs/assets/deck/`) |
|---|---|---|
| 1. Title | — | `01_welcome_screen.jpg` (optional, if you want the app visible behind the title) |
| 4. Architecture | `docs/04_Architecture.md`'s 6-layer diagram (text block) | `10_architecture_at_a_glance.jpg` |
| 5. Agent Flow | `docs/08_Diagrams.md` → "At a Glance" flowchart | `10_architecture_at_a_glance.jpg` (same image, used again) |
| 6. RAG + Grounding | `docs/08_Diagrams.md` → Section 4, RAG Pipeline Diagram | `05_retrieved_docs_recommendations_profile.jpg` (shows real retrieval scores) |
| 7. Responsible AI | `docs/08_Diagrams.md` → Section 7, Guardrail and Evaluation Flow | `08_scenario2_guardrail_note_amber.jpg` |
| 8. Prompt Governance + Observability | `docs/08_Diagrams.md` → Section 9, Prompt Governance Architecture | `06_rascef_evaluation_score.jpg` |
| 9. Key Capabilities | `docs/08_Diagrams.md` → Section 6, Agent Responsibility Diagram (optional) | `09_scenario3_returning_student_memory.jpg` |
| 10. AI Concepts, Named | `docs/07_Capstone_Mapping_and_Implementation_Plan.md` § 13 (source table for this slide) | — |
| 11. Live Demo | — | `02_scenario1_recommendations.jpg` / `03_scenario1_roadmap_funfacts.jpg` (backup stills if live demo has trouble) |
| 12. Results | `docs/12_DECISION_LOG.md` (point to it, don't screenshot it) | — |

All diagrams referenced above already exist in `docs/08_Diagrams.md` / `docs/04_Architecture.md` — reuse them directly (e.g. re-export the relevant Mermaid block to PNG) rather than redrawing anything.

---

## Appendix C — Demo Script

**Pre-demo setup (do this before you're on stage):**
Run Scenario 1 once, in advance, under a chosen name (e.g. "Morgan"), so that name already has conversation history in the database. During the live talk, Scenario 3 becomes as simple as reloading the page and typing that same name again — instant recall, no waiting for a fresh conversation to build up live. This is exactly how `09_scenario3_returning_student_memory.jpg` was captured.

### Scenario 1 — Discovery from scratch

- **Type:** a fresh student name (e.g. "Jordan"), then: `I like gaming, storytelling, and technology.`
- **Should happen:** 3 grounded recommendations render as side-by-side cards (e.g. Game Design, Game Developer, Narrative Designer), each with "Why it fits," a positive future outlook, and fun facts. A roadmap ("Your Roadmap — \[top pick]") renders below with short/medium/long-term tabs. A green quality badge and "Grounded in N sources" appear above the collapsed Technical Details.
- **Demonstrates:** Discovery Agent (profile extraction), Retrieval Agent + RAG grounding, Recommendation Agent, Path Planning Agent, RASCEF evaluation, the enrichment pass (fun facts/outlook).

### Scenario 2 — Guardrails firing live

- **Type (new/different student name):** `I want college recommendations but don't know my GPA.`
- **Should happen:** College recommendations still render (the system doesn't refuse), but a **"Keep in mind"** caption appears live in the chat — in this exact run it read *"Ask for GPA or provide only broad college pathway categories. Ask for budget preference or provide general cost-awareness language."* — and the quality badge often lands on **Amber** rather than Green, with "Guardrails: Flagged" shown.
- **Demonstrates:** the Guardrail Agent's `missing_gpa_for_college_guidance` (and often `missing_budget_for_affordability_guidance`) flags, the medium-risk "keep in mind" note behavior, and RASCEF scoring something down for incomplete context rather than rubber-stamping it.

### Scenario 3 — Returning student memory

- **Type:** reload the app (or open a fresh tab) and enter the **same name** used in the pre-demo setup (e.g. "Morgan") — do not send a new message yet.
- **Should happen:** the sidebar immediately shows "Welcome back, Morgan" with their remembered interests as a caption; the main chat shows a "Welcome back... restored your last N messages" banner and replays the prior conversation.
- **Demonstrates:** `MemoryAgent`/`ProfileRepository` persistence across sessions, the live profile snapshot in the sidebar, and history restoration — the core "doesn't make the student repeat themselves" pitch from Slide 2/9.

**If you have extra time:** reply to Scenario 1's follow-up question by naming one of the offered recommendations (e.g. "I think the \[X] path resonates most with me") — the next roadmap will show a **"Built around the path you picked"** caption, demonstrating the choice-aware roadmap from Slide 9 concretely instead of just claiming it.

---

## Appendix D — Recommendation: What to Cut or Merge for 10 Minutes

Rough timing at the pacing implied by the speaker notes above: ~8 minutes for slides 1–10 and 12–13, plus a live demo. A careful 3-scenario live demo (with real API latency) realistically needs 2.5–4 minutes, which puts the full 13-slide version at **10.5–12 minutes** — workable, but tight, and API latency on the day is the biggest wildcard.

**If you need to cut something, in this order:**

1. **Merge Slide 4 (Architecture) into Slide 5 (Agent Flow).** They're already telling one story at two zoom levels, and the "At a Glance" diagram (`10_architecture_at_a_glance.jpg`) already unifies both into one visual. Saves ~40–45 seconds with the least narrative loss of any cut available.
2. **Cap the live demo at 2 scenarios, not 3.** Fold Scenario 3 into Scenario 1's natural conclusion — after showing the fresh discovery conversation, just reload and re-enter the same name to show instant recall, instead of treating it as a fully separate scripted scenario. Saves ~30–45 seconds.
3. **Trim Slide 12 (Where It Stands) to its first two bullets only** (testing + RASCEF threshold), moving the decision-log count and the pytest-gap admission into the closing speaker notes as a spoken aside rather than an on-slide bullet.
4. **Cut Slide 10 (AI Concepts, Named) entirely if still over time.** Its content is already implied across slides 4–9; it's a reinforcement aid for evaluators skimming a recording, not new information the live talk depends on.

Applying just #1 and #2 comfortably brings the talk to ~9.5 minutes with room for the inevitable live-demo hiccup — recommended as the default plan rather than something to only fall back on if running long.
