# PathFinder AI — Product Requirements Document (PRD)

## Overview

PathFinder AI is a chat-first AI counselor for high school students. This PRD defines the product features, user stories, and acceptance criteria for the MVP.

---

## User Personas

### Persona 1 — The Undecided Student
- Name: Alex, Grade 11
- Situation: Likes science and gaming but has no idea what to major in
- Need: Someone to help them explore options without judgment
- Pain point: Every adult just says "follow your passion" with no concrete direction

### Persona 2 — The Anxious Applicant
- Name: Priya, Grade 12
- Situation: Wants to apply to college but doesn't know if her 3.2 GPA limits her options
- Need: Honest, realistic guidance on colleges and majors that fit her profile
- Pain point: College ranking sites don't tell her what's actually realistic for her

### Persona 3 — The Parent
- Name: David, parent of a Grade 10 student
- Situation: Wants his child to start thinking about direction now
- Need: A structured tool his child can use independently
- Pain point: No time to research this himself; counselor appointments are rare

---

## Feature List

### F-01: Chat Interface
- Students interact through a conversational text chat
- Interface is clean and distraction-free
- Powered by Streamlit

### F-02: Student Profile Extraction
- System extracts the following from natural conversation:
  - Interests and hobbies
  - Academic strengths and weaknesses
  - GPA or self-reported academic standing
  - Grade level (9–12)
  - Dislikes or subjects to avoid
- Profile is stored and updated across sessions

### F-03: Career Discovery
- System suggests careers relevant to student interests
- Careers include non-obvious options beyond common professional roles
- Each suggestion includes: career name, brief description, why it fits the student
- Minimum 3 career suggestions per session

### F-04: Major Recommendations
- System connects suggested careers to college majors
- Each major includes: major name, what students study, typical career outcomes

### F-05: College Pathway Guidance
- System provides basic college guidance based on student GPA
- Guidance is segmented (e.g., highly selective / selective / accessible)
- Guidance is constructive — not dismissive of lower GPAs

### F-06: Persistent Memory
- System saves student profile and conversation history to SQLite
- Returning students are recognized and greeted with context
- Memory includes: profile fields, past recommendations, conversation summaries

### F-07: Roadmap Summary
- At the end of a session (or on request), system generates a summary:
  - Student profile snapshot
  - Top career directions
  - Recommended majors
  - Next steps for the student
- Summary is displayable in the chat or as a text block

### F-08: Basic Evaluation Checks
- System can self-check whether a response is grounded and reasonable
- Flagging logic for out-of-scope questions (e.g., scholarship queries)

---

## User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| US-01 | Student | Chat freely about my interests | The system understands me without a rigid form |
| US-02 | Student | Get career suggestions I hadn't considered | I can discover paths beyond doctor/lawyer/engineer |
| US-03 | Student | Know what major connects to a career | I understand what to study in college |
| US-04 | Student | Get honest college guidance based on my GPA | I apply to realistic schools, not just reach schools |
| US-05 | Student | Return to the app and pick up where I left off | I don't repeat myself every session |
| US-06 | Student | Get a summary of my roadmap | I have something concrete to share with parents or counselors |
| US-07 | Parent | Have my child use a guided AI tool | They get structured direction without waiting for a counselor appointment |
| US-08 | Counselor | Know students have a self-service starting point | I can focus my limited time on deeper conversations |

---

## Acceptance Criteria

### Chat Interface
- [ ] Student can type a message and receive a response within 5 seconds
- [ ] Chat history is visible in the session
- [ ] UI works on a standard laptop browser

### Profile Extraction
- [ ] System correctly identifies at least 3 profile fields from a 5-message conversation
- [ ] Profile is saved to SQLite after each session

### Career Recommendations
- [ ] System returns at least 3 relevant careers with descriptions
- [ ] Careers are contextually relevant to stated interests

### Memory
- [ ] Returning user is greeted with their name and prior context
- [ ] No repeated profile questions if already answered in a prior session

### Roadmap Summary
- [ ] Summary includes at minimum: interests, top careers, top majors, one next step
- [ ] Summary is readable without system context

---

## Out of Scope (Product)

- Scholarship and financial aid features
- Parent-facing login or dashboard
- Counselor-facing student overview
- Live college admission data or acceptance rate APIs
- SAT/ACT analysis
- Application deadline tracking
- Essay or resume tools
