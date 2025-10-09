import streamlit as st
import os
from dotenv import load_dotenv
from utils.auth import check_credentials
import tabs.main  # импорт твоего основного меню

from streamlit_cookies_manager import EncryptedCookieManager

# Глобальная конфигурация страницы
st.set_page_config(page_title="ZM", layout="wide", initial_sidebar_state="expanded")

# --- Настройка cookies (измени пароль на свой уникальный!)
cookies = EncryptedCookieManager(
    prefix="mybank_", password="MY_SUPER_SECRET_2024"
)
if not cookies.ready():
    st.stop()

load_dotenv()
LOGIN = os.getenv("LOGIN")
PASSWORD = os.getenv("PASSWORD")

# --- Проверка авторизации при запуске (куки или session_state)
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = cookies.get("auth") == "1"

def show_login():
    st.set_page_config(page_title="Авторизация", layout="centered", initial_sidebar_state="collapsed")
    st.title("Вход в систему")
    login = st.text_input("Логин")
    pwd = st.text_input("Пароль", type="password")
    if st.button("Войти"):
        if check_credentials(login, pwd):
            st.session_state["authenticated"] = True
            cookies["auth"] = "1"
            cookies.save()
            st.rerun()
        else:
            st.error("Неверный логин или пароль")

if not st.session_state["authenticated"]:
    st.markdown("""
        <style>
        [data-testid="stSidebar"], [data-testid="stSidebarNav"] { display: none !important; }
        </style>
    """, unsafe_allow_html=True)
    show_login()
    st.stop()

# ======= после входа — меню и контент из main.py =======
tabs.main.render_main_menu(cookies)
