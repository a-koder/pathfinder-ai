import streamlit as st
from agents.orchestrator import get_profile_snapshot
from ui_shared import render_sidebar

st.set_page_config(page_title="PathFinder AI", page_icon=":material/rocket_launch:", layout="wide")

_student_name = st.session_state.get("student_name", "").strip()
_profile = get_profile_snapshot(_student_name) if _student_name else {}

with st.sidebar:
    render_sidebar(student_name=_student_name, profile=_profile)

chat_page = st.Page("app_pages/chat.py", title="Career Guidance", icon="💬", default=True)
architecture_page = st.Page("app_pages/architecture.py", title="Architecture", icon=":material/account_tree:")
technology_page = st.Page("app_pages/technology.py", title="Technology", icon=":material/memory:")
about_page = st.Page("app_pages/about.py", title="About", icon=":material/info:")

pg = st.navigation([chat_page, architecture_page, technology_page, about_page], position="top")
pg.run()
