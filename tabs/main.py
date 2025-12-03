import streamlit as st

from tabs.import_main import import_tab
from tabs.redact_main import redact_tab
from tabs.reports_main import reports_main
from tabs.import_income_expenses import import_income_expenses_tab


def logout_button(cookies, clear_session_fn=None):
    if st.sidebar.button("Выход"):
        if callable(clear_session_fn):
            clear_session_fn()
        else:
            st.session_state["authenticated"] = False
            cookies["auth"] = "0"
            cookies.save()
        st.rerun()


def _role() -> str:
    user = st.session_state.get("user") or {}
    return user.get("role", "")


def render_main_menu(cookies, clear_session_fn=None):
    role = _role()
    is_admin = role == "admin"

    menu_items = []
    if is_admin:
        menu_items.extend(
            [
                "Отчёты",
                "Импорт банковских выписок",
            ]
        )
    menu_items.append("Доходы / Расходы ресторана")
    if is_admin:
        menu_items.append("Редактирование")

    menu = st.sidebar.radio("Меню", menu_items, key="main_menu")

    if menu == "Отчёты":
        reports_main()
    elif menu == "Импорт банковских выписок":
        import_tab()
    elif menu == "Доходы / Расходы ресторана":
        import_income_expenses_tab()
    elif menu == "Редактирование":
        redact_tab()

    logout_button(cookies, clear_session_fn=clear_session_fn)
