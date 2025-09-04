import pandas as pd

# === Укажи пути к своим файлам ===
csv_path = "C:\Users\Admin\Desktop\ZMB\data\reference_data\firms_mapping.csv"    # исходный csv
excel_path = "C:\Users\Admin\Desktop\ZMB\data\reference_data\firms_mapping.xlsx" 
# === Загружаем CSV ===
df = pd.read_csv(csv_path, dtype=str)

# === Опционально: поправим ИНН, если они выглядят как float ===
def fix_inn(val):
    # Если это число и оканчивается на .0 — привести к целому
    try:
        if isinstance(val, str) and val.endswith('.0'):
            return str(int(float(val)))
    except:
        pass
    return str(val)

if "ИНН" in df.columns:
    df["ИНН"] = df["ИНН"].apply(fix_inn)
elif "inn" in df.columns:
    df["inn"] = df["inn"].apply(fix_inn)

# === Сохраняем в Excel (XLSX) ===
df.to_excel(excel_path, index=False)

print(f"Готово! CSV '{csv_path}' преобразован в Excel '{excel_path}'.")

