"""Small UI building blocks shared across pages - header, sidebar, and the doc/diagram
viewer used by both the Architecture and Technology pages. Presentation only; no
business logic, no imports from agents/services/infrastructure.
"""
import re
import subprocess
from pathlib import Path

import streamlit as st

_DOCS_DIR = Path(__file__).parent.parent / "docs"
_REPO_ROOT = Path(__file__).parent.parent
_MERMAID_FENCE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)

_GITHUB_URL = "https://github.com/a-koder/pathfinder-ai"
_LINKEDIN_URL = "https://www.linkedin.com/in/a-kabra/"

_GITHUB_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
<path d="M12 .5C5.6.5.5 5.6.5 12c0 5.1 3.3 9.4 7.9 11 .6.1.8-.3.8-.6v-2.1c-3.2.7-3.9-1.5-3.9-1.5-.5-1.3-1.3-1.7-1.3-1.7-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.4 1 .1-.8.4-1.3.8-1.6-2.6-.3-5.3-1.3-5.3-5.8 0-1.3.5-2.3 1.2-3.1-.1-.3-.5-1.6.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0c2.3-1.6 3.3-1.2 3.3-1.2.7 1.6.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.1 0 4.5-2.7 5.5-5.3 5.8.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6 4.6-1.6 7.9-5.9 7.9-11C23.5 5.6 18.4.5 12 .5z"/>
</svg>
"""

_LINKEDIN_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
<path d="M20.5 2h-17A1.5 1.5 0 0 0 2 3.5v17A1.5 1.5 0 0 0 3.5 22h17a1.5 1.5 0 0 0 1.5-1.5v-17A1.5 1.5 0 0 0 20.5 2zM8.3 19H5.5V9h2.8zm-1.4-11.3a1.6 1.6 0 1 1 0-3.2 1.6 1.6 0 0 1 0 3.2zM19 19h-2.8v-4.9c0-1.2 0-2.7-1.6-2.7s-1.9 1.3-1.9 2.6V19h-2.8V9h2.7v1.4h.1a2.9 2.9 0 0 1 2.7-1.5c2.9 0 3.6 1.9 3.6 4.5z"/>
</svg>
"""

_LINK_CSS = """
<style>
.pf-links { display: flex; gap: 0.5rem; margin: 0.35rem 0 0.4rem 0; flex-wrap: wrap; }
.pf-link {
    display: inline-flex; align-items: center; gap: 0.35rem;
    padding: 0.3rem 0.7rem; border-radius: 999px;
    border: 1px solid rgba(128,128,128,0.35);
    text-decoration: none !important; font-weight: 500; font-size: 0.78rem;
    color: inherit; transition: border-color 0.15s ease, background 0.15s ease;
}
.pf-link:hover { border-color: currentColor; background: rgba(128,128,128,0.08); }
</style>
"""


def render_social_links() -> None:
    """GitHub + LinkedIn pill links. Used in both the sidebar and the About page."""
    st.markdown(
        _LINK_CSS
        + '<div class="pf-links">'
        + f'<a class="pf-link" href="{_GITHUB_URL}" target="_blank" rel="noopener noreferrer">{_GITHUB_SVG}GitHub</a>'
        + f'<a class="pf-link" href="{_LINKEDIN_URL}" target="_blank" rel="noopener noreferrer">{_LINKEDIN_SVG}LinkedIn</a>'
        + "</div>",
        unsafe_allow_html=True,
    )


def render_header() -> None:
    """Compact app identity header - visible but not dominant, shown once per page."""
    st.markdown("### 🚀 PathFinder AI")
    st.caption("Explore Possibilities • Discover Your Path")


def _reset_conversation() -> None:
    st.session_state.messages = []
    st.session_state.notes_shown = set()
    name = st.session_state.get("student_name", "").strip()
    st.session_state.history_loaded_for = name or None


def _get_version() -> str:
    """Latest git tag (e.g. "v1.0.0"), read once at import time. Falls back to a static
    default if git isn't available - e.g. a packaged deployment without a .git folder."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=2,
        )
        tag = result.stdout.strip()
        if result.returncode == 0 and tag:
            return tag.lstrip("vV")
    except Exception:
        pass
    return "1.0"


_VERSION = _get_version()


def _render_profile_card(student_name: str, profile: dict) -> None:
    """Live 'what PathFinder knows about you' snapshot - the sidebar's actual reason to
    exist, not just branding. Updates every rerun as the profile grows."""
    with st.container(border=True):
        if not student_name:
            st.markdown(":material/waving_hand: **Welcome!**")
            st.caption("Enter your name above to get personalized guidance.")
            return

        st.markdown(f":material/waving_hand: **Welcome back, {student_name}**")

        details = []
        grade = profile.get("grade_level")
        if grade:
            details.append(f"Grade {grade}")
        gpa = profile.get("gpa")
        if gpa not in (None, ""):
            details.append(f"GPA {gpa}")
        if details:
            st.caption(" · ".join(details))

        interests = profile.get("interests") or []
        if interests:
            st.caption(":material/target: " + ", ".join(interests[:4]))
        else:
            st.caption("Still getting to know you — tell me what you're into!")


def render_sidebar(student_name: str = "", profile: dict | None = None) -> None:
    """
    Global sidebar shown on every page: brand mark, a live profile snapshot (once a
    name is entered), New Conversation, and creator credit at the bottom. Page
    navigation, student name entry, and the full "About" story live in the top nav /
    main content instead - this stays focused on quick context + one primary action.
    """
    st.caption(":material/rocket_launch: PathFinder AI")

    _render_profile_card(student_name, profile or {})

    st.button(
        "New conversation",
        icon=":material/add_comment:",
        on_click=_reset_conversation,
        width="stretch",
    )

    st.divider()
    st.caption("Created by Anurag Kabra")
    render_social_links()
    st.caption(f"Version {_VERSION}")


def load_doc(filename: str) -> str:
    """
    Reads a doc fresh on every call - deliberately not cached. These files are the
    single source of truth for both this viewer and the rest of the repo; editing one
    (there's exactly one copy) should show up on the very next page load.
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


def render_doc_with_diagrams(filename: str) -> None:
    """Renders a doc's markdown normally, but renders Mermaid fences as real diagrams
    via Streamlit's native st.mermaid_chart - no CDN, no custom HTML/JS."""
    segments = _split_mermaid_segments(load_doc(filename))
    for kind, content in segments:
        if kind == "mermaid":
            st.mermaid_chart(content)
        elif content.strip():
            st.markdown(content)


def render_doc_tabs(sections: list[tuple[str, str]]) -> None:
    """Renders a list of (tab_label, doc_filename) pairs as tabs, one doc per tab,
    with Mermaid diagrams (if any) rendered as real charts."""
    tabs = st.tabs([label for label, _ in sections])
    for tab, (label, filename) in zip(tabs, sections):
        with tab:
            try:
                if filename == "08_Diagrams.md":
                    render_doc_with_diagrams(filename)
                else:
                    st.markdown(load_doc(filename))
            except FileNotFoundError:
                st.warning(f"docs/{filename} could not be found.")


def render_doc_page(intro: str, sections: list[tuple[str, str]]) -> None:
    """
    Generic body for any page whose entire job is displaying real docs/*.md content -
    header, one intro line, a "rendered directly from docs" caption, then the tabs
    themselves. Used for Architecture, Technology, and Product Vision; adding another
    doc-viewer page is a few lines of st.Page(functools.partial(...)) config in app.py,
    not a new file - this was three near-identical files before.
    """
    render_header()
    st.write(intro)
    st.caption("Rendered directly from the project's own documentation - nothing duplicated.")
    render_doc_tabs(sections)
