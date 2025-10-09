import pandas as pd
import re
from db_models import company as company_model
from core.months import RU_MONTHS_MAP

# === Русские месяцы для отчётного месяца ===
RUS_MONTHS = RU_MONTHS_MAP

def try_float(val):
    """Безопасное приведение суммы к float с поддержкой запятой и пробелов."""
    try:
        return float(str(val).replace(',', '.').replace(' ', ''))
    except (ValueError, TypeError):
        return 0.0


def _safe_int(val):
    """Безопасно привести к int (или вернуть None), учитываем '', nan, '4.0' и т.п."""
    try:
        if val == "" or pd.isna(val):
            return None
        return int(float(val))
    except Exception:
        return None


def clean_inn(value: object) -> str:
    """
    Нормализация ИНН:
    - оставляем только цифры
    - если длина 11/13 и строка начинается с '0' → отбрасываем РОВНО один ноль (получаем 10/12)
    """
    if value is None:
        return ""
    s = str(value or "").strip()
    s = s.replace("\u00A0", "").replace(" ", "").replace("\t", "").replace("-", "")
    s = re.sub(r"[^\d]", "", s)
    if not s:
        return ""
    if s.startswith("0") and len(s) >= 11:
        s = s[1:]
    return s


# --- Парсер для 1С текстовой выписки ---
def parse_1c_client_bank(filepath):
    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()
    docs = []
    doc = {}
    in_doc = False
    for line in lines:
        line = line.strip()
        if line.startswith("СекцияДокумент="):
            in_doc = True
            doc = {}
        elif line.startswith("КонецДокумента"):
            in_doc = False
            if doc:
                docs.append(doc)
        elif in_doc and "=" in line:
            k, v = line.split("=", 1)
            doc[k.strip()] = v.strip()
    data = []
    for doc in docs:
        data.append({
            "Плательщик": doc.get("Плательщик", ""),
            "ПлательщикИНН": doc.get("ПлательщикИНН", ""),
            "Получатель": doc.get("Получатель", ""),
            "ПолучательИНН": doc.get("ПолучательИНН", ""),
            "Сумма": doc.get("Сумма", ""),
            "Дата": doc.get("Дата", ""),
            "Номер": doc.get("Номер", ""),
            "Назначение": doc.get("НазначениеПлатежа", ""),
            "ДатаСписано": doc.get("ДатаСписано", ""),
            "ДатаПоступило": doc.get("ДатаПоступило", "")
        })
    return pd.DataFrame(data)


def parse_bank_statement_to_df(
    filepath,
    session,
    find_firm_or_company_by_inn,
    find_category,
    find_group
):
    # 1. Загрузка файла
    if filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
    elif filepath.endswith('.xlsx'):
        df = pd.read_excel(filepath)
    elif filepath.endswith('.txt'):
        df = parse_1c_client_bank(filepath)
    else:
        raise ValueError("Формат файла не поддерживается (только .csv, .xlsx, .txt)")

    # Срезаем служебные строки из 1С
    remove_prefixes = ["1CClientBankExchange", "ВерсияФормата", "СекцияРасчСчет", "СекцияДокумент"]
    first_col = df.columns[0]
    df = df[~df[first_col].astype(str).str.startswith(tuple(remove_prefixes))].copy()
    df = df.reset_index(drop=True)

    # Удаляем мусорные колонки
    for col in list(df.columns):
        if "1CClientBankExchange" in col or "ВерсияФормата" in col:
            df = df.drop(columns=[col])

    # 2. Унификация колонок
    rename_map = {
        'Плательщик': 'payer_raw',
        'ПлательщикИНН': 'payer_inn',
        'Получатель': 'receiver_raw',
        'ПолучательИНН': 'receiver_inn',
        'Назначение': 'purpose',
        'Сумма': 'amount',
        'Дата': 'date',
        'Номер': 'doc_number',
        'ДатаСписано': 'date_spisano',
        'ДатаПоступило': 'date_postuplenie',
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # 3. Гарантируем все нужные поля (модель Statement)
    statement_cols = [
        "row_id", "date", "report_month", "doc_number",
        "payer_inn", "receiver_inn", "purpose", "amount", "operation_type", "comment", "recorded",
        "manually_edited", "payer_raw", "receiver_raw",
        "payer_company_id", "payer_firm_id", "receiver_company_id", "receiver_firm_id",
        "up_company_id", "group_id", "category_id",
        "za_kogo_platili_id",  # NEW
    ]
    for col in statement_cols + ["date_spisano", "date_postuplenie"]:
        if col not in df.columns:
            df[col] = ""

    # 4. Основная логика по строкам
    new_inns = set()
    for idx, row in df.iterrows():
        # будем помнить категорию фирм по сторонам (если фирма распознана)
        payer_firm_category_id = None
        receiver_firm_category_id = None

        # === Тип операции ===
        operation_type = ""
        if str(row["date_spisano"]).strip():
            operation_type = "Списание"
        elif str(row["date_postuplenie"]).strip():
            operation_type = "Поступление"
        df.at[idx, "operation_type"] = operation_type

        # === Коррекция суммы ===
        amount = try_float(row.get("amount", 0))
        if operation_type == "Списание":
            amount = -abs(amount)
        elif operation_type == "Поступление":
            amount = abs(amount)
        df.at[idx, "amount"] = amount

        purpose_text = str(row.get("purpose", "")).lower()

        # === Эквайринг === (принудительно "Списание" + локальный пересчёт row_id)
        if "эквайринг" in purpose_text:
            df.at[idx, "category_id"] = 60  # Эквайринг
            df.at[idx, "operation_type"] = "Списание"  # всегда списание

            # Ищем сумму комиссии "комиссия ХХХ,ХХ"
            def extract_commission(text):
                match = re.search(
                    r"комиссия[^\d]*(\d{1,3}(?:[ \u00A0]?\d{3})*(?:[.,]\d{2})?)",
                    str(text).lower()
                )
                if match:
                    raw = match.group(1)
                    cleaned = raw.replace(" ", "").replace("\u00A0", "").replace(",", ".")
                    try:
                        return float(cleaned)
                    except Exception:
                        return None
                return None

            commission = extract_commission(row.get("purpose", ""))
            if commission is not None:
                amount = -abs(commission)
            else:
                amount = -abs(try_float(row.get("amount", 0)))
            df.at[idx, "amount"] = amount

            # Пересчёт row_id (со знаком) — ИНН очищаем
            payer_inn_clean = clean_inn(row.get("payer_inn", ""))
            receiver_inn_clean = clean_inn(row.get("receiver_inn", ""))
            try:
                dt = pd.to_datetime(row.get("date", ""), dayfirst=True, errors="coerce")
                date_str = dt.strftime('%Y-%m-%d') if not pd.isna(dt) else ""
            except Exception:
                date_str = ""
            doc_number = str(row.get("doc_number", "")).strip()
            rowid = f"{date_str}|{doc_number}|{amount:.2f}|{payer_inn_clean}|{receiver_inn_clean}"
            df.at[idx, "row_id"] = rowid

        # === Заработная плата по реестру ===
        if "заработная плата по реестру" in purpose_text:
            df.at[idx, "category_id"] = 121  # ЗП по реестру
        if "денежное вознаграждение по реестру" in purpose_text:
            df.at[idx, "category_id"] = 142  # ЗП по реестру

        # === Плательщик и получатель (по ИНН) — очистка + fallback без ведущих нулей ===
        # Плательщик
        payer_inn_clean = clean_inn(row.get("payer_inn", ""))
        df.at[idx, "payer_inn"] = payer_inn_clean
        firm_obj, company_obj = find_firm_or_company_by_inn(payer_inn_clean, session)

        if not firm_obj and not company_obj and payer_inn_clean.startswith("0"):
            alt = payer_inn_clean.lstrip("0")
            if len(alt) in (10, 12):
                firm_obj, company_obj = find_firm_or_company_by_inn(alt, session)
                if firm_obj or company_obj:
                    payer_inn_clean = alt
                    df.at[idx, "payer_inn"] = alt  # зафиксируем нормализованное значение

        if firm_obj:
            df.at[idx, "payer_firm_id"] = firm_obj.id
            # сохраним категорию фирмы-плательщика, если есть
            if firm_obj and getattr(firm_obj, "category_id", None):
                payer_firm_category_id = firm_obj.category_id

        if company_obj:
            df.at[idx, "payer_company_id"] = company_obj.id
        if not firm_obj and not company_obj and payer_inn_clean:
            new_inns.add(payer_inn_clean)

        # Получатель
        receiver_inn_clean = clean_inn(row.get("receiver_inn", ""))
        df.at[idx, "receiver_inn"] = receiver_inn_clean
        firm_obj, company_obj = find_firm_or_company_by_inn(receiver_inn_clean, session)

        if not firm_obj and not company_obj and receiver_inn_clean.startswith("0"):
            alt = receiver_inn_clean.lstrip("0")
            if len(alt) in (10, 12):
                firm_obj, company_obj = find_firm_or_company_by_inn(alt, session)
                if firm_obj or company_obj:
                    receiver_inn_clean = alt
                    df.at[idx, "receiver_inn"] = alt

        if firm_obj:
            df.at[idx, "receiver_firm_id"] = firm_obj.id
            # только запоминаем категорию фирмы-получателя, назначим ниже едиными правилами
            if getattr(firm_obj, "category_id", None):
                receiver_firm_category_id = firm_obj.category_id

        if company_obj:
            df.at[idx, "receiver_company_id"] = company_obj.id
        if not firm_obj and not company_obj and receiver_inn_clean:
            new_inns.add(receiver_inn_clean)

        # === row_id (дату всегда в iso-формате, сумма с точкой, ИНН — окончательные очищенные) ===
        try:
            dt = pd.to_datetime(row.get("date", ""), dayfirst=True, errors="coerce")
            date_str = dt.strftime('%Y-%m-%d') if not pd.isna(dt) else ""
        except Exception:
            date_str = ""
        doc_number = str(row.get("doc_number", "")).strip()
        rowid = f"{date_str}|{doc_number}|{amount:.2f}|{payer_inn_clean}|{receiver_inn_clean}"
        df.at[idx, "row_id"] = rowid

        # --- report_month: русское название месяца из даты платежа (без года) ---
        if not str(row.get("report_month", "")).strip():
            try:
                dt_full = pd.to_datetime(row.get("date", ""), dayfirst=True, errors="coerce")
                if not pd.isna(dt_full):
                    df.at[idx, "report_month"] = RUS_MONTHS.get(dt_full.month, "")
                else:
                    df.at[idx, "report_month"] = ""
            except Exception:
                df.at[idx, "report_month"] = ""
                # --- ЕДИНОЕ НАЗНАЧЕНИЕ КАТЕГОРИИ/ГРУППЫ ПО firm_id КОНТРАГЕНТА ---
        # если категория ещё не назначена (не перетираем «эквайринг», «ЗП по реестру» и т.п.)
        if _safe_int(df.at[idx, "category_id"]) is None:
            op_type_l = str(df.at[idx, "operation_type"] or "").strip().lower()
            # выбираем чью фирму брать для категоризации
            if "списание" in op_type_l:
                chosen_cat_id = receiver_firm_category_id or payer_firm_category_id
            elif "поступление" in op_type_l:
                chosen_cat_id = payer_firm_category_id or receiver_firm_category_id
            else:
                chosen_cat_id = receiver_firm_category_id or payer_firm_category_id

            if chosen_cat_id:
                df.at[idx, "category_id"] = chosen_cat_id
                category_obj = find_category(chosen_cat_id, session)
                if category_obj and getattr(category_obj, "group_id", None) is not None:
                    df.at[idx, "group_id"] = category_obj.group_id

    # === Постпроход 1: консистентность category_id -> group_id ===
    for idx, row in df.iterrows():
        cat_id = _safe_int(row.get("category_id", ""))
        if cat_id is None:
            continue
        cat_obj = find_category(cat_id, session)
        if not cat_obj:
            continue
        wanted_group_id = cat_obj.group_id  # может быть None
        cur_group_id = _safe_int(row.get("group_id", ""))
        if wanted_group_id != cur_group_id:
            df.at[idx, "group_id"] = wanted_group_id if wanted_group_id is not None else ""

    # === Постпроход 2: автоназначение up_company_id по нашей компании (Company -> UpCompany) ===
    for idx, row in df.iterrows():
        op_type = str(row.get("operation_type", "")).strip().lower()
        payer_cid = _safe_int(row.get("payer_company_id", ""))
        receiver_cid = _safe_int(row.get("receiver_company_id", ""))

        # Выбираем "нашу" компанию по типу операции
        if "списание" in op_type:
            main_cid = payer_cid if payer_cid is not None else receiver_cid
        elif "поступление" in op_type:
            main_cid = receiver_cid if receiver_cid is not None else payer_cid
        else:
            main_cid = payer_cid if payer_cid is not None else receiver_cid

        up_id = None
        if main_cid is not None:
            comp = session.get(company_model.Company, main_cid)
            if comp and getattr(comp, "up_company_id", None):
                up_id = comp.up_company_id

        if up_id is not None:
            df.at[idx, "up_company_id"] = up_id
            # NEW: по умолчанию «за кого платили» = головная
            df.at[idx, "za_kogo_platili_id"] = up_id

    # === Постпроход 3: страховка по колонке «за кого платили» ===
    # если колонки нет или есть пропуски — подставляем из up_company_id
    if "za_kogo_platili_id" not in df.columns:
        df["za_kogo_platili_id"] = df.get("up_company_id")
    else:
        df["za_kogo_platili_id"] = df["za_kogo_platili_id"].where(
            pd.notna(df["za_kogo_platili_id"]) & (df["za_kogo_platili_id"] != ""),
            df.get("up_company_id")
        )

    # 5. Только нужные колонки в финале (по модели)
    df = df[statement_cols]

    # Вернём уже очищенные новые ИНН
    return df, sorted([inn for inn in new_inns if inn and inn != "nan"])
