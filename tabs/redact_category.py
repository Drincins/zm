import streamlit as st
import pandas as pd
from core.db import SessionLocal
from db_models import category, group


def redact_category():
    st.subheader("Категории")

    session = SessionLocal()
    try:
        # --- справочник групп
        groups_all = session.query(group.Group).order_by(group.Group.name.asc()).all()
        group_name_to_id = {g.name: g.id for g in groups_all}
        group_names = list(group_name_to_id.keys())

        # ---- Таблица предпросмотра категорий (без индекса и id)
        categories = (
            session.query(category.Category)
            .order_by(category.Category.name.asc())
            .all()
        )
        df = pd.DataFrame(
            [{
                "Код": c.code,
                "Название": c.name,
                "Группа": (session.query(group.Group).get(c.group_id).name if c.group_id else "")
            } for c in categories]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

        col_left, col_right = st.columns([1, 1])

        # -------- РЕДАКТИРОВАТЬ / УДАЛИТЬ --------
        with col_left.popover("✏️ Редактировать категорию"):
            if not categories:
                st.info("Нет категорий для редактирования.")
            else:
                cat_labels = [f"{c.code} — {c.name}" for c in categories]
                sel = st.selectbox("Категория", options=cat_labels, index=0, key="cat_edit_select")
                sel_obj = categories[cat_labels.index(sel)]

                new_code = st.text_input("Код категории", value=sel_obj.code, key="cat_edit_code")
                new_name = st.text_input("Название категории", value=sel_obj.name, key="cat_edit_name")

                cur_group_name = session.query(group.Group).get(sel_obj.group_id).name if sel_obj.group_id else ""
                new_group_name = st.selectbox(
                    "Группа", options=[""] + group_names,
                    index=([""] + group_names).index(cur_group_name) if cur_group_name in group_names else 0,
                    key="cat_edit_group"
                )

                c1, c2 = st.columns(2)
                if c1.button("💾 Сохранить", key="cat_save_btn"):
                    try:
                        sel_obj.code = new_code.strip()
                        sel_obj.name = new_name.strip()
                        sel_obj.group_id = group_name_to_id.get(new_group_name) if new_group_name else None
                        session.add(sel_obj)
                        session.commit()
                        st.success("Категория обновлена.")
                        st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"Ошибка сохранения: {e}")

                if c2.button("🗑 Удалить", key="cat_del_btn"):
                    try:
                        session.delete(sel_obj)
                        session.commit()
                        st.success("Категория удалена.")
                        st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"Ошибка удаления: {e}")

        # -------- ДОБАВИТЬ --------
        with col_right.popover("➕ Добавить категорию"):
            new_code = st.text_input("Код категории", key="cat_new_code")
            new_name = st.text_input("Название категории", key="cat_new_name")
            new_group_name = st.selectbox("Группа", options=[""] + group_names, index=0, key="cat_new_group")

            if st.button("Создать", key="cat_create_btn"):
                if not new_code.strip():
                    st.error("Код обязателен.")
                elif not new_name.strip():
                    st.error("Название обязательно.")
                else:
                    # проверка дублей по коду или названию
                    exists = (
                        session.query(category.Category)
                        .filter(
                            (category.Category.code == new_code.strip()) |
                            (category.Category.name == new_name.strip())
                        ).first()
                    )
                    if exists:
                        st.warning("Категория с таким кодом или названием уже существует.")
                    else:
                        try:
                            gid = group_name_to_id.get(new_group_name) if new_group_name else None
                            obj = category.Category(code=new_code.strip(), name=new_name.strip(), group_id=gid)
                            session.add(obj)
                            session.commit()
                            st.success("Категория добавлена.")
                            st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"Ошибка добавления: {e}")
    finally:
        session.close()
