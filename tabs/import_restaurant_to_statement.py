import datetime as dt
from decimal import Decimal
from typing import Dict, List, Optional

import pandas as pd
import streamlit as st
from sqlalchemy.orm import selectinload
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

from core.db import SessionLocal
from core.months import ru_label_from_rm
from db_models import restaurant_expense as m_re
from db_models import statement as m_st
from db_models import up_company as m_up
from db_models import company as m_company


def render_transfer_restaurant_to_statement_tab() -> None:
    st.subheader("Перенос ресторанных расходов в Statement")

    role = (st.session_state.get("user") or {}).get("role", "")
    if role not in ("admin", "manager"):
        st.warning("У вас нет доступа к этой странице.")
        return

    with SessionLocal() as session:
        up_obj = _select_up_company(session)
        if not up_obj:
            return

        month_rm, month_label = _select_report_month(session, up_obj)
        st.caption(f"Учётный месяц: {month_label}")
        expenses = _load_expenses(session, up_obj, month_rm)
        _ensure_rest_statements_have_company(session, up_obj)

        expense_map = {exp.id: exp for exp in expenses}
        selected_ids = _render_expenses_grid(expenses, month_label)

        _render_transfer_controls(session, up_obj, expense_map, selected_ids)


def _select_up_company(session) -> Optional[m_up.UpCompany]:
    ups = session.query(m_up.UpCompany).order_by(m_up.UpCompany.name.asc()).all()
    allowed_ids = st.session_state.get("allowed_company_ids")
    role = (st.session_state.get("user") or {}).get("role", "")
    if role != "admin" and allowed_ids:
        ups = [u for u in ups if u.id in allowed_ids]
    if role != "admin" and not allowed_ids:
        st.warning("Нет доступных компаний для ваших прав.")
        return None
    if not ups:
        st.warning("Нет доступных компаний для ваших прав.")
        return None

    names = [u.name for u in ups]
    choice = st.selectbox("Головная компания", options=names, key="rest_transfer_up_select")
    return next((u for u in ups if u.name == choice), None)


def _select_report_month(session, up_obj: m_up.UpCompany):
    today_rm = dt.date.today().strftime("%Y-%m")
    rows = (
        session.query(m_re.RestaurantExpense.report_month)
        .filter(m_re.RestaurantExpense.up_company_id == up_obj.id)
        .distinct()
        .all()
    )
    months = {row[0] for row in rows if row[0]}
    if not months:
        months = {today_rm}
    months_sorted = sorted(months, reverse=True)
    labels = [ru_label_from_rm(rm) for rm in months_sorted]
    today_label = ru_label_from_rm(today_rm)
    default_index = labels.index(today_label) if today_label in labels else 0
    label = st.selectbox(
        "Учётный месяц",
        options=labels,
        index=default_index,
        key=f"rest_transfer_month_{up_obj.id}",
    )
    rm = months_sorted[labels.index(label)]
    return rm, label


def _load_expenses(session, up_obj: m_up.UpCompany, report_month: str) -> List[m_re.RestaurantExpense]:
    return (
        session.query(m_re.RestaurantExpense)
        .options(
            selectinload(m_re.RestaurantExpense.category),
            selectinload(m_re.RestaurantExpense.payment_method),
        )
        .filter(
            m_re.RestaurantExpense.up_company_id == up_obj.id,
            m_re.RestaurantExpense.report_month == report_month,
        )
        .order_by(m_re.RestaurantExpense.date.asc(), m_re.RestaurantExpense.id.asc())
        .all()
    )


def _render_expenses_grid(expenses: List[m_re.RestaurantExpense], month_label: str) -> List[int]:
    if not expenses:
        st.info("За выбранный месяц расходов нет.")
        return []

    records = []
    for exp in expenses:
        records.append(
            {
                "ID": exp.id,
                "Дата": exp.date.strftime("%d.%m.%Y") if exp.date else "",
                "Учётный месяц": ru_label_from_rm(exp.report_month),
                "Тип": exp.operation_type or "",
                "Сумма": float(exp.amount),
                "Категория": exp.category.name if exp.category else "",
                "Метод оплаты": exp.payment_method.name if exp.payment_method else "",
                "Назначение": exp.purpose or "",
                "Перенесена": bool(getattr(exp, "transferred_to_statement", False)),
                "Комментарий": exp.comment or "",
            }
        )

    df = pd.DataFrame(records)
    builder = GridOptionsBuilder.from_dataframe(df)
    builder.configure_selection("multiple", use_checkbox=True)
    builder.configure_column("ID", pinned="left", width=90)
    builder.configure_pagination(enabled=True, paginationAutoPageSize=False, paginationPageSize=25)
    builder.configure_column("Перенесена", cellDataType="bool")
    grid = AgGrid(
        df,
        gridOptions=builder.build(),
        height=400,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        use_container_width=True,
    )
    selected_rows = grid.get("selected_rows", [])
    if isinstance(selected_rows, pd.DataFrame):
        selected_rows = selected_rows.to_dict("records")
    elif not selected_rows:
        selected_rows = []
    selected_ids = []
    blocked = []
    for row in selected_rows:
        try:
            row_id = int(row.get("ID"))
        except (TypeError, ValueError):
            continue
        transferred = str(row.get("Перенесена", "")).lower() in ("true", "1", "yes")
        if transferred:
            blocked.append(row_id)
        else:
            selected_ids.append(row_id)

    if blocked:
        st.warning(f"Строки с ID {blocked} уже перенесены и будут пропущены.")
    return selected_ids


def _primary_company(session, up_obj: m_up.UpCompany) -> Optional[m_company.Company]:
    company_obj = (
        session.query(m_company.Company)
        .filter(
            m_company.Company.up_company_id == up_obj.id,
            m_company.Company.is_primary.is_(True),
        )
        .first()
    )
    return company_obj if company_obj and company_obj.inn else None


def _ensure_rest_statements_have_company(session, up_obj: m_up.UpCompany) -> None:
    primary_company = _primary_company(session, up_obj)
    if not primary_company:
        return
    rows = (
        session.query(m_st.Statement)
        .filter(
            m_st.Statement.up_company_id == up_obj.id,
            m_st.Statement.doc_number.like("REST-%"),
            m_st.Statement.payer_company_id.is_(None),
        )
        .all()
    )
    if not rows:
        return
    for stmt in rows:
        stmt.payer_company_id = primary_company.id
        if not stmt.payer_inn:
            stmt.payer_inn = primary_company.inn
    session.commit()


def _render_transfer_controls(
    session,
    up_obj: m_up.UpCompany,
    expense_map: Dict[int, m_re.RestaurantExpense],
    selected_ids: List[int],
) -> None:
    st.markdown("#### Перенос выделенных расходов")
    if not expense_map:
        st.caption("Записей для переноса нет.")
        return

    btn_disabled = not selected_ids
    if st.button("Перенести в Statement", type="primary", disabled=btn_disabled):
        primary_company = _primary_company(session, up_obj)
        if not primary_company:
            st.error("Не удалось определить основную компанию — перенос невозможен.")
            return
        try:
            transferred = _transfer_to_statement(
                session,
                [expense_map[eid] for eid in selected_ids if eid in expense_map],
                primary_company,
            )
            st.success(f"Перенесено операций: {transferred}")
            st.rerun()
        except Exception as exc:
            session.rollback()
            st.error(f"Не удалось выполнить перенос: {exc}")
            st.error(f"Не удалось перенести: {exc}")


def _transfer_to_statement(
    session,
    expenses: List[m_re.RestaurantExpense],
    payer_company: m_company.Company,
) -> int:
    count = 0
    for exp in expenses:
        if getattr(exp, "transferred_to_statement", False):
            continue
        doc_number = f"REST-{exp.id}"
        amount = Decimal(str(exp.amount or 0))
        payer_inn = payer_company.inn
        row_id = f"{exp.date.isoformat() if exp.date else ''}|{doc_number}|{float(amount):.2f}|{payer_inn}|"
        st_obj = m_st.Statement(
            row_id=row_id,
            date=exp.date or dt.date.today(),
            report_month=exp.report_month,
            doc_number=doc_number,
            payer_inn=payer_inn,
            payer_company_id=payer_company.id,
            receiver_inn=None,
            purpose=exp.purpose or "",
            amount=float(amount),
            operation_type=exp.operation_type or "Списание",
            comment=exp.comment or "",
            recorded=bool(exp.recorded),
            up_company_id=exp.up_company_id,
            group_id=exp.group_id,
            category_id=exp.category_id,
        )
        session.add(st_obj)
        exp.transferred_to_statement = True
        count += 1
    session.commit()
    return count
