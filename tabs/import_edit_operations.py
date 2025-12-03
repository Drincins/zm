# tabs/import_edit_operations.py
import re
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

from core.db import SessionLocal
from core.months import RU_MONTHS, ru_label_from_rm, rm_from_ru_label
from db_models import editbank, statement, firm, company, category, group, up_company
from core.parser import clean_inn  # используем единую очистку ИНН

# --- RU months helpers (используем core.months) ---

def _is_rm_yyyy_mm(s: str) -> bool:
    return isinstance(s, str) and len(s) == 7 and s[4] == "-"

def import_edit_operations_tab():
    st.header("Редактирование операций (импортированные из выписки)")

    # Единый стиль кнопок (одинаковая ширина/высота)
    st.markdown("""
    <style>
      .stButton>button { width: 100%; min-height: 38px; }
    </style>
    """, unsafe_allow_html=True)

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
        category_to_group = {c.id: c.group_id for c in categories}
        up_company_map = {u.id: u.name for u in up_companies}
        up_company_name_to_id = {u.name: u.id for u in up_companies}

        # Обратные маппинги и категории по группам (для редактора)
        group_name_to_id = {v: k for k, v in group_map.items()}
        cat_name_to_id = {v: k for k, v in category_map.items()}
        cats_by_group: dict[int | None, list[category.Category]] = {}
        for c in categories:
            cats_by_group.setdefault(c.group_id, []).append(c)

        # --- Запрос временных операций ---
        ops = session.query(editbank.EditBank).order_by(editbank.EditBank.date.desc()).all()
        if not ops:
            st.info("Временная таблица пуста. Загрузите выписку для обработки.")
            return

        # --- Формируем DataFrame для грида ---
        df_rows = []
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

            df_rows.append({
                "id": op.id,
                "Дата": op.date.strftime('%d.%m.%Y') if op.date else "",
                "Учётный месяц": ru_label_from_rm(op.report_month or (op.date.strftime('%Y-%m') if op.date else "")),
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
            })
        df = pd.DataFrame(df_rows)
        if "Дата" in df.columns:
            df["Дата"] = pd.to_datetime(df["Дата"], dayfirst=True, errors="coerce")\
                            .dt.strftime("%d.%m.%Y")\
                            .fillna("")
        # --- Месяцы: общий список и маппинг label->raw для безопасного редактирования ---
        all_rm_values = []
        for op in ops:
            if op.report_month:
                all_rm_values.append(op.report_month)
            elif op.date:
                all_rm_values.append(op.date.strftime("%Y-%m"))
        all_rm_values = sorted(set(v for v in all_rm_values if v), reverse=True)

        month_label_to_value = {}
        for rm in all_rm_values:
            label = ru_label_from_rm(rm) if _is_rm_yyyy_mm(rm) else rm
            month_label_to_value[label] = rm
        ru_month_opts = list(month_label_to_value.keys()) or ["—"]

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

        # Все столбцы в таблице только для просмотра (редактирование через попапы)
        gb.configure_column("Учётный месяц", editable=False)

        # Остальное — явно нередактируемые
        gb.configure_column("Комментарий", editable=False)
        gb.configure_column("Записано", editable=False)
        gb.configure_column("Головная компания", editable=False)
        gb.configure_column("За кого платили", editable=False)
        gb.configure_column("Категория", editable=False)

        gb.configure_column("Группа", editable=False)
        gb.configure_column("Тип операции", editable=False)
        gb.configure_column("Назначение", editable=False)
        gb.configure_column("Сумма", editable=False)
        gb.configure_column("ИНН плательщика", editable=False)
        gb.configure_column("ИНН получателя", editable=False)
        gb.configure_column("Плательщик", editable=False)
        gb.configure_column("Получатель", editable=False)
        gb.configure_column("Дата", editable=False)
        gb.configure_column("row_id", editable=False)

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
            btn_transfer_sel = st.button("Перенести выбранные → Statement", disabled=(len(selected_list) == 0), use_container_width=True)
        with col2:
            btn_delete_sel = st.button("🗑️ Удалить выбранные из временной", disabled=(len(selected_list) == 0), use_container_width=True)
        # col3 — попап редактора
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
                    payer_name = company_map.get(obj.payer_company_id) or firm_map.get(obj.payer_firm_id) or (obj.payer_raw or "—")
                    receiver_name = company_map.get(obj.receiver_company_id) or firm_map.get(obj.receiver_firm_id) or (obj.receiver_raw or "—")
                    st.markdown(f"**Плательщик:** {payer_name}")
                    st.markdown(f"**Получатель:** {receiver_name}")
                    st.markdown(f"**Головная компания:** {up_company_map.get(obj.up_company_id, '—')}")
                    st.divider()

                    # значения по умолчанию
                    cur_group_name = group_map.get(obj.group_id, "")
                    cur_cat_name = category_map.get(obj.category_id, "")
                    cur_zk_name = up_company_map.get(obj.za_kogo_platili_id, up_company_map.get(obj.up_company_id, ""))

                    col_l, col_r = st.columns(2)
                    with col_l:
                        cur_month_label = (ru_label_from_rm(obj.report_month) if _is_rm_yyyy_mm(obj.report_month or "") else (obj.report_month or "—"))
                        new_month_label = st.selectbox(
                            "Учётный месяц",
                            options=ru_month_opts,
                            index=(ru_month_opts.index(cur_month_label) if cur_month_label in ru_month_opts else 0)
                        )

                        new_type = st.selectbox("Тип операции", options=["списание", "поступление"],
                                                index=(0 if (obj.operation_type or "").strip().lower() == "списание" else 1))
                        new_amount = st.number_input("Сумма", value=float(obj.amount or 0.0), step=100.0, format="%.2f")
                        up_names_all = [u.name for u in up_companies]
                        sel_zk_name = st.selectbox("За кого платили", options=up_names_all,
                                                   index=(up_names_all.index(cur_zk_name) if cur_zk_name in up_names_all else 0))
                        sel_zk = next((u for u in up_companies if u.name == sel_zk_name), None)

                    with col_r:
                        group_names = [g.name for g in groups]
                        sel_group_name = st.selectbox("Группа", options=["—"] + group_names,
                                                      index=(group_names.index(cur_group_name) + 1) if cur_group_name in group_names else 0)
                        sel_group = next((g for g in groups if g.name == sel_group_name), None)

                        # категории по выбранной группе
                        cats_for_group = cats_by_group.get(sel_group.id if sel_group else None, [])
                        cat_names = [c.name for c in cats_for_group] if cats_for_group else [c.name for c in categories]
                        sel_cat_name = st.selectbox("Категория", options=["—"] + cat_names,
                                                    index=(cat_names.index(cur_cat_name) + 1) if cur_cat_name in cat_names else 0)

                    new_purpose = st.text_input("Назначение", value=(obj.purpose or ""))
                    new_comment = st.text_area("Комментарий", value=(obj.comment or ""), height=120)

                    if st.button("💾 Сохранить изменения", use_container_width=True):
                        try:
                            obj.report_month = (
                                month_label_to_value.get(new_month_label)
                                or rm_from_ru_label(new_month_label)
                                or (new_month_label if new_month_label != "—" else None)
                            )

                            obj.operation_type = (new_type or "").strip().lower()
                            try:
                                obj.amount = float(new_amount)
                            except Exception:
                                pass
                            obj.purpose = (new_purpose or None)
                            obj.comment = (new_comment or None)

                            # категория/группа
                            if sel_cat_name and sel_cat_name != "—":
                                new_cat = next((c for c in categories if c.name == sel_cat_name), None)
                                if new_cat:
                                    obj.category_id = new_cat.id
                                    obj.group_id = new_cat.group_id
                            else:
                                if sel_group:
                                    obj.group_id = sel_group.id

                            # за кого платили
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

                # месяц берём из грида (если пользователь поправил)
                rm_label = str(row.get("Учётный месяц") or "").strip()
                report_month_val = (
                    month_label_to_value.get(rm_label)
                    or rm_from_ru_label(rm_label)
                    or (op_db.report_month if op_db else None)
                )

                stmt = statement.Statement(
                    row_id=row.get("row_id"),
                    date=pd.to_datetime(row.get("Дата"), dayfirst=True) if row.get("Дата") else (op_db.date if op_db else None),
                    report_month=report_month_val,
                    doc_number=op_db.doc_number if op_db else None,
                    payer_inn=clean_inn(row.get("ИНН плательщика") or (op_db.payer_inn if op_db else "")),
                    receiver_inn=clean_inn(row.get("ИНН получателя") or (op_db.receiver_inn if op_db else "")),
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
                    deleted = session.query(editbank.EditBank)\
                        .filter(editbank.EditBank.id.in_(ids_to_delete))\
                        .delete(synchronize_session=False)
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
                name = company_map.get(op.payer_company_id) or firm_map.get(op.payer_firm_id) or (op.payer_raw or "")
                inn  = clean_inn(op.payer_inn) or (clean_inn(firm_inn_map.get(op.payer_firm_id)) if op.payer_firm_id else "")
            else:
                name = company_map.get(op.receiver_company_id) or firm_map.get(op.receiver_firm_id) or (op.receiver_raw or "")
                inn  = clean_inn(op.receiver_inn) or (clean_inn(firm_inn_map.get(op.receiver_firm_id)) if op.receiver_firm_id else "")
            return name, inn

        # Список проблемных операций (нет группы или категории) — используем только для группировки новых контрагентов
        ops_missing_cat = []
        for op in ops:
            if not op.group_id or not op.category_id:
                ops_missing_cat.append(op)

        # ---------- Новые контрагенты (нет в базе) с массовым назначением ----------
        # Группируем проблемные операции по паре (имя/ИНН) только если такого контрагента нет среди firms/companies.
        existing_inn = {
            clean_inn(f.inn) for f in firms if f.inn
        } | {
            clean_inn(c.inn) for c in companies if getattr(c, "inn", None)
        }
        existing_names = { (f.name or "").strip().lower() for f in firms if f.name } | { (c.name or "").strip().lower() for c in companies if c.name }

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
                st.markdown(f"<div style='font-size:16px;font-weight:700;color:#d97706;'>Новая компания: {nm}</div>", unsafe_allow_html=True)
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
                            "Плательщик": company_map.get(op.payer_company_id) or firm_map.get(op.payer_firm_id) or (op.payer_raw or ""),
                            "Получатель": company_map.get(op.receiver_company_id) or firm_map.get(op.receiver_firm_id) or (op.receiver_raw or ""),
                            "Назначение": op.purpose or "",
                            "ID": op.id,
                        }
                    )
                st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

                if st.button("🟧 Создать фирму и назначить всем операциям группы", key=f"new_counterparty_btn_{idx}", use_container_width=True):
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
                                # обновим категорию, если нужно
                                if firm_obj.category_id != sel_cat.id:
                                    firm_obj.category_id = sel_cat.id

                            # Назначаем категорию/группу всем операциям группы
                            for op in op_list:
                                op.category_id = sel_cat.id
                                op.group_id = sel_cat.group_id

                            session.commit()
                            st.success(f"Создано/обновлено: {nm} • ИНН {inn_val or '—'}. Назначено операций: {len(op_list)}")
                            st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"Ошибка: {e}")
