"""Extract .zip / .rar archives dropped in the inbox before anything else
runs on their contents. Uses the system `7z` binary (p7zip), which reads both
formats - no extra Python dependency needed.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .staging import staging_dir

log = logging.getLogger("autoreply.archive")

ARCHIVE_SUFFIXES = {".zip", ".rar"}


def is_archive(path: Path) -> bool:
    return path.suffix.lower() in ARCHIVE_SUFFIXES


def extract_archive(path: Path) -> list[Path] | None:
    """Extracts `path` into a dedicated folder under main/.staging/ and
    returns the flat list of extracted file paths (nested folders inside the
    archive are walked, not returned as entries themselves).

    Returns None if `path` isn't a .zip/.rar, or if extraction fails (corrupt
    archive, wrong password, unsupported compression) - caller should treat
    that the same as any other file 7z couldn't make sense of.
    """
    if not is_archive(path):
        return None

    dest = staging_dir() / f"{path.stem}_extracted"
    dest.mkdir(exist_ok=True)

    result = subprocess.run(
        ["7z", "x", "-y", f"-o{dest}", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log.warning("Failed to extract %s: %s", path.name, result.stderr.strip())
        return None

    extracted = [p for p in dest.rglob("*") if p.is_file()]
    if not extracted:
        log.warning("Archive %s extracted no files", path.name)
        return None

    return extracted
