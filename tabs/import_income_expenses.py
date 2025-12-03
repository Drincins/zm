import streamlit as st

from tabs import import_expenses, import_incomes, payment_links

TAB_LABEL_INCOMES = "Доходы"
TAB_LABEL_EXPENSES = "Расходы"


def import_income_expenses_tab():
    """Main entry point for the income/expense import tab."""
    user = st.session_state.get("user") or {}
    role = user.get("role", "")
    if role not in ("admin", "manager"):
        st.warning("У вас нет доступа к этой странице.")
        return

    st.subheader("Доходы / Расходы / Платёжные ссылки")

    incomes_tab, expenses_tab, paylinks_tab = st.tabs([TAB_LABEL_INCOMES, TAB_LABEL_EXPENSES, "Платёжные ссылки"])

    with incomes_tab:
        import_incomes.render_import_incomes_tab()

    with expenses_tab:
        import_expenses.render_import_expenses_tab()

    with paylinks_tab:
        payment_links.render_payment_links_tab()
