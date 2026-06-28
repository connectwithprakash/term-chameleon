from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import suppress
from datetime import datetime
from pathlib import Path

# Maximum number of timestamped backups kept alongside each source file.
# Older backups beyond this limit are pruned (best-effort) after a new backup is created.
MAX_BACKUPS: int = 5


def unique_backup_path(path: str | Path, *, dest_dir: Path | None = None) -> Path:
    source = Path(path)
    parent = dest_dir if dest_dir is not None else source.parent
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S.%f")
    candidate = parent / f"{source.name}.backup.{stamp}"
    counter = 1
    while candidate.exists():
        candidate = parent / f"{source.name}.backup.{stamp}.{counter}"
        counter += 1
    return candidate


def _prune_backups(source: Path, keep: int = MAX_BACKUPS, *, dest_dir: Path | None = None) -> None:
    """Remove the oldest `<name>.backup.*` files, keeping the *keep* most recent.

    Collects (path, mtime) pairs inside a per-file try/except so that a
    concurrent pruner that already unlinked a globbed path does not raise
    FileNotFoundError (mirrors the race-safe pattern in _prune_artifacts).
    """
    parent = dest_dir if dest_dir is not None else source.parent
    pairs: list[tuple[float, Path]] = []
    for p in parent.glob(f"{source.name}.backup.*"):
        # File may vanish between glob and stat (concurrent pruner); skip it.
        with suppress(OSError):
            pairs.append((p.stat().st_mtime, p))
    pairs.sort(key=lambda t: t[0])
    existing = [p for _, p in pairs]
    for old in existing[:-keep] if keep > 0 else existing:
        with suppress(OSError):
            old.unlink()


def backup_file(path: str | Path, keep: int = MAX_BACKUPS, *, dest_dir: Path | None = None) -> Path:
    """Copy *path* to a timestamped backup and prune older backups beyond *keep*.

    By default the backup is a sibling of *path*. Pass *dest_dir* to place
    backups elsewhere — e.g. so a backup of a file inside a directory that another
    program scans (the iTerm2 AutoLaunch folder) does not land back in that folder.
    """
    source = Path(path)
    if dest_dir is not None:
        dest_dir.mkdir(parents=True, exist_ok=True)
    backup = unique_backup_path(source, dest_dir=dest_dir)
    if source.exists():
        shutil.copy2(source, backup)
    _prune_backups(source, keep=keep, dest_dir=dest_dir)
    return backup


def atomic_write_text(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    tmp = Path(tmp_name)
    success = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            # fsync is a best-effort durability hint; not all filesystems support it.
            with suppress(OSError):
                os.fsync(handle.fileno())
        tmp.replace(target)
        success = True
    finally:
        # On any failure path (exception or abnormal exit) best-effort remove
        # the temp file so the target directory is not littered with orphans.
        # On success tmp was already atomically renamed to target; the unlink
        # is a no-op that raises OSError which suppress() silences.
        if not success:
            with suppress(OSError):
                tmp.unlink(missing_ok=True)
