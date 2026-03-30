from __future__ import annotations

# --- Нормализация знака суммы по типу операции ---
def normalize_operation_type(op: str) -> str:
    """Приводим тип к нижнему регистру без пробелов."""
    return str(op or "").strip().lower()


def canonical_operation_type(op: str | None) -> str | None:
    """Приводим тип операции к единому виду для хранения в БД."""
    normalized = normalize_operation_type(op)
    if not normalized:
        return None
    if normalized == "списание":
        return "Списание"
    if normalized == "поступление":
        return "Поступление"
    return str(op).strip() or None


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
