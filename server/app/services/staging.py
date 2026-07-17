"""Shared staging location used by the inbox pipeline (splitter, archive
extraction) for intermediate files that must not be visible to the inbox
watcher.

main/'s watcher is non-recursive (`observer.schedule(..., recursive=False)`),
so anything written under main/.staging/ is invisible to it - a file that
ends up there with no further action needed (e.g. an A-Number split with no
Pending match) can be left in place without the watcher picking it up a
second time as if it were a brand new incoming file.

Always resolved relative to settings.main_dir itself (not the parent of
whatever file is currently being processed), so nested processing - e.g. a
CSV pulled out of a just-extracted .zip - lands in the same single staging
folder instead of accumulating nested ".staging/.staging/" directories.
"""

from __future__ import annotations

from pathlib import Path

from ..config import get_settings

_DIRNAME = ".staging"


def staging_dir() -> Path:
    settings = get_settings()
    d = Path(settings.main_dir) / _DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d
