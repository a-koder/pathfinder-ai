import streamlit as st

_GITHUB_URL = "https://github.com/a-koder/pathfinder-ai"
_LINKEDIN_URL = "https://www.linkedin.com/in/a-kabra/"

_GITHUB_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
<path d="M12 .5C5.6.5.5 5.6.5 12c0 5.1 3.3 9.4 7.9 11 .6.1.8-.3.8-.6v-2.1c-3.2.7-3.9-1.5-3.9-1.5-.5-1.3-1.3-1.7-1.3-1.7-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.4 1 .1-.8.4-1.3.8-1.6-2.6-.3-5.3-1.3-5.3-5.8 0-1.3.5-2.3 1.2-3.1-.1-.3-.5-1.6.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0c2.3-1.6 3.3-1.2 3.3-1.2.7 1.6.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.1 0 4.5-2.7 5.5-5.3 5.8.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6 4.6-1.6 7.9-5.9 7.9-11C23.5 5.6 18.4.5 12 .5z"/>
</svg>
"""

_LINKEDIN_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
<path d="M20.5 2h-17A1.5 1.5 0 0 0 2 3.5v17A1.5 1.5 0 0 0 3.5 22h17a1.5 1.5 0 0 0 1.5-1.5v-17A1.5 1.5 0 0 0 20.5 2zM8.3 19H5.5V9h2.8zm-1.4-11.3a1.6 1.6 0 1 1 0-3.2 1.6 1.6 0 0 1 0 3.2zM19 19h-2.8v-4.9c0-1.2 0-2.7-1.6-2.7s-1.9 1.3-1.9 2.6V19h-2.8V9h2.7v1.4h.1a2.9 2.9 0 0 1 2.7-1.5c2.9 0 3.6 1.9 3.6 4.5z"/>
</svg>
"""

_LINK_BUTTON_CSS = """
<style>
.pf-link-row { display: flex; gap: 0.75rem; margin: 0.25rem 0 0.5rem 0; flex-wrap: wrap; }
.pf-link-btn {
    display: inline-flex; align-items: center; gap: 0.5rem;
    padding: 0.45rem 1rem; border-radius: 999px;
    border: 1px solid rgba(128,128,128,0.35);
    text-decoration: none !important; font-weight: 500; font-size: 0.9rem;
    color: inherit; transition: border-color 0.15s ease, background 0.15s ease;
}
.pf-link-btn:hover { border-color: currentColor; background: rgba(128,128,128,0.08); }
</style>
"""

st.title("About")

with st.container(border=True):
    st.markdown("## :material/explore: PathFinder AI")
    st.markdown("##### Multi-Agent AI Career Counselor")
    st.write(
        "A chat-first career discovery and college pathway guidance platform for high "
        "school students, parents, and school counselors — built to show what a "
        "production-minded multi-agent AI system looks like end to end: memory, "
        "retrieval-augmented generation, layered safety guardrails, LLM-as-judge "
        "evaluation with a self-correcting revision loop, full observability, and a "
        "human feedback loop, all working together in one application."
    )

st.write("")

col_bio, col_stack = st.columns([3, 2], gap="large")

with col_bio:
    st.markdown("### Created by")
    st.markdown("#### Anurag Kabra")
    st.markdown(
        _LINK_BUTTON_CSS
        + '<div class="pf-link-row">'
        + f'<a class="pf-link-btn" href="{_GITHUB_URL}" target="_blank" rel="noopener noreferrer">{_GITHUB_SVG}GitHub</a>'
        + f'<a class="pf-link-btn" href="{_LINKEDIN_URL}" target="_blank" rel="noopener noreferrer">{_LINKEDIN_SVG}LinkedIn</a>'
        + "</div>",
        unsafe_allow_html=True,
    )
    st.write(
        "PathFinder AI started as a hands-on exploration of what it actually takes to "
        "ship a production-grade AI system — not just a prompt wrapped in a chat "
        "window, but one with memory, grounded retrieval, safety guardrails, automated "
        "quality evaluation, and a feedback loop that closes back to the people using "
        "it. Every architectural decision behind it is recorded in its own decision "
        "log, treating the build process itself as part of the craft."
    )

with col_stack:
    st.markdown("### Technology stack")
    with st.container(horizontal=True):
        for tech in ["Python", "Streamlit", "OpenAI", "Pinecone", "SQLite", "LangSmith", "Pydantic"]:
            st.badge(tech, color="blue")

st.divider()

st.markdown("### Architecture highlights")

hl_col1, hl_col2 = st.columns(2, gap="medium")

with hl_col1:
    st.markdown(
        "- :material/hub: **9 specialized agents** coordinated by a central orchestrator\n"
        "- :material/travel_explore: **RAG-grounded recommendations** via Pinecone — no hallucinated careers\n"
        "- :material/shield: **Layered guardrails** — input and output, 13 rule-based safety flags\n"
        "- :material/gavel: **RASCEF evaluation** — LLM-as-judge scoring with an automatic revision loop"
    )

with hl_col2:
    st.markdown(
        "- :material/monitoring: **Full observability** — every turn logged, optional LangSmith tracing\n"
        "- :material/description: **Governed prompts** — every response traceable to an exact prompt version\n"
        "- :material/thumb_up: **Human-in-the-loop feedback** wired directly to the turn that produced it\n"
        "- :material/memory: **Persistent memory** — returning students continue, never restart"
    )

st.caption("Full technical documentation lives in the project's `docs/` folder.")
