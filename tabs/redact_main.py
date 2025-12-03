import streamlit as st

from tabs.redact_company import redact_company
from tabs.redact_gc import redact_gc
from tabs.redact_firm import redact_firm
from tabs.redact_payment_methods import redact_payment_methods
from tabs.redact_statement import redact_statement
from tabs.redact_users import redact_users


def redact_tab():
    user = st.session_state.get("user") or {}
    role = user.get("role", "")
    if role not in ("admin", "manager"):
        st.warning("У вас нет доступа к этой странице.")
        return

    st.header("Редактирование справочников")
    tabs = st.tabs(
        [
            "Компании",
            "Группы и категории",
            "Фирмы",
            "Выписки",
            "Методы оплаты",
            "Пользователи",
        ]
    )

    with tabs[0]:
        redact_company()

    with tabs[1]:
        redact_gc()

    with tabs[2]:
        redact_firm()

    with tabs[3]:
        redact_statement()

    with tabs[4]:
        redact_payment_methods()

    with tabs[5]:
        redact_users()
