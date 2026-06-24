from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .diagnostics import diagnose
from .iterm_profile import ItermProfile, dumps_document, load_profile
from .presets import BALANCED


@dataclass(frozen=True)
class Change:
    key: str
    before: str
    after: str
    reason: str


def apply_balanced_fix(profile: ItermProfile) -> list[Change]:
    p = profile.profile
    changes: list[Change] = []

    def set_value(key: str, after, reason: str) -> None:
        before = p.get(key, "<unset>")
        if before != after:
            p[key] = after
            changes.append(Change(key, _format_value(before), _format_value(after), reason))

    def set_color(key: str, color_key: str, reason: str) -> None:
        after = BALANCED[color_key].to_iterm_dict()
        before = p.get(key, "<unset>")
        if before != after:
            p[key] = after
            changes.append(Change(key, _format_value(before), BALANCED[color_key].to_hex(), reason))

    set_value(
        "Use Separate Colors for Light and Dark Mode",
        False,
        "Prevent macOS/iTerm2 Light Mode variants from overriding the dark glass palette.",
    )
    color_map = {
        "Background Color": "background",
        "Foreground Color": "foreground",
        "Bold Color": "bold",
        "Cursor Color": "cursor",
        "Selection Color": "selection",
        "Selected Text Color": "selected_text",
        "Ansi 0 Color": "ansi_black",
        "Ansi 7 Color": "ansi_white",
        "Ansi 8 Color": "ansi_bright_black",
        "Ansi 15 Color": "ansi_bright_white",
    }
    for key, color_key in color_map.items():
        set_color(key, color_key, "Apply balanced dark-glass readable palette.")
        set_color(key + " (Light)", color_key, "Pin Light variant to the same palette.")
        set_color(key + " (Dark)", color_key, "Pin Dark variant to the same palette.")

    set_value("Transparency", BALANCED["transparency"], "Use visible but safer glass transparency.")
    set_value("Blur", BALANCED["blur"], "Enable blur to reduce high-frequency background noise.")
    set_value(
        "Blur Radius",
        BALANCED["blur_radius"],
        "Use balanced blur for readability and aesthetics.",
    )
    set_value(
        "Minimum Contrast",
        BALANCED["minimum_contrast"],
        "Let iTerm2 rescue low-contrast foreground colors.",
    )
    return changes


def fix_file(path: str | Path, *, dry_run: bool, yes: bool) -> tuple[list[Change], list]:
    profile = load_profile(path)
    changes = apply_balanced_fix(profile)
    remaining = diagnose(profile)
    if dry_run:
        return changes, remaining
    if not yes:
        raise ValueError("refusing to write without --yes or --dry-run")
    p = Path(path)
    backup = p.with_name(p.name + ".backup." + datetime.now().strftime("%Y%m%dT%H%M%S"))
    shutil.copy2(p, backup)
    p.write_text(dumps_document(profile.document), encoding="utf-8")
    return changes, remaining


def _format_value(value) -> str:
    if isinstance(value, dict):
        try:
            from .color import Color

            return Color.from_iterm_dict(value).to_hex()
        except Exception:
            return "<color>"
    return repr(value)
