import streamlit as st
import pandas as pd
from core.db import SessionLocal
from db_models import group


def redact_group():
    st.subheader("Группы")

    with SessionLocal() as session:
        # ---- Таблица предпросмотра (без индекса и id)
        groups = (
            session.query(group.Group)
            .order_by(group.Group.name.asc())
            .all()
        )
        df = pd.DataFrame(
            [{"Код": g.code, "Название": g.name} for g in groups]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

        col_left, col_right = st.columns([1, 1])

        # -------- РЕДАКТИРОВАТЬ / УДАЛИТЬ --------
        with col_left.popover("✏️ Редактировать группу"):
            if not groups:
                st.info("Нет групп для редактирования.")
            else:
                names = [f"{g.code} — {g.name}" for g in groups]
                sel = st.selectbox("Группа", options=names, index=0, key="grp_edit_select")
                # находим выбранный объект
                sel_obj = groups[names.index(sel)]

                new_code = st.text_input("Код группы", value=sel_obj.code, key="grp_edit_code")
                new_name = st.text_input("Название группы", value=sel_obj.name, key="grp_edit_name")

                c1, c2 = st.columns(2)
                if c1.button("💾 Сохранить", key="grp_save_btn"):
                    try:
                        sel_obj.code = new_code.strip()
                        sel_obj.name = new_name.strip()
                        session.add(sel_obj)
                        session.commit()
                        st.success("Группа обновлена.")
                        st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"Ошибка сохранения: {e}")

                if c2.button("🗑 Удалить", key="grp_del_btn"):
                    try:
                        session.delete(sel_obj)
                        session.commit()
                        st.success("Группа удалена.")
                        st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"Ошибка удаления: {e}")

        # -------- ДОБАВИТЬ --------
        with col_right.popover("➕ Добавить группу"):
            new_code = st.text_input("Код группы", key="grp_new_code")
            new_name = st.text_input("Название группы", key="grp_new_name")

            if st.button("Создать", key="grp_create_btn"):
                if not new_code.strip():
                    st.error("Код обязателен.")
                elif not new_name.strip():
                    st.error("Название обязательно.")
                else:
                    # проверка дублей по коду или названию
                    exists = (
                        session.query(group.Group)
                        .filter(
                            (group.Group.code == new_code.strip()) |
                            (group.Group.name == new_name.strip())
                        ).first()
                    )
                    if exists:
                        st.warning("Группа с таким кодом или названием уже существует.")
                    else:
                        try:
                            obj = group.Group(code=new_code.strip(), name=new_name.strip())
                            session.add(obj)
                            session.commit()
                            st.success("Группа добавлена.")
                            st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"Ошибка добавления: {e}")
