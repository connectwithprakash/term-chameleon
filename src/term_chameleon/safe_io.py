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


def unique_backup_path(path: str | Path) -> Path:
    source = Path(path)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S.%f")
    candidate = source.with_name(f"{source.name}.backup.{stamp}")
    counter = 1
    while candidate.exists():
        candidate = source.with_name(f"{source.name}.backup.{stamp}.{counter}")
        counter += 1
    return candidate


def _prune_backups(source: Path, keep: int = MAX_BACKUPS) -> None:
    """Remove the oldest `<name>.backup.*` files, keeping the *keep* most recent."""
    existing = sorted(
        source.parent.glob(f"{source.name}.backup.*"),
        key=lambda p: p.stat().st_mtime,
    )
    for old in existing[:-keep] if keep > 0 else existing:
        with suppress(OSError):
            old.unlink()


def backup_file(path: str | Path, keep: int = MAX_BACKUPS) -> Path:
    """Copy *path* to a timestamped backup and prune older backups beyond *keep*."""
    source = Path(path)
    backup = unique_backup_path(source)
    if source.exists():
        shutil.copy2(source, backup)
    _prune_backups(source, keep=keep)
    return backup


def atomic_write_text(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            # fsync is a best-effort durability hint; not all filesystems support it.
            with suppress(OSError):
                os.fsync(handle.fileno())
        tmp.replace(target)
    except Exception:
        with suppress(OSError):
            tmp.unlink()
        raise
