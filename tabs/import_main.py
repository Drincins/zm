import streamlit as st

from tabs.import_new_operations import import_new_operations_tab
from tabs.import_edit_operations import import_edit_operations_tab

def import_tab():
    st.header("Импорт и обработка банковских выписок")
    tabs = st.tabs(["Импорт новых операций", "Редактирование мастер-таблицы"])

    with tabs[0]:
        import_new_operations_tab()
    with tabs[1]:
        import_edit_operations_tab()
