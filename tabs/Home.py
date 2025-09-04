import streamlit as st

def render():
    st.set_page_config(page_title="Home", page_icon="🏠", layout="wide")
    st.sidebar.success("Выберите раздел в меню слева.")
    st.markdown("# Добро пожаловать в Home!")
    # Здесь будет дашборд/контент
