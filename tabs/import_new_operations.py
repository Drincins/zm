import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy.orm import Session

from core.db import SessionLocal
from core.parser import clean_account, clean_inn, parse_bank_statement_to_df
from db_models import category, company, editbank, firm, group, up_company
from db_models import statement as m_statement

BASE_BANK_DIR = Path(os.getenv("BANK_STATEMENTS_DIR", Path(__file__).resolve().parent.parent / "data" / "bank_statements"))
NEW_DIR = BASE_BANK_DIR / "new"
ARCHIVE_DIR = BASE_BANK_DIR / "archive"
NEW_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


def safe_int(val):
    if val == "" or pd.isna(val):
        return None
    try:
        return int(val)
    except Exception:
        return None


def build_archive_destination(file_path: Path) -> Path:
    base, ext = os.path.splitext(file_path.name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_name = f"{base}_{ts}{ext}"
    dest_path = ARCHIVE_DIR / dest_name
    counter = 1
    while dest_path.exists():
        dest_name = f"{base}_{ts}_{counter}{ext}"
        dest_path = ARCHIVE_DIR / dest_name
        counter += 1
    return dest_path


def find_firm_or_company(inn, account, session: Session):
    inn_norm = clean_inn(inn)
    account_norm = clean_account(account)

    if account_norm:
        company_obj = (
            session.query(company.Company)
            .filter(company.Company.settlement_account == account_norm)
            .first()
        )
        if company_obj:
            return None, company_obj

    firm_obj = session.query(firm.Firm).filter(firm.Firm.inn == inn_norm).first() if inn_norm else None
    company_matches = session.query(company.Company).filter(company.Company.inn == inn_norm).all() if inn_norm else []
    company_obj = company_matches[0] if len(company_matches) == 1 else None
    if not (firm_obj or company_obj) and inn_norm:
        alt = inn_norm.lstrip("0")
        if alt != inn_norm and len(alt) in (10, 12):
            firm_obj = firm_obj or session.query(firm.Firm).filter(firm.Firm.inn == alt).first()
            if not company_obj:
                company_matches = session.query(company.Company).filter(company.Company.inn == alt).all()
                company_obj = company_matches[0] if len(company_matches) == 1 else None
    return firm_obj, company_obj


def find_category(cat_id, session):
    return session.query(category.Category).filter(category.Category.id == cat_id).first()


def find_group(group_id, session):
    return session.query(group.Group).filter(group.Group.id == group_id).first()


def parse_file(filepath: Path, session: Session):
    if not filepath.exists():
        st.error(f"Файл не найден: {filepath}")
        return pd.DataFrame(), [], "error"
    try:
        if filepath.stat().st_size == 0:
            return pd.DataFrame(), [], "empty"
    except OSError as exc:
        st.error(f"Не удалось прочитать файл {filepath}: {exc}")
        return pd.DataFrame(), [], "error"

    if filepath.suffix.lower() in (".txt", ".csv", ".xlsx"):
        try:
            df, new_inns = parse_bank_statement_to_df(
                str(filepath),
                session,
                find_firm_or_company,
                find_category,
                find_group,
            )
        except pd.errors.EmptyDataError:
            return pd.DataFrame(), [], "empty"
        except ValueError as exc:
            if "empty" in str(exc).lower():
                return pd.DataFrame(), [], "empty"
            st.error(f"Не удалось распарсить файл {filepath.name}: {exc}")
            return pd.DataFrame(), [], "error"
        except FileNotFoundError:
            st.error(f"Файл не найден: {filepath}")
            return pd.DataFrame(), [], "error"
        except Exception as exc:
            st.error(f"Неожиданная ошибка при парсинге {filepath.name}: {exc}")
            return pd.DataFrame(), [], "error"
    else:
        st.error(f"Неподдерживаемый формат файла: {filepath}")
        return pd.DataFrame(), [], "error"

    status = "empty" if df.empty else "ok"
    return df, new_inns, status


def _build_preview_df(df: pd.DataFrame, session: Session) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    comp_map = {cid: name for cid, name in session.query(company.Company.id, company.Company.name).all()}
    firm_map = {fid: name for fid, name in session.query(firm.Firm.id, firm.Firm.name).all()}
    up_map = {uid: name for uid, name in session.query(up_company.UpCompany.id, up_company.UpCompany.name).all()}
    cat_map = {cid: name for cid, name in session.query(category.Category.id, category.Category.name).all()}
    group_map = {gid: name for gid, name in session.query(group.Group.id, group.Group.name).all()}

    preview = df.copy()

    # Плательщик
    payer_name = pd.Series([""] * len(preview))
    if "payer_company_id" in preview.columns:
        payer_name = preview["payer_company_id"].map(comp_map)
    if "payer_firm_id" in preview.columns:
        payer_name = payer_name.fillna(preview["payer_firm_id"].map(firm_map))
    if "payer_raw" in preview.columns:
        payer_name = payer_name.fillna(preview["payer_raw"])
    preview["Плательщик"] = payer_name.fillna("")

    # Получатель
    receiver_name = pd.Series([""] * len(preview))
    if "receiver_company_id" in preview.columns:
        receiver_name = preview["receiver_company_id"].map(comp_map)
    if "receiver_firm_id" in preview.columns:
        receiver_name = receiver_name.fillna(preview["receiver_firm_id"].map(firm_map))
    if "receiver_raw" in preview.columns:
        receiver_name = receiver_name.fillna(preview["receiver_raw"])
    preview["Получатель"] = receiver_name.fillna("")

    if "up_company_id" in preview.columns:
        preview["Головная компания"] = preview["up_company_id"].map(up_map).fillna("")
    if "za_kogo_platili_id" in preview.columns:
        preview["За кого платили"] = preview["za_kogo_platili_id"].map(up_map).fillna("")
    if "payer_account" in preview.columns:
        preview["Счет плательщика"] = preview["payer_account"].fillna("")
    if "receiver_account" in preview.columns:
        preview["Счет получателя"] = preview["receiver_account"].fillna("")

    if "category_id" in preview.columns:
        preview["Категория"] = preview["category_id"].map(cat_map).fillna("")
    if "group_id" in preview.columns:
        preview["Группа"] = preview["group_id"].map(group_map).fillna("")

    # Скрываем id-колонки, чтобы в интерфейсе были "человеческие" значения
    drop_cols = [
        "payer_company_id",
        "payer_firm_id",
        "receiver_company_id",
        "receiver_firm_id",
        "up_company_id",
        "za_kogo_platili_id",
        "group_id",
        "category_id",
        "payer_account",
        "receiver_account",
    ]
    preview = preview.drop(columns=[c for c in drop_cols if c in preview.columns])
    return preview


def _import_df(df: pd.DataFrame, session: Session) -> tuple[int, int, int]:
    """Return imported, total, duplicate counts."""
    imported_count = 0
    duplicate_count = 0
    total_count = 0
    if df.empty or "row_id" not in df.columns:
        return imported_count, total_count, duplicate_count

    target_ids = set(df["row_id"])
    if not target_ids:
        return imported_count, total_count, duplicate_count

    existing_edit_all = set(
        r[0]
        for r in session.query(editbank.EditBank.row_id)
        .filter(editbank.EditBank.row_id.in_(target_ids))
        .all()
    )
    existing_stmt_all = set(
        r[0]
        for r in session.query(m_statement.Statement.row_id)
        .filter(m_statement.Statement.row_id.in_(target_ids))
        .all()
    )
    existing_all = existing_edit_all | existing_stmt_all
    total_count = len(df)

    for _, row in df.iterrows():
        rid = row.get("row_id")
        if not rid or rid in existing_all:
            duplicate_count += 1
            continue
        stmt = editbank.EditBank(
            row_id=rid,
            date=pd.to_datetime(row.get("date")) if pd.notna(row.get("date")) else None,
            report_month=row.get("report_month"),
            doc_number=row.get("doc_number"),
            payer_inn=clean_inn(row.get("payer_inn")),
            receiver_inn=clean_inn(row.get("receiver_inn")),
            payer_account=clean_account(row.get("payer_account")),
            receiver_account=clean_account(row.get("receiver_account")),
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

    return imported_count, total_count, duplicate_count


def import_new_operations_tab():
    st.header("Импорт банковских операций")
    with SessionLocal() as session:
        _render_import_new_operations(session)


def _render_import_new_operations(session: Session):
    st.markdown("#### Ручная загрузка файла")
    uploaded = st.file_uploader(
        "Загрузить выписку (.xlsx, .csv, .txt)",
        type=["xlsx", "csv", "txt"],
        key="manual_bank_upload",
    )
    manual_state = st.session_state.get("manual_upload") or {}
    if uploaded:
        tmp_name = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded.name}"
        tmp_path = NEW_DIR / tmp_name
        tmp_path.write_bytes(uploaded.getbuffer())
        df_up, new_inns_up, status_up = parse_file(tmp_path, session)
        manual_state = {
            "path": str(tmp_path),
            "df": df_up,
            "new_inns": new_inns_up,
            "status": status_up,
        }
        st.session_state["manual_upload"] = manual_state

    if manual_state:
        filepath = Path(manual_state.get("path", ""))
        df_up = manual_state.get("df")
        if df_up is None:
            df_up = pd.DataFrame()
        new_inns_up = manual_state.get("new_inns") or []
        status_up = manual_state.get("status")
        archive_path = build_archive_destination(filepath)

        if status_up == "empty":
            st.warning("Загруженный файл пустой. Отправлен в архив.")
            if filepath.exists():
                filepath.rename(archive_path)
            st.session_state.pop("manual_upload", None)
        elif status_up == "error":
            st.error("Не удалось обработать загруженный файл.")
        elif "row_id" not in df_up.columns:
            st.warning("В загруженном файле нет столбца row_id. Отправлен в архив.")
            if filepath.exists():
                filepath.rename(archive_path)
            st.session_state.pop("manual_upload", None)
        else:
            target_ids = set(df_up["row_id"])
            existing_edit = set(
                r[0]
                for r in session.query(editbank.EditBank.row_id)
                .filter(editbank.EditBank.row_id.in_(target_ids))
                .all()
            )
            existing_stmt = set(
                r[0]
                for r in session.query(m_statement.Statement.row_id)
                .filter(m_statement.Statement.row_id.in_(target_ids))
                .all()
            )
            existing_row_ids = existing_edit | existing_stmt
            new_row_ids = target_ids - existing_row_ids
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Всего строк", len(df_up))
            col2.metric("Новые строки", len(new_row_ids))
            col3.metric("Есть в EditBank", len(existing_edit & target_ids))
            col4.metric("Есть в Statement", len(existing_stmt & target_ids))
            if new_inns_up:
                st.info(f"Новые ИНН: {', '.join(new_inns_up)}")
            st.dataframe(_build_preview_df(df_up, session).head(30), use_container_width=True)

            if st.button("Импортировать загруженный файл в БД и отправить в архив", type="primary"):
                imported, total, duplicate = _import_df(df_up, session)
                try:
                    session.commit()
                    if filepath.exists():
                        filepath.rename(archive_path)
                    st.success(f"Импортировано: {imported} из {total}. Дубликаты: {duplicate}.")
                    st.session_state.pop("manual_upload", None)
                except Exception as exc:
                    session.rollback()
                    st.error(f"Не удалось сохранить записи: {exc}")

    new_files = [p.name for p in NEW_DIR.iterdir() if p.is_file() and p.suffix.lower() in (".xlsx", ".csv", ".txt")]
    st.info(f"Файлов в очереди: **{len(new_files)}**")
    selected_files = st.multiselect("Выберите файл(ы) для просмотра и загрузки", new_files)
    file_parse_results = {}
    files_to_skip = set()

    if selected_files:
        for file in selected_files:
            st.markdown(f"**Просматриваем файл:** {file}")
            filepath = NEW_DIR / file
            df, new_inns, status = parse_file(filepath, session)
            file_parse_results[file] = (df, new_inns, status)
            if status == "empty":
                if filepath.exists():
                    try:
                        dest_path = build_archive_destination(filepath)
                        filepath.rename(dest_path)
                        st.warning(f"Файл {file} пустой. Отправлен в архив.")
                    except Exception as exc:
                        st.warning(f"Файл {file} пустой, но не удалось перенести его в архив: {exc}")
                else:
                    st.warning(f"Файл {file} пустой, но уже отсутствует в new.")
                files_to_skip.add(file)
                continue
            if status == "error":
                files_to_skip.add(file)
                continue
            if "row_id" not in df.columns:
                st.warning("В файле нет обязательного столбца `row_id`.")
                files_to_skip.add(file)
                continue

            target_ids = set(df["row_id"])
            existing_edit = set(
                r[0] for r in session.query(editbank.EditBank.row_id).filter(editbank.EditBank.row_id.in_(target_ids)).all()
            )
            existing_stmt = set(
                r[0] for r in session.query(m_statement.Statement.row_id).filter(m_statement.Statement.row_id.in_(target_ids)).all()
            )
            existing_row_ids = existing_edit | existing_stmt
            new_row_ids = target_ids - existing_row_ids
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Всего строк", len(df))
            col2.metric("Новые строки", len(new_row_ids))
            col3.metric("Есть в EditBank", len(existing_edit & target_ids))
            col4.metric("Есть в Statement", len(existing_stmt & target_ids))
            if new_inns:
                st.info(f"Новые ИНН: {', '.join(new_inns)}")
            st.dataframe(_build_preview_df(df, session).head(30), use_container_width=True)

    if st.button("Загрузить выбранные файлы в БД (EditBank)"):
        imported_count = 0
        duplicate_count = 0
        total_count = 0
        files_to_move = []
        all_selected_ids = set()

        for file in selected_files:
            if file in files_to_skip:
                continue
            df_tmp, _, status_tmp = file_parse_results.get(file, (pd.DataFrame(), [], "error"))
            if status_tmp != "ok" or df_tmp.empty or "row_id" not in df_tmp.columns:
                continue
            all_selected_ids.update(df_tmp["row_id"])

        if all_selected_ids:
            existing_edit_all = set(
                r[0] for r in session.query(editbank.EditBank.row_id).filter(editbank.EditBank.row_id.in_(all_selected_ids)).all()
            )
            existing_stmt_all = set(
                r[0] for r in session.query(m_statement.Statement.row_id).filter(m_statement.Statement.row_id.in_(all_selected_ids)).all()
            )
            existing_all = existing_edit_all | existing_stmt_all
        else:
            existing_all = set()

        for file in selected_files:
            if file in files_to_skip:
                continue
            filepath = NEW_DIR / file
            df, _, status = file_parse_results.get(file, (pd.DataFrame(), [], "error"))
            if status != "ok" or df.empty or "row_id" not in df.columns:
                continue
            total_count += len(df)
            for _, row in df.iterrows():
                rid = row.get("row_id")
                if not rid or rid in existing_all:
                    duplicate_count += 1
                    continue
                stmt = editbank.EditBank(
                    row_id=rid,
                    date=pd.to_datetime(row.get("date")) if pd.notna(row.get("date")) else None,
                    report_month=row.get("report_month"),
                    doc_number=row.get("doc_number"),
                    payer_inn=clean_inn(row.get("payer_inn")),
                    receiver_inn=clean_inn(row.get("receiver_inn")),
                    payer_account=clean_account(row.get("payer_account")),
                    receiver_account=clean_account(row.get("receiver_account")),
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
            if filepath.exists():
                files_to_move.append((filepath, build_archive_destination(filepath)))

        try:
            session.commit()
        except Exception as exc:
            session.rollback()
            st.error(f"Не удалось сохранить записи: {exc}")
            return

        for src_path, dest_path in files_to_move:
            try:
                src_path.rename(dest_path)
            except Exception as exc:
                st.warning(f"Не удалось перенести файл {src_path.name} в архив: {exc}")

        st.success(f"Загружено: {imported_count} из {total_count}")
        st.info(f"Дубликаты (EditBank+Statement): {duplicate_count}")
