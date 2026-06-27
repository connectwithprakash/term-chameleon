from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .color import Color
from .safe_io import atomic_write_text

COLOR_KEYS = [
    "Background Color",
    "Foreground Color",
    "Bold Color",
    "Cursor Color",
    "Selection Color",
    "Selected Text Color",
    "Ansi 0 Color",
    "Ansi 7 Color",
    "Ansi 8 Color",
    "Ansi 15 Color",
]

VARIANT_SUFFIXES = [" (Light)", " (Dark)"]


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

    def set_color(self, key: str, color: Color) -> None:
        """Write color into the profile, preserving Color Space and any unknown keys.

        If the profile already contains a dict for ``key``, unknown keys (such
        as the original "Color Space" value and any iTerm-specific extras) are
        kept intact so that round-tripping a P3/wide-gamut profile does not
        silently reinterpret the component values under a different gamut.
        """
        existing = self.profile.get(key)
        base: dict[str, object] = dict(existing) if isinstance(existing, dict) else {}
        # Merge only the four numeric component keys; let the existing Color Space
        # and any other iTerm-specific keys remain unchanged.
        new_dict = color.to_iterm_dict()
        component_keys = ("Red Component", "Green Component", "Blue Component", "Alpha Component")
        for k in component_keys:
            base[k] = new_dict[k]
        # For a new key with no prior dict, include the Color Space from to_iterm_dict.
        if "Color Space" not in base:
            base["Color Space"] = new_dict["Color Space"]
        self.profile[key] = base

    def minimum_contrast(self) -> float | None:
        value = self.profile.get("Minimum Contrast")
        return float(value) if value is not None else None

    def transparency(self) -> float | None:
        value = self.profile.get("Transparency")
        return float(value) if value is not None else None

    def write(self, path: Path | None = None) -> None:
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
