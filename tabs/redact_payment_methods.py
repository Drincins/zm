import streamlit as st
from sqlalchemy import exists
from sqlalchemy.orm import selectinload

from core.db import SessionLocal
from db_models import payment_method as m_pm
from db_models import restaurant_payment_method as m_rpm
from db_models import up_company as m_up


def redact_payment_methods() -> None:
    st.title("Методы оплаты ресторана")

    with SessionLocal() as session:
        methods = (
            session.query(m_pm.PaymentMethod)
            .options(selectinload(m_pm.PaymentMethod.company_links).selectinload(m_rpm.RestaurantPaymentMethod.up_company))
            .order_by(m_pm.PaymentMethod.is_active.desc(), m_pm.PaymentMethod.name.asc())
            .all()
        )
        companies = session.query(m_up.UpCompany).order_by(m_up.UpCompany.name.asc()).all()

        _render_methods_list(methods)
        st.divider()
        _render_actions(session, methods, companies)


def _render_methods_list(methods):
    st.subheader("Список методов оплаты")
    if not methods:
        st.info("Методы оплаты ещё не добавлены.")
        return

    rows = []
    for pm in methods:
        company_names = sorted({link.up_company.name for link in pm.company_links if link.up_company})
        rows.append(
            {
                "ID": pm.id,
                "Название": pm.name,
                "Описание": pm.description or "",
                "Активен": "✅" if pm.is_active else "",
                "Компании": ", ".join(company_names) if company_names else "—",
            }
        )
    st.table(rows)


def _render_actions(session, methods, companies):
    st.subheader("Действия")
    pop_fn = getattr(st, "popover", None)
    col_add, col_edit = st.columns(2)

    with col_add:
        if callable(pop_fn):
            with pop_fn("➕ Добавить метод"):
                _add_method_form(session, companies)
        else:
            with st.expander("➕ Добавить метод", expanded=False):
                _add_method_form(session, companies)

    with col_edit:
        if not methods:
            st.button("✏️ Редактировать метод", disabled=True, help="Нет методов для редактирования")
            return

        if callable(pop_fn):
            with pop_fn("✏️ Редактировать метод"):
                _render_edit_method(session, methods, companies)
        else:
            with st.expander("✏️ Редактировать метод", expanded=False):
                _render_edit_method(session, methods, companies)


def _render_add_method(session, companies):
    # оставлено для совместимости (не используется напрямую)
    dialog_fn = getattr(st, "dialog", None)
    if callable(dialog_fn):
        open_clicked = st.button("➕ Добавить метод", type="primary")
        if open_clicked:
            @dialog_fn("Новый метод оплаты")
            def _show_add_dialog():
                _add_method_form(session, companies)
            _show_add_dialog()
    else:
        with st.expander("Добавить метод", expanded=False):
            _add_method_form(session, companies)


def _add_method_form(session, companies):
    with st.form("payment_method_add"):
        name = st.text_input("Название", key="pm_add_name")
        description = st.text_area("Описание", key="pm_add_desc", height=60)
        is_active = st.checkbox("Активен", value=True, key="pm_add_active")
        company_options = {c.name: c.id for c in companies}
        selected_company_names = st.multiselect("Привязать к компаниям", options=list(company_options.keys()), key="pm_add_companies")

        default_company_name = st.selectbox(
            "По умолчанию (опционально)",
            options=["— нет —"] + selected_company_names,
            key="pm_add_default",
        )

        submitted = st.form_submit_button("Сохранить", type="primary")
        if not submitted:
            return

        if not name.strip():
            st.warning("Название не может быть пустым.")
            return

        try:
            exists_query = session.query(exists().where(m_pm.PaymentMethod.name == name.strip())).scalar()
            if exists_query:
                st.warning("Метод с таким названием уже существует.")
                return

            pm_obj = m_pm.PaymentMethod(
                name=name.strip(),
                description=description or None,
                is_active=is_active,
            )
            session.add(pm_obj)
            session.flush()

            selected_ids = {company_options[n] for n in selected_company_names}
            default_id = company_options.get(default_company_name) if default_company_name != "— нет —" else None

            for cid in selected_ids:
                if default_id == cid:
                    session.query(m_rpm.RestaurantPaymentMethod).filter(m_rpm.RestaurantPaymentMethod.up_company_id == cid).update({m_rpm.RestaurantPaymentMethod.is_default: False})
                session.add(
                    m_rpm.RestaurantPaymentMethod(
                        up_company_id=cid,
                        payment_method_id=pm_obj.id,
                        is_default=(cid == default_id),
                    )
                )

            session.commit()
            st.success("Метод и привязки добавлены.")
            _rerun()
        except Exception as exc:
            session.rollback()
            st.error(f"Не удалось добавить метод: {exc}")


def _render_edit_method(session, methods, companies):
    st.subheader("Редактировать метод")
    if not methods:
        st.info("Методы оплаты ещё не добавлены.")
        return

    method_options = {pm.name: pm.id for pm in methods}
    selected_name = st.selectbox("Метод", options=list(method_options.keys()), key="pm_edit_select")
    selected = next((pm for pm in methods if pm.name == selected_name), None)
    if not selected:
        st.warning("Метод не найден.")
        return

    pop_fn = getattr(st, "popover", None)
    if callable(pop_fn):
        with pop_fn("✏️ Открыть форму редактирования"):
            _edit_method_form(session, selected, companies)
    else:
        with st.expander(f"✏️ Редактировать «{selected.name}»", expanded=False):
            _edit_method_form(session, selected, companies)


def _edit_method_form(session, pm_obj: m_pm.PaymentMethod, companies):
    existing_links = {link.up_company_id for link in pm_obj.company_links}
    company_options = {c.name: c.id for c in companies}

    with st.form(f"payment_method_edit_{pm_obj.id}"):
        name = st.text_input("Название", value=pm_obj.name, key=f"pm_edit_name_{pm_obj.id}")
        description = st.text_area("Описание", value=pm_obj.description or "", height=60, key=f"pm_edit_desc_{pm_obj.id}")
        is_active = st.checkbox("Активен", value=bool(pm_obj.is_active), key=f"pm_edit_active_{pm_obj.id}")
        selected_company_names = st.multiselect(
            "Привязать к компаниям",
            options=list(company_options.keys()),
            default=[c.name for c in companies if c.id in existing_links],
            key=f"pm_edit_companies_{pm_obj.id}",
        )

        default_company_name = st.selectbox(
            "По умолчанию (опционально)",
            options=["— нет —"] + selected_company_names,
            index=(["— нет —"] + selected_company_names).index(
                next(
                    (link.up_company.name for link in pm_obj.company_links if link.is_default and link.up_company),
                    "— нет —",
                )
            ),
            key=f"pm_edit_default_{pm_obj.id}",
        )

        delete_flag = st.checkbox("Удалить метод (удалит привязки)", value=False, key=f"pm_edit_delete_{pm_obj.id}")

        submitted = st.form_submit_button("Сохранить", type="primary")
        if not submitted:
            return

        try:
            if delete_flag:
                for link in list(pm_obj.company_links):
                    session.delete(link)
                session.delete(pm_obj)
                session.commit()
                st.success("Метод удалён.")
                _rerun()
                return

            if not name.strip():
                st.warning("Название не может быть пустым.")
                return

            # Проверка уникальности имени
            exists_query = (
                session.query(exists().where((m_pm.PaymentMethod.name == name.strip()) & (m_pm.PaymentMethod.id != pm_obj.id))).scalar()
            )
            if exists_query:
                st.warning("Метод с таким названием уже существует.")
                return

            pm_obj.name = name.strip()
            pm_obj.description = description or None
            pm_obj.is_active = is_active

            selected_ids = {company_options[n] for n in selected_company_names}
            default_id = company_options.get(default_company_name) if default_company_name != "— нет —" else None

            # Удаляем лишние привязки
            for link in list(pm_obj.company_links):
                if link.up_company_id not in selected_ids:
                    session.delete(link)

            # Добавляем/обновляем нужные привязки
            for cid in selected_ids:
                link = next((l for l in pm_obj.company_links if l.up_company_id == cid), None)
                if not link:
                    if default_id == cid:
                        session.query(m_rpm.RestaurantPaymentMethod).filter(m_rpm.RestaurantPaymentMethod.up_company_id == cid).update({m_rpm.RestaurantPaymentMethod.is_default: False})
                    session.add(
                        m_rpm.RestaurantPaymentMethod(
                            up_company_id=cid,
                            payment_method_id=pm_obj.id,
                            is_default=(cid == default_id),
                        )
                    )
                else:
                    if default_id == cid:
                        session.query(m_rpm.RestaurantPaymentMethod).filter(m_rpm.RestaurantPaymentMethod.up_company_id == cid).update({m_rpm.RestaurantPaymentMethod.is_default: False})
                    link.is_default = (cid == default_id)

            session.commit()
            st.success("Изменения сохранены.")
            _rerun()
        except Exception as exc:
            session.rollback()
            st.error(f"Не удалось сохранить изменения: {exc}")


def _rerun():
    rerun_fn = getattr(st, "rerun", None)
    if callable(rerun_fn):
        rerun_fn()
    else:
        st.experimental_rerun()
