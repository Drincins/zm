# --- Нормализация знака суммы по типу операции ---
def normalize_operation_type(op: str) -> str:
    """Приводим тип к нижнему регистру без пробелов."""
    return str(op or "").strip().lower()

def normalize_amount_by_type(operation_type: str, amount):
    """
    Приводим знак суммы к типу операции:
    - 'списание'    -> отрицательное значение
    - 'поступление' -> положительное значение
    Поддержка float/Decimal/str ('12 345,67').
    Пустые/непарсимые значения возвращаем как есть.
    """
    if amount is None:
        return None
    try:
        if isinstance(amount, str):
            cleaned = amount.replace(" ", "").replace("\u00A0", "").replace(",", ".")
            val = float(cleaned)
        else:
            val = float(amount)
    except Exception:
        return amount  # оставляем как есть, если не смогли преобразовать

    op = normalize_operation_type(operation_type)
    if op == "списание":
        return -abs(val)
    if op == "поступление":
        return abs(val)
    return val
