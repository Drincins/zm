import streamlit as st
from utils.auth import check_credentials

def render():
    st.set_page_config(page_title="Авторизация", page_icon="🔐", layout="centered", initial_sidebar_state="collapsed")
    st.markdown("<h2 style='text-align: center;'>Вход в систему</h2>", unsafe_allow_html=True)
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        with st.form("login_form", clear_on_submit=True):
            username = st.text_input("Логин")
            password = st.text_input("Пароль", type="password")
            submitted = st.form_submit_button("Войти")
            if submitted:
                if check_credentials(username, password):
                    st.session_state["authenticated"] = True
                    st.success("Успешный вход!")
                    st.experimental_rerun()
                else:
                    st.error("Неверный логин или пароль")
    else:
        st.experimental_set_query_params(page="Home")
        st.experimental_rerun()
