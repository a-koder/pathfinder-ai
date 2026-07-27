import streamlit as st

st.set_page_config(page_title="PathFinder AI", page_icon=":material/explore:", layout="wide")

chat_page = st.Page("app_pages/chat.py", title="Chat", icon=":material/chat:", default=True)
about_page = st.Page("app_pages/about.py", title="About", icon=":material/info:")

pg = st.navigation([chat_page, about_page])
pg.run()
