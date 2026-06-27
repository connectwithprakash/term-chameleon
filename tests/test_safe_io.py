import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from term_chameleon.safe_io import (
    MAX_BACKUPS,
    _prune_backups,
    atomic_write_text,
    backup_file,
    unique_backup_path,
)


def test_atomic_write_text_creates_file(tmp_path):
    target = tmp_path / "out.json"
    atomic_write_text(target, '{"hello": true}')
    assert target.read_text(encoding="utf-8") == '{"hello": true}'


def test_atomic_write_text_overwrites_existing(tmp_path):
    target = tmp_path / "out.json"
    target.write_text("old", encoding="utf-8")
    atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_atomic_write_text_creates_parent_dirs(tmp_path):
    target = tmp_path / "nested" / "dir" / "out.json"
    atomic_write_text(target, "deep")
    assert target.read_text(encoding="utf-8") == "deep"


def test_atomic_write_text_cleans_up_temp_on_failure(tmp_path):
    target = tmp_path / "out.json"
    original_error = OSError("disk full")

    with patch("os.fdopen", side_effect=original_error), pytest.raises(OSError):
        atomic_write_text(target, "content")

    assert not target.exists()
    temp_files = list(tmp_path.glob(".*.tmp"))
    assert len(temp_files) == 0


def test_unique_backup_path_includes_timestamp(tmp_path):
    source = tmp_path / "profile.json"
    backup = unique_backup_path(source)
    assert backup.name.startswith("profile.json.backup.")
    assert backup != source


def test_unique_backup_path_avoids_collision(tmp_path):
    source = tmp_path / "profile.json"
    first = unique_backup_path(source)
    first.touch()
    second = unique_backup_path(source)
    assert first != second


def test_backup_file_copies_existing(tmp_path):
    source = tmp_path / "profile.json"
    source.write_text("data", encoding="utf-8")
    backup = backup_file(source)
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == "data"
    assert backup != source


def test_backup_file_returns_path_for_missing_source(tmp_path):
    source = tmp_path / "nonexistent.json"
    backup = backup_file(source)
    assert not backup.exists()


def test_atomic_write_text_fsync_oserror_does_not_abort_write(tmp_path):
    """fsync failing with OSError (e.g. unsupported filesystem) must not abort the write."""
    target = tmp_path / "out.json"
    with patch("os.fsync", side_effect=OSError("fsync not supported")):
        atomic_write_text(target, "content")
    assert target.read_text(encoding="utf-8") == "content"


def test_atomic_write_text_original_exception_preserved_when_cleanup_fails(tmp_path):
    """When the write fails and tmp.unlink() also raises, the original write error propagates."""
    target = tmp_path / "out.json"
    original_error = OSError("disk full")

    mock_path = MagicMock()
    mock_path.parent = tmp_path
    mock_path.name = "out.json"
    mock_path.__str__ = lambda self: str(target)

    # Simulate: fdopen succeeds, but something else raises original_error,
    # and tmp.unlink() itself raises PermissionError.
    with patch("os.fdopen", side_effect=original_error), pytest.raises(OSError) as exc_info:
        atomic_write_text(target, "content")

    # The raised exception must be the original disk-full error, not a cleanup error.
    assert exc_info.value is original_error


def test_atomic_write_text_suppress_broadened_to_oserror(tmp_path):
    """cleanup suppress(OSError) catches PermissionError so the original error propagates."""
    target = tmp_path / "out.json"
    original_error = OSError("disk full")
    cleanup_error = PermissionError("cannot unlink temp")

    # Patch os.fdopen to raise, then patch Path.unlink to also raise
    with (
        patch("os.fdopen", side_effect=original_error),
        patch("pathlib.Path.unlink", side_effect=cleanup_error),
        pytest.raises(OSError) as exc_info,
    ):
        atomic_write_text(target, "content")

    # The original error must be re-raised, not the cleanup PermissionError
    assert exc_info.value is original_error


# ---------------------------------------------------------------------------
# backup_file — retention / pruning
# ---------------------------------------------------------------------------


def test_backup_file_prunes_old_backups_beyond_keep(tmp_path):
    """backup_file must prune backups older than the *keep* most recent."""
    source = tmp_path / "profile.json"
    source.write_text("v0", encoding="utf-8")

    keep = 3
    # Create keep+2 backups; each needs a distinct mtime, so sleep briefly between calls.
    for i in range(keep + 2):
        source.write_text(f"v{i}", encoding="utf-8")
        backup_file(source, keep=keep)
        # Ensure distinct mtime on the next backup by advancing a little.
        time.sleep(0.01)

    backups = sorted(tmp_path.glob("profile.json.backup.*"))
    assert len(backups) == keep, f"expected {keep} backups, got {len(backups)}: {backups}"


def test_backup_file_keep_zero_removes_all_backups(tmp_path):
    """keep=0 must delete all backups (no retention)."""
    source = tmp_path / "profile.json"
    source.write_text("data", encoding="utf-8")

    # Create two backups first so there is something to prune.
    backup_file(source, keep=5)
    time.sleep(0.01)
    backup_file(source, keep=0)

    backups = list(tmp_path.glob("profile.json.backup.*"))
    assert backups == [], f"expected no backups with keep=0, got {backups}"


def test_backup_file_keep_default_matches_max_backups_constant(tmp_path):
    """Default keep uses the exported MAX_BACKUPS constant."""
    source = tmp_path / "profile.json"
    source.write_text("data", encoding="utf-8")

    # Create MAX_BACKUPS + 1 backups.
    for i in range(MAX_BACKUPS + 1):
        source.write_text(f"v{i}", encoding="utf-8")
        backup_file(source)
        time.sleep(0.01)

    backups = list(tmp_path.glob("profile.json.backup.*"))
    assert len(backups) == MAX_BACKUPS


def test_backup_file_prune_tolerates_already_deleted_backups(tmp_path):
    """_prune_backups must not raise even if a backup file was already removed externally."""
    source = tmp_path / "profile.json"
    source.write_text("data", encoding="utf-8")

    # Create one backup, then manually remove it to simulate a race / external deletion.
    bp = backup_file(source, keep=5)
    bp.unlink()

    # Second call should not raise even though the first backup no longer exists.
    backup_file(source, keep=5)  # should not raise


# ---------------------------------------------------------------------------
# _prune_backups — concurrent pruner race (stat-after-glob window)
# ---------------------------------------------------------------------------


def test_prune_backups_tolerates_concurrent_deletion(tmp_path):
    """_prune_backups must not raise FileNotFoundError when a concurrent pruner
    deletes a globbed backup between the glob and the stat() call.

    This tests the R4-concurrency-io fix: (path, mtime) pairs are collected
    inside a per-file try/except so vanished files are silently skipped.
    """
    source = tmp_path / "profile.json"
    source.write_text("data", encoding="utf-8")

    # Create several backup files so glob has results to iterate over.
    backups = []
    for _ in range(5):
        bp = backup_file(source, keep=100)
        backups.append(bp)
        time.sleep(0.01)

    # Simulate the race by pre-deleting all backup files so that when
    # _prune_backups calls glob() the files appear to exist (glob is mocked to
    # return the list) but stat() raises FileNotFoundError (they are gone).
    for bp in backups:
        bp.unlink()

    # Patch glob to return the already-deleted paths so _prune_backups tries to
    # stat them, simulating the window between glob and stat.
    deleted_paths = list(backups)

    errors: list[Exception] = []

    def patched_glob(self, pattern):
        # Return deleted paths only for the backup glob pattern.
        if ".backup." in pattern:
            return iter(deleted_paths)
        return iter([])

    import pathlib

    with patch.object(pathlib.Path, "glob", patched_glob):
        try:
            _prune_backups(source, keep=3)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    assert errors == [], f"_prune_backups raised during stat-after-glob race: {errors}"


def test_prune_backups_concurrent_threads_do_not_raise(tmp_path):
    """Multiple threads pruning the same backup set concurrently must not raise."""
    source = tmp_path / "profile.json"
    source.write_text("data", encoding="utf-8")

    # Pre-populate backups so all threads have something to prune.
    for _ in range(8):
        backup_file(source, keep=100)
        time.sleep(0.005)

    errors: list[Exception] = []
    lock = threading.Lock()

    def run():
        try:
            _prune_backups(source, keep=2)
        except Exception as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"concurrent _prune_backups raised: {errors}"


# ---------------------------------------------------------------------------
# atomic_write_text — orphaned .tmp cleanup on failure
# ---------------------------------------------------------------------------


def test_atomic_write_text_no_orphan_on_write_failure(tmp_path):
    """No .tmp file must remain in the directory after a write failure."""
    target = tmp_path / "profile.json"

    with patch("os.fdopen", side_effect=OSError("disk full")), pytest.raises(OSError):
        atomic_write_text(target, "content")

    orphans = list(tmp_path.glob(".profile.json.*.tmp"))
    assert orphans == [], f"orphaned .tmp files remain after write failure: {orphans}"
