# tabs/redact_company.py
import streamlit as st
import pandas as pd
from sqlalchemy import update
import datetime as dt  # + ДОБАВИТЬ

from core.db import SessionLocal
from db_models import company, up_company


# ----------------------------- ВКЛАДКА -----------------------------

def redact_company():
    session = SessionLocal()
    try:
        tabs = st.tabs(["Головная компания", "Компании"])

        # ========== ТАБ 1: Головная компания ==========
        with tabs[0]:
            st.subheader("Головные компании")

            up_list = (
                session.query(up_company.UpCompany)
                .order_by(up_company.UpCompany.name.asc())
                .all()
            )

            # Таблица ГК: показываем только то, что есть в БД
            up_list = (
                session.query(up_company.UpCompany)
                .order_by(up_company.UpCompany.name.asc())
                .all()
            )

            rows = []
            for u in up_list:
                rows.append({
                    "Название": u.name,
                    "Начальный баланс": f"{float(getattr(u, 'balance_base_amount', 0.0) or 0.0):,.2f}".replace(",", " "),
                    "Дата изменений": (u.balance_base_date.isoformat() if getattr(u, "balance_base_date", None) else "—"),
                    # Текущий баланс берём ТОЛЬКО из БД, если поле есть; иначе ставим «—»
                    "Текущий баланс": (
                        f"{float(getattr(u, 'current_balance', 0.0) or 0.0):,.2f}".replace(",", " ")
                        if hasattr(u, "current_balance") and getattr(u, "current_balance") is not None
                        else "—"
                    ),
                })
            df_up = pd.DataFrame(rows)
            st.dataframe(df_up, use_container_width=True, hide_index=True)


            col_left, col_right = st.columns([1, 1])

            # --- Попап: Редактировать/Удалить ГК ---
            with col_left.popover("✏️ Редактировать головную компанию"):
                if not up_list:
                    st.info("Нет головных компаний для редактирования.")
                else:
                    names = [u.name for u in up_list]
                    sel_name = st.selectbox("Головная компания", options=names, index=0, key="edit_up_select")
                    sel = next((u for u in up_list if u.name == sel_name), None)

                    if sel:
                        new_name = st.text_input("Новое название", value=sel.name, key="edit_up_name")
                        new_balance = st.number_input(
                            "Баланс (₽)", value=float(getattr(sel, "balance_base_amount", 0.0) or 0.0),
                            step=100.0, format="%.2f", key="edit_up_balance"
                        )

                        c1, c2 = st.columns(2)

                        if c1.button("💾 Сохранить изменения", key="save_up_btn"):
                            try:
                                sel.name = new_name.strip()
                                sel.balance_base_amount = float(new_balance or 0.0)
                                session.add(sel)
                                session.commit()
                                st.success("Головная компания обновлена.")
                                st.rerun()
                            except Exception as e:
                                session.rollback()
                                st.error(f"Ошибка сохранения: {e}")

                        # Удаление ГК с отвязкой компаний
                        if c2.button("🗑 Удалить головную компанию", key="del_up_btn"):
                            try:
                                # 1) отвязать все компании этой ГК
                                session.execute(
                                    update(company.Company)
                                    .where(company.Company.up_company_id == sel.id)
                                    .values(up_company_id=None)
                                )
                                session.flush()
                                # 2) удалить саму ГК
                                session.delete(sel)
                                session.commit()
                                st.success("Головная компания удалена, компании отвязаны.")
                                st.rerun()
                            except Exception as e:
                                session.rollback()
                                st.error(f"Ошибка удаления: {e}")

            # --- Попап: Добавить ГК ---
            with col_right.popover("➕ Добавить головную компанию"):
                with st.form("form_add_up_company"):
                    up_name = st.text_input("Название головной компании")
                    up_balance = st.number_input("Начальный баланс (₽)", value=0.0, step=100.0, format="%.2f")
                    submit_add = st.form_submit_button("Добавить")
                    if submit_add:
                        if not up_name.strip():
                            st.error("Название обязательно.")
                        else:
                            try:
                                # проверка дубля
                                exists = (
                                    session.query(up_company.UpCompany)
                                    .filter(up_company.UpCompany.name == up_name.strip())
                                    .first()
                                )
                                if exists:
                                    st.warning("Такая головная компания уже существует.")
                                else:
                                    obj = up_company.UpCompany(
                                        name=up_name.strip(),
                                        balance_base_amount=float(up_balance or 0.0),
                                    )
                                    session.add(obj)
                                    session.commit()
                                    st.success("Головная компания добавлена.")
                                    st.rerun()
                            except Exception as e:
                                session.rollback()
                                st.error(f"Ошибка добавления: {e}")

        # ========== ТАБ 2: Компании ==========
        with tabs[1]:
            st.subheader("Компании")

            # справочник ГК
            up_all = (
                session.query(up_company.UpCompany)
                .order_by(up_company.UpCompany.name.asc())
                .all()
            )
            up_name_by_id = {u.id: u.name for u in up_all}
            up_names = [""] + [u.name for u in up_all]

            # Таблица компаний: Название, ИНН, Головная
            comp_list = (
                session.query(company.Company)
                .order_by(company.Company.name.asc())
                .all()
            )
            df_comp = pd.DataFrame(
                [
                    {
                        "Название": c.name,
                        "ИНН": c.inn,
                        "Головная компания": up_name_by_id.get(c.up_company_id, ""),
                    }
                    for c in comp_list
                ]
            )
            st.dataframe(df_comp, use_container_width=True, hide_index=True)

            cL, cR = st.columns([1, 1])

            # --- Попап: Редактировать/Удалить компанию ---
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
                            "Головная компания", options=up_names,
                            index=(up_names.index(cur_up_name) if cur_up_name in up_names else 0),
                            key="edit_comp_up"
                        )

                        b1, b2 = st.columns(2)

                        if b1.button("💾 Сохранить", key="save_comp_btn"):
                            try:
                                sel_c.name = new_c_name.strip()
                                sel_c.inn = (new_c_inn or "").strip()
                                # привязка к ГК
                                uc = next((u for u in up_all if u.name == new_up_name), None) if new_up_name else None
                                sel_c.up_company_id = uc.id if uc else None
                                session.add(sel_c)
                                session.commit()
                                st.success("Компания обновлена.")
                                st.rerun()
                            except Exception as e:
                                session.rollback()
                                st.error(f"Ошибка сохранения: {e}")

                        if b2.button("🗑 Удалить компанию", key="del_comp_btn"):
                            try:
                                session.delete(sel_c)
                                session.commit()
                                st.success("Компания удалена.")
                                st.rerun()
                            except Exception as e:
                                session.rollback()
                                st.error(f"Ошибка удаления: {e}")

            # --- Попап: Добавить компанию ---
            with cR.popover("➕ Добавить компанию"):
                with st.form("form_add_company"):
                    c_name = st.text_input("Название компании")
                    c_inn = st.text_input("ИНН")
                    c_up_name = st.selectbox("Головная компания", options=up_names, index=0)
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
                                )
                                session.add(obj)
                                session.commit()
                                st.success("Компания добавлена.")
                                st.rerun()
                            except Exception as e:
                                session.rollback()
                                st.error(f"Ошибка добавления: {e}")

    finally:
        session.close()
