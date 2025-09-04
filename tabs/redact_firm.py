# tabs/redact_firm.py
import streamlit as st
import pandas as pd
from core.db import SessionLocal
from db_models import firm, category


def redact_firm():
    st.subheader("Фирмы")

    session = SessionLocal()
    try:
        # ---- Справочник категорий
        categories = session.query(category.Category).order_by(category.Category.name.asc()).all()
        cat_id_by_name = {c.name: c.id for c in categories}
        cat_names = list(cat_id_by_name.keys())

        # ---- Поисковые поля
        col_n, col_i = st.columns([2, 1])
        name_query = col_n.text_input("Поиск по названию", key="firm_search_name")
        inn_query = col_i.text_input("Поиск по ИНН", key="firm_search_inn")
        # ---- Фильтр по категории и сортировка
        col_c1, col_c2 = st.columns([2, 2])
        cat_filter = col_c1.multiselect(
            "Фильтр по категории",
            options=sorted(cat_names),
            default=[],
            key="firm_filter_cat",
        )
        sort_col = col_c2.selectbox(
            "Сортировка",
            options=["Название", "ИНН", "Категория"],
            index=0,
            key="firm_sort_col",
        )
        sort_desc = col_c2.checkbox("По убыванию", value=False, key="firm_sort_desc")

        # ---- Данные фирм
        firms_q = session.query(firm.Firm).order_by(firm.Firm.name.asc()).all()
        # Преобразуем в список словарей
        rows_all = []
        for f in firms_q:
            cat_name = ""
            if f.category_id:
                c = session.query(category.Category).get(f.category_id)
                cat_name = c.name if c else ""
            rows_all.append({
                "id": f.id,
                "Название": f.name,
                "ИНН": f.inn,
                "Категория": cat_name,
            })

        df = pd.DataFrame(rows_all)

        # ---- Фильтрация по поиску (без учета регистра)
        if not df.empty:
            if name_query:
                df = df[df["Название"].str.contains(name_query, case=False, na=False)]
            if inn_query:
                df = df[df["ИНН"].astype(str).str.contains(inn_query, case=False, na=False)]
            if cat_filter:
                df = df[df["Категория"].isin(cat_filter)]

        # ---- Таблица предпросмотра (без id, без индекса)
        view_df = df.drop(columns=["id"]) if "id" in df.columns else df
        st.dataframe(view_df, use_container_width=True, hide_index=True)
        # ---- Сортировка и вывод таблицы (без id, без индекса)
        if not df.empty:
            df = df.sort_values(by=sort_col, ascending=not sort_desc, kind="mergesort")
        view_df = df.drop(columns=["id"]) if "id" in df.columns else df
        st.dataframe(view_df, use_container_width=True, hide_index=True)

        colL, colR = st.columns([1, 1])

        # ================== РЕДАКТИРОВАТЬ / УДАЛИТЬ ==================
        with colL.popover("✏️ Редактировать фирму"):
            if df.empty:
                st.info("Нет фирм для редактирования (проверьте фильтры или добавьте новую).")
            else:
                # выбор из отфильтрованных
                label_list = [f"{r['ИНН']} — {r['Название']}" for _, r in df.sort_values("Название").iterrows()]
                sel_label = st.selectbox("Фирма", options=label_list, index=0, key="firm_edit_select")
                # найдём выбранную строку
                sel_row = df.iloc[label_list.index(sel_label)]
                sel_id = int(sel_row["id"])

                # текущие значения
                cur_name = sel_row["Название"] or ""
                cur_inn = sel_row["ИНН"] or ""
                cur_cat = sel_row["Категория"] or ""

                # поля редактирования
                new_name = st.text_input("Название", value=cur_name, key="firm_edit_name")
                new_inn = st.text_input("ИНН", value=cur_inn, key="firm_edit_inn")
                new_cat_name = st.selectbox(
                    "Категория", options=[""] + cat_names,
                    index=([""] + cat_names).index(cur_cat) if cur_cat in cat_names else 0,
                    key="firm_edit_cat"
                )

                c1, c2 = st.columns(2)

                if c1.button("💾 Сохранить", key="firm_save_btn"):
                    if not new_name.strip() or not new_inn.strip():
                        st.error("Заполните название и ИНН.")
                    else:
                        try:
                            # проверка дубля по ИНН (кроме текущей)
                            exists = session.query(firm.Firm).filter(
                                firm.Firm.inn == new_inn.strip(),
                                firm.Firm.id != sel_id
                            ).first()
                            if exists:
                                st.warning("Фирма с таким ИНН уже существует.")
                            else:
                                obj = session.query(firm.Firm).get(sel_id)
                                obj.name = new_name.strip()
                                obj.inn = new_inn.strip()
                                obj.category_id = cat_id_by_name.get(new_cat_name) if new_cat_name else None
                                session.add(obj)
                                session.commit()
                                st.success("Изменения сохранены.")
                                st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"Ошибка сохранения: {e}")

                if c2.button("🗑 Удалить фирму", key="firm_del_btn"):
                    try:
                        obj = session.query(firm.Firm).get(sel_id)
                        session.delete(obj)
                        session.commit()
                        st.success("Фирма удалена.")
                        st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"Ошибка удаления: {e}")

        # ================== ДОБАВИТЬ ==================
        with colR.popover("➕ Добавить фирму"):
            with st.form("firm_add_form"):
                add_name = st.text_input("Название компании")
                add_inn = st.text_input("ИНН")
                add_cat_name = st.selectbox("Категория", options=[""] + cat_names, index=0)

                submitted = st.form_submit_button("Добавить")
                if submitted:
                    if not add_name.strip() or not add_inn.strip():
                        st.error("Заполните название и ИНН.")
                    else:
                        try:
                            # проверка дубля по ИНН
                            exists = session.query(firm.Firm).filter(firm.Firm.inn == add_inn.strip()).first()
                            if exists:
                                st.warning("Фирма с таким ИНН уже существует.")
                            else:
                                obj = firm.Firm(
                                    name=add_name.strip(),
                                    inn=add_inn.strip(),
                                    category_id=cat_id_by_name.get(add_cat_name) if add_cat_name else None
                                )
                                session.add(obj)
                                session.commit()
                                st.success("Фирма добавлена.")
                                st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"Ошибка добавления: {e}")

    finally:
        session.close()
