from __future__ import annotations

# tabs/reports_itogbank.py
import os
from datetime import datetime
import pandas as pd
import streamlit as st
from sqlalchemy import or_
from core.parser import clean_account
from core.utils import normalize_amount_by_type
from core.months import format_report_month_label, format_month_year

from core.db import SessionLocal
from db_models import (
    statement as m_statement,
    company as m_company,
    up_company as m_up,
    group as m_group,
    category as m_cat,
    firm as m_firm,
)

# ----------------------------- УТИЛИТЫ -----------------------------

def _fmt_rub(x: float) -> str:
    try:
        return f"{int(round(float(x))):,}".replace(",", " ") + " ₽"
    except Exception:
        return "0 ₽"

def _companies_from_statement(session, up_company_id: int | None) -> list[m_company.Company]:
    q_payer = session.query(m_statement.Statement.payer_company_id).filter(
        m_statement.Statement.payer_company_id.isnot(None)
    )
    q_recv = session.query(m_statement.Statement.receiver_company_id).filter(
        m_statement.Statement.receiver_company_id.isnot(None)
    )
    if up_company_id:
        q_payer = q_payer.filter(m_statement.Statement.up_company_id == up_company_id)
        q_recv = q_recv.filter(m_statement.Statement.up_company_id == up_company_id)

    ids = {row[0] for row in q_payer.all()} | {row[0] for row in q_recv.all()}
    ids = [i for i in ids if i is not None]
    if not ids:
        return []

    return (
        session.query(m_company.Company)
        .filter(m_company.Company.id.in_(ids))
        .order_by(m_company.Company.name.asc())
        .all()
    )


def _companies_for_filter(session, up_company_id: int | None) -> list[m_company.Company]:
    if up_company_id is None:
        return session.query(m_company.Company).order_by(m_company.Company.name.asc()).all()

    historical = _companies_from_statement(session, up_company_id)
    current = (
        session.query(m_company.Company)
        .filter(m_company.Company.up_company_id == up_company_id)
        .order_by(m_company.Company.name.asc())
        .all()
    )

    merged_by_id = {c.id: c for c in historical}
    for company in current:
        merged_by_id[company.id] = company

    return sorted(merged_by_id.values(), key=lambda c: (c.name or "").lower())


def _za_kogo_for_filter(
    session,
    company_ids: list[int] | None,
    up_company_id: int | None,
    report_months: list[str],
    report_years: list[int] | None,
) -> list[m_up.UpCompany]:
    q = session.query(m_statement.Statement.za_kogo_platili_id).distinct()
    q = q.filter(m_statement.Statement.za_kogo_platili_id.isnot(None))
    q = q.filter(m_statement.Statement.report_month.in_(report_months))

    if report_years:
        q = q.filter(m_statement.Statement.report_year.in_(report_years))

    if company_ids:
        q = q.filter(
            or_(
                m_statement.Statement.payer_company_id.in_(company_ids),
                m_statement.Statement.receiver_company_id.in_(company_ids),
            )
        )

    if up_company_id:
        q = q.filter(m_statement.Statement.up_company_id == up_company_id)

    q = q.filter(m_statement.Statement.za_kogo_platili_id != m_statement.Statement.up_company_id)

    za_ids = [row[0] for row in q.all() if row and row[0] is not None]
    if not za_ids:
        return []

    return (
        session.query(m_up.UpCompany)
        .filter(m_up.UpCompany.id.in_(za_ids))
        .order_by(m_up.UpCompany.name.asc())
        .all()
    )

def _distinct_report_months(session, company_ids: list[int] | None, up_company_id: int | None) -> list[str]:
    q = session.query(m_statement.Statement.report_month).distinct()
    if company_ids:
        q = q.filter(
            or_(
                m_statement.Statement.payer_company_id.in_(company_ids),
                m_statement.Statement.receiver_company_id.in_(company_ids),
            )
        )
    if up_company_id:
        q = q.filter(m_statement.Statement.up_company_id == up_company_id)

    months = [row[0] for row in q.all() if row and row[0]]
    return sorted(set(months), reverse=True)


def _distinct_report_years(session, company_ids: list[int] | None, up_company_id: int | None) -> list[int]:
    q = session.query(m_statement.Statement.report_year).distinct()
    if company_ids:
        q = q.filter(
            or_(
                m_statement.Statement.payer_company_id.in_(company_ids),
                m_statement.Statement.receiver_company_id.in_(company_ids),
            )
        )
    if up_company_id:
        q = q.filter(m_statement.Statement.up_company_id == up_company_id)
    years = [row[0] for row in q.all() if row and row[0] is not None]
    return sorted(set(int(y) for y in years))


def _fetch_df(session, company_ids: list[int] | None, up_company_id: int | None, report_months: list[str], report_years: list[int] | None) -> pd.DataFrame:
    q = (
        session.query(
            m_statement.Statement.id.label("id"),
            m_statement.Statement.row_id.label("row_id"),
            m_statement.Statement.date.label("date"),
            m_statement.Statement.report_month.label("report_month"),
            m_statement.Statement.report_year.label("report_year"),
            m_statement.Statement.purpose.label("purpose"),
            m_statement.Statement.amount.label("amount"),
            m_statement.Statement.operation_type.label("operation_type"),
            m_statement.Statement.comment.label("comment"),
            m_statement.Statement.recorded.label("recorded"),
            m_statement.Statement.payer_account.label("_payer_account"),
            m_statement.Statement.receiver_account.label("_receiver_account"),
            # служебные поля для доп. колонок
            m_statement.Statement.payer_company_id.label("_payer_company_id"),
            m_statement.Statement.payer_firm_id.label("_payer_firm_id"),
            m_statement.Statement.payer_raw.label("_payer_raw"),
            m_statement.Statement.receiver_company_id.label("_receiver_company_id"),  # NEW
            m_statement.Statement.receiver_firm_id.label("_receiver_firm_id"),        # NEW
            m_statement.Statement.receiver_raw.label("_receiver_raw"),                # NEW
            m_statement.Statement.up_company_id.label("_up_company_id"),
            m_statement.Statement.za_kogo_platili_id.label("_za_kogo_platili_id"),
            m_group.Group.name.label("group_name"),
            m_cat.Category.name.label("category_name"),
        )
        .outerjoin(m_group.Group, m_group.Group.id == m_statement.Statement.group_id)
        .outerjoin(m_cat.Category, m_cat.Category.id == m_statement.Statement.category_id)
        .filter(m_statement.Statement.report_month.in_(report_months))
    )

    if report_years:
        q = q.filter(m_statement.Statement.report_year.in_(report_years))

    if company_ids:
        q = q.filter(
            or_(
                m_statement.Statement.payer_company_id.in_(company_ids),
                m_statement.Statement.receiver_company_id.in_(company_ids),
            )
        )
    if up_company_id:
        q = q.filter(m_statement.Statement.up_company_id == up_company_id)

    rows = q.all()
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([{
        "id": r.id,
        "row_id": r.row_id,
        "Дата": r.date,
        "Месяц": r.report_month or "",
        "Назначение": r.purpose,
        "Сумма": r.amount,
        "Тип": r.operation_type,
        "Группа": r.group_name,
        "Категория": r.category_name,
        "Комментарий": r.comment,
        "Записано": r.recorded,
        "_payer_account": r._payer_account,
        "_receiver_account": r._receiver_account,
        "_payer_company_id": r._payer_company_id,
        "_payer_firm_id": r._payer_firm_id,
        "_payer_raw": r._payer_raw,
        "_receiver_company_id": r._receiver_company_id,  # NEW
        "_receiver_firm_id": r._receiver_firm_id,        # NEW
        "_receiver_raw": r._receiver_raw,                # NEW
        "_up_company_id": r._up_company_id,
        "_za_kogo_platili_id": r._za_kogo_platili_id,
    } for r in rows])

    if df.empty:
        return df

    df["Дата"] = pd.to_datetime(df["Дата"], errors="coerce")
    df["Сумма"] = pd.to_numeric(df["Сумма"], errors="coerce").fillna(0.0)
    df["_op_type_norm"] = df["Тип"].astype(str).str.strip().str.lower()
    type_display_map = {"списание": "Списание", "поступление": "Поступление"}
    df["Тип"] = df["_op_type_norm"].map(type_display_map).fillna(df["Тип"])
    for col in ["Группа", "Категория"]:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    comp_ids = sorted(set([
        *[x for x in df["_payer_company_id"].dropna().tolist() if x is not None],
        *[x for x in df["_receiver_company_id"].dropna().tolist() if x is not None],  # NEW
    ]))
    firm_ids = sorted(set([
        *[x for x in df["_payer_firm_id"].dropna().tolist() if x is not None],
        *[x for x in df["_receiver_firm_id"].dropna().tolist() if x is not None],    # NEW
    ]))
    za_col = "_za_kogo_platili_id"
    up_ids = sorted(set(
        [x for x in df["_up_company_id"].dropna().tolist() if x is not None] +
        ([x for x in df[za_col].dropna().tolist() if x is not None] if za_col in df.columns else [])
    ))


    comp_name_by_id = {cid: name for cid, name in session.query(m_company.Company.id, m_company.Company.name).filter(
        m_company.Company.id.in_(comp_ids) if comp_ids else False
    ).all()} if comp_ids else {}
    firm_name_by_id = {fid: name for fid, name in session.query(m_firm.Firm.id, m_firm.Firm.name).filter(
        m_firm.Firm.id.in_(firm_ids) if firm_ids else False
    ).all()} if firm_ids else {}
    up_name_by_id = {uid: name for uid, name in session.query(m_up.UpCompany.id, m_up.UpCompany.name).filter(
        m_up.UpCompany.id.in_(up_ids) if up_ids else False
    ).all()} if up_ids else {}

    df["Плательщик"] = (
        df["_payer_company_id"].map(comp_name_by_id)
        .fillna(df["_payer_firm_id"].map(firm_name_by_id))
        .fillna(df["_payer_raw"])
        .fillna("")
    )
    df["Получатель"] = (
        df["_receiver_company_id"].map(comp_name_by_id)
        .fillna(df["_receiver_firm_id"].map(firm_name_by_id))
        .fillna(df["_receiver_raw"])
        .fillna("")
    )
    df["Счет плательщика"] = df["_payer_account"].map(clean_account).fillna("")
    df["Счет получателя"] = df["_receiver_account"].map(clean_account).fillna("")
    df["Головная компания"] = df["_up_company_id"].map(up_name_by_id).fillna("")
    # Отображение «За кого платили» — корректное имя поля
    if "_za_kogo_platili_id" in df.columns:
        df["За кого платили"] = df["_za_kogo_platili_id"].map(up_name_by_id).fillna("")
    else:
        df["За кого платили"] = ""


    return df

# ----------------------------- UI -----------------------------

def reports_itogbank():
    st.subheader("Итоги по компаниям")
    with SessionLocal() as session:
        _render_reports_itogbank(session)


def _render_reports_itogbank(session):
    # --- КОМПАКТНАЯ ПАНЕЛЬ ФИЛЬТРОВ ---
    applied_filters_key = "itog_applied_filters"
    with st.container():
        st.markdown("### Фильтры")

        # Базовые значения/списки
        up_list = session.query(m_up.UpCompany).order_by(m_up.UpCompany.name.asc()).all()
        up_names = [u.name for u in up_list]
        up_display = ["— все —"] + up_names

        # 1) Головная компания + компания
        c1, c2 = st.columns([2, 1])
        up_selected_name = c1.selectbox("Головная компания", options=up_display, index=0, key="itog_up_company")
        up_selected_obj = next((u for u in up_list if u.name == up_selected_name), None)
        up_selected_id = up_selected_obj.id if up_selected_obj else None

        companies_ref = _companies_for_filter(session, up_selected_id)
        if up_selected_id:
            all_companies_label = "— все компании головной —"
            company_help = "Можно оставить все компании выбранной головной или сузить выбор до одной."
        else:
            all_companies_label = "— все компании —"
            company_help = "Если нужно, можно сразу выбрать одну конкретную компанию."

        company_options = [all_companies_label] + [c.name for c in companies_ref]
        if st.session_state.get("itog_company_filter") not in company_options:
            st.session_state["itog_company_filter"] = all_companies_label
        selected_company_name = c2.selectbox(
            "Компания",
            options=company_options,
            key="itog_company_filter",
            help=company_help,
        )

        # 2) Выбор компании (опционально)
        company_ids: list[int] | None = None
        company_obj = None
        if selected_company_name != all_companies_label:
            company_obj = next((c for c in companies_ref if c.name == selected_company_name), None)
            company_ids = [company_obj.id] if company_obj else None

        if up_selected_id and not companies_ref:
            st.caption("У выбранной головной компании пока нет доступных компаний для точечного отбора.")

        # 3) Учётный месяц(ы) и год(ы)
        months = _distinct_report_months(session, company_ids, up_selected_id)
        years = _distinct_report_years(session, company_ids, up_selected_id)
        current_month_value = datetime.today().strftime("%Y-%m")
        current_year_value = datetime.today().year
        default_months = [current_month_value] if current_month_value in months else []
        default_years = [current_year_value] if current_year_value in years else []
        if "itog_months_draft" not in st.session_state:
            st.session_state["itog_months_draft"] = default_months
        else:
            st.session_state["itog_months_draft"] = [m for m in st.session_state["itog_months_draft"] if m in months]
        if "itog_years_draft" not in st.session_state:
            st.session_state["itog_years_draft"] = default_years
        else:
            st.session_state["itog_years_draft"] = [y for y in st.session_state["itog_years_draft"] if y in years]
        col_m, col_y = st.columns(2)
        sel_months_draft = col_m.multiselect(
            "Месяц",
            options=months,
            key="itog_months_draft",
            format_func=lambda m: m,
        )
        sel_years_draft = col_y.multiselect(
            "Год",
            options=years,
            key="itog_years_draft",
        )

        # 4) Частые фильтры — в две колонки
        c3, c4 = st.columns([1, 1])

        recorded_filter = c3.selectbox(
            "Что показывать",
            ["Все операции", "Только новые (не записанные)", "Только записанные"],
            index=1,
            key="itog_recorded_filter"  # уникальный ключ
        )

        op_type_options = ["Списание", "Поступление"]
        op_types = c4.multiselect(
            "Тип операции",
            op_type_options,
            default=op_type_options,
            key="itog_op_types"  # уникальный ключ
        )
        selected_type_norms_draft = [opt.lower() for opt in op_types] if op_types else []

        # 5) Редкие фильтры — под экспандер
        with st.expander("Доп. фильтры"):
            only_for_others_mode = st.selectbox(
                "Оплата за других",
                options=["Не применять", "Применить фильтр"],
                index=0,
                key="itb_for_others_mode",
            )
            only_for_others = only_for_others_mode == "Применить фильтр"
            selected_za_kogo_id = None
            if only_for_others:
                za_kogo_options = _za_kogo_for_filter(
                    session,
                    company_ids,
                    up_selected_id,
                    sel_months_draft,
                    sel_years_draft,
                )
                all_za_kogo_label = "— все компании —"
                za_kogo_names = [u.name for u in za_kogo_options]
                za_kogo_select_options = [all_za_kogo_label] + za_kogo_names
                if st.session_state.get("itb_for_others_company") not in za_kogo_select_options:
                    st.session_state["itb_for_others_company"] = all_za_kogo_label
                selected_za_kogo_name = st.selectbox(
                    "За кого платили",
                    options=za_kogo_select_options,
                    key="itb_for_others_company",
                    help="Список строится по операциям текущего среза до применения дополнительных фильтров.",
                )
                if selected_za_kogo_name != all_za_kogo_label:
                    selected_za_kogo = next((u for u in za_kogo_options if u.name == selected_za_kogo_name), None)
                    selected_za_kogo_id = selected_za_kogo.id if selected_za_kogo else None
                if not za_kogo_options:
                    st.caption("В текущем срезе нет операций с оплатой за других.")

            use_date_mode = st.selectbox(
                "Фильтр по датам",
                options=["Не применять", "Выбрать диапазон"],
                index=0,
                key="itb_use_date_mode",
            )
            use_date = use_date_mode == "Выбрать диапазон"
            if use_date:
                default_start = datetime.today().date().replace(day=1)
                default_end = datetime.today().date()
                st.date_input(
                    "Диапазон дат",
                    key="itb_date_range",
                    value=st.session_state.get("itb_date_range", (default_start, default_end)),
                )

        draft_filters = {
            "up_company_id": up_selected_id,
            "company_id": company_obj.id if company_obj else None,
            "months": list(sel_months_draft),
            "years": list(sel_years_draft),
            "recorded_filter": recorded_filter,
            "selected_type_norms": list(selected_type_norms_draft),
            "only_for_others": bool(only_for_others),
            "selected_za_kogo_id": selected_za_kogo_id,
            "use_date": bool(use_date),
            "date_range": st.session_state.get("itb_date_range"),
        }

        if applied_filters_key not in st.session_state:
            st.session_state[applied_filters_key] = draft_filters.copy()

        btn_col, info_col = st.columns([1, 3])
        if btn_col.button("Применить", key="itog_apply_filters", type="primary"):
            st.session_state[applied_filters_key] = draft_filters.copy()
            st.rerun()
        if draft_filters != st.session_state.get(applied_filters_key):
            info_col.caption("Есть несохранённые изменения фильтров. Отчёт обновится после нажатия «Применить».")

    applied_filters = st.session_state.get(applied_filters_key, {})
    up_selected_id = applied_filters.get("up_company_id")
    applied_company_id = applied_filters.get("company_id")
    company_ids = [applied_company_id] if applied_company_id else None
    sel_months = list(applied_filters.get("months", []))
    sel_years = list(applied_filters.get("years", []))
    recorded_filter = applied_filters.get("recorded_filter", "Только новые (не записанные)")
    selected_type_norms = list(applied_filters.get("selected_type_norms", []))
    only_for_others = bool(applied_filters.get("only_for_others", False))
    selected_za_kogo_id = applied_filters.get("selected_za_kogo_id")
    use_date = bool(applied_filters.get("use_date", False))
    applied_date_range = applied_filters.get("date_range")

    # --- Данные ---
    with st.spinner("Загружаем операции..."):
        df = _fetch_df(session, company_ids, up_selected_id, sel_months, sel_years)

    # Фильтр «Оплата за других»
    if only_for_others and not df.empty:
        cols = set(df.columns)
        if {"_up_company_id", "_za_kogo_platili_id"}.issubset(cols):
            others_mask = (
                (df["_za_kogo_platili_id"].notna())
                & (df["_up_company_id"] != df["_za_kogo_platili_id"])
            )
            if selected_za_kogo_id is not None:
                others_mask = others_mask & (df["_za_kogo_platili_id"] == selected_za_kogo_id)
            df = df[others_mask]
        else:
            st.info("Фильтр «Оплата за других» пропущен: в текущей выборке нет колонок _up_company_id / _za_kogo_platili_id.")

    # Фильтр по диапазону дат: календарь всегда виден, но применяем только при галочке
    if use_date and not df.empty:
        date_range = applied_date_range
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            d_from, d_to = date_range[0], date_range[1]
        else:
            d_from = d_to = date_range
        df = df[(df["Дата"].dt.date >= d_from) & (df["Дата"].dt.date <= d_to)]


    # Фильтр «Записано»
    if not df.empty and "Записано" in df.columns:
        if recorded_filter == "Только новые (не записанные)":
            df = df[(df["Записано"].isna()) | (df["Записано"] == False)]
        elif recorded_filter == "Только записанные":
            df = df[df["Записано"] == True]

    if df.empty:
        st.warning("Нет операций по выбранным условиям.")
        return

    # ------------------------------------------------------------------
    # ИТОГИ ПО КАТЕГОРИЯМ (вместо итогов по группам) + операции категории
    # ------------------------------------------------------------------
    st.markdown("### Итог по категориям")
    if selected_type_norms:
        df_types = df[df["_op_type_norm"].isin(selected_type_norms)].copy()
    else:
        df_types = df.copy()

    cat_summary = (
        df_types.groupby("Категория", dropna=False, as_index=False)["Сумма"]
        .sum()
        .sort_values("Сумма", ascending=False)
    )
    show_cat = cat_summary.copy()
    show_cat["Сумма"] = show_cat["Сумма"].apply(_fmt_rub)

    total_cat = float(pd.to_numeric(cat_summary["Сумма"], errors="coerce").fillna(0).sum())
    show_cat = pd.concat(
        [show_cat, pd.DataFrame([{"Категория": "ИТОГО", "Сумма": _fmt_rub(total_cat)}])],
        ignore_index=True
    )
    st.dataframe(show_cat, use_container_width=True, hide_index=True)

    # --- Drill-down: Категория → Операции + редактор ---
    st.markdown("#### Операции выбранной категории")

    options_cat = [c for c in cat_summary["Категория"].dropna().tolist()]
    if not options_cat:
        st.info("Нет категорий для детализации.")
        return

    if st.session_state.get("itog_selected_category") not in options_cat:
        st.session_state["itog_selected_category"] = options_cat[0]
    selected_category = st.selectbox(
        "Категория для детализации",
        options=options_cat,
        key="itog_selected_category",
    )
    ops_df = df_types[df_types["Категория"] == selected_category].copy()

    if ops_df.empty:
        st.info("Операций не найдено.")
    else:
        # добавили Плательщика/ГК/За кого платили + ИТОГО одной строкой
        view_df = ops_df[[
            "id", "Месяц", "Дата",
            "Плательщик", "Счет плательщика", "Получатель", "Счет получателя",
            "Головная компания", "За кого платили",
            "Назначение", "Сумма", "Записано", "Тип", "Комментарий"  # ← добавили «Записано»
        ]].copy().sort_values(["Дата", "id"], ascending=[False, False], na_position="last").reset_index(drop=True)

        search_key = f"itog_op_search::{selected_category}"
        op_search = st.text_input(
            "Поиск по операциям категории",
            key=search_key,
            placeholder="Плательщик, получатель, назначение, комментарий...",
        ).strip()

        filtered_view_df = view_df.copy()
        if op_search:
            search_blob = (
                view_df["Плательщик"].fillna("").astype(str)
                + " "
                + view_df["Счет плательщика"].fillna("").astype(str)
                + " "
                + view_df["Получатель"].fillna("").astype(str)
                + " "
                + view_df["Счет получателя"].fillna("").astype(str)
                + " "
                + view_df["Головная компания"].fillna("").astype(str)
                + " "
                + view_df["За кого платили"].fillna("").astype(str)
                + " "
                + view_df["Назначение"].fillna("").astype(str)
                + " "
                + view_df["Комментарий"].fillna("").astype(str)
                + " "
                + view_df["Тип"].fillna("").astype(str)
            ).str.lower()
            filtered_view_df = view_df[search_blob.str.contains(op_search.lower(), na=False)].copy()

        st.caption(f"Операций в текущем списке: {len(filtered_view_df)} из {len(view_df)}")

        disp_df = filtered_view_df.copy()
        disp_df["Сумма"] = disp_df["Сумма"].apply(_fmt_rub)

        total_ops = float(pd.to_numeric(filtered_view_df["Сумма"], errors="coerce").fillna(0).sum())
        total_row = {
            "id": None, "Месяц": "", "Дата": "",
            "Плательщик": "", "Счет плательщика": "", "Получатель": "", "Счет получателя": "",
            "Головная компания": "", "За кого платили": "",
            "Назначение": "ИТОГО",
            "Сумма": _fmt_rub(total_ops), "Записано": "", "Тип": "", "Комментарий": ""  # ← пусто для итога
        }

        disp_df = pd.concat([disp_df, pd.DataFrame([total_row])], ignore_index=True)
        disp_df["Записано"] = disp_df["Записано"].apply(lambda v: "✅" if bool(v) else "")

        disp_df["Дата"] = pd.to_datetime(disp_df["Дата"], errors="coerce", dayfirst=True).dt.strftime("%d.%m.%Y")
        st.dataframe(disp_df.drop(columns=["id"]), use_container_width=True, hide_index=True)

        # --- Выбор операции для редактирования ---
        options_ops = []
        for _, row in filtered_view_df.iterrows():
            try:
                rid = int(row["id"])
            except Exception:
                continue
            date_str = pd.to_datetime(row["Дата"], errors="coerce", dayfirst=True)
            if pd.isna(date_str):
                date_disp = ""
            else:
                date_disp = date_str.strftime("%d.%m.%Y")
            payer_name = str(row.get("Плательщик", "") or "")
            receiver_name = str(row.get("Получатель", "") or "")
            purpose_short = str(row["Назначение"])[:50]
            options_ops.append((rid, f"{date_disp} • {payer_name} -> {receiver_name} • {purpose_short} • {_fmt_rub(row['Сумма'])}"))

        if not options_ops:
            st.info("По текущему поиску операции не найдены. Очисти поиск, чтобы увидеть все записи категории.")
            return

        op_ids = [o[0] for o in options_ops]
        op_labels = dict(options_ops)
        selected_op_widget_key = "itog_selected_op_id"
        selected_op_pending_key = "itog_selected_op_id_pending"
        pending_selected_op_id = st.session_state.pop(selected_op_pending_key, None)
        if pending_selected_op_id in op_ids:
            st.session_state[selected_op_widget_key] = pending_selected_op_id
        elif st.session_state.get(selected_op_widget_key) not in op_ids:
            st.session_state[selected_op_widget_key] = op_ids[0]

        def _shift_selected_op(step: int) -> None:
            current_id = st.session_state.get(selected_op_widget_key, op_ids[0])
            try:
                current_idx = op_ids.index(current_id)
            except ValueError:
                current_idx = 0
            next_idx = max(0, min(len(op_ids) - 1, current_idx + step))
            st.session_state[selected_op_widget_key] = op_ids[next_idx]

        pop_ctx = getattr(st, "popover", None)
        ctx = pop_ctx("✏️ Редактировать выбранную операцию") if pop_ctx else st.expander("✏️ Редактировать выбранную операцию")

        with ctx:
            current_selected_id = st.session_state.get(selected_op_widget_key, op_ids[0])
            current_op_index = op_ids.index(current_selected_id)
            prev_col, next_col = st.columns([1, 1])
            prev_col.button(
                "←",
                key="itog_prev_op",
                disabled=current_op_index == 0,
                help="Предыдущая операция",
                on_click=_shift_selected_op,
                args=(-1,),
            )
            next_col.button(
                "→",
                key="itog_next_op",
                disabled=current_op_index == len(op_ids) - 1,
                help="Следующая операция",
                on_click=_shift_selected_op,
                args=(1,),
            )
            selected_id = st.selectbox(
                "Операция для редактирования",
                options=op_ids,
                key=selected_op_widget_key,
                format_func=lambda oid: op_labels.get(oid, "—"),
            )
            st.caption(op_labels.get(selected_id, ""))
            obj = session.get(m_statement.Statement, selected_id)
            st.markdown(f"**Счет плательщика:** {clean_account(getattr(obj, 'payer_account', None)) or '—'}")
            st.markdown(f"**Счет получателя:** {clean_account(getattr(obj, 'receiver_account', None)) or '—'}")

            # Справочники
            groups = session.query(m_group.Group).order_by(m_group.Group.name.asc()).all()
            cats = session.query(m_cat.Category).order_by(m_cat.Category.name.asc()).all()
            group_name_by_id = {g.id: g.name for g in groups}
            cats_by_group = {}
            for c in cats:
                cats_by_group.setdefault(c.group_id, []).append(c)
            up_companies = session.query(m_up.UpCompany).order_by(m_up.UpCompany.name.asc()).all()
            up_name_by_id = {u.id: u.name for u in up_companies}

            # Текущие значения
            cur_month = obj.report_month or ""
            cur_type = str(obj.operation_type or "").strip().lower()
            cur_comment = obj.comment or ""
            cur_group_name = group_name_by_id.get(obj.group_id, None)
            # Текущее «за кого платили»
            cur_zk_id = getattr(obj, "za_kogo_platili_id", None)
            cur_zk_name = up_name_by_id.get(cur_zk_id, up_name_by_id.get(obj.up_company_id, None))

            with st.form(f"itog_edit_form_{selected_id}"):
                # Поля формы
                new_month = st.text_input("Месяц", value=cur_month, placeholder="YYYY-MM")
                type_options = ["Списание", "Поступление"]
                new_type = st.selectbox(
                    "Тип операции",
                    options=type_options,
                    index=(0 if cur_type == "списание" else 1),
                    key=f"itog_edit_type_{selected_id}",
                )
                # За кого платили (UpCompany)
                up_names = [u.name for u in up_companies]
                sel_zk_name = st.selectbox(
                    "За кого платили",
                    options=up_names,
                    index=(up_names.index(cur_zk_name) if cur_zk_name in up_names else 0),
                    key=f"itog_edit_zk_{selected_id}",
                )
                sel_zk = next((u for u in up_companies if u.name == sel_zk_name), None)

                # Выбор группы
                group_names = [g.name for g in groups]
                sel_group_name = st.selectbox(
                    "Группа",
                    options=group_names,
                    index=(group_names.index(cur_group_name) if cur_group_name in group_names else 0),
                    key=f"itog_edit_group_{selected_id}",
                )
                sel_group = next((g for g in groups if g.name == sel_group_name), None)

                # Категории по выбранной группе (если нет — показываем все)
                cats_for_group = cats_by_group.get(sel_group.id if sel_group else None, [])
                cat_names = [c.name for c in cats_for_group] if cats_for_group else [c.name for c in cats]
                cur_cat_name = next((c.name for c in cats if c.id == obj.category_id), None)

                new_cat_name = st.selectbox(
                    "Категория",
                    options=cat_names,
                    index=(cat_names.index(cur_cat_name) if cur_cat_name in cat_names else 0),
                    key=f"itog_edit_category_{selected_id}",
                )

                new_comment = st.text_area("Комментарий", value=cur_comment, height=120, key=f"itog_edit_comment_{selected_id}")

                if st.form_submit_button("💾 Сохранить изменения"):
                    try:
                        obj.report_month = (new_month or "").strip() or None
                        obj.operation_type = (new_type or "").strip() or None
                        obj.comment = (new_comment or "").strip() or None

                        # Категория первична: её group_id также переносим в запись
                        new_cat = next((c for c in cats if c.name == new_cat_name), None)
                        target_category_after_save = selected_category
                        if new_cat:
                            obj.category_id = new_cat.id
                            obj.group_id = new_cat.group_id
                            target_category_after_save = new_cat.name or selected_category
                        else:
                            if sel_group:
                                obj.group_id = sel_group.id

                        # Приводим знак суммы локально под выбранный тип
                        obj.amount = normalize_amount_by_type(obj.operation_type, obj.amount)
                        # За кого платили
                        if sel_zk:
                            obj.za_kogo_platili_id = sel_zk.id  # правильное имя поля

                        session.commit()
                        st.session_state["itog_selected_category"] = target_category_after_save
                        st.session_state[selected_op_pending_key] = selected_id
                        st.success("Сохранено")
                        st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"Ошибка сохранения: {e}")

    # --- Массовая пометка только для НЕ записанных операций ---
    if recorded_filter == "Только новые (не записанные)":
        st.markdown("### 📌 Массовая пометка: «Записано» по категории")

        # Берём только реально «новые» — recorded == False ИЛИ NULL
        ops_unrec = ops_df[(ops_df["Записано"].isna()) | (ops_df["Записано"] == False)].copy()
        cat_count_unrec = int(len(ops_unrec))
        cat_sum_unrec = float(pd.to_numeric(ops_unrec["Сумма"], errors="coerce").fillna(0).sum()) if cat_count_unrec else 0.0

        if cat_count_unrec == 0:
            st.info("В выбранной категории нет новых (не записанных) операций для пометки.")
        else:
            _pop = getattr(st, "popover", None)
            if _pop:
                with _pop("✅ Записать новые операции категории (подтверждение)"):
                    st.info(
                        f"Будут помечены как **«Записано»** все **новые** операции категории **{selected_category}** "
                        f"по текущему срезу.\n\nКоличество: **{cat_count_unrec}**, сумма: **{_fmt_rub(cat_sum_unrec)}**."
                    )
                    if st.button("Подтвердить запись", key="confirm_record_category"):
                        try:
                            cat_ids = [r[0] for r in session.query(m_cat.Category.id)
                                    .filter(m_cat.Category.name == selected_category).all()]
                            if not cat_ids:
                                st.warning("Категория не найдена по текущему выбору.")
                            else:
                                upd = (
                                    m_statement.Statement.__table__.update()
                                    .where(m_statement.Statement.report_month.in_(sel_months))
                                    .where(m_statement.Statement.category_id.in_(cat_ids))
                                    .where(or_(  # только незаписанные (False или NULL)
                                        m_statement.Statement.recorded == False,
                                        m_statement.Statement.recorded.is_(None)
                                    ))
                                )
                                if company_ids:
                                    upd = upd.where(
                                        or_(
                                            m_statement.Statement.payer_company_id.in_(company_ids),
                                            m_statement.Statement.receiver_company_id.in_(company_ids),
                                        )
                                    )
                                if up_selected_id:
                                    upd = upd.where(m_statement.Statement.up_company_id == up_selected_id)

                                res = session.execute(upd.values(recorded=True))
                                session.commit()
                                st.success(f"Помечено 'Записано': {res.rowcount} операций")
                                st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"Ошибка массовой пометки: {e}")
            else:
                with st.expander("✅ Записать новые операции категории (подтверждение)"):
                    st.info(
                        f"Будут помечены как **«Записано»** все **новые** операции категории **{selected_category}** "
                        f"по текущему срезу.\n\nКоличество: **{cat_count_unrec}**, сумма: **{_fmt_rub(cat_sum_unrec)}**."
                    )
                    if st.button("Подтвердить запись", key="confirm_record_category_fallback"):
                        try:
                            cat_ids = [r[0] for r in session.query(m_cat.Category.id)
                                    .filter(m_cat.Category.name == selected_category).all()]
                            if not cat_ids:
                                st.warning("Категория не найдена по текущему выбору.")
                            else:
                                upd = (
                                    m_statement.Statement.__table__.update()
                                    .where(m_statement.Statement.report_month.in_(sel_months))
                                    .where(m_statement.Statement.category_id.in_(cat_ids))
                                    .where(or_(
                                        m_statement.Statement.recorded == False,
                                        m_statement.Statement.recorded.is_(None)
                                    ))
                                )
                                if company_ids:
                                    upd = upd.where(
                                        or_(
                                            m_statement.Statement.payer_company_id.in_(company_ids),
                                            m_statement.Statement.receiver_company_id.in_(company_ids),
                                        )
                                    )
                                if up_selected_id:
                                    upd = upd.where(m_statement.Statement.up_company_id == up_selected_id)

                                res = session.execute(upd.values(recorded=True))
                                session.commit()
                                st.success(f"Помечено 'Записано': {res.rowcount} операций")
                                st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"Ошибка массовой пометки: {e}")
    # Если выбран другой режим («Все операции»/«Только записанные») — кнопку не показываем.


    # --- Экспорт в Excel: УДАЛЁН ПО ТЗ ---
