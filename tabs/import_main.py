import streamlit as st

from tabs.import_new_operations import import_new_operations_tab
from tabs.import_edit_operations import import_edit_operations_tab
from tabs.import_restaurant_to_statement import render_transfer_restaurant_to_statement_tab


def import_tab():
    st.header("Импорт и обработка операций")
    tabs = st.tabs(
        [
            "Импорт банковских операций",
            "Редактирование операций",
            "Перенос ресторанных расходов",
        ]
    )

    with tabs[0]:
        import_new_operations_tab()
    with tabs[1]:
        import_edit_operations_tab()
    with tabs[2]:
        render_transfer_restaurant_to_statement_tab()
