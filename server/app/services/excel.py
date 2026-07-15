"""Parse a bulk-upload .xlsx into RequestCreate rows.

Expected headers (case-insensitive; extra columns ignored):
  Numbers | Duration Days | Case Officer | Justification | Request Date
`Numbers` may hold several values separated by comma / semicolon / newline.
"""

from __future__ import annotations

import io
import re
from datetime import date, datetime

from openpyxl import load_workbook

from ..schemas import RequestCreate

_HEADER_ALIASES = {
    "numbers": "numbers",
    "number": "numbers",
    "mobile": "numbers",
    "nic": "numbers",
    "duration days": "duration_days",
    "duration": "duration_days",
    "days": "duration_days",
    "case officer": "case_officer",
    "officer": "case_officer",
    "justification": "justification",
    "reason": "justification",
    "request date": "request_date",
    "date": "request_date",
}

_SPLIT_RE = re.compile(r"[,;\n]+")


def _to_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_excel(data: bytes) -> tuple[list[RequestCreate], list[str]]:
    rows: list[RequestCreate] = []
    errors: list[str] = []

    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.active
    header_cells = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if not header_cells:
        wb.close()
        return rows, ["Empty sheet"]

    col_map: dict[int, str] = {}
    for idx, cell in enumerate(header_cells):
        if cell is None:
            continue
        key = _HEADER_ALIASES.get(str(cell).strip().lower())
        if key:
            col_map[idx] = key

    if "numbers" not in col_map.values():
        wb.close()
        return rows, ["Missing required 'Numbers' column"]

    for row_no, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if row is None or all(c is None or c == "" for c in row):
            continue
        fields: dict = {}
        for idx, key in col_map.items():
            fields[key] = row[idx] if idx < len(row) else None

        raw_numbers = fields.get("numbers")
        numbers = (
            [n.strip() for n in _SPLIT_RE.split(str(raw_numbers)) if n.strip()]
            if raw_numbers is not None
            else []
        )
        if not numbers:
            errors.append(f"Row {row_no}: no numbers")
            continue

        duration = fields.get("duration_days")
        try:
            duration_days = int(duration) if duration not in (None, "") else None
        except (TypeError, ValueError):
            duration_days = None

        rows.append(
            RequestCreate(
                numbers=numbers,
                duration_days=duration_days,
                case_officer=str(fields.get("case_officer") or ""),
                justification=str(fields.get("justification") or ""),
                request_date=_to_date(fields.get("request_date")),
            )
        )

    wb.close()
    return rows, errors
