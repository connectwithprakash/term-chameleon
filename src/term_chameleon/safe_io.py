from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import suppress
from datetime import datetime
from pathlib import Path


def unique_backup_path(path: str | Path) -> Path:
    source = Path(path)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S.%f")
    candidate = source.with_name(f"{source.name}.backup.{stamp}")
    counter = 1
    while candidate.exists():
        candidate = source.with_name(f"{source.name}.backup.{stamp}.{counter}")
        counter += 1
    return candidate


def backup_file(path: str | Path) -> Path:
    source = Path(path)
    backup = unique_backup_path(source)
    if source.exists():
        shutil.copy2(source, backup)
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
