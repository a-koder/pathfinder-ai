"""Small UI building blocks shared across pages - header and sidebar footer branding.
Presentation only; no business logic, no imports from agents/services/infrastructure.
"""
import streamlit as st

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

_FOOTER_CSS = """
<style>
.pf-footer-links { display: flex; gap: 0.5rem; margin: 0.35rem 0 0.6rem 0; }
.pf-footer-link {
    display: inline-flex; align-items: center; gap: 0.35rem;
    padding: 0.3rem 0.7rem; border-radius: 999px;
    border: 1px solid rgba(128,128,128,0.35);
    text-decoration: none !important; font-weight: 500; font-size: 0.78rem;
    color: inherit; transition: border-color 0.15s ease, background 0.15s ease;
}
.pf-footer-link:hover { border-color: currentColor; background: rgba(128,128,128,0.08); }
</style>
"""


def render_header() -> None:
    """App identity header shown once at the top of each page's main content."""
    st.markdown("# 🚀 PathFinder AI")
    st.caption("Explore Possibilities. Discover Your Path.")


def render_sidebar_footer() -> None:
    """
    Low-key page links + creator credit, links, and version - pinned at the bottom of
    the sidebar. Career Guidance is the product; How PathFinder Works exists for
    reviewers and recruiters, so neither gets a prominent top-level nav bar - both are
    just quietly reachable down here, same as the "Created by" credit below them.
    """
    st.divider()
    st.page_link("app_pages/chat.py", label="Career Guidance", icon=":material/chat:")
    st.page_link("app_pages/how_it_works.py", label="How PathFinder Works", icon=":material/menu_book:")
    st.divider()
    st.caption("Created by")
    st.markdown("**Anurag Kabra**")
    st.markdown(
        _FOOTER_CSS
        + '<div class="pf-footer-links">'
        + f'<a class="pf-footer-link" href="{_GITHUB_URL}" target="_blank" rel="noopener noreferrer">{_GITHUB_SVG}GitHub</a>'
        + f'<a class="pf-footer-link" href="{_LINKEDIN_URL}" target="_blank" rel="noopener noreferrer">{_LINKEDIN_SVG}LinkedIn</a>'
        + "</div>",
        unsafe_allow_html=True,
    )
    st.caption("Version 1.0")
