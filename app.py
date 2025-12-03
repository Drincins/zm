import os
import streamlit as st
from dotenv import load_dotenv
from streamlit_cookies_manager import EncryptedCookieManager

import tabs.main  # основной роутер по вкладкам
from utils import auth

# Дефолтные настройки страницы
st.set_page_config(page_title="ZM", layout="wide", initial_sidebar_state="expanded")

# --- Инициализация cookies (шифрует содержимое, чтобы пароли не лежали открыто)
load_dotenv()
COOKIE_PASSWORD = os.getenv("COOKIE_PASSWORD")
if not COOKIE_PASSWORD:
    st.error("Не задан COOKIE_PASSWORD в .env")
    st.stop()

cookies = EncryptedCookieManager(prefix="mybank_", password=COOKIE_PASSWORD)
if not cookies.ready():
    st.stop()


def _set_user_session(user_info, company_ids, category_ids):
    st.session_state["authenticated"] = True
    st.session_state["user"] = user_info
    st.session_state["allowed_company_ids"] = company_ids
    st.session_state["allowed_category_ids"] = category_ids

    cookies["auth"] = "1"
    cookies["user_id"] = str(user_info["id"])
    cookies["role"] = user_info["role"]
    cookies.save()


def _clear_user_session():
    st.session_state["authenticated"] = False
    st.session_state.pop("user", None)
    st.session_state.pop("allowed_company_ids", None)
    st.session_state.pop("allowed_category_ids", None)
    cookies["auth"] = "0"
    cookies["user_id"] = ""
    cookies["role"] = ""
    cookies.save()


# --- Сохраняем состояние пользователя (может прийти из cookie)
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    cached_user_id = cookies.get("user_id")
    if cookies.get("auth") == "1" and cached_user_id:
        loaded = auth.load_user(cached_user_id)
        if loaded:
            user_info, company_ids, category_ids = loaded
            _set_user_session(user_info, company_ids, category_ids)


def show_login():
    st.title("Вход в систему")
    login = st.text_input("Логин")
    pwd = st.text_input("Пароль", type="password")
    if st.button("Войти"):
        result = auth.authenticate(login, pwd)
        if result:
            user_info, company_ids, category_ids = result
            _set_user_session(user_info, company_ids, category_ids)
            st.rerun()
        else:
            st.error("Неверные логин или пароль")


if not st.session_state.get("authenticated"):
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"], [data-testid="stSidebarNav"] { display: none !important; }
        </style>
    """,
        unsafe_allow_html=True,
    )
    show_login()
    st.stop()

# ======= Запускаем навигацию по вкладкам =======
tabs.main.render_main_menu(cookies, clear_session_fn=_clear_user_session)
