import streamlit as st
from ui_shared import render_header, render_doc_tabs

# How the system is put together and how a turn flows through it.
_SECTIONS = [
    ("System Overview", "04_Architecture.md"),
    ("Agent Flow", "09_Agent_Contracts.md"),
    ("Architecture Diagrams", "08_Diagrams.md"),
    ("Decision Log", "12_DECISION_LOG.md"),
]

render_header()
st.write(
    "How PathFinder AI is put together: the Clean Architecture layers, the 10-agent "
    "turn-by-turn flow, the visual diagrams behind it, and the decisions that shaped it."
)
st.caption("Rendered directly from the project's own documentation - nothing duplicated.")

render_doc_tabs(_SECTIONS)
