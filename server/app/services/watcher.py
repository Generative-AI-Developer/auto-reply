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
from ..models import ResponseFile, Status
from . import parsers
from .archive import extract_archive, is_archive
from .matcher import find_matches
from .splitter import split_by_a_number
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


def _route_file(
    path: Path,
    numbers: set[str],
    file_date: date | None = None,
    *,
    move_unmatched: bool = True,
) -> list[str]:
    """Match one already-filtered file against Pending identifiers and distribute it."""
    routed: list[str] = []
    incoming_hash = _sha256(path)
    with SessionLocal() as db:
        matches = find_matches(db, numbers)
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
            # arrive; skip only when this identifier already holds a file with
            # identical content (an operator re-dropping the same file).
            if incoming_hash is not None and any(
                _sha256(Path(f.stored_path)) == incoming_hash for f in ident.files
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

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._handle(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._handle(event.dest_path)


def start_watcher() -> Observer:
    settings.ensure_dirs()
    observer = Observer()
    observer.schedule(_Handler(), str(settings.main_dir), recursive=False)
    observer.start()
    log.info("Watching %s", settings.main_dir)
    return observer
