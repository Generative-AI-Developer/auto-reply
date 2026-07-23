"""Watch the main folder's top level and route response files into the
permanent main/<user_id>/<request_number-or-request_id>/ tree.

Layout:
    main/<user_id>/                                 created on Add User (permanent)
    main/<user_id>/<request_number, or request_id>/  created on request submission (permanent)
A raw file dropped directly in main/ (top level) is the "inbox": wait until its
size is stable -> if it's a .zip/.rar archive, extract it FIRST and process
each extracted file the same way (recursively, so an extracted archive-of-an-
archive or CSV is handled too) -> if it's a CDR-style CSV (has an "A Number"
column), split it into one .xlsx per A Number, so each request only ever
receives its own filtered rows, never the raw multi-number file -> for each
resulting file (or the original file, if it wasn't split): extract
numbers+date -> find matching Pending numbers (each number tracks its own
status) -> copy the file into each matched number's request folder, record a
ResponseFile against that number, flip only that number's status to Sent,
broadcast. No match -> move to the unmatched folder for the operator to
review.

The observer watches main/ non-recursively, so writes into the nested
<user_id>/<request_id>/ folders never re-trigger processing.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import time
from datetime import date
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..config import get_settings
from ..database import SessionLocal
from ..models import RequestIdentifier, ResponseFile, Status
from . import parsers
from .archive import extract_archive, is_archive
from .formats import CDR, IMEI, UFONE, ZONG, norm_network, norm_type
from .matcher import find_matches
from .response_formats import detect_imei_operator, imei_column_values
from .splitter import split_by_a_number, split_by_column
from .ws_manager import manager

log = logging.getLogger("autoreply.watcher")
settings = get_settings()


def _wait_stable(path: Path, tries: int = 10, interval: float = 0.4) -> bool:
    """Return True once the file size stops changing (fully written)."""
    last = -1
    for _ in range(tries):
        try:
            size = path.stat().st_size
        except OSError:
            return False
        if size == last and size > 0:
            return True
        last = size
        time.sleep(interval)
    return path.exists()


def _dir_signature(path: Path) -> tuple[int, int]:
    """(file count, total bytes) of a folder tree - used to detect a copy in progress."""
    count = total = 0
    for p in path.rglob("*"):
        if p.is_file():
            count += 1
            try:
                total += p.stat().st_size
            except OSError:
                pass
    return count, total


def _wait_stable_dir(path: Path, tries: int = 20, interval: float = 0.5) -> bool:
    """Return True once the folder's contents stop changing (copy finished)."""
    last: tuple[int, int] | None = None
    for _ in range(tries):
        if not path.exists():
            return False
        sig = _dir_signature(path)
        if sig == last:
            return True
        last = sig
        time.sleep(interval)
    return path.exists()


def _sha256(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _unique_dest(folder: Path, filename: str) -> Path:
    dest = folder / filename
    if not dest.exists():
        return dest
    stem, suffix = Path(filename).stem, Path(filename).suffix
    i = 1
    while (folder / f"{stem}_{i}{suffix}").exists():
        i += 1
    return folder / f"{stem}_{i}{suffix}"


def process_incoming_file(path: Path) -> list[str]:
    """Extract, filter, then distribute. Returns the request_ids the file(s) were routed to."""
    path = Path(path)

    if is_archive(path):
        extracted = extract_archive(path)
        path.unlink(missing_ok=True)
        if extracted is None:
            log.warning("Could not extract %s (corrupt or unsupported archive)", path.name)
            return []
        log.info(
            "Extracted %s into %d file(s): %s",
            path.name,
            len(extracted),
            ", ".join(p.name for p in extracted),
        )
        routed: list[str] = []
        for extracted_path in extracted:
            routed.extend(process_incoming_file(extracted_path))
        return routed

    # An operator reply is recognised by its header row and routed straight to
    # that operator's records. This must run before split_by_a_number: the Ufone
    # reply carries an "A Number" column and would otherwise be mistaken for a
    # generic CDR file and split by A-Number for every network.
    operator = detect_imei_operator(path)
    if operator == UFONE:
        # Ufone returns IMEI and CDR results in one file with identical columns.
        # Which column identifies a row is driven by our request's type: an IMEI
        # request matches the IMEI column, a CDR request the A Number column.
        return _route_operator_split(path, UFONE, [(["IMEI"], IMEI), (["A Number"], CDR)])
    if operator == ZONG:
        # Zong IMEI replies arrive in bulk: split per IMEI so each request folder
        # receives only its own rows.
        return _route_operator_split(path, ZONG, [(["IMEI"], IMEI)])
    if operator is not None:
        # Telenor / Mobilink: routed whole-file to the operator's IMEI record.
        numbers, file_date = parsers.extract(path)
        # Ensure the IMEI itself is in the match set: the generic extractor
        # returns only the "A Number" column on some replies, masking the IMEI.
        numbers |= imei_column_values(path)
        log.info("Incoming IMEI reply %s -> operator=%s numbers=%s", path.name, operator, numbers)
        return _route_file(path, numbers, file_date, operator=operator, request_type=IMEI)

    split_files = split_by_a_number(path)
    if split_files is not None:
        path.unlink(missing_ok=True)
        log.info(
            "Filtered %s into %d file(s) by A Number: %s",
            path.name,
            len(split_files),
            ", ".join(p.name for p, _ in split_files),
        )
        routed: list[str] = []
        for split_path, a_number in split_files:
            # A filtered-by-A-Number file with no Pending request for that
            # number takes no action: it stays in main/<...>/.staging/, not
            # unmatched/ - unlike an arbitrary unrecognized incoming file,
            # it's already known to be a single clean number with nothing
            # currently asking for it, so there's nothing for an operator to
            # triage yet.
            routed.extend(_route_file(split_path, {a_number}, move_unmatched=False))
        return routed

    numbers, file_date = parsers.extract(path)
    log.info("Incoming %s -> numbers=%s date=%s", path.name, numbers, file_date)
    return _route_file(path, numbers, file_date)


def _route_operator_split(
    path: Path, operator: str, specs: list[tuple[list[str], str]]
) -> list[str]:
    """Split a bulk/combined operator reply into per-record filtered files and
    route each to the matching operator+type record.

    `specs` pairs the column(s) to filter on with the request type those rows
    belong to (e.g. IMEI column -> IMEI records, A Number column -> CDR records).
    A recognised header whose expected columns are all absent falls back to
    whole-file routing so nothing is silently dropped.
    """
    routed: list[str] = []
    split_any = False
    for column_names, rtype in specs:
        splits = split_by_column(path, column_names)
        if not splits:
            continue
        split_any = True
        log.info(
            "Filtered %s into %d %s file(s) by %s",
            path.name, len(splits), rtype.upper(), "/".join(column_names),
        )
        for split_path, value in splits:
            routed.extend(_route_file(
                split_path, {value}, operator=operator, request_type=rtype, move_unmatched=False,
            ))
    if split_any:
        path.unlink(missing_ok=True)
    else:
        numbers, file_date = parsers.extract(path)
        numbers |= imei_column_values(path)
        routed.extend(_route_file(path, numbers, file_date, operator=operator))
    return routed


def _accepts(
    ident: RequestIdentifier,
    operator: str | None,
    file_date: date | None,
    request_type: str | None,
) -> bool:
    """Whether a value-matched identifier should actually receive this file.

    A single number can back several sibling records (per-operator IMEI rows, or
    two Telenor CDR date windows) that all match on value; this narrows the file
    to the sibling it really belongs to:
      - operator reply (detected from the header): only that operator's records,
        and when a `request_type` is given only records of that type (so a Ufone
        file's IMEI-column split reaches IMEI records, its A Number-column split
        reaches CDR records).
      - Telenor CDR split window (date_from/date_to set): only the window whose
        range contains the file's date. With no date we can't tell the windows
        apart, so both take it (nothing is lost).
      - anything else: unchanged - every value match receives the file.
    """
    if operator is not None:
        if norm_network(ident.network) != operator:
            return False
        return request_type is None or norm_type(ident.request_type) == request_type
    if ident.date_from and ident.date_to and file_date is not None:
        return ident.date_from <= file_date <= ident.date_to
    return True


def _route_file(
    path: Path,
    numbers: set[str],
    file_date: date | None = None,
    *,
    move_unmatched: bool = True,
    operator: str | None = None,
    request_type: str | None = None,
) -> list[str]:
    """Match one already-filtered file against Pending identifiers and distribute it."""
    routed: list[str] = []
    incoming_hash = _sha256(path)
    with SessionLocal() as db:
        matches = [i for i in find_matches(db, numbers) if _accepts(i, operator, file_date, request_type)]
        if not matches:
            if move_unmatched:
                settings.unmatched_dir.mkdir(parents=True, exist_ok=True)
                dest = _unique_dest(settings.unmatched_dir, path.name)
                shutil.move(str(path), str(dest))
                log.info("No match for %s -> moved to unmatched", path.name)
            else:
                log.info("No pending request for %s -> left in place, no action taken", path.name)
            return routed

        for ident in matches:
            req = ident.request
            # Sent/Awaited numbers keep matching so multi-part responses all
            # arrive; skip only when this identifier already holds the *same
            # filename* with identical content (an operator re-dropping the
            # exact same file). Different extensions/names for the same number
            # are distinct files and are all kept, even if their bytes match.
            if incoming_hash is not None and any(
                f.original_filename == path.name
                and _sha256(Path(f.stored_path)) == incoming_hash
                for f in ident.files
            ):
                log.info(
                    "Duplicate of %s already delivered to %s / %s -> skipped",
                    path.name,
                    req.request_id,
                    ident.value,
                )
                routed.append(req.request_id)
                continue
            # Folder already exists (created eagerly at request-submission time).
            # Named after request_number when the request has one, else request_id
            # (legacy requests created before request_number existed).
            folder_name = req.request_number or req.request_id
            request_folder = Path(settings.main_dir) / req.owner.user_id / folder_name
            request_folder.mkdir(parents=True, exist_ok=True)
            dest = _unique_dest(request_folder, path.name)
            shutil.copy2(str(path), str(dest))

            db.add(
                ResponseFile(
                    identifier_id=ident.id,
                    original_filename=path.name,
                    stored_path=str(dest),
                    matched_date=file_date,
                )
            )
            ident.status = Status.SENT
            routed.append(req.request_id)

        db.commit()

        for ident in matches:
            manager.broadcast_threadsafe(
                {
                    "event": "status_changed",
                    "request_id": ident.request.request_id,
                    "number": ident.value,
                    "status": ident.status,
                }
            )

    # Distributed to every match; remove the original from the incoming folder.
    try:
        path.unlink(missing_ok=True)
    except OSError:
        log.warning("Could not remove original %s after routing", path)

    log.info("Routed %s to %s", path.name, routed)
    return routed


def process_incoming_folder(path: Path) -> list[str]:
    """Route a whole folder by its NAME, without inspecting its contents.

    A folder dropped in main/ whose name matches an IMEI / NIC / mobile of a
    pending request is moved wholesale into that request's folder - never opened,
    split, or de-duplicated file-by-file. Numbers/date come from the name only.
    """
    path = Path(path)
    numbers = parsers.extract_numbers_from_text(parsers._strip_dates(path.name))
    file_date = parsers.extract_date_from_text(path.name)
    log.info("Incoming folder %s -> numbers=%s date=%s", path.name, numbers, file_date)

    routed: list[str] = []
    with SessionLocal() as db:
        matches = find_matches(db, numbers)
        if not matches:
            # Not a number we're waiting on (also the case for user folders like
            # main/<user_id>/): leave it untouched, take no action.
            log.info("No pending request for folder %s -> left in place", path.name)
            return routed

        for ident in matches:
            req = ident.request
            folder_name = req.request_number or req.request_id
            request_folder = Path(settings.main_dir) / req.owner.user_id / folder_name
            request_folder.mkdir(parents=True, exist_ok=True)
            dest = _unique_dest(request_folder, path.name)
            shutil.copytree(str(path), str(dest))
            db.add(
                ResponseFile(
                    identifier_id=ident.id,
                    original_filename=path.name,
                    stored_path=str(dest),
                    matched_date=file_date,
                )
            )
            ident.status = Status.SENT
            routed.append(req.request_id)

        db.commit()
        for ident in matches:
            manager.broadcast_threadsafe(
                {
                    "event": "status_changed",
                    "request_id": ident.request.request_id,
                    "number": ident.value,
                    "status": ident.status,
                }
            )

    # Copied into every matched request folder; remove the original drop.
    shutil.rmtree(path, ignore_errors=True)
    log.info("Routed folder %s to %s", path.name, routed)
    return routed


class _Handler(FileSystemEventHandler):
    def _handle(self, path_str: str) -> None:
        path = Path(path_str)
        if path.is_dir():
            return
        # Only handle files dropped directly at the top level of main_dir; the
        # non-recursive schedule already guarantees this, this is a defensive check.
        if path.parent.resolve() != Path(settings.main_dir).resolve():
            return
        if not _wait_stable(path):
            return
        try:
            process_incoming_file(path)
        except Exception:
            log.exception("Failed to process %s", path)

    def _handle_dir(self, path_str: str) -> None:
        path = Path(path_str)
        if not path.is_dir():
            return
        # Only top-level folders dropped directly in main/ (skip .staging and
        # any dotfolder). Nested folders are never watched (non-recursive).
        if path.parent.resolve() != Path(settings.main_dir).resolve():
            return
        if path.name.startswith("."):
            return
        if not _wait_stable_dir(path):
            return
        try:
            process_incoming_folder(path)
        except Exception:
            log.exception("Failed to process folder %s", path)

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            self._handle_dir(event.src_path)
        else:
            self._handle(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            self._handle_dir(event.dest_path)
        else:
            self._handle(event.dest_path)


def start_watcher() -> Observer:
    settings.ensure_dirs()
    observer = Observer()
    observer.schedule(_Handler(), str(settings.main_dir), recursive=False)
    observer.start()
    log.info("Watching %s", settings.main_dir)
    return observer
