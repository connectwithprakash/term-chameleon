from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .color import Color
from .safe_io import atomic_write_text


@dataclass
class ItermProfile:
    path: Path | None
    document: dict[str, Any]
    profile: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.profile.get("Name", "<unnamed>"))

    @property
    def guid(self) -> str | None:
        value = self.profile.get("Guid")
        return str(value) if value is not None else None

    @property
    def background(self) -> Color | None:
        return self.color("Background Color")

    @property
    def foreground(self) -> Color | None:
        return self.color("Foreground Color")

    def color(self, key: str) -> Color | None:
        """Return Color if key is present and parseable, None if key is absent.

        When the key is present but the dict is malformed, still returns None
        so callers don't raise, but `is_color_malformed` can distinguish the case.
        """
        value = self.profile.get(key)
        if isinstance(value, dict):
            try:
                return Color.from_iterm_dict(value)
            except (ValueError, TypeError):
                return None
        return None

    def is_color_malformed(self, key: str) -> bool:
        """Return True when the color key is present as a dict but unparseable.

        Distinguishes 'key absent' (False) from 'key present but corrupt' (True).
        """
        value = self.profile.get(key)
        if not isinstance(value, dict):
            return False
        try:
            Color.from_iterm_dict(value)
            return False
        except (ValueError, TypeError):
            return True

    def minimum_contrast(self) -> float | None:
        """Return Minimum Contrast as a float, or None if absent or malformed."""
        value = self.profile.get("Minimum Contrast")
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def is_minimum_contrast_malformed(self) -> bool:
        """Return True when Minimum Contrast is present but not coercible to float."""
        value = self.profile.get("Minimum Contrast")
        if value is None:
            return False
        try:
            float(value)
            return False
        except (TypeError, ValueError):
            return True

    def transparency(self) -> float | None:
        """Return Transparency as a float, or None if absent or malformed."""
        value = self.profile.get("Transparency")
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def is_transparency_malformed(self) -> bool:
        """Return True when Transparency is present but not coercible to float."""
        value = self.profile.get("Transparency")
        if value is None:
            return False
        try:
            float(value)
            return False
        except (TypeError, ValueError):
            return True

    def write(self, path: Path | None = None) -> None:
        """Serialise the profile document and write it atomically to *path*.

        ``atomic_write_text`` guarantees the target file is never half-written
        (it uses ``os.replace`` which is atomic on POSIX), but it does **not**
        provide mutual exclusion across the full read-modify-write span.  Two
        concurrent write commands that both read the same baseline and then each
        call ``write()`` will produce a lost-update: the second ``os.replace``
        silently overwrites the first writer's changes.

        This is intentional for the single-daemon usage model: the watch daemon
        applies changes via the iTerm2 live API (not by rewriting this file), so
        concurrent file writes from multiple CLI invocations on the same path are
        an edge case that the caller is responsible for avoiding.  If future
        multi-writer scenarios arise, add ``fcntl.flock`` or an equivalent
        per-file advisory lock around the read-modify-write span in the caller.
        """
        target = path or self.path
        if target is None:
            raise ValueError("no path supplied")
        atomic_write_text(target, dumps_document(self.document))


def loads_document(text: str, path: Path | None = None) -> ItermProfile:
    document = json.loads(text)
    if not isinstance(document, dict):
        raise ValueError(
            f"iTerm2 Dynamic Profile JSON root must be an object, got {type(document).__name__}"
        )
    profiles = document.get("Profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("iTerm2 Dynamic Profile JSON must contain non-empty Profiles list")
    if len(profiles) != 1:
        raise ValueError(
            "this MVP intentionally supports exactly one profile per Dynamic Profile JSON; "
            f"found {len(profiles)} profiles"
        )
    profile = profiles[0]
    if not isinstance(profile, dict):
        raise ValueError("first profile must be an object")
    return ItermProfile(path=path, document=document, profile=profile)


def load_profile(path: str | Path) -> ItermProfile:
    p = Path(path)
    return loads_document(p.read_text(encoding="utf-8"), p)


def dumps_document(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def color_hex(profile: dict[str, Any], key: str) -> str | None:
    value = profile.get(key)
    if not isinstance(value, dict):
        return None
    try:
        return Color.from_iterm_dict(value).to_hex()
    except (ValueError, TypeError):
        return None
