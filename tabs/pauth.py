import streamlit as st
from utils import auth


def render():
    st.set_page_config(
        page_title="Авторизация",
        page_icon="🔐",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    st.markdown("<h2 style='text-align: center;'>Вход в систему</h2>", unsafe_allow_html=True)
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        with st.form("login_form", clear_on_submit=True):
            username = st.text_input("Логин")
            password = st.text_input("Пароль", type="password")
            submitted = st.form_submit_button("Войти")
            if submitted:
                result = auth.authenticate(username, password)
                if not result:
                    st.error("Неверный логин или пароль")
                    return
                user_info, company_ids, category_ids = result
                st.session_state["authenticated"] = True
                st.session_state["user"] = user_info
                st.session_state["allowed_company_ids"] = company_ids
                st.session_state["allowed_category_ids"] = category_ids
                st.success("Успешный вход!")
                st.experimental_rerun()
    else:
        st.experimental_set_query_params(page="Home")
        st.experimental_rerun()
