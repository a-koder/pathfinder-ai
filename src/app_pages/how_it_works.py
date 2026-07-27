import re
from pathlib import Path

import streamlit as st
from ui_shared import render_sidebar_footer

_DOCS_DIR = Path(__file__).parent.parent.parent / "docs"

# Ordered to tell a logical story: what it does, how a turn flows through it, the
# visual map of that flow, how it's grounded in real data, how prompts are governed,
# and finally why things were built this way.
_SECTIONS = [
    ("System Overview", "04_Architecture.md"),
    ("Agent Flow", "09_Agent_Contracts.md"),
    ("Architecture Diagrams", "08_Diagrams.md"),
    ("RAG Design", "13_RAG_Implementation.md"),
    ("Prompt Governance", "99_REFERENCE.md"),
    ("Decision Log", "12_DECISION_LOG.md"),
]

_MERMAID_FENCE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)


def _load_doc(filename: str) -> str:
    """
    Reads a doc fresh on every call - these files are the single source of truth for
    both this viewer and the rest of the repo. No caching, deliberately: editing a .md
    file (there's exactly one copy) should be reflected on the very next page load,
    with no stale content and no separate cache to invalidate.
    """
    return (_DOCS_DIR / filename).read_text(encoding="utf-8")


def _split_mermaid_segments(markdown_text: str) -> list[tuple[str, str]]:
    """Splits a markdown doc into ordered ('text', ...) / ('mermaid', ...) segments."""
    segments = []
    last_end = 0
    for match in _MERMAID_FENCE.finditer(markdown_text):
        if match.start() > last_end:
            segments.append(("text", markdown_text[last_end:match.start()]))
        segments.append(("mermaid", match.group(1).strip()))
        last_end = match.end()
    if last_end < len(markdown_text):
        segments.append(("text", markdown_text[last_end:]))
    return segments


def _render_doc_with_diagrams(filename: str) -> None:
    """Renders a doc's markdown normally, but renders Mermaid fences as real diagrams
    via Streamlit's native st.mermaid_chart - no CDN, no custom HTML/JS."""
    segments = _split_mermaid_segments(_load_doc(filename))
    for kind, content in segments:
        if kind == "mermaid":
            st.mermaid_chart(content)
        elif content.strip():
            st.markdown(content)


with st.sidebar:
    render_sidebar_footer()

st.markdown("# 🚀 How PathFinder Works")
st.write(
    "PathFinder AI combines memory, retrieval-augmented generation (RAG), guardrails, "
    "evaluation, observability, prompt governance, and human feedback loops to help "
    "students explore careers, majors, colleges, trades, and future opportunities."
)
st.caption(
    "A look under the hood for reviewers, recruiters, and capstone evaluators - "
    "rendered directly from the project's own documentation, nothing duplicated."
)

tabs = st.tabs([label for label, _ in _SECTIONS])
for tab, (label, filename) in zip(tabs, _SECTIONS):
    with tab:
        try:
            if filename == "08_Diagrams.md":
                _render_doc_with_diagrams(filename)
            else:
                st.markdown(_load_doc(filename))
        except FileNotFoundError:
            st.warning(f"docs/{filename} could not be found.")
