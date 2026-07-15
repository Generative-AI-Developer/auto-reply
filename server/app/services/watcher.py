"""Watch the main folder's top level and route response files into the
permanent main/<user_id>/<request_id>/ tree.

Layout:
    main/<user_id>/                 created on Add User (permanent)
    main/<user_id>/<request_id>/    created on request submission (permanent)
A raw file dropped directly in main/ (top level) is the "inbox": wait until its
size is stable -> extract numbers+date -> find matching Pending requests -> move
(or copy, if several requests match) the file into each matched request's
folder, record a ResponseFile, flip status to Sent, broadcast. No match -> move
to the unmatched folder for the operator to review.

The observer watches main/ non-recursively, so writes into the nested
<user_id>/<request_id>/ folders never re-trigger processing.
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..config import get_settings
from ..database import SessionLocal
from ..models import ResponseFile, Status
from . import parsers
from .matcher import find_matches
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
    """Match and distribute one file. Returns the request_ids it was routed to."""
    path = Path(path)
    numbers, file_date = parsers.extract(path)
    log.info("Incoming %s -> numbers=%s date=%s", path.name, numbers, file_date)

    routed: list[str] = []
    with SessionLocal() as db:
        matches = find_matches(db, numbers, file_date)
        if not matches:
            settings.unmatched_dir.mkdir(parents=True, exist_ok=True)
            dest = _unique_dest(settings.unmatched_dir, path.name)
            shutil.move(str(path), str(dest))
            log.info("No match for %s -> moved to unmatched", path.name)
            return routed

        for req in matches:
            # Folder already exists (created eagerly at request-submission time).
            request_folder = Path(settings.main_dir) / req.owner.user_id / req.request_id
            request_folder.mkdir(parents=True, exist_ok=True)
            dest = _unique_dest(request_folder, path.name)
            shutil.copy2(str(path), str(dest))

            matched_value = next(
                (i.value for i in req.identifiers if i.value in numbers), ""
            )
            db.add(
                ResponseFile(
                    request_id=req.id,
                    original_filename=path.name,
                    stored_path=str(dest),
                    matched_value=matched_value,
                    matched_date=file_date,
                )
            )
            req.status = Status.SENT
            routed.append(req.request_id)

        db.commit()

        for req in matches:
            manager.broadcast_threadsafe(
                {
                    "event": "status_changed",
                    "request_id": req.request_id,
                    "status": Status.SENT,
                }
            )

    # Distributed to every owner; remove the original from the incoming folder.
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
