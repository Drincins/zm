import streamlit as st
from tabs.redact_group import redact_group
from tabs.redact_category import redact_category



def redact_gc():
    st.title("Редактирование групп и категорий")
    tabs = st.tabs(["Группы", "Категории"])

    with tabs[0]:
        redact_group()

    with tabs[1]:
        redact_category()
