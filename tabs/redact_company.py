# tabs/redact_company.py
import datetime as dt
import pandas as pd
import streamlit as st
from sqlalchemy import update

from core.db import SessionLocal
from db_models import company, up_company


def redact_company():
    with SessionLocal() as session:
        tabs = st.tabs(["Управляющие компании", "Компании"])

        # ========== Вкладка 1: Управляющие компании ==========
        with tabs[0]:
            st.subheader("Управляющие компании")

            ups = session.query(up_company.UpCompany).order_by(up_company.UpCompany.name.asc()).all()

            rows = []
            for u in ups:
                rows.append(
                    {
                        "Название": u.name,
                        "Базовый баланс": f"{float(getattr(u, 'balance_base_amount', 0.0) or 0.0):,.2f}".replace(",", " "),
                        "Дата базового баланса": u.balance_base_date.isoformat() if getattr(u, "balance_base_date", None) else "",
                        "Текущий баланс": (
                            f"{float(getattr(u, 'current_balance', 0.0) or 0.0):,.2f}".replace(",", " ")
                            if hasattr(u, "current_balance") and getattr(u, "current_balance") is not None
                            else ""
                        ),
                    }
                )
            df_up = pd.DataFrame(rows)
            st.dataframe(df_up, use_container_width=True, hide_index=True)

            col_left, col_right = st.columns(2)

            # --- Редактировать/удалить УП ---
            with col_left.popover("✏️ Редактировать управляющую компанию"):
                if not ups:
                    st.info("Нет доступных управляющих компаний.")
                else:
                    names = [u.name for u in ups]
                    sel_name = st.selectbox("Управляющая компания", options=names, index=0, key="edit_up_select")
                    sel = next((u for u in ups if u.name == sel_name), None)

                    if sel:
                        new_name = st.text_input("Новое название", value=sel.name, key="edit_up_name")
                        new_balance = st.number_input(
                            "Базовый баланс (₽)",
                            value=float(getattr(sel, "balance_base_amount", 0.0) or 0.0),
                            step=100.0,
                            format="%.2f",
                            key="edit_up_balance",
                        )
                        new_date = st.date_input(
                            "Дата базового баланса",
                            value=getattr(sel, "balance_base_date", dt.date.today()),
                            key="edit_up_date",
                        )

                        c1, c2 = st.columns(2)

                        if c1.button("Сохранить", key="save_up_btn"):
                            try:
                                sel.name = new_name.strip()
                                sel.balance_base_amount = float(new_balance or 0.0)
                                sel.balance_base_date = new_date
                                session.add(sel)
                                session.commit()
                                st.success("Управляющая компания обновлена.")
                                st.rerun()
                            except Exception as e:
                                session.rollback()
                                st.error(f"Ошибка сохранения: {e}")

                        if c2.button("Удалить", key="del_up_btn"):
                            try:
                                session.execute(
                                    update(company.Company)
                                    .where(company.Company.up_company_id == sel.id)
                                    .values(up_company_id=None)
                                )
                                session.flush()
                                session.delete(sel)
                                session.commit()
                                st.success("Управляющая компания удалена, привязки сброшены.")
                                st.rerun()
                            except Exception as e:
                                session.rollback()
                                st.error(f"Ошибка удаления: {e}")

            # --- Добавить УП ---
            with col_right.popover("➕ Добавить управляющую компанию"):
                with st.form("form_add_up_company"):
                    up_name = st.text_input("Название управляющей компании")
                    up_balance = st.number_input("Базовый баланс (₽)", value=0.0, step=100.0, format="%.2f")
                    up_date = st.date_input("Дата базового баланса", value=dt.date.today())
                    submit_add = st.form_submit_button("Добавить")
                    if submit_add:
                        if not up_name.strip():
                            st.error("Название обязательно.")
                        else:
                            try:
                                exists = (
                                    session.query(up_company.UpCompany)
                                    .filter(up_company.UpCompany.name == up_name.strip())
                                    .first()
                                )
                                if exists:
                                    st.warning("Такая управляющая компания уже существует.")
                                else:
                                    obj = up_company.UpCompany(
                                        name=up_name.strip(),
                                        balance_base_amount=float(up_balance or 0.0),
                                        balance_base_date=up_date,
                                    )
                                    session.add(obj)
                                    session.commit()
                                    st.success("Управляющая компания добавлена.")
                                    st.rerun()
                            except Exception as e:
                                session.rollback()
                                st.error(f"Ошибка добавления: {e}")

        # ========== Вкладка 2: Компании ==========
        with tabs[1]:
            st.subheader("Компании")

            up_all = session.query(up_company.UpCompany).order_by(up_company.UpCompany.name.asc()).all()
            up_name_by_id = {u.id: u.name for u in up_all}
            up_names = [""] + [u.name for u in up_all]

            comp_list = session.query(company.Company).order_by(company.Company.name.asc()).all()
            df_comp = pd.DataFrame(
                [
                    {
                        "Название": c.name,
                        "ИНН": c.inn,
                        "Управляющая": up_name_by_id.get(c.up_company_id, ""),
                        "Основная": "Да" if getattr(c, "is_primary", False) else "",
                    }
                    for c in comp_list
                ]
            )
            st.dataframe(df_comp, use_container_width=True, hide_index=True)

            cL, cR = st.columns(2)

            # --- Редактировать/удалить компанию ---
            with cL.popover("✏️ Редактировать компанию"):
                if not comp_list:
                    st.info("Нет компаний для редактирования.")
                else:
                    comp_names = [c.name for c in comp_list]
                    sel_comp_name = st.selectbox("Компания", options=comp_names, index=0, key="edit_comp_select")
                    sel_c = next((c for c in comp_list if c.name == sel_comp_name), None)

                    if sel_c:
                        new_c_name = st.text_input("Название", value=sel_c.name, key="edit_comp_name")
                        new_c_inn = st.text_input("ИНН", value=sel_c.inn or "", key="edit_comp_inn")
                        cur_up_name = up_name_by_id.get(sel_c.up_company_id, "")
                        new_up_name = st.selectbox(
                            "Управляющая компания",
                            options=up_names,
                            index=(up_names.index(cur_up_name) if cur_up_name in up_names else 0),
                            key="edit_comp_up",
                        )
                        new_primary = st.checkbox(
                            "Основная по умолчанию", value=bool(getattr(sel_c, "is_primary", False)), key="edit_comp_primary"
                        )

                        b1, b2 = st.columns(2)

                        if b1.button("Сохранить", key="save_comp_btn"):
                            try:
                                sel_c.name = new_c_name.strip()
                                sel_c.inn = (new_c_inn or "").strip()
                                uc = next((u for u in up_all if u.name == new_up_name), None) if new_up_name else None
                                sel_c.up_company_id = uc.id if uc else None
                                sel_c.is_primary = bool(new_primary)
                                session.add(sel_c)
                                session.commit()
                                st.success("Компания обновлена.")
                                st.rerun()
                            except Exception as e:
                                session.rollback()
                                st.error(f"Ошибка сохранения: {e}")

                        if b2.button("Удалить", key="del_comp_btn"):
                            try:
                                session.delete(sel_c)
                                session.commit()
                                st.success("Компания удалена.")
                                st.rerun()
                            except Exception as e:
                                session.rollback()
                                st.error(f"Ошибка удаления: {e}")

            # --- Добавить компанию ---
            with cR.popover("➕ Добавить компанию"):
                with st.form("form_add_company"):
                    c_name = st.text_input("Название компании")
                    c_inn = st.text_input("ИНН")
                    c_up_name = st.selectbox("Управляющая компания", options=up_names, index=0)
                    c_primary = st.checkbox("Основная по умолчанию", value=False, key="add_comp_primary")
                    submit_c = st.form_submit_button("Добавить")
                    if submit_c:
                        if not c_name.strip():
                            st.error("Название компании обязательно.")
                        elif not c_inn.strip():
                            st.error("ИНН обязателен.")
                        else:
                            try:
                                uc = next((u for u in up_all if u.name == c_up_name), None) if c_up_name else None
                                obj = company.Company(
                                    name=c_name.strip(),
                                    inn=c_inn.strip(),
                                    up_company_id=(uc.id if uc else None),
                                    is_primary=bool(c_primary),
                                )
                                session.add(obj)
                                session.commit()
                                st.success("Компания добавлена.")
                                st.rerun()
                            except Exception as e:
                                session.rollback()
                                st.error(f"Ошибка добавления: {e}")
