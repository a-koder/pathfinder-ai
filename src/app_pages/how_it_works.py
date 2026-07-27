from pathlib import Path

import streamlit as st
from ui_shared import render_header, render_sidebar_footer

_DOCS_DIR = Path(__file__).parent.parent.parent / "docs"

_SECTIONS = [
    ("System Overview", "04_Architecture.md"),
    ("Architecture Diagrams", "08_Diagrams.md"),
    ("Agent Flow", "09_Agent_Contracts.md"),
    ("RAG Design", "13_RAG_Implementation.md"),
    ("Decision Log", "12_DECISION_LOG.md"),
    ("Prompt Governance", "99_REFERENCE.md"),
]


@st.cache_data
def _load_doc(filename: str) -> str:
    return (_DOCS_DIR / filename).read_text(encoding="utf-8")


with st.sidebar:
    render_sidebar_footer()

render_header()
st.caption(
    "A look under the hood for reviewers, recruiters, and capstone evaluators - "
    "rendered directly from the project's own documentation, nothing duplicated."
)

tabs = st.tabs([label for label, _ in _SECTIONS])
for tab, (label, filename) in zip(tabs, _SECTIONS):
    with tab:
        try:
            st.markdown(_load_doc(filename))
        except FileNotFoundError:
            st.warning(f"docs/{filename} could not be found.")
