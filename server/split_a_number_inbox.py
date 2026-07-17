"""Cron entry point: split raw CDR-style CSVs dropped in main/ by A Number.

Runs every minute (see crontab). For each *.csv directly under main/ (top
level only, matching what the app's own watcher scans) whose header includes
an "A Number" column: group rows by unique A Number, write one .xlsx file per
number (sheet "Sheet1", header row preserved) named
"<original_stem>_<A Number>.xlsx" back into main/, then delete the raw CSV.

The app's own inbox watcher (server/app/services/watcher.py) picks up each
resulting per-number .xlsx from main/ and routes it to the matching request
folder - this script only does the splitting step, nothing else.

A file still being written (size changing) is left alone and retried on the
next run. A file that fails to parse is logged and left in place rather than
deleted, so no data is lost; it will be retried on the next run too.
"""

from __future__ import annotations

import csv
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook

MAIN_DIR = Path(__file__).resolve().parent / "main"
LOCK_FILE = Path(__file__).resolve().parent / ".split_a_number_inbox.lock"
LOG_FILE = Path(__file__).resolve().parent / "split_a_number_inbox.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("split_a_number_inbox")


def _is_stable(path: Path, wait: float = 1.0) -> bool:
    try:
        size1 = path.stat().st_size
    except OSError:
        return False
    time.sleep(wait)
    try:
        size2 = path.stat().st_size
    except OSError:
        return False
    return size1 == size2 and size1 > 0


def _split_file(path: Path) -> None:
    with path.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            log.warning("Skipping empty file %s", path.name)
            return

        if "A Number" not in header:
            return  # not a CDR-style file we own; leave for other handling

        a_idx = header.index("A Number")
        groups: dict[str, list[list[str]]] = defaultdict(list)
        for row in reader:
            if len(row) <= a_idx:
                continue
            groups[row[a_idx]].append(row)

    if not groups:
        log.warning("No data rows with A Number in %s", path.name)
        return

    written: list[Path] = []
    for number, rows in groups.items():
        wb = Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        ws.append(header)
        for row in rows:
            ws.append(row)
        out_path = MAIN_DIR / f"{path.stem}_{number}.xlsx"
        wb.save(out_path)
        written.append(out_path)

    path.unlink()
    log.info(
        "Split %s into %d file(s): %s",
        path.name,
        len(written),
        ", ".join(p.name for p in written),
    )


def main() -> None:
    if not MAIN_DIR.is_dir():
        log.error("main dir %s does not exist", MAIN_DIR)
        return

    for path in sorted(MAIN_DIR.glob("*.csv")):
        if not path.is_file():
            continue
        if not _is_stable(path):
            log.info("Skipping %s: not stable yet", path.name)
            continue
        try:
            _split_file(path)
        except Exception:
            log.exception("Failed to process %s", path.name)


if __name__ == "__main__":
    import fcntl

    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)  # another run is still in progress
    try:
        main()
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
