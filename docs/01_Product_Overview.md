# PathFinder AI — Product Overview (PRFAQ)

## Press Release

### PathFinder AI helps high school students discover careers they never knew existed.

Today, PathFinder AI announced a new AI-powered career counselor designed to help high school students explore careers, college majors, and educational pathways through natural conversation.

For many students, career planning comes down to a single meeting with an overextended school counselor or a generic personality quiz that offers little more than a label. By the time students realize how their academic choices affect future opportunities, it is often too late to make meaningful adjustments.

PathFinder AI was built to change that.

Instead of asking students to complete a static assessment, PathFinder AI starts with a conversation. Students can talk about their interests, strengths, hobbies, and goals in their own words. The system asks thoughtful follow-up questions and recommends career paths, college majors, and schools that align with the student's interests and academic profile.

For example, a student might say:

> *"I like gaming and I'm pretty good at math, but I have no idea what I should major in."*

Rather than assigning a personality type, PathFinder AI explores the student's interests and recommends several career directions—such as game development, cybersecurity, data science, or software engineering—explaining why each fits, what education it requires, and what the student can do next to move toward that goal.

Every recommendation is grounded in a curated knowledge base of careers, majors, colleges, and interests rather than relying solely on an AI model's memory. That knowledge base is intentionally a starting point, not a ceiling — it's built to keep growing as more careers, majors, and schools are added, without changing how the system works. When discussing college options, the system presents schools as **Reach**, **Target**, or **Likely** based on the student's academic profile, helping students set realistic expectations without closing doors or making guarantees.

Unlike traditional career tools, PathFinder AI also remembers previous conversations. Students can return weeks later and continue exploring without repeating their interests or starting from scratch.

> "Students deserve guidance that's both encouraging and realistic," said Anurag Kabra, creator of PathFinder AI. "Too many tools either oversimplify career exploration or make recommendations without context. PathFinder AI is designed to have honest conversations that help students discover opportunities they may never have considered."

PathFinder AI is currently available as a working prototype featuring conversational career guidance, persistent student profiles, a curated knowledge base, and built-in safeguards designed to keep recommendations accurate, transparent, and grounded in available evidence.

---

## Frequently Asked Questions

### Customer FAQ

#### Who is PathFinder AI for?

PathFinder AI is designed primarily for high school students in grades 9–12 who are exploring careers, choosing college majors, or planning for life after graduation. It can also help parents begin productive conversations about future planning and support school counselors by providing students with a starting point before one-on-one meetings.

#### How is this different from a career quiz?

Traditional career quizzes typically classify students into broad personality categories and stop there.

PathFinder AI has an ongoing conversation. It learns about each student's interests, asks follow-up questions, remembers previous discussions, and recommends specific careers, majors, and college pathways with explanations tailored to the individual.

#### Will my GPA limit the recommendations?

No.

PathFinder AI does not tell students that a goal is impossible. Instead, it presents colleges as **Reach**, **Target**, or **Likely** based on the student's academic profile, helping students understand their options while encouraging them to improve where possible.

#### Does it remember previous conversations?

Yes.

PathFinder AI maintains a persistent student profile so returning users can continue exploring without repeating information they've already shared.

#### Can it help with scholarships, financial aid, or college essays?

Not yet.

The current version focuses on career exploration, major selection, and college pathway recommendations. Scholarship search, financial aid guidance, essay review, and application management are planned as future areas of expansion.

#### Is my information secure?

The current prototype identifies returning students by name only and does not include a production authentication system.

This approach is appropriate for demonstration purposes but would be replaced with secure authentication and student privacy protections before any production deployment.

---

### Internal FAQ

#### Why use a multi-agent architecture instead of a single prompt?

Career advising involves multiple independent tasks: understanding the student, retrieving reliable information, generating recommendations, planning actionable next steps, validating responses, and evaluating output quality.

Separating these responsibilities into specialized agents creates a system that is easier to test, debug, improve, and monitor than relying on one large prompt.

#### Why use a curated knowledge base instead of relying only on the language model?

Career and college guidance requires factual accuracy.

Every recommendation is grounded in a curated knowledge base retrieved through Pinecone, allowing recommendations to be traced back to verified information. If relevant information cannot be retrieved, the system acknowledges the limitation rather than generating unsupported advice.

#### Why focus only on career discovery?

Building an excellent career discovery experience was intentionally prioritized over supporting every aspect of the college application process.

Adding scholarship search, essay coaching, and application tracking before the core advising experience was mature would have increased complexity without delivering a better student experience. These capabilities are natural extensions once the foundation is established.

#### What is the biggest technical limitation today?

Verification today is uneven, not absent. Intent classification — deciding what kind of turn a message is — has a real automated test: a golden dataset scored with a confusion matrix and explicit pass/fail thresholds, run against the live API. Everything else in the pipeline (recommendations, guardrails, evaluation, the full end-to-end flow) is verified through manual, eyeball-style scripts run against the live OpenAI and Pinecone APIs — thorough, but not automated or threshold-gated, and not wired into a CI pipeline that blocks a bad merge.

Extending that same rigor — automated, metric-based, with a clear pass/fail bar — to the rest of the system would be a priority before deploying at larger scale.

#### What does success look like?

A successful interaction ends with a student discovering career paths they had never previously considered while receiving guidance that reflects both their interests and academic profile.

Parents and school counselors should be able to review the conversation and feel confident that the recommendations are thoughtful, realistic, transparent, and actionable.
