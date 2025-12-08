# tabs/import_edit_operations.py
import re
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

from core.db import SessionLocal
from core.months import RU_MONTHS, RU_MONTH_NAME_TO_INDEX, month_name_from_date
from db_models import editbank, statement, firm, company, category, group, up_company
from core.parser import clean_inn  #    

# --- RU months helpers ( core.months) ---

def _is_rm_yyyy_mm(s: str) -> bool:
    return isinstance(s, str) and len(s) == 7 and s[4] == "-"


def _resolve_month_year(raw_month: str | None, date_val) -> tuple[str | None, int]:
    """ (-, )   /."""
    default_year = 2025
    if raw_month:
        raw = str(raw_month).strip()
        if _is_rm_yyyy_mm(raw):
            year_val = int(raw[:4])
            month_idx = int(raw[5:])
            month_name = RU_MONTHS[month_idx - 1] if 1 <= month_idx <= 12 else raw
            return month_name, year_val
        parts = raw.split()
        if len(parts) >= 2 and parts[-1].isdigit():
            try:
                year_val = int(parts[-1])
            except ValueError:
                year_val = date_val.year if date_val else default_year
            month_name = " ".join(parts[:-1]).strip() or (month_name_from_date(date_val) if date_val else None)
            return month_name, year_val
        if raw in RU_MONTH_NAME_TO_INDEX:
            return raw, (date_val.year if date_val else default_year)
        # Fallback:   
        return raw, (date_val.year if date_val else default_year)

    #          
    month_name = month_name_from_date(date_val) if date_val else None
    year_val = date_val.year if date_val else default_year
    return month_name, year_val

def import_edit_operations_tab():
    st.header("  (  )")

    #    ( /)
    st.markdown("""
    <style>
      .stButton>button { width: 100%; min-height: 38px; }
    </style>
    """, unsafe_allow_html=True)

    with SessionLocal() as session:
        # ---  ---
        firms = session.query(firm.Firm).all()
        companies = session.query(company.Company).all()
        categories = session.query(category.Category).all()
        groups = session.query(group.Group).all()
        up_companies = session.query(up_company.UpCompany).all()

        firm_map = {f.id: f.name for f in firms}
        firm_inn_map = {f.id: f.inn for f in firms}
        company_map = {c.id: c.name for c in companies}
        company_up_map = {c.id: c.up_company_id for c in companies}  #   
        category_map = {c.id: c.name for c in categories}
        group_map = {g.id: g.name for g in groups}
        category_to_group = {c.id: c.group_id for c in categories}
        up_company_map = {u.id: u.name for u in up_companies}
        up_company_name_to_id = {u.name: u.id for u in up_companies}

        #       ( )
        group_name_to_id = {v: k for k, v in group_map.items()}
        cat_name_to_id = {v: k for k, v in category_map.items()}
        cats_by_group: dict[int | None, list[category.Category]] = {}
        for c in categories:
            cats_by_group.setdefault(c.group_id, []).append(c)

        # ---    ---
        ops = session.query(editbank.EditBank).order_by(editbank.EditBank.date.desc()).all()
        if not ops:
            st.info("  .    .")
            return

        # ---  DataFrame   ---
        df_rows = []
        for op in ops:
            month_name, year_val = _resolve_month_year(op.report_month, op.date)
            #  up_company_id   (      )
            inferred_up_id = op.up_company_id
            if not inferred_up_id:
                op_type = (op.operation_type or "").strip().lower()
                if "" in op_type and op.payer_company_id:
                    inferred_up_id = company_up_map.get(op.payer_company_id)
                elif "" in op_type and op.receiver_company_id:
                    inferred_up_id = company_up_map.get(op.receiver_company_id)
                if not inferred_up_id:
                    inferred_up_id = company_up_map.get(op.payer_company_id) or company_up_map.get(op.receiver_company_id)

            # "  "   (    ,  inferred_up_id)
            zk_id = op.za_kogo_platili_id or inferred_up_id

            df_rows.append({
                "id": op.id,
                "": op.date.strftime('%d.%m.%Y') if op.date else "",
                " ": month_name or "",
                " ": year_val,
                " ": up_company_map.get(inferred_up_id, ""),
                "  ": up_company_map.get(zk_id, ""),  # NEW
                "": (
                    company_map.get(op.payer_company_id)
                    or firm_map.get(op.payer_firm_id)
                    or op.payer_raw
                    or ""
                ),
                " ": clean_inn(op.payer_inn) or "",
                "": (
                    company_map.get(op.receiver_company_id)
                    or firm_map.get(op.receiver_firm_id)
                    or op.receiver_raw
                    or ""
                ),
                " ": clean_inn(op.receiver_inn) or "",
                "": op.purpose or "",
                "": op.amount,
                " ": op.operation_type or "",
                "": category_map.get(op.category_id, ""),
                "": group_map.get(op.group_id, ""),
                "": op.comment or "",
                "row_id": op.row_id,
                "": bool(op.recorded),
            })
        df = pd.DataFrame(df_rows)
        if "" in df.columns:
            df[""] = pd.to_datetime(df[""], dayfirst=True, errors="coerce")\
                            .dt.strftime("%d.%m.%Y")\
                            .fillna("")
        # --- :     label->raw    ---
        ru_month_opts = RU_MONTHS

        # --- AgGrid ( ) ---
        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_default_column(editable=False, filter=True, resizable=True)  #  read-only  
        gb.configure_selection(selection_mode="multiple", use_checkbox=True)
        gb.configure_column(
            "id",
            headerCheckboxSelection=True,
            headerCheckboxSelectionFilteredOnly=True,
            checkboxSelection=True,
            pinned="left",
            width=90,
        )

        #        (  )
        gb.configure_column(" ", editable=False)

        #    
        gb.configure_column("", editable=False)
        gb.configure_column("", editable=False)
        gb.configure_column(" ", editable=False)
        gb.configure_column("  ", editable=False)
        gb.configure_column("", editable=False)

        gb.configure_column("", editable=False)
        gb.configure_column(" ", editable=False)
        gb.configure_column("", editable=False)
        gb.configure_column("", editable=False)
        gb.configure_column(" ", editable=False)
        gb.configure_column(" ", editable=False)
        gb.configure_column("", editable=False)
        gb.configure_column("", editable=False)
        gb.configure_column("", editable=False)
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

        #   
        grid_data = (grid_response or {}).get("data", df)
        edited_df = pd.DataFrame(grid_data)

        #  
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
        # ===================== - ( ) =====================
        col1, col2, col3 = st.columns([2.5, 2.5, 3])
        with col1:
            btn_transfer_sel = st.button("   Statement", disabled=(len(selected_list) == 0), width="stretch")
        with col2:
            btn_delete_sel = st.button("    ", disabled=(len(selected_list) == 0), width="stretch")
        # col3   
        with col3:
            pop = getattr(st, "popover", None)
            ctx_edit = pop("   ") if pop else st.expander("   ")

        # ---------------------     ---------------------
        with ctx_edit:
            if len(selected_list) != 1:
                st.info("       .")
            else:
                sel_id = int(float(selected_list[0]["id"]))
                obj = session.get(editbank.EditBank, sel_id)
                if not obj:
                    st.warning("  .")
                else:
                    # read-only 
                    payer_name = company_map.get(obj.payer_company_id) or firm_map.get(obj.payer_firm_id) or (obj.payer_raw or "")
                    receiver_name = company_map.get(obj.receiver_company_id) or firm_map.get(obj.receiver_firm_id) or (obj.receiver_raw or "")
                    st.markdown(f"**:** {payer_name}")
                    st.markdown(f"**:** {receiver_name}")
                    st.markdown(f"** :** {up_company_map.get(obj.up_company_id, '')}")
                    st.divider()

                    #   
                    cur_group_name = group_map.get(obj.group_id, "")
                    cur_cat_name = category_map.get(obj.category_id, "")
                    cur_zk_name = up_company_map.get(obj.za_kogo_platili_id, up_company_map.get(obj.up_company_id, ""))
                    cur_month_name, cur_year_val = _resolve_month_year(obj.report_month, obj.date)

                    col_l, col_r = st.columns(2)
                    with col_l:
                        new_month_name = st.selectbox(
                            " ",
                            options=RU_MONTHS,
                            index=(RU_MONTHS.index(cur_month_name) if cur_month_name in RU_MONTHS else 0),
                        )
                        new_year_val = st.number_input(
                            " ",
                            value=int(cur_year_val or 2025),
                            min_value=2000,
                            max_value=2100,
                            step=1,
                        )

                        new_type = st.selectbox(" ", options=["", ""],
                                                index=(0 if (obj.operation_type or "").strip().lower() == "" else 1))
                        new_amount = st.number_input("", value=float(obj.amount or 0.0), step=100.0, format="%.2f")
                        up_names_all = [u.name for u in up_companies]
                        sel_zk_name = st.selectbox("  ", options=up_names_all,
                                                   index=(up_names_all.index(cur_zk_name) if cur_zk_name in up_names_all else 0))
                        sel_zk = next((u for u in up_companies if u.name == sel_zk_name), None)

                    with col_r:
                        group_names = [g.name for g in groups]
                        sel_group_name = st.selectbox("", options=[""] + group_names,
                                                      index=(group_names.index(cur_group_name) + 1) if cur_group_name in group_names else 0)
                        sel_group = next((g for g in groups if g.name == sel_group_name), None)

                        #    
                        cats_for_group = cats_by_group.get(sel_group.id if sel_group else None, [])
                        cat_names = [c.name for c in cats_for_group] if cats_for_group else [c.name for c in categories]
                        sel_cat_name = st.selectbox("", options=[""] + cat_names,
                                                    index=(cat_names.index(cur_cat_name) + 1) if cur_cat_name in cat_names else 0)

                    new_purpose = st.text_input("", value=(obj.purpose or ""))
                    new_comment = st.text_area("", value=(obj.comment or ""), height=120)

                    if st.button("  ", width="stretch"):
                        try:
                            obj.report_month = new_month_name
                            obj.report_year = int(new_year_val) if new_year_val else None

                            obj.operation_type = (new_type or "").strip().lower()
                            try:
                                obj.amount = float(new_amount)
                            except Exception:
                                pass
                            obj.purpose = (new_purpose or None)
                            obj.comment = (new_comment or None)

                            # /
                            if sel_cat_name and sel_cat_name != "":
                                new_cat = next((c for c in categories if c.name == sel_cat_name), None)
                                if new_cat:
                                    obj.category_id = new_cat.id
                                    obj.group_id = new_cat.group_id
                            else:
                                if sel_group:
                                    obj.group_id = sel_group.id

                            #   
                            if sel_zk:
                                obj.za_kogo_platili_id = sel_zk.id

                            session.commit()
                            st.success(" .")
                            st.rerun()
                        except Exception as e:
                            session.rollback()
                            st.error(f" : {e}")

        # ---------------------   ---------------------
        if btn_transfer_sel:
            selected = pd.DataFrame(selected_list)
            imported_count = 0
            for _, row in selected.iterrows():
                #   row_id
                exists = session.query(statement.Statement).filter_by(row_id=row["row_id"]).first()
                if exists:
                    continue

                #  cat/group    
                cat_id = next((k for k, v in category_map.items() if v == row.get("")), None)
                group_id = next((k for k, v in group_map.items() if v == row.get("")), None)

                #   
                op_db = session.query(editbank.EditBank).filter_by(row_id=row["row_id"]).first()

                #      
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
                    zk_id = up_company_name_to_id.get(row.get("  ") or "")
                    inferred_up_id = zk_id or up_company_name_to_id.get(row.get(" ") or "")

                # /    (  )
                report_month_val, report_year_val = _resolve_month_year(
                    row.get(" "),
                    pd.to_datetime(row.get(""), dayfirst=True, errors="coerce") if row.get("") else (op_db.date if op_db else None),
                )
                #          op_db
                if not row.get("") and op_db and op_db.date:
                    date_for_year = op_db.date
                else:
                    date_for_year = pd.to_datetime(row.get(""), dayfirst=True, errors="coerce")
                if not report_year_val and date_for_year is not None:
                    try:
                        report_year_val = int(date_for_year.year)
                    except Exception:
                        report_year_val = 2025

                stmt = statement.Statement(
                    row_id=row.get("row_id"),
                    date=pd.to_datetime(row.get(""), dayfirst=True) if row.get("") else (op_db.date if op_db else None),
                    report_month=report_month_val,
                    report_year=report_year_val,
                    doc_number=op_db.doc_number if op_db else None,
                    payer_inn=clean_inn(row.get(" ") or (op_db.payer_inn if op_db else "")),
                    receiver_inn=clean_inn(row.get(" ") or (op_db.receiver_inn if op_db else "")),
                    purpose=row.get("") or (op_db.purpose if op_db else None),
                    amount=row.get("") if pd.notna(row.get("")) else (op_db.amount if op_db else None),
                    operation_type=row.get(" ") or (op_db.operation_type if op_db else None),
                    comment=row.get("") or (op_db.comment if op_db else None),
                    recorded=bool(row.get("", False)),
                    payer_raw=row.get("") or (op_db.payer_raw if op_db else None),
                    receiver_raw=row.get("") or (op_db.receiver_raw if op_db else None),
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
            st.success(f" : {imported_count}")
            st.rerun()

        if btn_delete_sel:
            ids_to_delete = []
            for r in selected_list:
                try:
                    ids_to_delete.append(int(float(r.get("id"))))
                except Exception:
                    continue
            if not ids_to_delete:
                st.warning("    .")
            else:
                try:
                    deleted = session.query(editbank.EditBank)\
                        .filter(editbank.EditBank.id.in_(ids_to_delete))\
                        .delete(synchronize_session=False)
                    session.commit()
                    st.success(f" : {deleted}")
                    st.rerun()
                except Exception as e:
                    session.rollback()
                    st.error(f"  : {e}")

        #  
        def _fmt_rub(x):
            try:
                return f"{int(round(float(x))):,}".replace(",", " ") + " "
            except Exception:
                return x

        def _fmt_date(d):
            return d.strftime("%d.%m.%Y") if d else ""

        def _counterparty_fields(op):
            """
            /    (  ).
              ,   .
            """
            t = (op.operation_type or "").strip().lower()
            if "" in t:
                name = company_map.get(op.payer_company_id) or firm_map.get(op.payer_firm_id) or (op.payer_raw or "")
                inn  = clean_inn(op.payer_inn) or (clean_inn(firm_inn_map.get(op.payer_firm_id)) if op.payer_firm_id else "")
            else:
                name = company_map.get(op.receiver_company_id) or firm_map.get(op.receiver_firm_id) or (op.receiver_raw or "")
                inn  = clean_inn(op.receiver_inn) or (clean_inn(firm_inn_map.get(op.receiver_firm_id)) if op.receiver_firm_id else "")
            return name, inn

        #    (   )       
        ops_missing_cat = []
        for op in ops:
            if not op.group_id or not op.category_id:
                ops_missing_cat.append(op)

        # ----------   (  )    ----------
        #      (/)       firms/companies.
        existing_inn = {
            clean_inn(f.inn) for f in firms if f.inn
        } | {
            clean_inn(c.inn) for c in companies if getattr(c, "inn", None)
        }
        existing_names = { (f.name or "").strip().lower() for f in firms if f.name } | { (c.name or "").strip().lower() for c in companies if c.name }

        new_groups: dict[tuple[str, str], list[editbank.EditBank]] = {}
        for op in ops_missing_cat:
            nm, inn = _counterparty_fields(op)
            nm = (nm or "").strip() or ""
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
            st.markdown("####   (   )")
            for idx, ((nm, inn_val), op_list) in enumerate(sorted(new_groups.items(), key=lambda x: x[0][0].lower()), 1):
                st.markdown(f"<div style='font-size:16px;font-weight:700;color:#d97706;'> : {nm}</div>", unsafe_allow_html=True)
                st.markdown(f"*:* **{inn_val or ''}**  : **{len(op_list)}**")

                #      
                cat_names = [c.name for c in categories]
                sel_cat_name = st.selectbox(
                    "    (    )",
                    options=cat_names,
                    index=0,
                    key=f"new_counterparty_cat_{idx}",
                )
                sel_cat = next((c for c in categories if c.name == sel_cat_name), None)
                group_hint = next((g.name for g in groups if sel_cat and g.id == sel_cat.group_id), "")
                st.caption(f"  : **{group_hint}**")

                #  
                table_rows = []
                for op in op_list:
                    table_rows.append(
                        {
                            "": _fmt_date(op.date),
                            "": _fmt_rub(op.amount),
                            "": company_map.get(op.payer_company_id) or firm_map.get(op.payer_firm_id) or (op.payer_raw or ""),
                            "": company_map.get(op.receiver_company_id) or firm_map.get(op.receiver_firm_id) or (op.receiver_raw or ""),
                            "": op.purpose or "",
                            "ID": op.id,
                        }
                    )
                st.dataframe(pd.DataFrame(table_rows), width="stretch", hide_index=True)

                if st.button("       ", key=f"new_counterparty_btn_{idx}", width="stretch"):
                    try:
                        if not sel_cat:
                            st.error("  .")
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
                                #  ,  
                                if firm_obj.category_id != sel_cat.id:
                                    firm_obj.category_id = sel_cat.id

                            #  /   
                            for op in op_list:
                                op.category_id = sel_cat.id
                                op.group_id = sel_cat.group_id

                            session.commit()
                            st.success(f"/: {nm}   {inn_val or ''}.  : {len(op_list)}")
                            st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f": {e}")

