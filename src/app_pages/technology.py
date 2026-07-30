import streamlit as st
from ui_shared import render_header, render_doc_tabs

# The AI techniques that power it: how recommendations stay grounded, and how
# prompts are versioned and governed.
_SECTIONS = [
    ("RAG Design", "13_RAG_Implementation.md"),
    ("Prompt Governance", "09_Agent_Contracts.md"),
]

render_header()
st.write(
    "The AI techniques behind PathFinder AI: retrieval-augmented generation over a "
    "curated knowledge base, and how every prompt is versioned, logged, and traced."
)
st.caption("Rendered directly from the project's own documentation - nothing duplicated.")

render_doc_tabs(_SECTIONS)
