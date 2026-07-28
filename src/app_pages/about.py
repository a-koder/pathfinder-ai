import streamlit as st
from ui_shared import render_header, render_social_links

render_header()

with st.container(border=True):
    st.markdown("#### Multi-Agent AI Career Counselor")
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
    render_social_links()
    st.write(
        "PathFinder AI started as a hands-on exploration of what it actually takes to "
        "ship a production-grade AI system — not just a prompt wrapped in a chat "
        "window, but one with memory, grounded retrieval, safety guardrails, automated "
        "quality evaluation, and a feedback loop that closes back to the people using "
        "it. Every architectural decision behind it is recorded in its own decision "
        "log, treating the build process itself as part of the craft."
    )
    st.caption("Curious how it actually works? See the Architecture and Technology tabs above.")

with col_stack:
    st.markdown("### Technology stack")
    with st.container(horizontal=True):
        for tech in ["Python", "Streamlit", "OpenAI", "Pinecone", "SQLite", "LangSmith", "Pydantic"]:
            st.badge(tech, color="blue")
