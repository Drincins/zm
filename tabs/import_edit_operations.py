from __future__ import annotations

# tabs/import_edit_operations.py
from datetime import datetime

import streamlit as st
import pandas as pd
from sqlalchemy import or_
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

from core.db import SessionLocal
from core.months import RU_MONTHS, RU_MONTH_NAME_TO_INDEX, month_name_from_date
from db_models import editbank, statement, firm, company, category, group, up_company
from core.parser import clean_account, clean_inn  # единая очистка ИНН/счета


def _is_rm_yyyy_mm(s: str) -> bool:
    return isinstance(s, str) and len(s) == 7 and s[4] == "-"


def _resolve_month_year(raw_month: str | None, date_val) -> tuple[str | None, int]:
    """Вернуть (месяц-словом, год) из разных форматов; год по умолчанию текущий."""
    default_year = datetime.now().year
    if raw_month:
        raw = str(raw_month).strip()
        # форматы YYYY-MM
        if _is_rm_yyyy_mm(raw):
            year_val = int(raw[:4])
            month_idx = int(raw[5:])
            month_name = RU_MONTHS[month_idx - 1] if 1 <= month_idx <= 12 else raw
            return month_name, year_val
        parts = raw.split()
        # формат "Ноябрь 2025"
        if len(parts) >= 2 and parts[-1].isdigit():
            try:
                year_val = int(parts[-1])
            except ValueError:
                year_val = date_val.year if date_val else default_year
            month_name = " ".join(parts[:-1]).strip() or (month_name_from_date(date_val) if date_val else None)
            return month_name, year_val
        # просто название месяца
        if raw in RU_MONTH_NAME_TO_INDEX:
            return raw, (date_val.year if date_val else default_year)
        # дефолт — оставляем как есть и год по дате/умолчанию
        return raw, (date_val.year if date_val else default_year)

    # если месяца нет — берем из даты/дефолта
    month_name = month_name_from_date(date_val) if date_val else None
    year_val = date_val.year if date_val else default_year
    return month_name, year_val


def import_edit_operations_tab():
    st.header("Редактирование операций (импортированные из выписки)")

    # Единый стиль кнопок (одинаковая ширина/высота)
    st.markdown(
        """
    <style>
      .stButton>button { width: 100%; min-height: 38px; }
    </style>
    """,
        unsafe_allow_html=True,
    )

    with SessionLocal() as session:
        # --- Справочники ---
        firms = session.query(firm.Firm).all()
        companies = session.query(company.Company).all()
        categories = session.query(category.Category).all()
        groups = session.query(group.Group).all()
        up_companies = session.query(up_company.UpCompany).all()

        firm_map = {f.id: f.name for f in firms}
        firm_inn_map = {f.id: f.inn for f in firms}
        company_map = {c.id: c.name for c in companies}
        company_up_map = {c.id: c.up_company_id for c in companies}  # фолбэк головной компании
        category_map = {c.id: c.name for c in categories}
        group_map = {g.id: g.name for g in groups}
        up_company_map = {u.id: u.name for u in up_companies}
        up_company_name_to_id = {u.name: u.id for u in up_companies}

        # Обратные маппинги и категории по группам (для редактора)
        cats_by_group: dict[int | None, list[category.Category]] = {}
        for c in categories:
            cats_by_group.setdefault(c.group_id, []).append(c)

        # --- SQL-фильтры + пагинация ---
        up_name_to_ids: dict[str, set[int]] = {}
        for u in up_companies:
            up_name_to_ids.setdefault(u.name, set()).add(u.id)

        op_type_options = sorted(
            {str(r[0]).strip() for r in session.query(editbank.EditBank.operation_type).distinct().all() if r[0] and str(r[0]).strip()}
        )
        report_month_options = sorted(
            [r[0] for r in session.query(editbank.EditBank.report_month).distinct().all() if r[0]]
        )

        st.session_state.setdefault(
            "editbank_filters",
            {"up_company": [], "month": [], "op_type": [], "recorded": "Все"},
        )
        fstate = st.session_state["editbank_filters"]

        with st.form("editbank_filters_form", clear_on_submit=False, border=True):
            st.markdown("### Фильтры")
            c1, c2, c3 = st.columns(3)
            with c1:
                sel_up = st.multiselect("Головная компания", options=sorted(up_name_to_ids.keys()), default=fstate.get("up_company", []))
            with c2:
                sel_month = st.multiselect("Учётный месяц", options=report_month_options, default=fstate.get("month", []))
            with c3:
                sel_type = st.multiselect("Тип операции", options=op_type_options, default=fstate.get("op_type", []))
                sel_recorded = st.selectbox(
                    "Записано",
                    options=["Все", "Только новые (не записанные)", "Только записанные"],
                    index=["Все", "Только новые (не записанные)", "Только записанные"].index(fstate.get("recorded", "Все")),
                )
            submitted_filters = st.form_submit_button("Применить", type="primary")

        if submitted_filters:
            st.session_state["editbank_filters"] = {
                "up_company": sel_up,
                "month": sel_month,
                "op_type": sel_type,
                "recorded": sel_recorded,
            }
            st.session_state["editbank_page"] = 1
            st.session_state["editbank_page_input"] = 1

        fstate = st.session_state["editbank_filters"]
        filtered_query = session.query(editbank.EditBank)

        if fstate.get("up_company"):
            up_ids = sorted({uid for name in fstate["up_company"] for uid in up_name_to_ids.get(name, set())})
            filtered_query = filtered_query.filter(editbank.EditBank.up_company_id.in_(up_ids)) if up_ids else filtered_query.filter(editbank.EditBank.id == -1)

        if fstate.get("month"):
            filtered_query = filtered_query.filter(editbank.EditBank.report_month.in_(fstate["month"]))

        if fstate.get("op_type"):
            filtered_query = filtered_query.filter(editbank.EditBank.operation_type.in_(fstate["op_type"]))

        rec_filter = fstate.get("recorded", "Все")
        if rec_filter == "Только новые (не записанные)":
            filtered_query = filtered_query.filter(editbank.EditBank.recorded.is_(False))
        elif rec_filter == "Только записанные":
            filtered_query = filtered_query.filter(editbank.EditBank.recorded.is_(True))

        total_rows = filtered_query.count()
        page_size = st.selectbox("Строк на странице", options=[50, 100, 200, 500], index=1, key="editbank_page_size")
        total_pages = max(1, (total_rows + page_size - 1) // page_size)
        current_page = min(max(int(st.session_state.get("editbank_page", 1)), 1), total_pages)
        page_input_value = min(max(int(st.session_state.get("editbank_page_input", current_page)), 1), total_pages)
        st.session_state["editbank_page_input"] = page_input_value

        p1, p2 = st.columns([1, 4])
        with p1:
            current_page = int(
                st.number_input(
                    "Страница",
                    min_value=1,
                    max_value=total_pages,
                    value=page_input_value,
                    step=1,
                    key="editbank_page_input",
                )
            )
        st.session_state["editbank_page"] = current_page
        with p2:
            st.caption(f"Найдено строк: {total_rows}. Показано: {min(page_size, max(total_rows - (current_page - 1) * page_size, 0))}. Страница {current_page}/{total_pages}.")

        ops = (
            filtered_query
            .order_by(editbank.EditBank.date.desc(), editbank.EditBank.id.desc())
            .offset((current_page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        if not ops:
            st.info("По текущим фильтрам записи не найдены.")
            return

        # --- Формируем DataFrame для грида ---
        df_rows = []
        year_candidates = set()
        for op in ops:
            # вычисляем up_company_id для отображения (если пусто — по участнику и типу)
            inferred_up_id = op.up_company_id
            if not inferred_up_id:
                op_type = (op.operation_type or "").strip().lower()
                if "списание" in op_type and op.payer_company_id:
                    inferred_up_id = company_up_map.get(op.payer_company_id)
                elif "поступление" in op_type and op.receiver_company_id:
                    inferred_up_id = company_up_map.get(op.receiver_company_id)
                if not inferred_up_id:
                    inferred_up_id = company_up_map.get(op.payer_company_id) or company_up_map.get(op.receiver_company_id)

            # "за кого платили" для отображения (приоритет — поле из БД, иначе inferred_up_id)
            zk_id = op.za_kogo_platili_id or inferred_up_id

            month_name, year_val = _resolve_month_year(op.report_month, op.date)
            if year_val:
                year_candidates.add(year_val)

            df_rows.append(
                {
                    "id": op.id,
                    "Дата": op.date.strftime("%d.%m.%Y") if op.date else "",
                    "Учётный месяц": month_name or "",
                    "Учётный год": year_val,
                    "Головная компания": up_company_map.get(inferred_up_id, ""),
                    "За кого платили": up_company_map.get(zk_id, ""),  # NEW
                    "Плательщик": (
                        company_map.get(op.payer_company_id)
                        or firm_map.get(op.payer_firm_id)
                        or op.payer_raw
                        or ""
                    ),
                    "ИНН плательщика": clean_inn(op.payer_inn) or "",
                    "Получатель": (
                        company_map.get(op.receiver_company_id)
                        or firm_map.get(op.receiver_firm_id)
                        or op.receiver_raw
                        or ""
                    ),
                    "ИНН получателя": clean_inn(op.receiver_inn) or "",
                    "Назначение": op.purpose or "",
                    "Сумма": op.amount,
                    "Тип операции": op.operation_type or "",
                    "Категория": category_map.get(op.category_id, ""),
                    "Группа": group_map.get(op.group_id, ""),
                    "Комментарий": op.comment or "",
                    "row_id": op.row_id,
                    "Записано": bool(op.recorded),
                }
            )
        df = pd.DataFrame(df_rows)
        if "Дата" in df.columns:
            df["Дата"] = (
                pd.to_datetime(df["Дата"], dayfirst=True, errors="coerce")
                .dt.strftime("%d.%m.%Y")
                .fillna("")
            )

        # --- Месяцы/годы для селектов ---
        ru_month_opts = RU_MONTHS
        year_opts = sorted(year_candidates | {datetime.now().year})

        # --- AgGrid (только просмотр) ---
        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_default_column(editable=False, filter=True, resizable=True)  # всё read-only по умолчанию
        gb.configure_selection(selection_mode="multiple", use_checkbox=True)
        gb.configure_column(
            "id",
            headerCheckboxSelection=True,
            headerCheckboxSelectionFilteredOnly=True,
            checkboxSelection=True,
            pinned="left",
            width=90,
        )

        # Столбцы только для просмотра
        for col in [
            "Учётный месяц",
            "Учётный год",
            "Комментарий",
            "Записано",
            "Головная компания",
            "За кого платили",
            "Категория",
            "Группа",
            "Тип операции",
            "Назначение",
            "Сумма",
            "ИНН плательщика",
            "ИНН получателя",
            "Плательщик",
            "Получатель",
            "Дата",
            "row_id",
        ]:
            gb.configure_column(col, editable=False)

        grid_options = gb.build()
        grid_response = AgGrid(
            df,
            gridOptions=grid_options,
            update_mode=GridUpdateMode.MODEL_CHANGED,
            allow_unsafe_jscode=True,
            theme="streamlit",
            height=650,
            fit_columns_on_grid_load=True,
        )

        # Данные из грида
        grid_data = (grid_response or {}).get("data", df)
        edited_df = pd.DataFrame(grid_data)

        # Выбранные строки
        selected_raw = (grid_response or {}).get("selected_rows", None)
        if selected_raw is None:
            selected_list = []
        elif isinstance(selected_raw, list):
            selected_list = selected_raw
        else:
            try:
                selected_list = selected_raw.to_dict("records")
            except Exception:
                selected_list = []
        # ===================== КНОПКИ-ДЕЙСТВИЯ (в линию) =====================
        col1, col2, col3 = st.columns([2.5, 2.5, 3])
        with col1:
            btn_transfer_sel = st.button(
                "Перенести выбранные → Statement",
                disabled=(len(selected_list) == 0),
                width="stretch",
            )
        with col2:
            btn_delete_sel = st.button(
                "🗑️ Удалить выбранные из временной",
                disabled=(len(selected_list) == 0),
                width="stretch",
            )
        with col3:
            pop = getattr(st, "popover", None)
            ctx_edit = pop("✏️ Редактировать выбранную запись") if pop else st.expander("✏️ Редактировать выбранную запись")

        # --------------------- Попап «Редактировать выбранную запись» ---------------------
        with ctx_edit:
            if len(selected_list) != 1:
                st.info("Выберите ровно одну строку в таблице для редактирования.")
            else:
                sel_id = int(float(selected_list[0]["id"]))
                obj = session.get(editbank.EditBank, sel_id)
                if not obj:
                    st.warning("Запись не найдена.")
                else:
                    # read-only информация
                    payer_name = (
                        company_map.get(obj.payer_company_id)
                        or firm_map.get(obj.payer_firm_id)
                        or (obj.payer_raw or "—")
                    )
                    receiver_name = (
                        company_map.get(obj.receiver_company_id)
                        or firm_map.get(obj.receiver_firm_id)
                        or (obj.receiver_raw or "—")
                    )
                    st.markdown(f"**Плательщик:** {payer_name}")
                    st.markdown(f"**Получатель:** {receiver_name}")
                    st.markdown(f"**Головная компания:** {up_company_map.get(obj.up_company_id, '—')}")
                    st.divider()

                    cur_group_name = group_map.get(obj.group_id, "")
                    cur_cat_name = category_map.get(obj.category_id, "")
                    cur_zk_name = up_company_map.get(obj.za_kogo_platili_id, up_company_map.get(obj.up_company_id, ""))
                    cur_month, cur_year = _resolve_month_year(obj.report_month, obj.date)
                    col_l, col_r = st.columns(2)
                    with col_l:
                        new_month_label = st.selectbox(
                            "Учётный месяц",
                            options=ru_month_opts,
                            index=(ru_month_opts.index(cur_month) if cur_month in ru_month_opts else 0),
                            key=f"edit_month_{sel_id}",
                        )
                        year_options = sorted(set(year_opts) | ({cur_year} if cur_year else set()))
                        new_year_val = st.selectbox(
                            "Учётный год",
                            options=year_options,
                            index=year_options.index(cur_year) if cur_year in year_options else 0,
                            key=f"edit_year_{sel_id}",
                        )

                        new_type = st.selectbox(
                            "Тип операции",
                            options=["Списание", "Поступление"],
                            index=(0 if (obj.operation_type or "").strip().lower() == "списание" else 1),
                            key=f"edit_type_{sel_id}",
                        )
                        new_amount = st.number_input("Сумма", value=float(obj.amount or 0.0), step=100.0, format="%.2f")
                        up_names_all = [u.name for u in up_companies]
                        sel_zk_name = st.selectbox(
                            "За кого платили",
                            options=up_names_all,
                            index=(up_names_all.index(cur_zk_name) if cur_zk_name in up_names_all else 0),
                            key=f"edit_zk_{sel_id}",
                        )
                        sel_zk = next((u for u in up_companies if u.name == sel_zk_name), None)

                    with col_r:
                        group_names = [g.name for g in groups]
                        sel_group_name = st.selectbox(
                            "Группа",
                            options=["—"] + group_names,
                            index=(group_names.index(cur_group_name) + 1) if cur_group_name in group_names else 0,
                            key=f"edit_group_{sel_id}",
                        )
                        sel_group = next((g for g in groups if g.name == sel_group_name), None)

                        # категории по выбранной группе
                        cats_for_group = cats_by_group.get(sel_group.id if sel_group else None, [])
                        cat_names = [c.name for c in cats_for_group] if cats_for_group else [c.name for c in categories]
                        sel_cat_name = st.selectbox(
                            "Категория",
                            options=["—"] + cat_names,
                            index=(cat_names.index(cur_cat_name) + 1) if cur_cat_name in cat_names else 0,
                            key=f"edit_cat_{sel_id}",
                        )

                    new_purpose = st.text_input("Назначение", value=(obj.purpose or ""))
                    new_comment = st.text_area("Комментарий", value=(obj.comment or ""), height=120)

                    if st.button("💾 Сохранить изменения", width="stretch", key=f"btn_save_edit_{sel_id}"):
                        try:
                            obj.report_month = new_month_label or None
                            obj.report_year = int(new_year_val) if new_year_val else None

                            obj.operation_type = (new_type or "").strip() or None
                            try:
                                obj.amount = float(new_amount)
                            except Exception:
                                pass
                            obj.purpose = new_purpose or None
                            obj.comment = new_comment or None

                            if sel_cat_name and sel_cat_name != "—":
                                new_cat = next((c for c in categories if c.name == sel_cat_name), None)
                                if new_cat:
                                    obj.category_id = new_cat.id
                                    obj.group_id = new_cat.group_id
                            else:
                                if sel_group:
                                    obj.group_id = sel_group.id

                            if sel_zk:
                                obj.za_kogo_platili_id = sel_zk.id

                            session.commit()
                            st.success("Изменения сохранены.")
                            st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"Ошибка сохранения: {e}")

        # --------------------- Обработчики кнопок ---------------------
        if btn_transfer_sel:
            selected = pd.DataFrame(selected_list)
            imported_count = 0
            for _, row in selected.iterrows():
                # дубликаты по row_id
                exists = session.query(statement.Statement).filter_by(row_id=row["row_id"]).first()
                if exists:
                    continue

                # маппинг cat/group по названию из грида
                cat_id = next((k for k, v in category_map.items() if v == row.get("Категория")), None)
                group_id = next((k for k, v in group_map.items() if v == row.get("Группа")), None)

                # исходная временная запись
                op_db = session.query(editbank.EditBank).filter_by(row_id=row["row_id"]).first()

                # определяем головную и «за кого платили»
                inferred_up_id = None
                zk_id = None
                if op_db:
                    inferred_up_id = (
                        op_db.up_company_id
                        or company_up_map.get(op_db.payer_company_id)
                        or company_up_map.get(op_db.receiver_company_id)
                    )
                    zk_id = op_db.za_kogo_platili_id or inferred_up_id
                else:
                    zk_id = up_company_name_to_id.get(row.get("За кого платили") or "")
                    inferred_up_id = zk_id or up_company_name_to_id.get(row.get("Головная компания") or "")

                # месяц/год из грида или из БД
                rm_label = str(row.get("Учётный месяц") or "").strip()
                report_month_val, report_year_val = _resolve_month_year(
                    rm_label,
                    pd.to_datetime(row.get("Дата"), dayfirst=True, errors="coerce") if row.get("Дата") else (op_db.date if op_db else None),
                )
                # если в таблице есть явный год — используем его
                row_year = row.get("Учётный год")
                if pd.notna(row_year):
                    try:
                        report_year_val = int(row_year)
                    except Exception:
                        pass

                stmt = statement.Statement(
                    row_id=row.get("row_id"),
                    date=pd.to_datetime(row.get("Дата"), dayfirst=True) if row.get("Дата") else (op_db.date if op_db else None),
                    report_month=report_month_val,
                    report_year=report_year_val,
                    doc_number=op_db.doc_number if op_db else None,
                    payer_inn=clean_inn(row.get("ИНН плательщика") or (op_db.payer_inn if op_db else "")),
                    receiver_inn=clean_inn(row.get("ИНН получателя") or (op_db.receiver_inn if op_db else "")),
                    payer_account=clean_account(op_db.payer_account if op_db else ""),
                    receiver_account=clean_account(op_db.receiver_account if op_db else ""),
                    purpose=row.get("Назначение") or (op_db.purpose if op_db else None),
                    amount=row.get("Сумма") if pd.notna(row.get("Сумма")) else (op_db.amount if op_db else None),
                    operation_type=row.get("Тип операции") or (op_db.operation_type if op_db else None),
                    comment=row.get("Комментарий") or (op_db.comment if op_db else None),
                    recorded=bool(row.get("Записано", False)),
                    payer_raw=row.get("Плательщик") or (op_db.payer_raw if op_db else None),
                    receiver_raw=row.get("Получатель") or (op_db.receiver_raw if op_db else None),
                    category_id=cat_id or (op_db.category_id if op_db else None),
                    group_id=group_id or (op_db.group_id if op_db else None),
                    up_company_id=inferred_up_id,
                    za_kogo_platili_id=zk_id,
                    payer_company_id=(op_db.payer_company_id if op_db else None),
                    payer_firm_id=(op_db.payer_firm_id if op_db else None),
                    receiver_company_id=(op_db.receiver_company_id if op_db else None),
                    receiver_firm_id=(op_db.receiver_firm_id if op_db else None),
                )
                session.add(stmt)
                session.query(editbank.EditBank).filter_by(row_id=row["row_id"]).delete()
                imported_count += 1
            session.commit()
            st.success(f"Перенесено записей: {imported_count}")
            st.rerun()

        if btn_delete_sel:
            ids_to_delete = []
            for r in selected_list:
                try:
                    ids_to_delete.append(int(float(r.get("id"))))
                except Exception:
                    continue
            if not ids_to_delete:
                st.warning("Не выбрано ни одной строки.")
            else:
                try:
                    deleted = (
                        session.query(editbank.EditBank)
                        .filter(editbank.EditBank.id.in_(ids_to_delete))
                        .delete(synchronize_session=False)
                    )
                    session.commit()
                    st.success(f"Удалено строк: {deleted}")
                    st.rerun()
                except Exception as e:
                    session.rollback()
                    st.error(f"Ошибка при удалении: {e}")

        # Вспомогательные форматтеры
        def _fmt_rub(x):
            try:
                return f"{int(round(float(x))):,}".replace(",", " ") + " ₽"
            except Exception:
                return x

        def _fmt_date(d):
            return d.strftime("%d.%m.%Y") if d else ""

        def _counterparty_fields(op):
            """
            Имя/ИНН «контрагента по смыслу» (для автосборов списков).
            Поступление → плательщик, Списание → получатель.
            """
            t = (op.operation_type or "").strip().lower()
            if "поступление" in t:
                name = (
                    company_map.get(op.payer_company_id)
                    or firm_map.get(op.payer_firm_id)
                    or (op.payer_raw or "")
                )
                inn = clean_inn(op.payer_inn) or (
                    clean_inn(firm_inn_map.get(op.payer_firm_id)) if op.payer_firm_id else ""
                )
            else:
                name = (
                    company_map.get(op.receiver_company_id)
                    or firm_map.get(op.receiver_firm_id)
                    or (op.receiver_raw or "")
                )
                inn = clean_inn(op.receiver_inn) or (
                    clean_inn(firm_inn_map.get(op.receiver_firm_id)) if op.receiver_firm_id else ""
                )
            return name, inn

        # Список проблемных операций (нет группы или категории) в пределах текущих SQL-фильтров.
        # Ограничиваем выборку, чтобы блок новых контрагентов не перегружал страницу.
        ops_missing_cat = (
            filtered_query
            .filter(or_(editbank.EditBank.group_id.is_(None), editbank.EditBank.category_id.is_(None)))
            .order_by(editbank.EditBank.date.desc(), editbank.EditBank.id.desc())
            .limit(1000)
            .all()
        )

        # ---------- Новые контрагенты (нет в базе) с массовым назначением ----------
        # Группируем проблемные операции по паре (имя/ИНН) только если такого контрагента нет среди firms/companies.
        existing_inn = {clean_inn(f.inn) for f in firms if f.inn} | {
            clean_inn(c.inn) for c in companies if getattr(c, "inn", None)
        }
        existing_names = {
            (f.name or "").strip().lower() for f in firms if f.name
        } | { (c.name or "").strip().lower() for c in companies if c.name }

        new_groups: dict[tuple[str, str], list[editbank.EditBank]] = {}
        for op in ops_missing_cat:
            nm, inn = _counterparty_fields(op)
            nm = (nm or "").strip() or "—"
            inn_clean = clean_inn(inn)
            exists = False
            if inn_clean and inn_clean in existing_inn:
                exists = True
            if not exists and nm and nm.lower() in existing_names:
                exists = True
            if exists:
                continue
            key = (nm, inn_clean or "")
            new_groups.setdefault(key, []).append(op)

        if new_groups:
            st.markdown("#### Новые контрагенты (не найдены в базе)")
            for idx, ((nm, inn_val), op_list) in enumerate(sorted(new_groups.items(), key=lambda x: x[0][0].lower()), 1):
                st.markdown(
                    f"<div style='font-size:16px;font-weight:700;color:#d97706;'>Новая компания: {nm}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"*ИНН:* **{inn_val or '—'}** • операций: **{len(op_list)}**")

                # Форма выбора категории сразу под названием
                cat_names = [c.name for c in categories]
                sel_cat_name = st.selectbox(
                    "Категория для новой фирмы (будет назначена всем операциям группы)",
                    options=cat_names,
                    index=0,
                    key=f"new_counterparty_cat_{idx}",
                )
                sel_cat = next((c for c in categories if c.name == sel_cat_name), None)
                group_hint = next((g.name for g in groups if sel_cat and g.id == sel_cat.group_id), "—")
                st.caption(f"Группа по категории: **{group_hint}**")

                # Таблица операций
                table_rows = []
                for op in op_list:
                    table_rows.append(
                        {
                            "Дата": _fmt_date(op.date),
                            "Сумма": _fmt_rub(op.amount),
                            "Плательщик": company_map.get(op.payer_company_id)
                            or firm_map.get(op.payer_firm_id)
                            or (op.payer_raw or ""),
                            "Получатель": company_map.get(op.receiver_company_id)
                            or firm_map.get(op.receiver_firm_id)
                            or (op.receiver_raw or ""),
                            "Назначение": op.purpose or "",
                            "ID": op.id,
                        }
                    )
                st.dataframe(pd.DataFrame(table_rows), width="stretch", hide_index=True)

                if st.button(
                    "🟧 Создать фирму и назначить всем операциям группы",
                    key=f"new_counterparty_btn_{idx}",
                    width="stretch",
                ):
                    try:
                        if not sel_cat:
                            st.error("Категория не найдена.")
                        else:
                            firm_obj = None
                            if inn_val:
                                firm_obj = session.query(firm.Firm).filter(firm.Firm.inn == inn_val).first()
                            if not firm_obj and nm:
                                firm_obj = session.query(firm.Firm).filter(firm.Firm.name == nm).first()
                            if not firm_obj:
                                firm_obj = firm.Firm(name=nm, inn=(inn_val or None), category_id=sel_cat.id)
                                session.add(firm_obj)
                                session.flush()
                            else:
                                if firm_obj.category_id != sel_cat.id:
                                    firm_obj.category_id = sel_cat.id

                            for op in op_list:
                                op.category_id = sel_cat.id
                                op.group_id = sel_cat.group_id

                            session.commit()
                            st.success(f"Создано/обновлено: {nm} • ИНН {inn_val or '—'}. Назначено операций: {len(op_list)}")
                            st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"Ошибка: {e}")
