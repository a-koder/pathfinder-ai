import streamlit as st

st.set_page_config(page_title="PathFinder AI", page_icon=":material/explore:", layout="wide")

chat_page = st.Page("app_pages/chat.py", title="Career Guidance", icon="💬", default=True)
how_it_works_page = st.Page("app_pages/how_it_works.py", title="How PathFinder Works", icon="📖")

pg = st.navigation([chat_page, how_it_works_page])
pg.run()
