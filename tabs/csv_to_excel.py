import pandas as pd

# === Source CSV and target Excel paths ===
CSV_PATH = r"C:\Users\Admin\Desktop\ZMB\data\reference_data\firms_mapping.csv"    # original csv
EXCEL_PATH = r"C:\Users\Admin\Desktop\ZMB\data\reference_data\firms_mapping.xlsx"


def fix_inn(val):
    """Normalises values that arrive as strings like '1234567890.0'."""
    try:
        if isinstance(val, str) and val.endswith('.0'):
            return str(int(float(val)))
    except Exception:
        pass
    return str(val)


def convert_csv_to_excel(csv_path: str = CSV_PATH, excel_path: str = EXCEL_PATH) -> None:
    """Loads the CSV, fixes INN column formatting, and writes an Excel copy."""
    df = pd.read_csv(csv_path, dtype=str)

    if '\u0418\u041d\u041d' in df.columns:  # 'ИНН'
        df['\u0418\u041d\u041d'] = df['\u0418\u041d\u041d'].apply(fix_inn)
    elif 'inn' in df.columns:
        df['inn'] = df['inn'].apply(fix_inn)

    df.to_excel(excel_path, index=False)
    print(f"Готово! CSV '{csv_path}' сконвертирован в Excel '{excel_path}'.")


if __name__ == '__main__':
    convert_csv_to_excel()
