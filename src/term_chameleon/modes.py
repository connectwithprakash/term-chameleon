from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .diagnostics import diagnose
from .install import PROFILE_BACKUP_DIR
from .iterm_profile import dumps_document, load_profile
from .presets import apply_preset_to_profile_dict, get_preset
from .safe_io import atomic_write_text, backup_file


@dataclass(frozen=True)
class ModeChange:
    key: str
    before: str
    after: str


def apply_mode(
    path: str | Path, mode: str, *, dry_run: bool, yes: bool
) -> tuple[list[ModeChange], list]:
    profile = load_profile(path)
    profile_dict = profile.profile
    before = dict(profile_dict)
    apply_preset_to_profile_dict(profile_dict, get_preset(mode))
    changes = [
        _diff_value(key, before.get(key, "<unset>"), profile_dict[key])
        for key in sorted(profile_dict)
        if before.get(key) != profile_dict[key]
    ]
    remaining = diagnose(profile)
    if dry_run:
        return changes, remaining
    if not yes:
        raise ValueError("refusing to write without --yes or --dry-run")
    target = Path(path)
    backup_file(target, dest_dir=PROFILE_BACKUP_DIR)
    atomic_write_text(target, dumps_document(profile.document))
    return changes, remaining


def _diff_value(key: str, before, after) -> ModeChange:
    return ModeChange(key=key, before=_fmt(before), after=_fmt(after))


def _fmt(value) -> str:
    if isinstance(value, dict):
        from .color import Color

        try:
            return Color.from_iterm_dict(value).to_hex()
        except (KeyError, ValueError, TypeError):
            return "<color>"
    return repr(value)
