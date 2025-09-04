import streamlit as st
from tabs.redact_company import redact_company
from tabs.redact_gc import redact_gc
from tabs.redact_firm import redact_firm

from tabs.redact_statement import redact_statement

def redact_tab():
    st.header("Редактирование справочников")
    tabs = st.tabs(["Компании", "Группы и категории", "Фирмы", "Мастер"])

    with tabs[0]:
        redact_company()

    with tabs[1]:
        redact_gc()

    with tabs[2]:
        redact_firm()

    with tabs[3]:
       redact_statement()    