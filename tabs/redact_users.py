import streamlit as st
import pandas as pd
from sqlalchemy.orm import selectinload

from core.db import SessionLocal
from db_models.user import User
from db_models.user_company import UserCompany
from db_models.user_category import UserCategory
from db_models import up_company as m_up
from db_models import category as m_cat
from utils.auth import _hash_password


def redact_users() -> None:
    st.subheader("Пользователи и доступы")

    with SessionLocal() as session:
        users = (
            session.query(User)
            .options(
                selectinload(User.company_links),
                selectinload(User.category_links),
            )
            .order_by(User.username.asc())
            .all()
        )
        companies = session.query(m_up.UpCompany).order_by(m_up.UpCompany.name.asc()).all()
        categories = session.query(m_cat.Category).order_by(m_cat.Category.name.asc()).all()

        _render_users_table(users, companies, categories)

        col_left, col_right = st.columns([1, 1])
        with col_left.popover("➕ Добавить пользователя"):
            _render_add_user(session, users, companies, categories)

        with col_right.popover("✏️ Редактировать пользователя"):
            _render_edit_user(session, users, companies, categories)


def _render_users_table(users, companies, categories) -> None:
    if not users:
        st.info("Пользователи ещё не созданы.")
        return

    company_map = {c.id: c.name for c in companies}
    category_map = {c.id: c.name for c in categories}
    rows = []
    for u in users:
        rows.append(
            {
                "Логин": u.username,
                "Роль": u.role,
                "Активен": "✅" if u.is_active else "—",
                "Компании": ", ".join(sorted({company_map.get(link.up_company_id, "") for link in u.company_links if company_map.get(link.up_company_id)})),
                "Категории": ", ".join(sorted({category_map.get(link.category_id, "") for link in u.category_links if category_map.get(link.category_id)})),
            }
        )
    df = pd.DataFrame(rows, columns=["Логин", "Роль", "Активен", "Компании", "Категории"])
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_add_user(session, users, companies, categories) -> None:
    username = st.text_input("Логин")
    password = st.text_input("Пароль", type="password")
    role = st.selectbox("Роль", options=["admin", "manager"], index=1)
    is_active = st.checkbox("Активен", value=True, key="user_add_active")

    companies_options = {c.name: c.id for c in companies}
    categories_options = {c.name: c.id for c in categories}

    allowed_company_names = st.multiselect(
        "Доступные компании",
        options=list(companies_options.keys()),
        key="user_add_companies",
    )
    allowed_category_names = st.multiselect(
        "Доступные категории",
        options=list(categories_options.keys()),
        key="user_add_categories",
    )

    if st.button("Создать пользователя", type="primary", key="user_add_submit"):
        if not username or not password:
            st.warning("Заполните логин и пароль.")
            return
        if any(u.username == username for u in users):
            st.error("Пользователь с таким логином уже существует.")
            return

        try:
            user = User(
                username=username,
                password_hash=_hash_password(password),
                role=role,
                is_active=is_active,
            )
            session.add(user)
            session.flush()  # получаем id

            if role != "admin":
                _replace_companies(session, user.id, [companies_options[n] for n in allowed_company_names])
                _replace_categories(session, user.id, [categories_options[n] for n in allowed_category_names])

            session.commit()
            st.success("Пользователь создан.")
            st.rerun()
        except Exception as exc:
            session.rollback()
            st.error(f"Не удалось создать пользователя: {exc}")


def _render_edit_user(session, users, companies, categories) -> None:
    if not users:
        st.info("Нет пользователей для редактирования.")
        return

    user_labels = [f"{u.username} ({u.role})" for u in users]
    selected_label = st.selectbox("Пользователь", options=user_labels)
    user = users[user_labels.index(selected_label)]

    new_username = st.text_input("Логин", value=user.username)
    new_password = st.text_input("Новый пароль (если нужно сменить)", type="password")
    role = st.selectbox("Роль", options=["admin", "manager"], index=0 if user.role == "admin" else 1)
    is_active = st.checkbox("Активен", value=bool(user.is_active), key=f"user_edit_active_{user.id}")

    companies_options = {c.name: c.id for c in companies}
    categories_options = {c.name: c.id for c in categories}
    current_company_names = [c.name for c in companies if any(link.up_company_id == c.id for link in user.company_links)]
    current_category_names = [c.name for c in categories if any(link.category_id == c.id for link in user.category_links)]

    allowed_company_names = st.multiselect(
        "Доступные компании",
        options=list(companies_options.keys()),
        default=current_company_names,
        key=f"user_edit_companies_{user.id}",
    )
    allowed_category_names = st.multiselect(
        "Доступные категории",
        options=list(categories_options.keys()),
        default=current_category_names,
        key=f"user_edit_categories_{user.id}",
    )

    delete_flag = st.checkbox("Удалить пользователя", value=False, key=f"user_edit_delete_{user.id}")

    if st.button("Сохранить изменения", type="primary", key=f"user_edit_submit_{user.id}"):
        try:
            if delete_flag:
                session.query(UserCompany).filter(UserCompany.user_id == user.id).delete()
                session.query(UserCategory).filter(UserCategory.user_id == user.id).delete()
                session.delete(user)
                session.commit()
                st.success("Пользователь удалён.")
                st.rerun()
                return

            if not new_username:
                st.warning("Логин не может быть пустым.")
                return
            if new_username != user.username and any(u.username == new_username for u in users):
                st.error("Пользователь с таким логином уже существует.")
                return

            user.username = new_username
            if new_password:
                user.password_hash = _hash_password(new_password)
            user.role = role
            user.is_active = is_active

            session.flush()

            # Обновляем доступы только для не-admin
            if role == "admin":
                session.query(UserCompany).filter(UserCompany.user_id == user.id).delete()
                session.query(UserCategory).filter(UserCategory.user_id == user.id).delete()
            else:
                _replace_companies(session, user.id, [companies_options[n] for n in allowed_company_names])
                _replace_categories(session, user.id, [categories_options[n] for n in allowed_category_names])

            session.commit()
            st.success("Изменения сохранены.")
            st.rerun()
        except Exception as exc:
            session.rollback()
            st.error(f"Не удалось сохранить изменения: {exc}")


def _replace_companies(session, user_id: int, company_ids):
    session.query(UserCompany).filter(UserCompany.user_id == user_id).delete()
    for cid in company_ids:
        session.add(UserCompany(user_id=user_id, up_company_id=cid))


def _replace_categories(session, user_id: int, category_ids):
    session.query(UserCategory).filter(UserCategory.user_id == user_id).delete()
    for cid in category_ids:
        session.add(UserCategory(user_id=user_id, category_id=cid))
