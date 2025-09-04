import streamlit as st
# Импортируем функции вкладок
from .reports_itogbank import reports_itogbank

def reports_main():
    st.title("Отчёты")

    tab_itog, = st.tabs(["📊 Итоги по компаниям"])  # распаковка единственного элемента

    with tab_itog:
        reports_itogbank()