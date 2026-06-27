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
        value = self.profile.get(key)
        if isinstance(value, dict):
            try:
                return Color.from_iterm_dict(value)
            except (ValueError, TypeError):
                return None
        return None

    def set_color(self, key: str, color: Color) -> None:
        self.profile[key] = color.to_iterm_dict()

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
    return Color.from_iterm_dict(value).to_hex()
