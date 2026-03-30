from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import List

import pandas as pd
import streamlit as st

from core.db import SessionLocal
from core.months import ru_label_from_rm
from db_models import payment_link as m_pl
from db_models import up_company as m_up

STATUS_OPTIONS = {
    "received": "Поступили средства",
    "booked": "Бронирование завершено",
}


def render_payment_links_tab() -> None:
    role = (st.session_state.get("user") or {}).get("role", "")
    if role not in ("admin", "manager"):
        st.warning("У вас нет доступа к этой вкладке.")
        return

    with SessionLocal() as session:
        up_obj = _select_up_company(session)
        if not up_obj:
            st.info("Нет доступных компаний.")
            return

        flash = st.session_state.pop("paylinks_flash", None)
        if flash:
            st.success(flash)

        st.markdown("### Платёжные ссылки")
        st.caption("Выберите компанию, отфильтруйте по месяцам бронирования и платежа, управляйте записями.")

        all_links = _load_links(session, up_obj)

        booking_months = sorted({l.booking_date.strftime("%Y-%m") for l in all_links if l.booking_date})
        payment_months = sorted({l.payment_date.strftime("%Y-%m") for l in all_links if l.payment_date})
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            booking_choice = st.selectbox(
                "Месяц бронирования",
                options=["Все"] + booking_months,
                format_func=lambda rm: ru_label_from_rm(rm) if rm != "Все" else "Все",
                index=0,
            )
        with col_f2:
            payment_choice = st.selectbox(
                "Месяц платежа",
                options=["Все"] + payment_months,
                format_func=lambda rm: ru_label_from_rm(rm) if rm != "Все" else "Все",
                index=0,
            )

        links = [
            l
            for l in all_links
            if (booking_choice == "Все" or (l.booking_date and l.booking_date.strftime("%Y-%m") == booking_choice))
            and (payment_choice == "Все" or (l.payment_date and l.payment_date.strftime("%Y-%m") == payment_choice))
        ]

        total_all = sum(_to_decimal(l.amount) for l in links)
        total_booked = sum(_to_decimal(l.amount) for l in links if _auto_status(l) == "booked")
        total_unbooked = sum(_to_decimal(l.amount) for l in links if _auto_status(l) == "received")
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Всего поступило", f"{total_all:,.2f}".replace(",", " ").replace(".", ","))
        col_m2.metric("Использовано (бронирование завершено)", f"{total_booked:,.2f}".replace(",", " ").replace(".", ","))
        col_m3.metric("Не использовано (ожидает бронирования)", f"{total_unbooked:,.2f}".replace(",", " ").replace(".", ","))

        st.markdown("#### Список записей")
        if not links:
            st.info("Записей по выбранным фильтрам нет.")
        else:
            df = pd.DataFrame(
                [
                    {
                        "ID": l.id,
                        "Дата бронирования": l.booking_date.strftime("%d.%m.%Y") if l.booking_date else "",
                        "Дата платежа": l.payment_date.strftime("%d.%m.%Y") if l.payment_date else "",
                        "Сумма": f"{_to_decimal(l.amount):,.2f}".replace(",", " ").replace(".", ","),
                        "Статус": STATUS_OPTIONS.get(_auto_status(l), _auto_status(l)),
                    }
                    for l in links
                ]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("#### Действия")
        col_add, col_edit = st.columns(2)
        with col_add:
            _render_add_form(session, up_obj)
        with col_edit:
            _render_edit_form(session, up_obj, links)


def _select_up_company(session) -> m_up.UpCompany | None:
    ups = session.query(m_up.UpCompany).order_by(m_up.UpCompany.name.asc()).all()
    allowed_ids = st.session_state.get("allowed_company_ids")
    role = (st.session_state.get("user") or {}).get("role", "")
    if role != "admin" and allowed_ids:
        ups = [u for u in ups if u.id in allowed_ids]
    if role != "admin" and allowed_ids == []:
        st.warning("Нет разрешённых компаний.")
        return None
    if not ups:
        st.warning("Нет доступных компаний.")
        return None
    if role != "admin" and len(ups) == 1:
        st.markdown(
            f"<div style='font-weight:700; font-size:18px;'>Компания: {ups[0].name}</div>",
            unsafe_allow_html=True,
        )
        return ups[0]

    names = [u.name for u in ups]
    choice = st.selectbox("Компания", options=["- выберите -"] + names, index=0, key="paylink_up_select")
    return next((u for u in ups if u.name == choice), None)


def _render_add_form(session, up_obj: m_up.UpCompany) -> None:
    dialog_fn = getattr(st, "dialog", None)

    def _form():
        today = dt.date.today()
        raw_booking = st.text_input(
            "Дата бронирования (ДД.ММ.ГГГГ)",
            value=today.strftime("%d.%m.%Y"),
            key=f"paylink_add_booking_{up_obj.id}",
        )
        raw_payment = st.text_input(
            "Дата платежа (ДД.ММ.ГГГГ)",
            value=today.strftime("%d.%m.%Y"),
            key=f"paylink_add_payment_{up_obj.id}",
        )
        booking_date = _parse_date(raw_booking)
        payment_date = _parse_date(raw_payment)
        amount_value = st.number_input("Сумма", min_value=0.0, step=100.0, format="%.2f", key=f"paylink_add_amount_{up_obj.id}")
        submit = st.form_submit_button("Добавить", type="primary")
        if submit:
            if not booking_date or not payment_date:
                st.warning("Введите даты в формате ДД.ММ.ГГГГ.")
                return
            if amount_value <= 0:
                st.warning("Сумма должна быть положительной.")
                return
            try:
                session.add(
                    m_pl.PaymentLink(
                        up_company_id=up_obj.id,
                        booking_date=booking_date,
                        payment_date=payment_date,
                        report_month=f"{booking_date.year:04d}-{booking_date.month:02d}",
                        amount=Decimal(str(amount_value)),
                        status=_auto_status_dates(booking_date),
                    )
                )
                session.commit()
                st.session_state["paylinks_flash"] = "Запись добавлена."
                st.rerun()
            except Exception as exc:
                session.rollback()
                st.error(f"Не удалось добавить запись: {exc}")

    if dialog_fn and callable(dialog_fn):
        if st.button("Добавить запись", type="primary", key=f"paylink_add_btn_{up_obj.id}"):
            @dialog_fn("Добавить платёжную ссылку")
            def _show():
                with st.form(f"paylink_add_{up_obj.id}", border=True):
                    _form()
            _show()
    else:
        with st.expander("Добавить запись", expanded=False):
            with st.form(f"paylink_add_{up_obj.id}", border=True):
                _form()


def _render_edit_form(session, up_obj: m_up.UpCompany, links: List[m_pl.PaymentLink]) -> None:
    if not links:
        st.info("Нет записей для редактирования.")
        return

    options = {link.id: f"ID {link.id} | {link.booking_date} | {link.payment_date} | {_to_decimal(link.amount)}" for link in links}
    dialog_fn = getattr(st, "dialog", None)

    def _form(target: m_pl.PaymentLink):
        raw_booking = st.text_input(
            "Дата бронирования (ДД.ММ.ГГГГ)",
            value=(target.booking_date.strftime("%d.%m.%Y") if target.booking_date else dt.date.today().strftime("%d.%m.%Y")),
            key=f"paylink_edit_booking_{target.id}",
        )
        raw_payment = st.text_input(
            "Дата платежа (ДД.ММ.ГГГГ)",
            value=(target.payment_date.strftime("%d.%m.%Y") if target.payment_date else dt.date.today().strftime("%d.%m.%Y")),
            key=f"paylink_edit_payment_{target.id}",
        )
        booking_date = _parse_date(raw_booking)
        payment_date = _parse_date(raw_payment)
        amount_value = st.number_input(
            "Сумма",
            min_value=0.0,
            value=float(_to_decimal(target.amount)),
            step=100.0,
            format="%.2f",
            key=f"paylink_edit_amount_{target.id}",
        )
        delete_flag = st.checkbox("Удалить запись", value=False, key=f"paylink_edit_delete_{target.id}")
        submit = st.form_submit_button("Сохранить", type="primary")

        if submit:
            if not booking_date or not payment_date:
                st.warning("Введите даты в формате ДД.ММ.ГГГГ.")
                return
            if amount_value <= 0:
                st.warning("Сумма должна быть положительной.")
                return
            try:
                if delete_flag:
                    session.delete(target)
                    session.commit()
                    st.session_state["paylinks_flash"] = "Запись удалена."
                    st.rerun()
                    return
                target.booking_date = booking_date
                target.payment_date = payment_date
                target.report_month = f"{booking_date.year:04d}-{booking_date.month:02d}"
                target.amount = Decimal(str(amount_value))
                target.status = _auto_status_dates(booking_date)
                session.commit()
                st.session_state["paylinks_flash"] = "Запись сохранена."
                st.rerun()
            except Exception as exc:
                session.rollback()
                st.error(f"Не удалось сохранить запись: {exc}")

    if dialog_fn and callable(dialog_fn):
        if st.button("Редактировать / удалить", key=f"paylink_edit_btn_{up_obj.id}"):
            @dialog_fn("Редактировать платёжную ссылку")
            def _show():
                selected_id = st.selectbox("Выберите запись", options=list(options.keys()), format_func=options.get)
                target = next((l for l in links if l.id == selected_id), None)
                if not target:
                    st.warning("Запись не найдена.")
                    return
                with st.form(f"paylink_edit_{up_obj.id}_{selected_id}", border=True):
                    _form(target)
            _show()
    else:
        with st.expander("Редактировать / удалить", expanded=False):
            selected_id = st.selectbox("Выберите запись", options=list(options.keys()), format_func=options.get)
            target = next((l for l in links if l.id == selected_id), None)
            if not target:
                st.warning("Запись не найдена.")
                return
            with st.form(f"paylink_edit_{up_obj.id}_{selected_id}", border=True):
                _form(target)


def _load_links(session, up_obj: m_up.UpCompany) -> List[m_pl.PaymentLink]:
    return (
        session.query(m_pl.PaymentLink)
        .filter(m_pl.PaymentLink.up_company_id == up_obj.id)
        .order_by(m_pl.PaymentLink.booking_date.desc(), m_pl.PaymentLink.id.desc())
        .all()
    )


def _auto_status(link: m_pl.PaymentLink) -> str:
    return _auto_status_dates(link.booking_date)


def _auto_status_dates(booking_date: dt.date | None) -> str:
    if booking_date and booking_date <= dt.date.today():
        return "booked"
    return "received"


def _parse_date(raw: str) -> dt.date | None:
    try:
        return dt.datetime.strptime(raw.strip(), "%d.%m.%Y").date()
    except Exception:
        return None


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")
