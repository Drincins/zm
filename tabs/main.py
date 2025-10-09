import streamlit as st
from tabs.import_main import import_tab 
from tabs.redact_main import redact_tab
from tabs.reports_main import reports_main
from tabs.import_income_expenses import import_income_expenses_tab

def logout_button(cookies):
    if st.sidebar.button("Выйти"):
        st.session_state["authenticated"] = False
        cookies["auth"] = "0"
        cookies.save()
        st.rerun()

def home_tab():
    st.title("Добро пожаловать в Главная!")
    st.write("Тут будут дашборды и сводная информация.")

def analytics_tab():
    st.title("Аналитика")
    st.write("Здесь будет аналитика.")

def render_main_menu(cookies):
    
    menu = st.sidebar.radio(  
        "Меню", 
        [
            "Главная",
            "Аналитика",
            "Отчёты",
            "Импорт банковской выписки", 
            "Импорт расходов/доходов" ,
            "Редактор"
        ],
        key="main_menu"
    )

    if menu == "Главная":
        home_tab()
    elif menu == "Аналитика":
        analytics_tab()
    elif menu == "Отчёты":
        reports_main()
    elif menu == "Импорт банковской выписки":
        import_tab()
    elif menu == "Импорт расходов/доходов":
        import_income_expenses_tab()  
    elif menu == "Редактор":
        redact_tab()
    logout_button(cookies)
