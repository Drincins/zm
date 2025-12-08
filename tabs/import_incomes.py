from __future__ import annotations

import calendar
import datetime as dt
from decimal import Decimal
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from core.db import SessionLocal
from core.months import ru_label_from_rm
from db_models import income_format as m_if
from db_models import restaurant_expense as m_re
from db_models import payment_method as m_pm
from db_models import up_company as m_up
from db_models import company as m_company
from db_models import group as m_group
from db_models import category as m_cat
from db_models import income_expense as m_ie


MONTH_LABELS = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]


def render_import_incomes_tab() -> None:
    """Основная страница импорта доходов."""
    role = (st.session_state.get("user") or {}).get("role", "")
    if role not in ("admin", "manager"):
        st.warning("У вас нет прав на эту вкладку.")
        return

    st.markdown("### Доходы ресторана")

    with SessionLocal() as session:
        up_obj = _select_up_company(session)
        if not up_obj:
            st.info("Нет доступных компаний.")
            return

        flash_message = st.session_state.pop(_flash_key(up_obj.id), None)
        if flash_message:
            st.success(flash_message)

        month_rm, month_label = _select_report_month(session, up_obj)
        formats = _load_income_formats(session)
        if not formats:
            st.warning("Не настроены форматы доходов. Добавьте их в админке.")
            return

        companies = _load_companies_for_up(session, up_obj)
        entries = _build_income_entries(formats, companies)

        records = _load_month_records(session, up_obj, month_rm)

        st.markdown(f"#### Таблица по дням — {month_label}")
        _render_month_matrix(session, up_obj, entries, records, month_rm, month_label)

        st.markdown("#### Бланк кассира")
        _render_day_form(session, up_obj, entries, month_rm, records)


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
    choice = st.selectbox(
        "Выберите компанию",
        options=["- Выберите -"] + names,
        index=0,
        key="income_up_company_select",
    )
    return next((u for u in ups if u.name == choice), None)


def _select_report_month(session, up_obj: m_up.UpCompany) -> Tuple[str, str]:
    today_rm = _ym(dt.date.today())
    month_rows = (
        session.query(m_if.IncomeRecord.report_month)
        .filter(m_if.IncomeRecord.up_company_id == up_obj.id)
        .distinct()
        .all()
    )
    months = {row[0] for row in month_rows if row and row[0]}
    months.add(today_rm)
    months_sorted = sorted(months, reverse=True)
    labels = [ru_label_from_rm(rm) for rm in months_sorted]
    default_index = labels.index(ru_label_from_rm(today_rm)) if labels else 0
    label = st.selectbox(
        "Учётный месяц",
        options=labels,
        index=default_index,
        key=f"income_report_month_{up_obj.id}",
    )
    rm = months_sorted[labels.index(label)]
    return rm, label


def _load_income_formats(session) -> List[m_if.IncomeFormat]:
    return (
        session.query(m_if.IncomeFormat)
        .filter(m_if.IncomeFormat.is_active.is_(True))
        .order_by(m_if.IncomeFormat.id.asc())
        .all()
    )


def _load_month_records(session, up_obj: m_up.UpCompany, report_month: str) -> List[m_if.IncomeRecord]:
    return (
        session.query(m_if.IncomeRecord)
        .options(selectinload(m_if.IncomeRecord.format))
        .options(selectinload(m_if.IncomeRecord.company))
        .filter(
            m_if.IncomeRecord.up_company_id == up_obj.id,
            m_if.IncomeRecord.report_month == report_month,
        )
        .order_by(
            m_if.IncomeRecord.date.asc(),
            m_if.IncomeRecord.format_id.asc(),
            m_if.IncomeRecord.company_id.asc(),
        )
        .all()
    )


def _load_companies_for_up(session, up_obj: m_up.UpCompany) -> List[m_company.Company]:
    return (
        session.query(m_company.Company)
        .filter(m_company.Company.up_company_id == up_obj.id)
        .order_by(m_company.Company.name.asc())
        .all()
    )


def _build_income_entries(
    formats: List[m_if.IncomeFormat],
    companies: List[m_company.Company],
) -> List[Dict[str, object]]:
    entries: List[Dict[str, object]] = []
    card_codes = {"cards_ooo", "cards_ip"}
    card_formats = [fmt for fmt in formats if (fmt.code or "").lower() in card_codes]
    primary_card_fmt = card_formats[0] if card_formats else None

    for fmt in formats:
        code = (fmt.code or "").lower()
        if code == "payment_link":
            continue
        if code in card_codes and fmt is not primary_card_fmt:
            continue

        if code in card_codes and primary_card_fmt and companies:
            for comp in companies:
                entries.append(
                    {
                        "fmt": primary_card_fmt,
                        "company": comp,
                        "label": f"Карта {comp.name}",
                    }
                )
        else:
            entries.append({"fmt": fmt, "company": None, "label": fmt.name})
    return entries


def _render_month_matrix(
    session,
    up_obj: m_up.UpCompany,
    entries: List[Dict[str, object]],
    records: List[m_if.IncomeRecord],
    report_month: str,
    month_label: str,
) -> None:
    if not entries:
        st.info("Нет доступных форматов доходов.")
        return

    year, month = [int(part) for part in report_month.split("-")]
    days_in_month = calendar.monthrange(year, month)[1]
    day_labels = [f"{day:02d}" for day in range(1, days_in_month + 1)]

    record_map: Dict[Tuple[int, int | None, int], m_if.IncomeRecord] = {}
    for rec in records:
        if rec.format_id and rec.date:
            record_map[(rec.format_id, rec.company_id, rec.date.day)] = rec

    data_rows: List[Dict[str, object]] = []
    totals_by_day = {day: Decimal("0") for day in range(1, days_in_month + 1)}
    grand_total = Decimal("0")

    for entry in entries:
        fmt: m_if.IncomeFormat = entry["fmt"]
        comp: m_company.Company | None = entry.get("company")  # type: ignore
        row: Dict[str, object] = {"Статья": entry["label"]}
        row_total = Decimal("0")
        for day in range(1, days_in_month + 1):
            rec = record_map.get((fmt.id, comp.id if comp else None, day))
            if rec:
                amount = _to_decimal(rec.amount)
                row_total += amount
                totals_by_day[day] += amount
                grand_total += amount
                row[f"{day:02d}"] = _format_cell(amount, rec.recorded)
            else:
                row[f"{day:02d}"] = ""
        row["Итого"] = _format_currency(row_total) if row_total else ""
        data_rows.append(row)

    totals_row = {"Статья": "Итого"}
    for day in range(1, days_in_month + 1):
        amount = totals_by_day[day]
        totals_row[f"{day:02d}"] = _format_currency(amount) if amount else ""
    totals_row["Итого"] = _format_currency(grand_total) if grand_total else ""
    data_rows.extend(_build_restaurant_row(session, up_obj, report_month, days_in_month))
    data_rows.append(totals_row)

    df = pd.DataFrame(data_rows, columns=["Статья", *day_labels, "Итого"])
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_day_form(
    session,
    up_obj: m_up.UpCompany,
    entries: List[Dict[str, object]],
    report_month: str,
    records: List[m_if.IncomeRecord],
) -> None:
    if not entries:
        st.info("Нет доступных форматов доходов.")
        return

    year, month = [int(part) for part in report_month.split("-")]
    start_date = dt.date(year, month, 1)
    end_date = dt.date(year, month, calendar.monthrange(year, month)[1])
    today = dt.date.today()
    default_date = min(max(today, start_date), end_date)

    selected_date = st.date_input(
        "Дата",
        value=default_date,
        min_value=start_date,
        max_value=end_date,
        key=f"income_day_date_{up_obj.id}_{report_month}",
    )

    grouped = _group_records_by_date(records)
    existing_map = grouped.get(selected_date, {}) or {}
    allow_overwrite = True
    if existing_map:
        allow_overwrite = st.checkbox(
            "Перезаписать существующие значения",
            value=False,
            key=f"overwrite_{up_obj.id}_{report_month}_{selected_date}",
        )
        if not allow_overwrite:
            st.info("Включите переключатель, чтобы редактировать существующий день.")
    else:
        st.caption("День пустой — будут созданы новые записи.")

    with st.form(f"income_day_form_{up_obj.id}_{report_month}_{selected_date.isoformat()}"):
        st.caption("Заполните суммы по форматам. Пустые значения удалят запись за день.")
        entry_items = [entry for entry in entries if (entry["fmt"].code or "").lower() != "payment_link"]
        inputs_per_row = 2
        cols = st.columns(inputs_per_row)
        rows: List[Dict[str, object]] = []
        for idx, entry in enumerate(entry_items):
            if idx % inputs_per_row == 0 and idx != 0:
                cols = st.columns(inputs_per_row)

            fmt = entry["fmt"]
            comp: m_company.Company | None = entry.get("company")  # type: ignore
            record = existing_map.get((fmt.id, comp.id if comp else None))
            col = cols[idx % inputs_per_row]
            with col:
                amount_value = st.number_input(
                    entry["label"],
                    value=float(_to_decimal(record.amount)) if record else 0.0,
                    min_value=0.0,
                    step=100.0,
                    format="%.2f",
                    key=f"day_amount_{up_obj.id}_{report_month}_{selected_date.isoformat()}_{fmt.id}_{comp.id if comp else 'none'}",
                )
                amount_value = Decimal(str(amount_value))

            rows.append(
                {
                    "Название": entry["label"],
                    "format_id": fmt.id,
                    "company_id": comp.id if comp else None,
                    "Сумма": amount_value,
                    "Записано": bool(record.recorded) if record else False,
                    "Комментарий": record.comment if record else None,
                }
            )

        submit = st.form_submit_button("Сохранить записи", type="primary")

        if submit:
            if existing_map and not allow_overwrite:
                st.warning("Включите перезапись, чтобы обновить существующие записи.")
                return
            entries_by_key = {
                (entry["fmt"].id, (entry.get("company").id if entry.get("company") else None)): entry  # type: ignore
                for entry in entries
            }
            try:
                created, updated, deleted = _save_day_records(
                    session,
                    up_obj,
                    selected_date,
                    rows,
                    entries_by_key,
                    existing_map,
                )
                _sync_income_expense_for_date(session, up_obj, selected_date)
                st.session_state[_flash_key(up_obj.id)] = _format_day_message(created, updated, deleted, selected_date)
                st.rerun()
            except Exception as exc:
                session.rollback()
                st.error(f"Не удалось сохранить записи дня: {exc}")


def _group_records_by_date(
    records: List[m_if.IncomeRecord],
) -> Dict[dt.date, Dict[Tuple[int, int | None], m_if.IncomeRecord]]:
    grouped: Dict[dt.date, Dict[Tuple[int, int | None], m_if.IncomeRecord]] = {}
    for rec in records:
        if not rec.date:
            continue
        grouped.setdefault(rec.date, {})[(rec.format_id, rec.company_id)] = rec
    return grouped


def _flash_key(up_company_id: int) -> str:
    return f"income_day_flash_{up_company_id}"


def _day_refresh_key(up_company_id: int, report_month: str) -> str:
    return f"income_day_refresh_{up_company_id}_{report_month}"


def _format_day_message(created: int, updated: int, deleted: int, date_value: dt.date) -> str:
    parts: List[str] = []
    if created:
        parts.append(f"добавлено {created}")
    if updated:
        parts.append(f"обновлено {updated}")
    if deleted:
        parts.append(f"удалено {deleted}")
    summary = ", ".join(parts) if parts else "без изменений"
    return f"День {date_value.strftime('%d.%m.%Y')}: {summary}."


def _save_day_records(
    session,
    up_obj: m_up.UpCompany,
    date_value: dt.date,
    rows: List[Dict[str, object]],
    entries_by_key: Dict[Tuple[int, int | None], Dict[str, object]],
    existing_map: Dict[Tuple[int, int | None], m_if.IncomeRecord],
) -> Tuple[int, int, int]:
    report_month = _ym(date_value)
    created = 0
    updated = 0
    deleted = 0

    for row in rows:
        fmt_raw = row.get("format_id")
        if fmt_raw is None:
            continue
        fmt_id = int(fmt_raw)
        company_raw = row.get("company_id")
        comp_id = int(company_raw) if company_raw is not None else None
        key = (fmt_id, comp_id)
        entry = entries_by_key.get(key)
        if not entry:
            continue
        fmt: m_if.IncomeFormat = entry["fmt"]  # type: ignore

        amount = Decimal(str(row.get("Сумма") or 0))
        recorded = bool(row.get("Записано"))
        comment = row.get("Комментарий") or None
        existing = existing_map.get(key)

        if amount <= 0:
            if existing:
                session.delete(existing)
                deleted += 1
            continue

        if existing:
            changed = False
            if _to_decimal(existing.amount) != amount:
                existing.amount = amount
                changed = True
            if existing.recorded != recorded:
                existing.recorded = recorded
                changed = True
            if (existing.comment or "") != (comment or ""):
                existing.comment = comment
                changed = True
            if existing.report_month != report_month:
                existing.report_month = report_month
                changed = True
            if (existing.company_id or None) != comp_id:
                existing.company_id = comp_id
                changed = True
            if changed:
                updated += 1
        else:
            new_record = m_if.IncomeRecord(
                date=date_value,
                report_month=report_month,
                up_company_id=up_obj.id,
                company_id=comp_id,
                format_id=fmt.id,
                amount=amount,
                comment=comment,
                recorded=recorded,
            )
            session.add(new_record)
            created += 1

    if created or updated or deleted:
        session.commit()

    return created, updated, deleted


def _sync_income_expense_for_date(session, up_obj: m_up.UpCompany, date_value: dt.date) -> None:
    marker = "[income_auto]"
    group_obj = _ensure_income_group(session)

    session.query(m_ie.IncomeExpense).filter(
        m_ie.IncomeExpense.up_company_id == up_obj.id,
        m_ie.IncomeExpense.date == date_value,
        m_ie.IncomeExpense.operation_type == "поступление",
        m_ie.IncomeExpense.comment.contains(marker),
    ).delete(synchronize_session=False)

    records = (
        session.query(m_if.IncomeRecord)
        .options(selectinload(m_if.IncomeRecord.format))
        .filter(
            m_if.IncomeRecord.up_company_id == up_obj.id,
            m_if.IncomeRecord.date == date_value,
        )
        .all()
    )

    category_cache: Dict[int, m_cat.Category] = {}
    for rec in records:
        if not rec.format:
            continue
        cat_obj = category_cache.get(rec.format.id) or _ensure_income_category_for_format(session, rec.format, group_obj)
        category_cache[rec.format.id] = cat_obj

        amount = _to_decimal(rec.amount)
        comment_parts = [marker, f"income_record_id={rec.id}"]
        if rec.comment:
            comment_parts.append(str(rec.comment))
        comment_value = " ".join(comment_parts)

        session.add(
            m_ie.IncomeExpense(
                date=rec.date,
                report_month=rec.report_month or _ym(rec.date),
                up_company_id=rec.up_company_id,
                company_id=rec.company_id,
                group_id=cat_obj.group_id if cat_obj else None,
                category_id=cat_obj.id if cat_obj else None,
                paid_for_company_id=None,
                operation_type="поступление",
                amount=amount,
                comment=comment_value,
            )
        )

    session.commit()


def _ensure_income_group(session) -> m_group.Group:
    code = "restaurant_income"
    group_obj = session.query(m_group.Group).filter(m_group.Group.code == code).one_or_none()
    if not group_obj:
        group_obj = m_group.Group(code=code, name="Доходы ресторана")
        session.add(group_obj)
        session.flush()
    return group_obj


def _ensure_income_category_for_format(session, fmt: m_if.IncomeFormat, group_obj: m_group.Group) -> m_cat.Category:
    code = (fmt.code or f"income_{fmt.id}").lower()
    cat_obj = session.query(m_cat.Category).filter(m_cat.Category.code == code).one_or_none()
    if not cat_obj:
        cat_obj = session.query(m_cat.Category).filter(m_cat.Category.name == fmt.name).one_or_none()
    if not cat_obj:
        cat_obj = m_cat.Category(code=code, name=fmt.name, group_id=group_obj.id)
        session.add(cat_obj)
        session.flush()
    else:
        if not cat_obj.group_id:
            cat_obj.group_id = group_obj.id
    return cat_obj


def _build_restaurant_row(
    session,
    up_obj: m_up.UpCompany,
    report_month: str,
    days_in_month: int,
) -> List[Dict[str, object]]:
    expenses_by_day = _get_restaurant_expenses(session, up_obj, report_month)
    row: Dict[str, object] = {"Статья": "Расходы ресторан"}
    total = Decimal("0")
    for day in range(1, days_in_month + 1):
        value = _to_decimal(expenses_by_day.get(day, 0))
        row[f"{day:02d}"] = _format_currency(value) if value else ""
        total += value
    row["Итого"] = _format_currency(total) if total else ""
    return [row]


def _get_restaurant_expenses(
    session,
    up_obj: m_up.UpCompany,
    report_month: str,
) -> Dict[int, Decimal]:
    rows = (
        session.query(
            m_re.RestaurantExpense.date,
            func.coalesce(func.sum(m_re.RestaurantExpense.amount), 0),
        )
        .outerjoin(m_pm.PaymentMethod, m_pm.PaymentMethod.id == m_re.RestaurantExpense.payment_method_id)
        .filter(
            m_re.RestaurantExpense.up_company_id == up_obj.id,
            m_re.RestaurantExpense.report_month == report_month,
            # включаем только методы, участвующие в дневном учёте; если метода нет — не отфильтровываем
            (m_re.RestaurantExpense.payment_method_id.is_(None)) | (m_pm.PaymentMethod.participates_in_daily.is_(True)),
        )
        .group_by(m_re.RestaurantExpense.date)
        .all()
    )
    result: Dict[int, Decimal] = {}
    for date_val, amount in rows:
        if not date_val:
            continue
        result[date_val.day] = _to_decimal(amount)
    return result


def _format_cell(amount: Decimal, recorded: bool) -> str:
    value = _format_currency(amount)
    return f"{value} ✅" if recorded else value


def _format_currency(amount: Decimal | float | int) -> str:
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return str(amount or "")
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def _parse_amount(raw_value) -> Decimal:
    if raw_value is None:
        return Decimal("0")
    text = str(raw_value).strip()
    if not text:
        return Decimal("0")
    text = text.replace("\xa0", "").replace(" ", "")
    if "," in text and "." in text:
        last_dot = text.rfind(".")
        last_comma = text.rfind(",")
        if last_comma > last_dot:
            text = text.replace(".", "")
            text = text.replace(",", ".")
        else:
            text = text.replace(",", "")
    else:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except Exception:
        try:
            return Decimal(str(float(text)))
        except Exception:
            return Decimal("0")


def _to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _ym(date_value: dt.date) -> str:
    return f"{date_value.year:04d}-{date_value.month:02d}"
