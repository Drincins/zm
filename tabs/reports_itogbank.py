# tabs/reports_itogbank.py
import os
from datetime import datetime
import pandas as pd
import streamlit as st
from sqlalchemy import or_
from core.utils import normalize_amount_by_type

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

def _company_ids_for_up(session, up_company_id: int) -> list[int]:
    rows = (
        session.query(m_company.Company.id)
        .filter(m_company.Company.up_company_id == up_company_id)
        .all()
    )
    return [r[0] for r in rows]

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

def _distinct_report_months(session, company_ids: list[int] | None, up_company_id: int | None) -> list[str]:
    q = session.query(m_statement.Statement.report_month).distinct()
    if company_ids:
        q = q.filter(
            or_(
                m_statement.Statement.payer_company_id.in_(company_ids),
                m_statement.Statement.receiver_company_id.in_(company_ids),
            )
        )
    elif up_company_id:
        q = q.filter(m_statement.Statement.up_company_id == up_company_id)

    months = [row[0] for row in q.all() if row and row[0]]
    return sorted(set(months), reverse=True)

def _fetch_df(session, company_ids: list[int] | None, up_company_id: int | None, report_months: list[str]) -> pd.DataFrame:
    q = (
        session.query(
            m_statement.Statement.id.label("id"),
            m_statement.Statement.row_id.label("row_id"),
            m_statement.Statement.date.label("date"),
            m_statement.Statement.report_month.label("report_month"),
            m_statement.Statement.purpose.label("purpose"),
            m_statement.Statement.amount.label("amount"),
            m_statement.Statement.operation_type.label("operation_type"),
            m_statement.Statement.comment.label("comment"),
            m_statement.Statement.recorded.label("recorded"),
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
        "Месяц": r.report_month,
        "Назначение": r.purpose,
        "Сумма": r.amount,
        "Тип": r.operation_type,
        "Группа": r.group_name,
        "Категория": r.category_name,
        "Комментарий": r.comment,
        "Записано": r.recorded,
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

    df["Дата"] = pd.to_datetime(df["Дата"])
    df["Сумма"] = pd.to_numeric(df["Сумма"], errors="coerce").fillna(0.0)
    df["Тип"] = df["Тип"].astype(str).str.strip().str.lower()
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
    # Исправление имени колонки + защита
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

    def _payer_name(row):
        return (
            comp_name_by_id.get(row["_payer_company_id"])
            or firm_name_by_id.get(row["_payer_firm_id"])
            or (row["_payer_raw"] or "")
            or ""
        )

    def _receiver_name(row):  # NEW
        return (
            comp_name_by_id.get(row["_receiver_company_id"])
            or firm_name_by_id.get(row["_receiver_firm_id"])
            or (row["_receiver_raw"] or "")
            or ""
        )

    df["Плательщик"] = [_payer_name(row) for _, row in df.iterrows()]
    df["Получатель"] = [_receiver_name(row) for _, row in df.iterrows()]  # NEW
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
    with st.form("itogbank_filters", border=True):
        st.markdown("### Фильтры")

        # Базовые значения/списки
        up_list = session.query(m_up.UpCompany).order_by(m_up.UpCompany.name.asc()).all()
        up_names = [u.name for u in up_list]
        up_display = ["— все —"] + up_names

        # 1) Головная + режим выбора компаний (в две колонки)
        c1, c2 = st.columns([2, 1])
        up_selected_name = c1.selectbox("Головная компания", options=up_display, index=0)
        up_selected_obj = next((u for u in up_list if u.name == up_selected_name), None)
        up_selected_id = up_selected_obj.id if up_selected_obj else None

        if up_selected_id:
            mode = c2.radio("Режим выбора компаний",
                            options=["Все компании головной", "Одна компания"],
                            index=0, horizontal=True)
        else:
            mode = c2.radio("Режим выбора компаний",
                            options=["Все компании", "Одна компания"],
                            index=0, horizontal=True)

        # 2) Выбор компании (при необходимости)
        company_ids: list[int] | None = None
        company_obj = None
        allow_all_companies = False

        if up_selected_id:
            if mode == "Все компании головной":
                company_ids = _company_ids_for_up(session, up_selected_id)
            else:
                companies_ref = (
                    session.query(m_company.Company)
                    .filter(m_company.Company.up_company_id == up_selected_id)
                    .order_by(m_company.Company.name.asc())
                    .all()
                )
                names = [c.name for c in companies_ref]
                choice = st.selectbox("Компания", options=(["— выберите компанию —"] + names), index=0)
                company_obj = next((c for c in companies_ref if c.name == choice), None)
                company_ids = [company_obj.id] if company_obj else None
        else:
            if mode == "Все компании":
                allow_all_companies = True
                company_ids = None
            else:
                companies_fact = _companies_from_statement(session, up_company_id=None)
                names = [c.name for c in companies_fact]
                choice = st.selectbox("Компания", options=(["— выберите компанию —"] + names), index=0)
                company_obj = next((c for c in companies_fact if c.name == choice), None)
                company_ids = [company_obj.id] if company_obj else None

        # 3) Учётный месяц(ы)
        months = _distinct_report_months(session, company_ids, up_selected_id)
        sel_months = st.multiselect("Учётный месяц(ы)", options=months, default=(months[:1] if months else []))

        # 4) Частые фильтры — в две колонки
        c3, c4 = st.columns([1, 1])

        recorded_filter = c3.selectbox(
            "Что показывать",
            ["Все операции", "Только новые (не записанные)", "Только записанные"],
            index=0,
            key="itog_recorded_filter"  # уникальный ключ
        )

        op_types = c4.multiselect(
            "Тип операции",
            ["списание", "поступление"],
            default=["списание", "поступление"],
            key="itog_op_types"  # уникальный ключ
        )

        # 5) Редкие фильтры — под экспандер
        with st.expander("Доп. фильтры"):
            only_for_others = st.checkbox("Оплата за других (up_company ≠ за кого платили)", value=False)

            # Фильтр по датам — календарь всегда виден, фильтр применяется только при включенной галочке
            use_date = st.checkbox("Фильтр по диапазону дат", value=False, key="itb_use_date")

            default_start = datetime.today().date().replace(day=1)
            default_end = datetime.today().date()
            date_range = st.date_input(
                "Диапазон дат",
                key="itb_date_range",
                value=st.session_state.get("itb_date_range", (default_start, default_end)),
            )
            st.caption("Подсчет по датам применяется только при включенной галочке выше.")


        filters_submitted = st.form_submit_button("Применить")

    # --- Данные ---
    with st.spinner("Загружаем операции..."):
        df = _fetch_df(session, company_ids, up_selected_id, sel_months)

    # Фильтр «Оплата за других»
    if only_for_others and not df.empty:
        cols = set(df.columns)
        if {"_up_company_id", "_za_kogo_platili_id"}.issubset(cols):  # защита + правильное имя колонки
            df = df[(df["_za_kogo_platili_id"].notna()) & (df["_up_company_id"] != df["_za_kogo_platili_id"])]
        else:
            st.info("Фильтр «Оплата за других» пропущен: в текущей выборке нет колонок _up_company_id / _za_kogo_platili_id.")

    # Фильтр по диапазону дат: календарь всегда виден, но применяем только при галочке
    if st.session_state.get("itb_use_date") and not df.empty:
        date_range = st.session_state.get("itb_date_range")
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
    df_types = df[df["Тип"].isin(op_types)].copy()

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

    selected_category = st.selectbox("Категория для детализации", options=options_cat, index=0 if options_cat else 0)
    ops_df = df_types[df_types["Категория"] == selected_category].copy()

    if ops_df.empty:
        st.info("Операций не найдено.")
    else:
        # добавили Плательщика/ГК/За кого платили + ИТОГО одной строкой
        view_df = ops_df[[
            "id", "Месяц", "Дата",
            "Плательщик","Получатель", "Головная компания", "За кого платили",
            "Назначение", "Сумма", "Записано", "Тип", "Комментарий"  # ← добавили «Записано»
        ]].copy()


        disp_df = view_df.copy()
        disp_df["Сумма"] = disp_df["Сумма"].apply(_fmt_rub)

        total_ops = float(pd.to_numeric(view_df["Сумма"], errors="coerce").fillna(0).sum())
        total_row = {
            "id": None, "Месяц": "", "Дата": "",
            "Плательщик": "", "Получатель": "", "Головная компания": "", "За кого платили": "",
            "Назначение": "ИТОГО",
            "Сумма": _fmt_rub(total_ops), "Записано": "", "Тип": "", "Комментарий": ""  # ← пусто для итога
        }

        disp_df = pd.concat([disp_df, pd.DataFrame([total_row])], ignore_index=True)

        disp_df["Дата"] = pd.to_datetime(disp_df["Дата"], errors="coerce").dt.strftime("%Y-%m-%d")
        st.dataframe(disp_df.drop(columns=["id"]), use_container_width=True, hide_index=True)

        # --- Выбор операции для редактирования ---
        options_ops = [
            (int(row["id"]),
             f'{pd.to_datetime(row["Дата"]).date()} • {str(row["Назначение"])[:60]} • {_fmt_rub(row["Сумма"])}')
            for _, row in view_df.iterrows()
        ]
        selected_id = st.selectbox(
            "Выберите операцию для редактирования",
            options=[o[0] for o in options_ops],
            format_func=lambda oid: dict(options_ops).get(oid, "—")
        )

        # Попап (если поддерживается), иначе — expander
        pop_ctx = getattr(st, "popover", None)
        ctx = pop_ctx("✏️ Редактировать выбранную операцию") if pop_ctx else st.expander("✏️ Редактировать выбранную операцию")

        with ctx:
            obj = session.get(m_statement.Statement, selected_id)

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


            # Поля формы
            new_month = st.text_input("Месяц", value=cur_month, placeholder="YYYY-MM")
            new_type = st.selectbox("Тип операции", options=["списание", "поступление"],
                                    index=(0 if cur_type == "списание" else 1))
            # За кого платили (UpCompany)
            up_names = [u.name for u in up_companies]
            sel_zk_name = st.selectbox(
                "За кого платили",
                options=up_names,
                index=(up_names.index(cur_zk_name) if cur_zk_name in up_names else 0),
                key="edit_zk_select"
            )
            sel_zk = next((u for u in up_companies if u.name == sel_zk_name), None)

            # Выбор группы
            group_names = [g.name for g in groups]
            sel_group_name = st.selectbox(
                "Группа",
                options=group_names,
                index=(group_names.index(cur_group_name) if cur_group_name in group_names else 0),
                key="edit_group_select"
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
                key="edit_category_select"
            )

            new_comment = st.text_area("Комментарий", value=cur_comment, height=120)

            # Сохранение
            if st.button("💾 Сохранить изменения"):
                try:
                    obj.report_month = (new_month or "").strip() or None
                    obj.operation_type = (new_type or "").strip().lower()
                    obj.comment = (new_comment or "").strip() or None

                    # Категория первична: её group_id также переносим в запись
                    new_cat = next((c for c in cats if c.name == new_cat_name), None)
                    if new_cat:
                        obj.category_id = new_cat.id
                        obj.group_id = new_cat.group_id
                    else:
                        if sel_group:
                            obj.group_id = sel_group.id
                    # Приводим знак суммы локально под выбранный тип
                    obj.amount = normalize_amount_by_type(obj.operation_type, obj.amount)
                    # За кого платили
                    if sel_zk:
                        obj.za_kogo_platili_id = sel_zk.id  # правильное имя поля


                    session.commit()
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

