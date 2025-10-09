# tabs/import_income_expenses.py
import datetime as dt
import pandas as pd
import streamlit as st

from core.db import SessionLocal
from core.utils import normalize_amount_by_type
from core.months import RU_MONTHS, ru_label_from_rm, rm_from_ru_label
from db_models import (
    up_company as m_up,
    company as m_company,
    group as m_group,
    category as m_cat,
)
from db_models import income_expense as m_ie


def _ym(d: dt.date) -> str:
    """YYYY-MM из даты."""
    return f"{d.year:04d}-{d.month:02d}"


def _fmt_num(x) -> str:
    """Красивое отображение суммы (без знака ₽, как в предпросмотрах)."""
    try:
        return f"{int(round(float(x))):,}".replace(",", " ")
    except Exception:
        return str(x or "")


# Русские месяцы + конвертеры
# RU month helpers (см. core.months)

def import_income_expenses_tab():
    st.subheader("Импорт расходов/доходов")

    with SessionLocal() as session:
        _render_import_income_expenses(session)


def _render_import_income_expenses(session):
    # --- 1) Выбор головной компании (обязательно) ---
    ups = session.query(m_up.UpCompany).order_by(m_up.UpCompany.name.asc()).all()
    up_names = [u.name for u in ups]
    up_choice = st.selectbox("Головная компания", ["— выберите —"] + up_names, index=0)
    up_obj = next((u for u in ups if u.name == up_choice), None)
    if not up_obj:
        st.info("Выберите головную.")
        return

    # --- 2) Фильтры предпросмотра (по выбранной головной) ---
    # Компания (опционально)
    comps = (
        session.query(m_company.Company)
        .filter(m_company.Company.up_company_id == up_obj.id)
        .order_by(m_company.Company.name.asc())
        .all()
    )
    comp_names = ["— все компании —"] + [c.name for c in comps]
    comp_choice = st.selectbox("Компания (фильтр предпросмотра)", comp_names, index=0)
    comp_obj = next((c for c in comps if c.name == comp_choice), None)

    # Месяцы (мультивыбор, русские названия)
    months_rows = (
        session.query(m_ie.IncomeExpense.report_month)
        .filter(m_ie.IncomeExpense.up_company_id == up_obj.id)
        .distinct().all()
    )
    months_rm = sorted({r[0] for r in months_rows if r and r[0]}, reverse=True)

    # Если записей ещё нет — подставляем текущий месяц, чтобы UI работал
    if not months_rm:
        current_rm = _ym(dt.date.today())  # YYYY-MM
        months_rm = [current_rm]
        st.caption("Пока записей нет — подставлен текущий месяц для фильтра.")

    # Преобразуем в русские ярлыки 'Месяц YYYY'
    months_labels = [ru_label_from_rm(rm) for rm in months_rm]
    default_labels = months_labels[:1] if months_labels else []
    sel_months_labels = st.multiselect("Учётный месяц(ы)", options=months_labels, default=default_labels)

    # Обратно к 'YYYY-MM' для запроса
    sel_months_rm = [rm_from_ru_label(lbl) for lbl in (sel_months_labels or default_labels)]

    # --- 3) Предпросмотр записей по выбранным фильтрам ---
    q = session.query(m_ie.IncomeExpense).filter(
        m_ie.IncomeExpense.up_company_id == up_obj.id,
        m_ie.IncomeExpense.report_month.in_(sel_months_rm),
    )
    if comp_obj:
        q = q.filter(m_ie.IncomeExpense.company_id == comp_obj.id)

    rows = q.order_by(m_ie.IncomeExpense.date.asc(), m_ie.IncomeExpense.id.asc()).all()

    st.markdown("### Предпросмотр")
    if not rows:
        st.info("Нет записей по выбранным условиям.")
    else:
        data = []
        for r in rows:
            data.append({
                "id": r.id,
                "Дата": r.date,
                "Месяц": ru_label_from_rm(r.report_month) if r.report_month else "",
                "Головная": r.up_company.name if r.up_company else "",
                "Компания": r.company.name if r.company else "",
                "Группа": r.group.name if r.group else "",
                "Категория": r.category.name if r.category else "",
                "Тип": r.operation_type,
                "Сумма": float(r.amount or 0),
                "Комментарий": r.comment or "",
            })
        df = pd.DataFrame(data)
        df_view = df.copy()
        try:
            df_view["Дата"] = pd.to_datetime(df_view["Дата"]).dt.strftime("%Y-%m-%d")
        except Exception:
            pass
        df_view["Сумма"] = df_view["Сумма"].map(_fmt_num)
        st.dataframe(df_view.drop(columns=["id"]), use_container_width=True, hide_index=True)

    st.divider()

    # --- 4) Две кнопки под предпросмотром: Добавить / Редактировать ---
    col_add, col_edit = st.columns(2)

    # ====== 4.1 Добавление записи ======
    with col_add:
        pop = getattr(st, "popover", None)
        add_ctx = pop("➕ Добавить запись") if pop else st.expander("➕ Добавить запись", expanded=False)

    with add_ctx:
        # Тянем актуальные справочники для формы
        groups = session.query(m_group.Group).order_by(m_group.Group.name.asc()).all()
        g_names = ["— не указана —"] + [g.name for g in groups]

        date_val = st.date_input("Дата", value=dt.date.today(), key="ie_add_date")
        op_type = st.selectbox("Тип операции", ["списание", "поступление"], index=0, key="ie_add_type")
        amount_raw = st.number_input("Сумма", value=0.0, step=100.0, format="%.2f", key="ie_add_amount")

        # Учётный месяц (рус.) — по умолчанию = месяц даты платежа
        default_month_index_add = (date_val.month - 1) if isinstance(date_val, dt.date) else (dt.date.today().month - 1)
        sel_ru_month_add = st.selectbox("Учётный месяц", options=RU_MONTHS, index=default_month_index_add, key="ie_add_ru_month")

        # Компания для добавления (может отличаться от фильтра предпросмотра)
        comp_names_add = ["— не указана —"] + [c.name for c in comps]
        comp_choice_add = st.selectbox(
            "Компания",
            comp_names_add,
            index=(0 if not comp_obj else comp_names_add.index(comp_obj.name) if comp_obj.name in comp_names_add else 0),
            key="ie_add_company"
        )
        comp_obj_add = next((c for c in comps if c.name == comp_choice_add), None)

        g_choice = st.selectbox("Группа", g_names, index=0, key="ie_add_group")
        g_obj = next((g for g in groups if g.name == g_choice), None)

        cats_q = session.query(m_cat.Category)
        if g_obj:
            cats_q = cats_q.filter(m_cat.Category.group_id == g_obj.id)
        cats = cats_q.order_by(m_cat.Category.name.asc()).all()
        c_names = ["— не указана —"] + [c.name for c in cats]
        c_choice = st.selectbox("Категория", c_names, index=0, key="ie_add_category")
        c_obj = next((c for c in cats if c.name == c_choice), None)

        comment = st.text_input("Комментарий", value="", placeholder="необязательно", key="ie_add_comment")

        if st.button("Добавить", key="ie_add_btn"):
            try:
                if amount_raw is None or float(amount_raw) == 0.0:
                    st.warning("Сумма не может быть нулевой.")
                else:
                    amount = normalize_amount_by_type(op_type, amount_raw)
                    month_idx_add = (RU_MONTHS.index(sel_ru_month_add) + 1) if sel_ru_month_add in RU_MONTHS else date_val.month
                    obj = m_ie.IncomeExpense(
                        date=date_val,
                        report_month=f"{date_val.year:04d}-{month_idx_add:02d}",
                        up_company_id=up_obj.id,
                        company_id=comp_obj_add.id if comp_obj_add else None,
                        group_id=g_obj.id if g_obj else None,
                        category_id=c_obj.id if c_obj else None,
                        operation_type=op_type,
                        amount=amount,
                        comment=(comment or None),
                    )
                    session.add(obj)
                    session.commit()
                    st.success("Запись добавлена.")
                    st.rerun()
            except Exception as e:
                session.rollback()
                st.error(f"Ошибка добавления: {e}")

    # ====== 4.2 Редактирование/Удаление ======
    with col_edit:
        pop = getattr(st, "popover", None)
        edit_ctx = pop("✏️ Редактировать / Удалить") if pop else st.expander("✏️ Редактировать / Удалить", expanded=False)

    with edit_ctx:
        # Нечего редактировать
        if not rows:
            st.info("Нет записей для редактирования.")
        else:
            # Список записей из текущего предпросмотра
            options = []
            for r in rows:
                marker = (r.comment or (r.category.name if r.category else (r.group.name if r.group else "")))
                label = f"{r.id} • {r.date} • {r.operation_type} • {str(marker).strip()[:50]}"
                options.append((r.id, label))
            selected_id = st.selectbox(
                "Запись",
                options=[oid for oid, _ in options],
                format_func=lambda oid: dict(options).get(oid, "—"),
                key="ie_edit_pick",
            )

            obj = session.get(m_ie.IncomeExpense, selected_id)
            if not obj:
                st.warning("Запись не найдена.")
            else:
                # Текущие справочники
                groups = session.query(m_group.Group).order_by(m_group.Group.name.asc()).all()
                g_names = [g.name for g in groups]
                cur_group_name = obj.group.name if obj.group else None

                # Для компании
                comp_names_all = [c.name for c in comps]
                cur_comp_name = obj.company.name if obj.company else None

                # Поля формы
                col1, col2 = st.columns(2)
                with col1:
                    new_date = st.date_input("Дата", value=obj.date or dt.date.today(), key="ie_edit_date")
                    new_type = st.selectbox("Тип операции", ["списание", "поступление"],
                                            index=(0 if (obj.operation_type or "") == "списание" else 1),
                                            key="ie_edit_type")
                    new_amount_raw = st.number_input("Сумма", value=float(obj.amount or 0.0), step=100.0, format="%.2f", key="ie_edit_amount")
                with col2:
                    new_comp_name = st.selectbox(
                        "Компания",
                        options=["— не указана —"] + comp_names_all,
                        index=(0 if not cur_comp_name else (comp_names_all.index(cur_comp_name) + 1) if cur_comp_name in comp_names_all else 0),
                        key="ie_edit_company"
                    )
                    new_group_name = st.selectbox(
                        "Группа",
                        options=["— не указана —"] + g_names,
                        index=(0 if not cur_group_name else (g_names.index(cur_group_name) + 1) if cur_group_name in g_names else 0),
                        key="ie_edit_group"
                    )

                # Категории по выбранной группе
                new_group_obj = next((g for g in groups if g.name == new_group_name), None)
                cats_q = session.query(m_cat.Category)
                if new_group_obj:
                    cats_q = cats_q.filter(m_cat.Category.group_id == new_group_obj.id)
                cats = cats_q.order_by(m_cat.Category.name.asc()).all()
                cat_names = [c.name for c in cats]
                cur_cat_name = obj.category.name if obj.category else None
                new_cat_name = st.selectbox(
                    "Категория",
                    options=["— не указана —"] + cat_names,
                    index=(0 if not cur_cat_name else (cat_names.index(cur_cat_name) + 1) if cur_cat_name in cat_names else 0),
                    key="ie_edit_category"
                )

                # Учётный месяц (рус.) — по умолчанию из report_month или из даты
                try:
                    cur_m = int((obj.report_month or _ym(obj.date)).split("-")[1])
                except Exception:
                    cur_m = (obj.date.month if isinstance(obj.date, dt.date) else dt.date.today().month)
                sel_ru_month_edit = st.selectbox(
                    "Учётный месяц",
                    options=RU_MONTHS,
                    index=max(0, min(11, cur_m - 1)),
                    key="ie_edit_ru_month"
                )

                new_comment = st.text_input("Комментарий", value=(obj.comment or ""), key="ie_edit_comment")

                c1, _, c3 = st.columns([1, 1, 1])
                with c1:
                    if st.button("💾 Сохранить", key="ie_edit_save"):
                        try:
                            obj.date = new_date
                            # report_month — по выбору пользователя (рус. месяц → YYYY-MM)
                            m_idx = (RU_MONTHS.index(sel_ru_month_edit) + 1) if sel_ru_month_edit in RU_MONTHS else new_date.month
                            obj.report_month = f"{new_date.year:04d}-{m_idx:02d}"
                            obj.operation_type = (new_type or "").strip().lower()
                            obj.amount = normalize_amount_by_type(obj.operation_type, new_amount_raw)
                            obj.comment = (new_comment or None)

                            # Компания
                            if new_comp_name and new_comp_name != "— не указана —":
                                new_comp_obj = next((c for c in comps if c.name == new_comp_name), None)
                                obj.company_id = new_comp_obj.id if new_comp_obj else None
                            else:
                                obj.company_id = None

                            # Группа и категория
                            if new_group_obj:
                                obj.group_id = new_group_obj.id
                            else:
                                obj.group_id = None

                            if new_cat_name and new_cat_name != "— не указана —":
                                new_cat_obj = next((c for c in cats if c.name == new_cat_name), None)
                                obj.category_id = new_cat_obj.id if new_cat_obj else None
                            else:
                                obj.category_id = None

                            session.commit()
                            st.success("Изменения сохранены.")
                            st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"Ошибка сохранения: {e}")

                with c3:
                    if st.button("🗑 Удалить", key="ie_edit_delete"):
                        try:
                            session.delete(obj)
                            session.commit()
                            st.success("Запись удалена.")
                            st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"Ошибка удаления: {e}")

