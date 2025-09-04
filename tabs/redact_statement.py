# tabs/redact_statement.py
from datetime import datetime
import streamlit as st
import pandas as pd
from core.db import SessionLocal
from db_models import statement, company, up_company, category, group, firm
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
from io import BytesIO  # для формирования XLSX в памяти

# ----------------------------- RU months helpers -----------------------------
_RU_MONTHS = [
    "Январь","Февраль","Март","Апрель","Май","Июнь",
    "Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь"
]

def _ru_label_from_rm(rm: str) -> str:
    """YYYY-MM -> 'Месяц ГГГГ' (ru)"""
    if not rm or len(rm) != 7 or "-" not in rm:
        return rm or "—"
    y, m = rm.split("-")
    try:
        return f"{_RU_MONTHS[int(m)-1]} {y}"
    except Exception:
        return rm

def _rm_from_ru_label(label: str) -> str | None:
    """'Месяц ГГГГ' (ru) -> YYYY-MM"""
    try:
        name, y = label.strip().split()
        m = _RU_MONTHS.index(name) + 1
        return f"{y}-{m:02d}"
    except Exception:
        return None


def redact_statement():
    st.title("Мастер-таблица Statement")

    session = SessionLocal()
    try:
        # ----------------------------- Справочники -----------------------------
        companies = session.query(company.Company).all()
        up_companies = session.query(up_company.UpCompany).all()
        categories = session.query(category.Category).all()
        groups = session.query(group.Group).all()
        firms = session.query(firm.Firm).all()

        company_dict = {c.id: c.name for c in companies}
        up_company_dict = {u.id: u.name for u in up_companies}
        cat_dict = {c.id: c.name for c in categories}
        group_dict = {g.id: g.name for g in groups}
        firm_dict = {f.id: f.name for f in firms}

        group_name_to_id = {g.name: g.id for g in groups}
        cat_name_to_id = {c.name: c.id for c in categories}
        group_names_all = list(group_name_to_id.keys())
        cat_names_all = list(cat_name_to_id.keys())

        # категории по group_id (для узких списков в формах)
        cats_by_group: dict[int | None, list[category.Category]] = {}
        for c in categories:
            cats_by_group.setdefault(c.group_id, []).append(c)

        # ----------------------------- Данные -----------------------------
        stmts = session.query(statement.Statement).all()
        rows = []
        for s in stmts:
            rid = f"RID_{s.row_id}" if getattr(s, "row_id", None) else "—"
            rows.append({
                "id": s.id,
                "row_id": rid,
                "Дата": s.date.strftime('%d.%m.%Y') if s.date else "—",
                "Месяц": s.report_month or "—",
                # Компания -> Фирма -> сырой текст
                "Плательщик": (
                    company_dict.get(s.payer_company_id)
                    or firm_dict.get(s.payer_firm_id)
                    or (getattr(s, "payer_raw", None) or "—")
                ),
                "Получатель": (
                    company_dict.get(s.receiver_company_id)
                    or firm_dict.get(s.receiver_firm_id)
                    or (getattr(s, "receiver_raw", None) or "—")
                ),
                "Категория (название)": cat_dict.get(s.category_id, "—"),
                "Группа (название)": group_dict.get(s.group_id, "—"),
                "Тип операции": s.operation_type or "—",
                "Назначение": s.purpose or "—",
                "Сумма": s.amount if s.amount is not None else None,  # числом/NaN
                "Комментарий": s.comment or "—",
                "Головная компания": up_company_dict.get(s.up_company_id, "—"),
                "За кого платили": up_company_dict.get(getattr(s, "za_kogo_platili_id", None), "—"),
                "Записано": bool(getattr(s, "recorded", False)),
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df["row_id"] = df["row_id"].astype(str)

        text_cols = [
            "Дата", "Месяц", "Плательщик", "Получатель",
            "Категория (название)", "Группа (название)",
            "Тип операции", "Назначение", "Комментарий",
            "Головная компания", "За кого платили", "row_id"
        ]
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].fillna("—")
        if "Сумма" in df.columns:
            df["Сумма"] = pd.to_numeric(df["Сумма"], errors="coerce")

        # ----------------------------- Фильтры -----------------------------
        st.markdown("### Фильтры")
        # Инициализация session_state под фильтры (сохраняем выбор)
        for key in ["up_company", "company", "month", "payer", "receiver", "group", "category", "op_type", "za_kogo"]:
            st.session_state.setdefault(f"flt_{key}", [])

        def dyn_multiselect(label, column, df_local, key):
            options = sorted([x for x in df_local[column].dropna().unique().tolist()]) if column in df_local else []
            default = [val for val in st.session_state.get(key, []) if val in options]
            return st.multiselect(label, options, default=default, key=key)

        current_df = df.copy()
        cols = st.columns(4)
        with cols[0]:
            up_company_vals = dyn_multiselect("Головная компания", "Головная компания", current_df, "flt_up_company")
            if up_company_vals:
                current_df = current_df[current_df["Головная компания"].isin(up_company_vals)]

            pay = current_df[["Плательщик"]].copy()
            rec = current_df[["Получатель"]].copy()
            rec.columns = ["Плательщик"]
            df_both = pd.concat([pay, rec], axis=0, ignore_index=True)
            company_vals = dyn_multiselect("Компания (Плательщик/Получатель)", "Плательщик", df_both, "flt_company")
            if company_vals:
                mask = (current_df["Плательщик"].isin(company_vals)) | (current_df["Получатель"].isin(company_vals))
                current_df = current_df[mask]

        with cols[1]:
            month_vals = dyn_multiselect("Месяц", "Месяц", current_df, "flt_month")
            if month_vals:
                current_df = current_df[current_df["Месяц"].isin(month_vals)]
            payer_vals = dyn_multiselect("Плательщик", "Плательщик", current_df, "flt_payer")
            if payer_vals:
                current_df = current_df[current_df["Плательщик"].isin(payer_vals)]

        with cols[2]:
            receiver_vals = dyn_multiselect("Получатель", "Получатель", current_df, "flt_receiver")
            if receiver_vals:
                current_df = current_df[current_df["Получатель"].isin(receiver_vals)]
            group_vals = dyn_multiselect("Группа", "Группа (название)", current_df, "flt_group")
            if group_vals:
                current_df = current_df[current_df["Группа (название)"].isin(group_vals)]

        with cols[3]:
            category_vals = dyn_multiselect("Категория", "Категория (название)", current_df, "flt_category")
            if category_vals:
                current_df = current_df[current_df["Категория (название)"].isin(category_vals)]
            op_type_vals = dyn_multiselect("Тип операции", "Тип операции", current_df, "flt_op_type")
            if op_type_vals:
                current_df = current_df[current_df["Тип операции"].isin(op_type_vals)]

        # Фильтр «За кого платили»
        za_kogo_vals = dyn_multiselect("За кого платили", "За кого платили", current_df, "flt_za_kogo")
        if za_kogo_vals:
            current_df = current_df[current_df["За кого платили"].isin(za_kogo_vals)]

        # Фильтр «Записано»
        recorded_filter = st.selectbox(
            "Записано",
            options=["Все", "Только новые (не записанные)", "Только записанные"],
            index=0,
            key="flt_recorded",
        )
        if recorded_filter == "Только новые (не записанные)":
            current_df = current_df[current_df["Записано"] == False]
        elif recorded_filter == "Только записанные":
            current_df = current_df[current_df["Записано"] == True]

        df_filtered = current_df.reset_index(drop=True)

        # ----------------------------- Восстановление настроек таблицы (без серверной сортировки) -----------------------------
        saved_state = st.session_state.get("stmt_grid_state")
        # 1) порядок/видимость
        if saved_state and isinstance(saved_state.get("columns"), list) and not df_filtered.empty:
            visible_cols = [c.get("colId") for c in saved_state["columns"] if not c.get("hide", False)]
            hidden_cols  = [c.get("colId") for c in saved_state["columns"] if c.get("hide", False)]
            visible_cols = [c for c in visible_cols if c in df_filtered.columns]
            hidden_cols  = [c for c in hidden_cols if c in df_filtered.columns]
            left_fixed = [c for c in ["id"] if c in df_filtered.columns and c in visible_cols]
            rest = [c for c in visible_cols if c not in left_fixed]
            others = [c for c in df_filtered.columns if c not in left_fixed and c not in rest and c not in hidden_cols]
            new_order = left_fixed + rest + others
            try:
                df_filtered = df_filtered.reindex(columns=new_order)
            except Exception:
                pass
            _widths = {c["colId"]: c.get("width") for c in saved_state["columns"] if c.get("width")}
        else:
            _widths = {}

        # ----------------------------- AgGrid -----------------------------
        if "id" not in df_filtered.columns:
            st.warning("В текущем наборе данных нет колонки 'id' — удаление и массовые операции отключены.")

        gb = GridOptionsBuilder.from_dataframe(df_filtered)
        gb.configure_default_column(resizable=True, filter=True)
        gb.configure_selection(selection_mode="multiple", use_checkbox=True, suppressRowDeselection=False)

        # Стабильный ключ строки и delta-режим — чтобы чекбоксы не улетали
        gb.configure_grid_options(
            ensureDomOrder=True,
            getRowId=JsCode("function(p){ return p && p.data && p.data.id != null ? String(p.data.id) : String(Math.random()); }"),
            immutableData=True,
            deltaRowDataMode=True,
            animateRows=True,
        )

        # чекбокс выбора
        gb.configure_column(
            "id",
            headerCheckboxSelection=True,
            headerCheckboxSelectionFilteredOnly=True,
            checkboxSelection=True,
            pinned="left",
            width=90,
        )

        # редактирование в таблице
        gb.configure_column(
            "Группа (название)",
            editable=True,
            cellEditor="agRichSelectCellEditor",        # поиск по мере ввода
            cellEditorParams={"values": group_names_all, "searchDebounceDelay": 100},
            cellEditorPopup=True,
        )
        gb.configure_column(
            "Категория (название)",
            editable=True,
            cellEditor="agRichSelectCellEditor",        # поиск по мере ввода
            cellEditorParams={"values": cat_names_all, "searchDebounceDelay": 100},
            cellEditorPopup=True,
        )
        gb.configure_column("Комментарий", editable=True)
        gb.configure_column("Назначение", editable=True)
        gb.configure_column("Сумма", editable=True)

        gb.configure_column("Записано", editable=False, width=110)  # помечаем кнопкой

        gb.configure_column(
            "Тип операции",
            editable=True,
            cellEditor="agRichSelectCellEditor",
            cellEditorParams={"values": sorted(df["Тип операции"].dropna().unique().tolist()) if "Тип операции" in df else []},
            cellEditorPopup=True,
        )

        # служебные поля — только чтение
        for col in ["row_id", "Дата", "Месяц", "Плательщик", "Получатель", "Головная компания", "За кого платили"]:
            if col in df_filtered.columns:
                gb.configure_column(col, editable=False)

        # применим сохранённые ширины
        if _widths:
            for col_name, w in _widths.items():
                if col_name in df_filtered.columns:
                    try:
                        gb.configure_column(col_name, width=int(w))
                    except Exception:
                        pass

        gridOptions = gb.build()
        grid_response = AgGrid(
            df_filtered,
            gridOptions=gridOptions,
            update_mode=GridUpdateMode.SELECTION_CHANGED | GridUpdateMode.VALUE_CHANGED,
            allow_unsafe_jscode=True,
            theme="streamlit",
            height=700,
            use_container_width=True,
            fit_columns_on_grid_load=True,
            key="statement_table",  # постоянный ключ — состояние сохраняем вручную
        )

        # сохраним состояние грида (порядок/ширины/сортировка)
        grid_state = (grid_response or {}).get("grid_state")
        if grid_state:
            st.session_state["stmt_grid_state"] = grid_state

        # ----------------------------- Нормализация выбранных -----------------------------
        selected_raw = (grid_response or {}).get('selected_rows', None)
        selected_list = []
        if isinstance(selected_raw, list):
            selected_list = selected_raw
        elif isinstance(selected_raw, dict):
            selected_list = [selected_raw]
        elif isinstance(selected_raw, pd.DataFrame):
            selected_list = selected_raw.to_dict("records")
        elif selected_raw is None:
            selected_list = []
        else:
            to_dict = getattr(selected_raw, "to_dict", None)
            if callable(to_dict):
                try:
                    selected_list = to_dict("records")
                except Exception:
                    selected_list = []
            else:
                try:
                    selected_list = list(selected_raw)
                except Exception:
                    selected_list = []

        selected_ids = []
        for r in selected_list:
            try:
                selected_ids.append(int(float(r.get("id"))))
            except Exception:
                continue

        # ----------------------------- Кнопки под таблицей -----------------------------
        c_rec, c_export, c_edit = st.columns([1.3, 1.6, 2.2])  # добавили среднюю колонку для экспорта

        # Записать (recorded=True) выбранные
        with c_rec:
            btn_caption = f"✅ Записать выделенные ({len(selected_ids)})" if selected_ids else "✅ Записать выделенные"
            if st.button(btn_caption, use_container_width=True):
                if not selected_ids:
                    st.warning("Не выбрано ни одной строки.")
                else:
                    try:
                        session.query(statement.Statement)\
                            .filter(statement.Statement.id.in_(selected_ids))\
                            .update({statement.Statement.recorded: True}, synchronize_session=False)
                        session.commit()
                        st.success(f"Помечено 'Записано': {len(selected_ids)}")
                        st.rerun()  # выделение пропадёт, настройки восстановим
                    except Exception as e:
                        session.rollback()
                        st.error(f"Ошибка пометки: {e}")
        # --- Экспорт в Excel: только выделенные строки ---
        with c_export:
            st.caption(f"Экспорт: выделено {len(selected_ids)}")
            if selected_ids:
                # Берём именно видимые и отфильтрованные пользователем строки
                export_df = df_filtered[df_filtered["id"].isin(selected_ids)].copy()

                # Приведём дату к ISO, сумму — к числу
                if "Дата" in export_df.columns:
                    export_df["Дата"] = pd.to_datetime(export_df["Дата"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
                if "Сумма" in export_df.columns:
                    export_df["Сумма"] = pd.to_numeric(export_df["Сумма"], errors="coerce").fillna(0.0)

                # Упорядочим колонки для выгрузки (только те, что реально есть)
                cols_order = [
                    "id", "row_id", "Дата", "Месяц",
                    "Плательщик", "Получатель",
                    "Головная компания", "За кого платили",
                    "Группа (название)", "Категория (название)",
                    "Тип операции", "Назначение", "Сумма", "Комментарий", "Записано",
                ]
                export_df = export_df[[c for c in cols_order if c in export_df.columns]]

                # Пишем xlsx в память с запасным движком
                bio = BytesIO()
                try:
                    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
                        export_df.to_excel(writer, index=False, sheet_name="Выбранные операции")
                except Exception:
                    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
                        export_df.to_excel(writer, index=False, sheet_name="Выбранные операции")
                bio.seek(0)

                st.download_button(
                    "⬇️ Выгрузить выделенные в Excel",
                    data=bio.getvalue(),
                    file_name=f'statement_selected_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="stmt_export_selected_xlsx"
                )
            else:
                st.caption("Выделите строки чекбоксами слева и повторите.")

        # Редактор операции (popover/expander)
        with c_edit:
            pop = getattr(st, "popover", None)
            title = "Редактор операции"
            ctx = pop(title) if pop else st.expander(title)

        with ctx:
            if len(selected_ids) != 1:
                st.info("Выберите ровно одну строку для редактирования.")
            else:
                oid = selected_ids[0]
                obj = session.get(statement.Statement, oid)
                if not obj:
                    st.warning("Операция не найдена.")
                else:
                    # read-only заголовок
                    payer_name = (company_dict.get(obj.payer_company_id)
                                  or firm_dict.get(obj.payer_firm_id)
                                  or (getattr(obj, "payer_raw", None) or "—"))
                    receiver_name = (company_dict.get(obj.receiver_company_id)
                                     or firm_dict.get(obj.receiver_firm_id)
                                     or (getattr(obj, "receiver_raw", None) or "—"))

                    st.markdown(f"**Плательщик:** {payer_name}")
                    st.markdown(f"**Получатель:** {receiver_name}")
                    st.markdown(f"**Головная компания:** {up_company_dict.get(obj.up_company_id, '—')}")
                    st.divider()

                    cur_group_name = group_dict.get(obj.group_id, None)
                    cur_cat_name = cat_dict.get(obj.category_id, None)

                    col1, col2 = st.columns(2)
                    with col1:
                        # Месяц — поддерживаем 'YYYY-MM' и 'Май 2024'
                        all_rms = [s.report_month for s in stmts if s.report_month]
                        month_label_to_value = {}
                        for rm in sorted(set(all_rms)):
                            if isinstance(rm, str) and len(rm) == 7 and rm[4] == "-":
                                label = _ru_label_from_rm(rm)
                            else:
                                label = rm
                            month_label_to_value[label] = rm

                        ru_month_opts = list(month_label_to_value.keys()) or ["—"]
                        cur_month_label = (
                            _ru_label_from_rm(obj.report_month)
                            if (obj.report_month and isinstance(obj.report_month, str) and len(obj.report_month) == 7 and obj.report_month[4] == "-")
                            else (obj.report_month or "—")
                        )
                        new_month_label = st.selectbox(
                            "Месяц", options=ru_month_opts,
                            index=(ru_month_opts.index(cur_month_label) if cur_month_label in ru_month_opts else 0),
                            key="edit_month_ru"
                        )

                        new_type = st.selectbox(
                            "Тип операции", options=["списание", "поступление"],
                            index=(0 if (obj.operation_type or '').strip().lower() == "списание" else 1),
                            key="edit_op_type"
                        )

                        new_amount = st.number_input(
                            "Сумма", value=float(obj.amount or 0.0), step=100.0, format="%.2f", key="edit_amount"
                        )

                        # За кого платили
                        up_names_all = [u.name for u in up_companies]
                        up_name_by_id = {u.id: u.name for u in up_companies}
                        cur_zk_name = up_name_by_id.get(
                            getattr(obj, "za_kogo_platili_id", None),
                            up_name_by_id.get(obj.up_company_id, "—")
                        )
                        sel_zk_name = st.selectbox(
                            "За кого платили",
                            options=up_names_all,
                            index=(up_names_all.index(cur_zk_name) if cur_zk_name in up_names_all else 0),
                            key="edit_za_kogo"
                        )
                        sel_zk = next((u for u in up_companies if u.name == sel_zk_name), None)

                    with col2:
                        group_names = [g.name for g in groups]
                        sel_group_name = st.selectbox(
                            "Группа",
                            options=["—"] + group_names,
                            index=(group_names.index(cur_group_name) + 1) if cur_group_name in group_names else 0,
                            key="edit_group_select_stmt"
                        )
                        sel_group = next((g for g in groups if g.name == sel_group_name), None)

                        # Категории по выбранной группе (если пусто — все)
                        cats_for_group = cats_by_group.get(sel_group.id if sel_group else None, [])
                        cat_names = [c.name for c in cats_for_group] if cats_for_group else [c.name for c in categories]
                        new_cat_name = st.selectbox(
                            "Категория",
                            options=["—"] + cat_names,
                            index=(cat_names.index(cur_cat_name) + 1) if cur_cat_name in cat_names else 0,
                            key="edit_category_select_stmt"
                        )

                    new_purpose = st.text_input("Назначение", value=(obj.purpose or ""), key="edit_purpose")
                    new_comment = st.text_area("Комментарий", value=(obj.comment or ""), height=120, key="edit_comment")

                    if st.button("💾 Сохранить изменения по операции", use_container_width=True, key="btn_save_edit_stmt"):
                        try:
                            obj.report_month = (
                                month_label_to_value.get(new_month_label)
                                or _rm_from_ru_label(new_month_label)
                                or (new_month_label if new_month_label != "—" else None)
                            )
                            obj.operation_type = (new_type or "").strip().lower()
                            obj.purpose = (new_purpose or None)
                            obj.comment = (new_comment or None)
                            try:
                                obj.amount = float(new_amount)
                            except Exception:
                                pass

                            # Категория приоритетна (её group_id пишем в запись)
                            if new_cat_name and new_cat_name != "—":
                                new_cat = next((c for c in categories if c.name == new_cat_name), None)
                                if new_cat:
                                    obj.category_id = new_cat.id
                                    obj.group_id = new_cat.group_id
                            else:
                                if sel_group_name and sel_group_name != "—":
                                    sel_group_obj = next((g for g in groups if g.name == sel_group_name), None)
                                    obj.group_id = sel_group_obj.id if sel_group_obj else None
                                    # если текущая категория не из этой группы — обнулим
                                    if obj.category_id:
                                        cat_obj = next((c for c in categories if c.id == obj.category_id), None)
                                        if not cat_obj or cat_obj.group_id != obj.group_id:
                                            obj.category_id = None
                                else:
                                    obj.group_id = None
                                    obj.category_id = None

                            # За кого платили
                            if sel_zk:
                                obj.za_kogo_platili_id = sel_zk.id

                            session.commit()
                            st.success("Изменения сохранены.")
                            st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"Ошибка сохранения: {e}")

                    # Удаление внутри редактора (с подтверждением)
                    st.markdown("---")
                    st.warning("Удаление операции — необратимо.", icon="⚠️")
                    col_del1, col_del2 = st.columns([1, 2])
                    with col_del1:
                        want_delete = st.toggle("Подтвердить удаление", key="stmt_delete_confirm")
                    with col_del2:
                        if st.button("🗑️ Удалить операцию", type="primary", disabled=not want_delete,
                                     key="btn_delete_stmt", use_container_width=True):
                            try:
                                session.delete(obj)
                                session.commit()
                                st.success("Операция удалена.")
                                st.rerun()
                            except Exception as e:
                                session.rollback()
                                st.error(f"Ошибка при удалении: {e}")

        # ----------------------------- Массовое присвоение категории -----------------------------
        with st.expander(f"Массовое присвоение категории — выделено {len(selected_ids)}"):
            st.caption("Выберите категорию. Её group_id автоматически запишется в каждую выбранную операцию.")
            col_me1, col_me2 = st.columns([2, 1])

            with col_me1:
                bulk_cat_name = st.selectbox(
                    "Новая категория",
                    options=["—"] + cat_names_all,
                    index=0,
                    key="bulk_cat_only_select",
                )
                bulk_cat = next((c for c in categories if c.name == bulk_cat_name), None) if bulk_cat_name != "—" else None

            with col_me2:
                can_apply = len(selected_ids) > 0 and (bulk_cat is not None)
                if st.button("✳️ Применить к выбранным", use_container_width=True, disabled=not can_apply, key="btn_bulk_cat_apply"):
                    if not selected_ids:
                        st.warning("Не выбрано ни одной строки.")
                    elif not bulk_cat:
                        st.warning("Не выбрана категория.")
                    else:
                        try:
                            updated = 0
                            for rid in selected_ids:
                                s_obj = session.get(statement.Statement, rid)
                                if not s_obj:
                                    continue
                                # Категория приоритетна: ставим category_id и синхронизируем group_id
                                s_obj.category_id = bulk_cat.id
                                s_obj.group_id = bulk_cat.group_id
                                updated += 1

                            session.commit()
                            st.success(f"Обновлено строк: {updated}")
                            st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f"Ошибка массового изменения: {e}")

        st.divider()

        # ----------------------------- Сохранение правок из таблицы -----------------------------
        if st.button("💾 Сохранить изменения из таблицы (кроме 'Записано')"):
            if not grid_response or "data" not in grid_response:
                st.info("Нет данных для сохранения.")
            else:
                df_final = pd.DataFrame(grid_response["data"])
                updated = 0
                for _, row in df_final.iterrows():
                    try:
                        rid = int(row["id"])
                    except Exception:
                        continue
                    s_obj = session.get(statement.Statement, rid)
                    if not s_obj:
                        continue

                    # Комментарий / Назначение
                    s_obj.comment = None if str(row.get("Комментарий", "—")) == "—" else str(row.get("Комментарий"))
                    s_obj.purpose = None if str(row.get("Назначение", "—")) == "—" else str(row.get("Назначение"))

                    # Сумма
                    val = row.get("Сумма")
                    if pd.isna(val):
                        s_obj.amount = None
                    else:
                        try:
                            s_obj.amount = float(val)
                        except Exception:
                            pass

                    # Группа / Категория — категория приоритетна
                    new_group_name = row.get("Группа (название)")
                    new_cat_name = row.get("Категория (название)")
                    new_group_id = group_name_to_id.get(new_group_name)
                    new_cat_id = cat_name_to_id.get(new_cat_name)

                    if new_cat_id:
                        s_obj.category_id = new_cat_id
                        cat_obj = next((c for c in categories if c.id == new_cat_id), None)
                        s_obj.group_id = getattr(cat_obj, "group_id", None)
                    else:
                        s_obj.category_id = None
                        s_obj.group_id = new_group_id

                    # Тип операции
                    s_obj.operation_type = None if str(row.get("Тип операции", "—")) == "—" else str(row.get("Тип операции"))
                    updated += 1

                try:
                    session.commit()
                    st.success(f"Сохранено изменений: {updated}")
                except Exception as e:
                    session.rollback()
                    st.error(f"Ошибка при сохранении: {e}")

    finally:
        session.close()
