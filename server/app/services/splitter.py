"""Split a CDR-style CSV (one with an "A Number" column) into one .xlsx file
per unique A Number, so a request only ever receives the rows about its own
number - never the raw multi-number file.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook

from .staging import staging_dir


def split_by_a_number(path: Path) -> list[tuple[Path, str]] | None:
    """Returns [(per-number .xlsx path, A Number), ...] written into
    main/.staging/ (see staging.py), or None if `path` isn't this CDR format
    (no "A Number" column) - caller should fall back to routing the original
    file as-is.
    """
    if path.suffix.lower() != ".csv":
        return None

    with path.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return None
        if "A Number" not in header:
            return None

        idx = header.index("A Number")
        groups: dict[str, list[list[str]]] = defaultdict(list)
        for row in reader:
            if len(row) > idx:
                groups[row[idx]].append(row)

    if not groups:
        return None

    out_dir = staging_dir()

    written: list[tuple[Path, str]] = []
    for number, rows in groups.items():
        wb = Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(header)
        for row in rows:
            ws.append(row)
        out_path = out_dir / f"{path.stem}_{number}.xlsx"
        wb.save(out_path)
        written.append((out_path, number))

    return written
