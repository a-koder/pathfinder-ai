# PathFinder AI — Business Requirements Document (BRD)

## Purpose

This document defines the business goals, stakeholder needs, and high-level constraints that PathFinder AI must satisfy at the MVP level.

---

## Business Goals

1. Deliver a working AI counselor prototype that demonstrates end-to-end value in 1–2 weeks
2. Show that conversational AI can meaningfully improve career and college discovery for high school students
3. Prove that persistent memory transforms a one-time chatbot into a longitudinal counseling tool
4. Produce a capstone artifact that is presentable to academic evaluators and potential stakeholders

---

## Stakeholders

| Stakeholder | Role | Primary Need |
|---|---|---|
| High school student | End user | Career and major discovery; realistic college guidance |
| Parent | Secondary user | Confidence that their child is getting structured guidance |
| School counselor | Secondary user | Scalable, consistent support for students |
| Capstone evaluator | Reviewer | Clear demonstration of AI/system design and working prototype |

---

## Business Requirements

### BR-01: Conversational Experience
The system must allow students to explore career and academic topics through natural, open-ended conversation — not rigid forms or quizzes.

### BR-02: Student Profile Extraction
The system must extract key student attributes from conversation: interests, strengths, dislikes, GPA or academic standing, and grade level.

### BR-03: Career Discovery
The system must surface careers that students may not have considered, grounded in the student's stated interests and profile.

### BR-04: Major and College Pathway Guidance
The system must connect careers to related college majors and provide basic guidance on realistic college pathways given the student's GPA.

### BR-05: Persistent Memory
The system must remember prior conversations so returning students do not need to repeat their context.

### BR-06: GPA-Aware Recommendations
Guidance on college options must factor in the student's academic profile. Recommendations must be honest and constructive, not aspirational-only.

### BR-07: Local Knowledge Base
Career, major, and college data must be stored locally as curated files — no dependency on real-time external APIs in the MVP.

### BR-08: Simple, Accessible UI
The interface must be usable by a high school student with no technical background. A simple chat interface is sufficient.

---

## Constraints

- **Timeline:** 1–2 week capstone — scope must remain achievable
- **Team size:** Single developer (capstone project)
- **Infrastructure:** Local-first; no cloud deployment required for MVP
- **Data:** Curated local files only — no live API calls to college databases
- **Cost:** Minimize external API costs; use efficient LLM prompting

---

## Assumptions

- Students are willing to share basic academic profile information (GPA, grade level, interests) in conversation
- A curated local knowledge base is sufficient to demonstrate value without real-time data
- SQLite is adequate for persistent memory at prototype scale
- The Claude API (or equivalent LLM API) is available for conversational reasoning

---

## Out of Scope (Business)

- Scholarship matching and financial aid guidance
- Parent-facing portal or counselor dashboard
- Real-time integration with college admission databases
- SAT/ACT score analysis or prediction
- College application tracking or deadline management
- Resume or personal statement writing tools
