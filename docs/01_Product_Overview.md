# PathFinder AI — Product Overview (PRFAQ)

## Press Release

**PathFinder AI helps high school students find careers they didn't know existed**

A new AI counselor called PathFinder AI is now available to help high school students figure out what to do with their lives, one honest conversation at a time. Instead of a career quiz that spits out a generic label like "Investigative type," PathFinder AI talks with a student about what they actually like, then surfaces careers, majors, and college pathways they may never have considered, grounded in real data rather than guesswork.

Most students only get one shot at real career guidance: a rushed meeting with a school counselor who's juggling 400+ other students. Career aptitude tests hand back a label and nothing else. And by the time GPA starts to matter for college planning, it's often application season already, too late to course-correct. PathFinder AI is built to close that gap by being available whenever a student wants to talk, and by remembering the conversation so a student never has to start over.

A student opens the app, types their name, and just talks: "I like gaming and I'm decent at math, but I have no idea what I'd major in." PathFinder AI asks a follow-up or two, then comes back with three or four real career directions grounded in a curated knowledge base of 73 careers, 47 majors, and 45 colleges, each with an honest explanation of why it fits, what it opens up, and a next step the student can actually take this semester. If GPA comes up, the guidance is framed as reach, target, or likely, never a guarantee. If the student comes back next week, PathFinder AI remembers them and picks up where they left off.

"I built this because I kept hearing the same thing from students: nobody ever tells them what's realistic *and* what's possible at the same time," said Anurag Kabra, the project's creator. "Most tools pick one or the other. This one tries to do both, honestly."

PathFinder AI is available today as a working prototype, with a persistent memory system, a curated career knowledge base, and built-in safety checks that keep the system honest about GPA, admissions, and outcomes.

---

## Frequently Asked Questions

### Customer FAQ

**Who is this for?**
High school students, primarily grades 9 through 12, who are unsure what to do after graduation. It's also useful for parents who want their kid to have somewhere to start, and school counselors who are stretched too thin to give every student the time they need.

**What makes this different from a career quiz?**
A quiz gives you a label. PathFinder AI gives you a conversation. It asks what you're actually into, remembers what you tell it, and comes back with specific careers and majors, not personality types. And it's honest about GPA and realistic options instead of pretending every path is equally open to everyone.

**Will it tell me I can't do something because of my GPA?**
No. It frames college options as reach, target, or likely based on your academic profile, but it never dismisses a lower GPA or tells you something is impossible. The goal is honest framing, not gatekeeping.

**Does it remember me if I come back later?**
Yes. Your profile, interests, and past conversation carry over, so you don't have to repeat yourself every time you open the app.

**Can it help me with scholarships or my college essay?**
Not yet. This version focuses specifically on career discovery, major guidance, and GPA-aware college pathway suggestions. Scholarships, financial aid, essay review, and application tracking are explicitly out of scope for now.

**Is my information safe?**
The prototype recognizes returning students by name only, with no password or account system. That's fine for a demo, but it's not how a production version handling real student data would work; a real deployment would need proper authentication before it could be used with actual students.

---

### Internal FAQ

**Why build this as a multi-agent system instead of one big prompt?**
Because career guidance actually breaks down into distinct jobs: understanding the student, retrieving relevant knowledge, generating recommendations, planning next steps, checking for unsafe claims, and scoring quality. Splitting those into separate, testable components with defined contracts makes the system's behavior traceable and its failures debuggable in a way that one giant prompt never is.

**Why not just use the model's own training data for career and college info?**
Because it hallucinates, and the stakes here are a teenager's actual life decisions. Every recommendation is grounded in a curated knowledge base retrieved through Pinecone, so a recommendation can always be traced back to a real document. If retrieval comes back empty, the system says so rather than making something up.

**What stopped this from being scholarships, applications, and essays too?**
Time and focus, mostly. The team judged that career and major discovery, done well, was already a full scope for a first version, and that bolting on scholarships or essay review without doing them properly would weaken the core experience rather than strengthen it. Those are the natural next things to build once this foundation is solid.

**What's the biggest technical risk in the current version?**
There's no automated test suite yet; verification today happens through a set of manual scripts run against the live OpenAI and Pinecone APIs. That's a real gap for anything beyond a prototype, and it's the first thing that would need to change before this went further.

**What does success look like for the next version?**
A student has a real conversation, walks away with career directions they hadn't thought of, and the guidance holds up against their actual GPA and interests, not a generic template. If a counselor or parent looked at the transcript afterward, they should trust it, not wince at it.
