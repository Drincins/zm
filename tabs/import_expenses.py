import calendar
import datetime as dt
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy.orm import selectinload

from core.db import SessionLocal
from core.months import ru_label_from_rm
from db_models import category as m_cat
from db_models import payment_method as m_pm
from db_models import restaurant_expense as m_re
from db_models import restaurant_payment_method as m_rpm
from db_models import up_company as m_up


def render_import_expenses_tab() -> None:
    """UI для учёта ресторанных расходов."""
    role = (st.session_state.get("user") or {}).get("role", "")
    if role not in ("admin", "manager"):
        st.warning("У вас нет доступа к этой странице.")
        return
    st.markdown("### Расходы ресторана")
    st.caption("Фиксируйте ежедневные расходы и привязывайте их к методам оплаты конкретных компаний.")

    with SessionLocal() as session:
        up_obj = _select_up_company(session)
        if not up_obj:
            st.info("Выберите головную компанию, чтобы продолжить.")
            return

        flash_msg = st.session_state.pop(_flash_key(up_obj.id), None)
        if flash_msg:
            st.success(flash_msg)

        month_rm, month_label = _select_report_month(session, up_obj)
        expenses = _load_expenses(session, up_obj, month_rm)
        categories = _allowed_categories(_load_categories(session))
        if categories is None:
            st.warning("Нет доступных категорий для ваших прав.")
            return
        expenses = _filter_expenses_by_categories(expenses, categories)
        company_methods_active = _load_company_payment_methods(session, up_obj, active_only=True)
        company_methods_all = _load_company_payment_methods(session, up_obj, active_only=False)

        st.markdown(f"#### Записи за {month_label}")
        _render_expenses_table(expenses)

        st.markdown("#### Действия")
        col_edit, col_add = st.columns(2)
        with col_edit:
            _render_edit_expense(session, up_obj, expenses, categories, company_methods_all)
        with col_add:
            _render_add_expense(session, up_obj, month_rm, categories, company_methods_active)


def _select_up_company(session) -> Optional[m_up.UpCompany]:
    ups = session.query(m_up.UpCompany).order_by(m_up.UpCompany.name.asc()).all()
    allowed_ids = st.session_state.get("allowed_company_ids")
    role = (st.session_state.get("user") or {}).get("role", "")
    if role != "admin" and allowed_ids:
        ups = [u for u in ups if u.id in allowed_ids]
    if role != "admin" and allowed_ids == []:
        st.warning("Нет доступных компаний для ваших прав.")
        return None
    if not ups:
        st.warning("Нет доступных компаний для ваших прав.")
        return None
    if role != "admin" and len(ups) == 1:
        # Единственная доступная компания — выбор не нужен
        st.markdown(
            f"<div style='font-weight:700; font-size:18px;'>Компания: {ups[0].name}</div>",
            unsafe_allow_html=True,
        )
        return ups[0]

    names = [u.name for u in ups]
    default_index = 0
    if names:
        default_name = names[0] if role != "admin" else None
        # selectbox имеет placeholder на позиции 0, реальные элементы сдвинуты на +1
        if default_name and default_name in names:
            default_index = names.index(default_name) + 1

    choice = st.selectbox(
        "Головная компания",
        options=["— выберите —"] + names,
        index=default_index,
        key="rest_expenses_up_company_select",
    )
    return next((u for u in ups if u.name == choice), None)


def _select_report_month(session, up_obj: m_up.UpCompany) -> Tuple[str, str]:
    today = dt.date.today()
    today_rm = _ym(today)

    month_rows = (
        session.query(m_re.RestaurantExpense.report_month)
        .filter(m_re.RestaurantExpense.up_company_id == up_obj.id)
        .distinct()
        .all()
    )
    months = {row[0] for row in month_rows if row and row[0]}
    months.add(today_rm)

    months_sorted = sorted(months, reverse=True)
    labels = [ru_label_from_rm(rm) for rm in months_sorted]
    today_label = ru_label_from_rm(today_rm)
    default_index = labels.index(today_label) if today_label in labels else 0

    label = st.selectbox(
        "Отчётный месяц",
        options=labels,
        index=default_index if labels else 0,
        key=f"rest_expenses_report_month_{up_obj.id}",
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


def _render_expenses_table(expenses: List[m_re.RestaurantExpense]) -> None:
    if not expenses:
        st.caption("Расходов за выбранный месяц пока нет.")
        return

    rows: List[Dict[str, object]] = []
    total = Decimal("0")
    for exp in expenses:
        amount = _to_decimal(exp.amount)
        total += amount
        rows.append(
            {
                "ID": exp.id,
                "Дата": exp.date.strftime("%d.%m.%Y") if exp.date else "",
                "Сумма": _format_currency(amount),
                "Категория": exp.category.name if exp.category else "",
                "Метод оплаты": exp.payment_method.name if exp.payment_method else "",
                "Тип": exp.operation_type or "",
                "Перенесена": "✅" if getattr(exp, "transferred_to_statement", False) else "",
                "Записано": "✅" if exp.recorded else "",
                "Назначение": exp.purpose or "",
                "Комментарий": exp.comment or "",
            }
        )

    df = pd.DataFrame(
        rows,
        columns=[
            "ID",
            "Дата",
            "Сумма",
            "Категория",
            "Метод оплаты",
            "Тип",
            "Перенесена",
            "Записано",
            "Назначение",
            "Комментарий",
        ],
    )
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"Итого расходов за месяц: {_format_currency(total)}.")


def _render_add_expense(
    session,
    up_obj: m_up.UpCompany,
    report_month: str,
    categories: List[m_cat.Category],
    payment_methods: Sequence[m_pm.PaymentMethod],
) -> None:
    if not categories or not payment_methods:
        msg = "Нет доступных категорий для добавления." if not categories else "Для этой компании нет настроенных методов оплаты. Настройте их в редакторе."
        st.info(msg)
        return

    dialog_fn = getattr(st, "dialog", None)
    if callable(dialog_fn):
        if st.button("➕ Добавить расход", type="primary", key=f"btn_add_exp_{up_obj.id}_{report_month}"):
            @dialog_fn("Новый расход")
            def _show_add_dialog():
                _add_expense_form(session, up_obj, report_month, categories, payment_methods)
            _show_add_dialog()
    else:
        with st.expander("Добавить расход", expanded=False):
            _add_expense_form(session, up_obj, report_month, categories, payment_methods)


def _add_expense_form(session, up_obj, report_month, categories, payment_methods):
    year, month = [int(part) for part in report_month.split("-")]
    start_date = dt.date(year, month, 1)
    end_date = dt.date(year, month, calendar.monthrange(year, month)[1])
    today = dt.date.today()
    default_date = min(max(today, start_date), end_date)

    with st.form(f"add_rest_expense_{up_obj.id}_{report_month}"):
        category_options = ["— выберите категорию —"] + [c.name for c in categories]
        category_name = st.selectbox(
            "Категория",
            options=category_options,
            index=0,
            key=f"rest_expense_category_add_{up_obj.id}_{report_month}",
        )
        category_obj = next((c for c in categories if c.name == category_name), None)

        method_options = [pm.name for pm in payment_methods]
        method_name = st.selectbox(
            "Метод оплаты",
            options=method_options,
            index=0,
            key=f"rest_expense_method_add_{up_obj.id}_{report_month}",
        )
        method_obj = next((pm for pm in payment_methods if pm.name == method_name), None)

        op_type = st.selectbox(
            "Тип операции",
            options=["Списание", "Поступление"],
            index=0,
            key=f"rest_expense_op_add_{up_obj.id}_{report_month}",
        )

        date_value = st.date_input(
            "Дата расхода",
            value=default_date,
            min_value=start_date,
            max_value=end_date,
        )

        amount_value = st.number_input("Сумма", min_value=None, step=100.0, format="%.2f")
        purpose_value = st.text_input(
            "Назначение",
            value="",
            key=f"rest_expense_purpose_add_{up_obj.id}_{report_month}",
        )
        comment_value = st.text_area("Комментарий", value="", height=80)

        if st.form_submit_button("Сохранить", type="primary"):
            if amount_value <= 0:
                st.warning("Сумма должна быть больше нуля.")
                return
            if not category_obj:
                st.warning("Выберите категорию.")
                return
            if not method_obj:
                st.warning("Укажите метод оплаты.")
                return
            purpose_clean = (purpose_value or "").strip()
            if not purpose_clean:
                st.warning("Заполните назначение.")
                return

            try:
                expense = m_re.RestaurantExpense(
                    date=date_value,
                    report_month=_ym(date_value),
                    up_company_id=up_obj.id,
                    group_id=category_obj.group_id,
                    category_id=category_obj.id,
                    payment_method_id=method_obj.id,
                    amount=Decimal(str(amount_value if op_type == "Поступление" else -abs(amount_value))),
                    operation_type=op_type,
                    purpose=purpose_clean,
                    comment=comment_value or None,
                    recorded=False,
                )
                session.add(expense)
                session.commit()
                st.session_state[_flash_key(up_obj.id)] = "Расход успешно добавлен."
                _rerun_app()
            except Exception as exc:
                session.rollback()
                st.error(f"Не удалось сохранить расход: {exc}")


def _render_edit_expense(
    session,
    up_obj: m_up.UpCompany,
    expenses: List[m_re.RestaurantExpense],
    categories: List[m_cat.Category],
    payment_methods: Sequence[m_pm.PaymentMethod],
) -> None:
    if not expenses:
        st.caption("Редактировать пока нечего.")
        return

    if not payment_methods:
        st.info("Нет доступных методов оплаты. Настройте их в редакторе.")
        return
    if not categories:
        st.info("Нет доступных категорий для редактирования.")
        return

    options = {
        exp.id: f"{exp.date.strftime('%d.%m.%Y') if exp.date else '—'} — {_format_currency(exp.amount)} (ID {exp.id})"
        for exp in expenses
    }
    selected_id = st.selectbox(
        "Выберите запись",
        options=list(options.keys()),
        format_func=options.get,
        key=f"rest_expense_edit_select_{up_obj.id}",
    )
    selected = next((exp for exp in expenses if exp.id == selected_id), None)
    if not selected:
        st.warning("Запись не найдена.")
        return

    with st.form(f"edit_rest_expense_{selected.id}"):
        date_value = st.date_input("Дата", value=selected.date or dt.date.today())
        amount_value = st.number_input(
            "Сумма",
            min_value=None,
            value=float(_to_decimal(selected.amount)),
            step=100.0,
            format="%.2f",
        )

        category_options = ["— выберите категорию —"] + [c.name for c in categories]
        current_cat_name = selected.category.name if selected.category else "— выберите категорию —"
        cat_index = category_options.index(current_cat_name) if current_cat_name in category_options else 0
        category_name = st.selectbox(
            "Категория",
            options=category_options,
            index=cat_index,
            key=f"rest_expense_category_edit_{selected.id}",
        )
        category_obj = next((c for c in categories if c.name == category_name), None)

        method_names = [pm.name for pm in payment_methods]
        current_method_name = selected.payment_method.name if selected.payment_method else None
        if current_method_name and current_method_name not in method_names:
            method_names.append(current_method_name)
        method_index = method_names.index(current_method_name) if current_method_name in method_names else 0
        method_name = st.selectbox(
            "Метод оплаты",
            options=method_names,
            index=method_index,
            key=f"rest_expense_method_edit_{selected.id}",
        )
        method_obj = next((pm for pm in payment_methods if pm.name == method_name), None)

        recorded_value = st.checkbox("Записано", value=bool(selected.recorded))
        purpose_value = st.text_input(
            "Назначение",
            value=selected.purpose or "",
            key=f"rest_expense_purpose_edit_{selected.id}",
        )
        comment_value = st.text_area("Комментарий", value=selected.comment or "", height=80)
        delete_flag = st.checkbox("Удалить запись", value=False)

        if st.form_submit_button("Сохранить изменения", type="primary"):
            try:
                if delete_flag:
                    session.delete(selected)
                    session.commit()
                    st.session_state[_flash_key(up_obj.id)] = "Запись удалена."
                    _rerun_app()
                    return

                if amount_value <= 0:
                    st.warning("Сумма должна быть больше нуля. Удалите запись, если расход нужно убрать.")
                    return
                if not category_obj:
                    st.warning("Выберите категорию.")
                    return
                if not method_obj:
                    st.warning("Укажите метод оплаты.")
                    return

                selected.date = date_value
                selected.report_month = _ym(date_value)
                selected.amount = Decimal(str(amount_value))
                selected.group_id = category_obj.group_id if category_obj else None
                selected.category_id = category_obj.id
                selected.payment_method_id = method_obj.id
                purpose_clean = (purpose_value or "").strip()
                if not purpose_clean:
                    st.warning("Заполните назначение.")
                    return
                selected.recorded = recorded_value
                selected.purpose = purpose_clean
                selected.comment = comment_value or None
                session.commit()
                st.session_state[_flash_key(up_obj.id)] = "Изменения сохранены."
                _rerun_app()
            except Exception as exc:
                session.rollback()
                st.error(f"Не удалось обновить запись: {exc}")


def _load_categories(session) -> List[m_cat.Category]:
    return session.query(m_cat.Category).order_by(m_cat.Category.name.asc()).all()


def _allowed_categories(categories: List[m_cat.Category]) -> Optional[List[m_cat.Category]]:
    """Return categories filtered by user rights; None if nothing is allowed."""
    role = (st.session_state.get("user") or {}).get("role", "")
    if role == "admin":
        return categories
    allowed_ids = st.session_state.get("allowed_category_ids") or []
    if not allowed_ids:
        return None
    return [c for c in categories if c.id in allowed_ids]


def _filter_expenses_by_categories(
    expenses: List[m_re.RestaurantExpense], categories: List[m_cat.Category]
) -> List[m_re.RestaurantExpense]:
    allowed_ids = {c.id for c in categories}
    role = (st.session_state.get("user") or {}).get("role", "")
    if role == "admin":
        return expenses
    return [exp for exp in expenses if exp.category_id in allowed_ids]


def _load_payment_methods(session, *, active_only: bool) -> List[m_pm.PaymentMethod]:
    query = session.query(m_pm.PaymentMethod)
    if active_only:
        query = query.filter(m_pm.PaymentMethod.is_active.is_(True))
    return query.order_by(m_pm.PaymentMethod.name.asc()).all()


def _load_company_payment_methods(
    session,
    up_obj: m_up.UpCompany,
    *,
    active_only: bool,
) -> List[m_pm.PaymentMethod]:
    query = (
        session.query(m_pm.PaymentMethod)
        .join(m_rpm.RestaurantPaymentMethod)
        .filter(m_rpm.RestaurantPaymentMethod.up_company_id == up_obj.id)
    )
    if active_only:
        query = query.filter(m_pm.PaymentMethod.is_active.is_(True))
    return query.order_by(m_pm.PaymentMethod.name.asc()).all()


def _flash_key(up_company_id: int) -> str:
    return f"rest_expenses_flash_{up_company_id}"


def _format_currency(value) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return str(value or "")
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",")


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _ym(date_value: dt.date) -> str:
    return f"{date_value.year:04d}-{date_value.month:02d}"


def _rerun_app() -> None:
    rerun = getattr(st, "rerun", None)
    if callable(rerun):
        rerun()
    else:
        st.experimental_rerun()


# === Новая версия редактора расходов с всплывашкой ===
def _render_edit_expense(
    session,
    up_obj: m_up.UpCompany,
    expenses: List[m_re.RestaurantExpense],
    categories: List[m_cat.Category],
    payment_methods: Sequence[m_pm.PaymentMethod],
) -> None:
    if not expenses:
        st.caption("Редактировать пока нечего.")
        return
    if not payment_methods:
        st.info("Нет доступных методов оплаты. Настройте их в редакторе.")
        return
    if not categories:
        st.info("Нет доступных категорий для редактирования.")
        return

    dialog_fn = getattr(st, "dialog", None)
    if callable(dialog_fn):
        if st.button("✏️ Редактировать запись", type="secondary", key=f"btn_edit_exp_{up_obj.id}"):
            @dialog_fn("Редактирование записи")
            def _show_edit_dialog():
                _edit_expense_form(session, expenses, categories, payment_methods, up_obj)
            _show_edit_dialog()
    else:
        with st.expander("Редактировать запись", expanded=False):
            _edit_expense_form(session, expenses, categories, payment_methods, up_obj)


def _edit_expense_form(session, expenses, categories, payment_methods, up_obj):
    options = {
        exp.id: f"ID {exp.id} | {exp.date.strftime('%d.%m.%Y') if exp.date else '-'} | {exp.category.name if exp.category else '-'} | {_format_currency(exp.amount)}"
        for exp in expenses
    }
    if not options:
        st.caption("Редактировать пока нечего.")
        return

    with st.form(f"edit_rest_expense_form_{up_obj.id}"):
        selected_id = st.selectbox(
            "Запись (ID | дата | категория | сумма)",
            options=list(options.keys()),
            format_func=options.get,
            key=f"rest_expense_edit_select_{up_obj.id}",
        )
        selected = next((exp for exp in expenses if exp.id == selected_id), None)
        if not selected:
            st.warning("Запись не найдена.")
            return

        date_value = st.date_input("Дата", value=selected.date or dt.date.today())
        amount_value = st.number_input(
            "Сумма",
            min_value=None,
            value=float(_to_decimal(selected.amount)),
            step=100.0,
            format="%.2f",
        )

        category_options = ["— выберите категорию —"] + [c.name for c in categories]
        current_cat_name = selected.category.name if selected.category else "— выберите категорию —"
        cat_index = category_options.index(current_cat_name) if current_cat_name in category_options else 0
        category_name = st.selectbox(
            "Категория",
            options=category_options,
            index=cat_index,
            key=f"rest_expense_category_edit_{selected.id}",
        )
        category_obj = next((c for c in categories if c.name == category_name), None)

        method_names = [pm.name for pm in payment_methods]
        current_method_name = selected.payment_method.name if selected.payment_method else None
        if current_method_name and current_method_name not in method_names:
            method_names.append(current_method_name)
        method_index = method_names.index(current_method_name) if current_method_name in method_names else 0
        method_name = st.selectbox(
            "Метод оплаты",
            options=method_names,
            index=method_index,
            key=f"rest_expense_method_edit_{selected.id}",
        )
        method_obj = next((pm for pm in payment_methods if pm.name == method_name), None)

        recorded_value = st.checkbox("Записано", value=bool(selected.recorded))
        purpose_value = st.text_input(
            "Назначение",
            value=selected.purpose or "",
            key=f"rest_expense_purpose_edit_alt_{selected.id}",
        )
        comment_value = st.text_area("Комментарий", value=selected.comment or "", height=80)
        delete_flag = st.checkbox("Удалить запись", value=False)

        if st.form_submit_button("Сохранить", type="primary"):
            try:
                if delete_flag:
                    session.delete(selected)
                    session.commit()
                    st.session_state[_flash_key(up_obj.id)] = "Запись удалена."
                    _rerun_app()
                    return

                if amount_value <= 0:
                    st.warning("Сумма должна быть больше нуля. Изменения не будут сохранены.")
                    return
                if not category_obj:
                    st.warning("Выберите категорию.")
                    return
                if not method_obj:
                    st.warning("Укажите метод оплаты.")
                    return

                selected.date = date_value
                selected.report_month = _ym(date_value)
                selected.amount = Decimal(str(amount_value))
                selected.group_id = category_obj.group_id if category_obj else None
                selected.category_id = category_obj.id
                selected.payment_method_id = method_obj.id
                purpose_clean = (purpose_value or "").strip()
                if not purpose_clean:
                    st.warning("Заполните назначение.")
                    return
                selected.recorded = recorded_value
                selected.purpose = purpose_clean
                selected.comment = comment_value or None
                session.commit()
                st.session_state[_flash_key(up_obj.id)] = "Запись обновлена."
                _rerun_app()
            except Exception as exc:
                session.rollback()
                st.error(f"Не удалось сохранить изменения: {exc}")



