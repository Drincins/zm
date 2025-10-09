"""Вспомогательные структуры и функции для работы с русскими названиями месяцев."""

from __future__ import annotations

from typing import Optional

# Список названий месяцев с января по декабрь.
RU_MONTHS = [
    "\u042f\u043d\u0432\u0430\u0440\u044c",
    "\u0424\u0435\u0432\u0440\u0430\u043b\u044c",
    "\u041c\u0430\u0440\u0442",
    "\u0410\u043f\u0440\u0435\u043b\u044c",
    "\u041c\u0430\u0439",
    "\u0418\u044e\u043d\u044c",
    "\u0418\u044e\u043b\u044c",
    "\u0410\u0432\u0433\u0443\u0441\u0442",
    "\u0421\u0435\u043d\u0442\u044f\u0431\u0440\u044c",
    "\u041e\u043a\u0442\u044f\u0431\u0440\u044c",
    "\u041d\u043e\u044f\u0431\u0440\u044c",
    "\u0414\u0435\u043a\u0430\u0431\u0440\u044c",
]

# Словарь для быстрого доступа по индексу (1..12).
RU_MONTHS_MAP = {idx + 1: name for idx, name in enumerate(RU_MONTHS)}


def ru_month_name(month_number: int) -> str:
    """Возвращает название месяца по его номеру (1-12)."""
    return RU_MONTHS_MAP.get(month_number, "")


def ru_label_from_rm(report_month: str) -> str:
    """Преобразует 'YYYY-MM' в строку вида 'Месяц YYYY'."""
    if not report_month or len(report_month) != 7 or "-" not in report_month:
        return report_month or ""
    year, month = report_month.split("-", 1)
    try:
        month_index = int(month)
    except ValueError:
        return report_month
    month_name = ru_month_name(month_index)
    return f"{month_name} {year}" if month_name else report_month


def rm_from_ru_label(label: str) -> Optional[str]:
    """Преобразует строку вида 'Месяц YYYY' обратно в 'YYYY-MM'."""
    if not label:
        return None
    parts = label.strip().rsplit(" ", 1)
    if len(parts) != 2:
        return None
    month_name, year = parts
    try:
        month_index = RU_MONTHS.index(month_name) + 1
        year_int = int(year)
    except (ValueError, IndexError):
        return None
    return f"{year_int:04d}-{month_index:02d}"
