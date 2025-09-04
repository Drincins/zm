import streamlit as st
import os
import pandas as pd
from sqlalchemy.orm import Session
from core.db import SessionLocal
from db_models import firm, company, category, group, editbank
from core.parser import parse_bank_statement_to_df
from core.parser import clean_inn
from db_models import statement as m_statement  # для проверки дублей в основной таблице
from datetime import datetime  # NEW

NEW_DIR = r"C:\Users\Admin\Desktop\ZM\data\bank_statements\new"
ARCHIVE_DIR = r"C:\Users\Admin\Desktop\ZM\data\bank_statements\archiv"

# --- Вспомогательные функции ---
def find_firm_or_company_by_inn(inn, session):
    inn_norm = clean_inn(inn)
    firm_obj = session.query(firm.Firm).filter(firm.Firm.inn == inn_norm).first() if inn_norm else None
    company_obj = session.query(company.Company).filter(company.Company.inn == inn_norm).first() if inn_norm else None
    if not (firm_obj or company_obj) and inn_norm:
        alt = inn_norm.lstrip("0")
        if alt != inn_norm and len(alt) in (10, 12):
            firm_obj = firm_obj or session.query(firm.Firm).filter(firm.Firm.inn == alt).first()
            company_obj = company_obj or session.query(company.Company).filter(company.Company.inn == alt).first()
    return firm_obj, company_obj

def find_category(cat_id, session):
    return session.query(category.Category).filter(category.Category.id == cat_id).first()

def find_group(group_id, session):
    return session.query(group.Group).filter(group.Group.id == group_id).first()

def parse_file(filepath, session):
    if filepath.endswith('.txt') or filepath.endswith('.csv') or filepath.endswith('.xlsx'):
        df, _ = parse_bank_statement_to_df(
            filepath,
            session,
            find_firm_or_company_by_inn,
            find_category,
            find_group
        )
    else:
        st.error(f"Неизвестный формат файла: {filepath}")
        return pd.DataFrame()
    return df

def import_new_operations_tab():
    st.header("Импорт банковских выписок")
    session = SessionLocal()

    new_files = [f for f in os.listdir(NEW_DIR) if f.lower().endswith(('.xlsx', '.csv', '.txt'))]
    st.info(f"Найдено новых файлов: **{len(new_files)}**")
    selected_files = st.multiselect("Выберите файл(ы) для предпросмотра и импорта", new_files)

    if selected_files:
        for file in selected_files:
            st.markdown(f"**Предпросмотр файла:** {file}")
            filepath = os.path.join(NEW_DIR, file)
            df = parse_file(filepath, session)

            if df.empty or "row_id" not in df.columns:
                st.warning("В файле нет данных или отсутствует колонка `row_id` — пропускаю предпросмотр.")
                continue

            target_ids = set(df["row_id"])

            existing_edit = set(r[0] for r in (
                session.query(editbank.EditBank.row_id)
                .filter(editbank.EditBank.row_id.in_(target_ids))
                .all()
            ))
            existing_stmt = set(r[0] for r in (
                session.query(m_statement.Statement.row_id)
                .filter(m_statement.Statement.row_id.in_(target_ids))
                .all()
            ))

            existing_row_ids = existing_edit | existing_stmt
            duplicate_row_ids = target_ids & existing_row_ids
            new_row_ids = target_ids - existing_row_ids

            # --- Раздельные метрики
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Всего операций", len(df))
            col2.metric("Новых операций", len(new_row_ids))
            col3.metric("Дубликатов в EditBank", len(existing_edit & target_ids))
            col4.metric("Дубликатов в Statement", len(existing_stmt & target_ids))

            st.dataframe(df.head(30), use_container_width=True)

    if st.button("Импортировать выбранные файлы в базу (EditBank)"):
        imported_count = 0
        duplicate_count = 0
        total_count = 0

        all_selected_ids = set()
        for file in selected_files:
            df_tmp = parse_file(os.path.join(NEW_DIR, file), session)
            if not df_tmp.empty and "row_id" in df_tmp.columns:
                all_selected_ids.update(df_tmp["row_id"])

        if all_selected_ids:
            existing_edit_all = set(r[0] for r in (
                session.query(editbank.EditBank.row_id)
                .filter(editbank.EditBank.row_id.in_(all_selected_ids))
                .all()
            ))
            existing_stmt_all = set(r[0] for r in (
                session.query(m_statement.Statement.row_id)
                .filter(m_statement.Statement.row_id.in_(all_selected_ids))
                .all()
            ))
            existing_all = existing_edit_all | existing_stmt_all
        else:
            existing_all = set()

        for file in selected_files:
            filepath = os.path.join(NEW_DIR, file)
            df = parse_file(filepath, session)
            if df.empty:
                continue

            total_count += len(df)

            for _, row in df.iterrows():
                rid = row.get("row_id")
                if not rid:
                    duplicate_count += 1
                    continue
                if rid in existing_all:
                    duplicate_count += 1
                    continue

                def safe_int(val):
                    if val == '' or pd.isna(val):
                        return None
                    try:
                        return int(val)
                    except Exception:
                        return None

                stmt = editbank.EditBank(
                    row_id=rid,
                    date=pd.to_datetime(row.get("date")) if pd.notna(row.get("date")) else None,
                    report_month=row.get("report_month"),
                    doc_number=row.get("doc_number"),
                    payer_inn=clean_inn(row.get("payer_inn")),
                    receiver_inn=clean_inn(row.get("receiver_inn")),
                    purpose=row.get("purpose"),
                    amount=row.get("amount"),
                    operation_type=row.get("operation_type"),
                    comment=row.get("comment"),
                    recorded=bool(row.get("recorded", False)),
                    manually_edited=bool(row.get("manually_edited", False)),
                    payer_raw=row.get("payer_raw"),
                    receiver_raw=row.get("receiver_raw"),
                    payer_company_id=safe_int(row.get("payer_company_id")),
                    payer_firm_id=safe_int(row.get("payer_firm_id")),
                    receiver_company_id=safe_int(row.get("receiver_company_id")),
                    receiver_firm_id=safe_int(row.get("receiver_firm_id")),
                    up_company_id=safe_int(row.get("up_company_id")),
                    group_id=safe_int(row.get("group_id")),
                    category_id=safe_int(row.get("category_id")),
                )
                session.add(stmt)
                existing_all.add(rid)
                imported_count += 1

            # --- Переносим файл с уникальным именем
            try:
                base, ext = os.path.splitext(file)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_name = f"{base}_{ts}{ext}"
                dest_path = os.path.join(ARCHIVE_DIR, dest_name)

                counter = 1
                while os.path.exists(dest_path):
                    dest_name = f"{base}_{ts}_{counter}{ext}"
                    dest_path = os.path.join(ARCHIVE_DIR, dest_name)
                    counter += 1

                os.rename(filepath, dest_path)
            except Exception as e:
                st.warning(f"Не удалось переместить файл в архив: {file}. Ошибка: {e}")

        session.commit()
        st.success(f"Импортировано новых операций: {imported_count} из {total_count}")
        st.info(f"Пропущено дубликатов (EditBank+Statement): {duplicate_count}")

    session.close()
