from functools import partial

import streamlit as st
from agents.orchestrator import get_profile_snapshot
from ui_shared import render_doc_page, render_sidebar

st.set_page_config(page_title="PathFinder AI", page_icon=":material/rocket_launch:", layout="wide")

_student_name = st.session_state.get("student_name", "").strip()
_profile = get_profile_snapshot(_student_name) if _student_name else {}

with st.sidebar:
    render_sidebar(student_name=_student_name, profile=_profile)

chat_page = st.Page("app_pages/chat.py", title="Career Guidance", icon="💬", default=True)

product_vision_page = st.Page(
    partial(
        render_doc_page,
        "Why PathFinder AI exists, who it's for, and the honest tradeoffs behind building "
        "it - written as a Press Release / FAQ.",
        [("Press Release & FAQ", "01_Product_Overview.md")],
    ),
    title="Product Vision",
    icon=":material/campaign:",
    url_path="product-vision",
)

architecture_page = st.Page(
    partial(
        render_doc_page,
        "How PathFinder AI is put together: the Clean Architecture layers, the 10-agent "
        "turn-by-turn flow, the visual diagrams behind it, and the decisions that shaped it.",
        [
            ("System Overview", "04_Architecture.md"),
            ("Agent Flow", "09_Agent_Contracts.md"),
            ("Architecture Diagrams", "08_Diagrams.md"),
            ("Decision Log", "12_DECISION_LOG.md"),
        ],
    ),
    title="Architecture",
    icon=":material/account_tree:",
    url_path="architecture",
)

technology_page = st.Page(
    partial(
        render_doc_page,
        "The AI techniques behind PathFinder AI: retrieval-augmented generation over a "
        "curated knowledge base, and how every prompt is versioned, logged, and traced.",
        [
            ("RAG Design", "13_RAG_Implementation.md"),
            ("Prompt Governance", "09_Agent_Contracts.md"),
        ],
    ),
    title="Technology",
    icon=":material/memory:",
    url_path="technology",
)

about_page = st.Page("app_pages/about.py", title="About", icon=":material/info:")

pg = st.navigation(
    [chat_page, product_vision_page, architecture_page, technology_page, about_page],
    position="top",
)
pg.run()
