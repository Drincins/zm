from pathlib import Path
path = Path(r"c:\Users\Admin\Desktop\ZM\tabs\import_incomes.py")
text = path.read_text(encoding="utf-8")
lines = text.splitlines()
start = end = None
for idx, line in enumerate(lines):
    if line.startswith('def _render_day_modal') and start is None:
        start = idx
    if line.startswith('def _render_records_table'):
        end = idx
        break
if start is None or end is None:
    raise SystemExit('markers not found')
new_block = """def _render_day_modal(
    session,
    up_obj: m_up.UpCompany,
    entries: List[Dict[str, object]],
    report_month: str,
    records_by_date: Dict[dt.date, Dict[Tuple[int, int | None], m_if.IncomeRecord]],
) -> bool:
    st.markdown(\"#### Заполнение данных за день\")
    open_key = _modal_state_key(up_obj.id, report_month)
    if st.button(\"➕ Заполнить день\", key=f\"open_income_day_{up_obj.id}_{report_month}\"):
        st.session_state[open_key] = True

    if not st.session_state.get(open_key):
        return False

    dialog_fn = getattr(st, \"dialog\", None)
    if callable(dialog_fn):
        dialog_handler = dialog_fn(\"Заполнение дня\")
        if hasattr(dialog_handler, \"__call__\"):
            result_holder = {\"changed\": False}

            @dialog_handler
            def _show_day_dialog():
                result_holder[\"changed\"] = _render_day_form(
                    session, up_obj, entries, report_month, records_by_date, open_key
                )

            _show_day_dialog()
            return result_holder[\"changed\"]
        if hasattr(dialog_handler, \"__enter__\"):
            with dialog_handler:
                changed = _render_day_form(
                    session, up_obj, entries, report_month, records_by_date, open_key
                )
            return changed

    with st.expander(\"Заполнение дня\", expanded=False):
        return _render_day_form(session, up_obj, entries, report_month, records_by_date, open_key)

    return False


def _render_day_form(
    session,
    up_obj: m_up.UpCompany,
    entries: List[Dict[str, object]],
    report_month: str,
    records_by_date: Dict[dt.date, Dict[Tuple[int, int | None], m_if.IncomeRecord]],
    modal_state_key: str,
) -> bool:
    if not entries:
        st.info(\"Нет доступных форматов доходов.\")
        return False

    year, month = [int(part) for part in report_month.split(\"-\")]
    start_date = dt.date(year, month, 1)
    end_date = dt.date(year, month, calendar.monthrange(year, month)[1])
    today = dt.date.today()
    default_date = min(max(today, start_date), end_date)

    date_key = _modal_date_key(up_obj.id, report_month)
    if date_key not in st.session_state:
        st.session_state[date_key] = default_date

    with st.form(f\"income_day_form_{up_obj.id}_{report_month}\"):
        selected_date = st.date_input(
            \"Дата\",
            min_value=start_date,
            max_value=end_date,
            key=date_key,
        )

        existing_map = records_by_date.get(selected_date, {}) or {}
        rows: List[Dict[str, object]] = []

        st.caption(\"Заполните суммы по форматам. Пустые значения будут удалены из записей дня.\")
        entry_items = [entry for entry in entries if (entry[\"fmt\"].code or \"\").lower() != \"payment_link\"]
        inputs_per_row = 2
        cols = st.columns(inputs_per_row)
        for idx, entry in enumerate(entry_items):
            if idx % inputs_per_row == 0 and idx != 0:
                cols = st.columns(inputs_per_row)

            fmt = entry[\"fmt\"]
            comp: m_company.Company | None = entry.get(\"company\")  # type: ignore
            record = existing_map.get((fmt.id, comp.id if comp else None))
            default_value = float(_to_decimal(record.amount)) if record and record.amount is not None else 0.0
            col = cols[idx % inputs_per_row]
            with col:
                amount_value = st.number_input(
                    entry[\"label\"],
                    min_value=0.0,
                    value=default_value,
                    step=100.0,
                    format=\"%.2f\",
                    key=f\"day_amount_{up_obj.id}_{report_month}_{selected_date.isoformat()}_{fmt.id}_{comp.id if comp else 'none'}\",
                )

            rows.append(
                {
                    \"Название\": entry[\"label\"],
                    \"format_id\": fmt.id,
                    \"company_id\": comp.id if comp else None,
                    \"Сумма\": amount_value,
                    \"Записано\": bool(record.recorded) if record else False,
                    \"Комментарий\": record.comment if record else None,
                }
            )

        col_save, col_cancel = st.columns([1, 1])
        with col_save:
            submit = st.form_submit_button(\"Сохранить записи\", type=\"primary\")
        with col_cancel:
            cancel = st.form_submit_button(\"Отмена\", type=\"secondary\")

        if submit:
            existing_map = records_by_date.get(selected_date, {})
            entries_by_key = {
                (entry[\"fmt\"].id, (entry.get(\"company\").id if entry.get(\"company\") else None)): entry  # type: ignore
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
                st.session_state[_flash_key(up_obj.id)] = _format_day_message(
                    created, updated, deleted, selected_date
                )
                _close_day_modal(modal_state_key)
                return bool(created or updated or deleted)
            except Exception as exc:
                session.rollback()
                st.error(f\"Не удалось сохранить записи дня: {exc}\")
                return False
        elif cancel:
            _close_day_modal(modal_state_key)
            return False

    return False
"""
new_lines = lines[:start] + new_block.splitlines() + lines[end:]
path.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
