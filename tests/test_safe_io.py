from unittest.mock import patch

import pytest

from term_chameleon.safe_io import atomic_write_text, backup_file, unique_backup_path


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
