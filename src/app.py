import streamlit as st

st.set_page_config(page_title="PathFinder AI", page_icon=":material/rocket_launch:", layout="wide")

chat_page = st.Page("app_pages/chat.py", title="Career Guidance", icon="💬", default=True)
how_it_works_page = st.Page("app_pages/how_it_works.py", title="How PathFinder Works", icon="📖")

# Hidden: Career Guidance is the product, not a nav bar. Both pages stay reachable via
# the low-key links in the sidebar footer (see ui_shared.render_sidebar_footer).
pg = st.navigation([chat_page, how_it_works_page], position="hidden")
pg.run()
