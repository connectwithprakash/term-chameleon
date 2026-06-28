from __future__ import annotations

from dataclasses import dataclass

from .color import Color


@dataclass(frozen=True)
class Preset:
    name: str
    background: Color
    foreground: Color
    bold: Color
    cursor: Color
    selection: Color
    selected_text: Color
    ansi_black: Color
    ansi_bright_black: Color
    ansi_white: Color
    ansi_bright_white: Color
    transparency: float
    blur: bool
    blur_radius: int
    minimum_contrast: float
    # Keep empty space glassy while colored (non-default-bg) cells render opaque,
    # so a bright/colored backdrop cannot bleed through a colored cell and bury its
    # text. Part of the worst-case-background readability strategy.
    only_default_bg_transparent: bool = True

    def as_legacy_dict(self) -> dict[str, object]:
        return {
            "background": self.background,
            "foreground": self.foreground,
            "bold": self.bold,
            "cursor": self.cursor,
            "selection": self.selection,
            "selected_text": self.selected_text,
            "ansi_black": self.ansi_black,
            "ansi_bright_black": self.ansi_bright_black,
            "ansi_white": self.ansi_white,
            "ansi_bright_white": self.ansi_bright_white,
            "transparency": self.transparency,
            "blur": self.blur,
            "blur_radius": self.blur_radius,
            "minimum_contrast": self.minimum_contrast,
            "only_default_bg_transparent": self.only_default_bg_transparent,
        }


PRESETS: dict[str, Preset] = {
    "dark-glass": Preset(
        name="dark-glass",
        background=Color.from_hex("#090C16"),
        foreground=Color.from_hex("#E5EBF5"),
        bold=Color.from_hex("#E5EBF5"),
        cursor=Color.from_hex("#939FFB"),
        selection=Color.from_hex("#31394F"),
        selected_text=Color.from_hex("#E5EBF5"),
        ansi_black=Color.from_hex("#6B7280"),
        ansi_bright_black=Color.from_hex("#9CA3AF"),
        ansi_white=Color.from_hex("#C7CDD8"),
        ansi_bright_white=Color.from_hex("#F8FAFC"),
        transparency=0.10,
        blur=True,
        blur_radius=18,
        minimum_contrast=0.30,
    ),
    "balanced": Preset(
        name="balanced",
        background=Color.from_hex("#090C16"),
        foreground=Color.from_hex("#E5EBF5"),
        bold=Color.from_hex("#E5EBF5"),
        cursor=Color.from_hex("#939FFB"),
        selection=Color.from_hex("#31394F"),
        selected_text=Color.from_hex("#E5EBF5"),
        ansi_black=Color.from_hex("#6B7280"),
        ansi_bright_black=Color.from_hex("#9CA3AF"),
        ansi_white=Color.from_hex("#C7CDD8"),
        ansi_bright_white=Color.from_hex("#F8FAFC"),
        transparency=0.08,
        blur=True,
        blur_radius=18,
        minimum_contrast=0.35,
    ),
    "bright-safe": Preset(
        name="bright-safe",
        background=Color.from_hex("#090C16"),
        foreground=Color.from_hex("#F1F5F9"),
        bold=Color.from_hex("#F8FAFC"),
        cursor=Color.from_hex("#A5B4FC"),
        selection=Color.from_hex("#334155"),
        selected_text=Color.from_hex("#F8FAFC"),
        ansi_black=Color.from_hex("#94A3B8"),
        ansi_bright_black=Color.from_hex("#CBD5E1"),
        ansi_white=Color.from_hex("#E2E8F0"),
        ansi_bright_white=Color.from_hex("#FFFFFF"),
        transparency=0.04,
        blur=True,
        blur_radius=22,
        minimum_contrast=0.45,
    ),
    "high-variance-safe": Preset(
        name="high-variance-safe",
        background=Color.from_hex("#090C16"),
        foreground=Color.from_hex("#F1F5F9"),
        bold=Color.from_hex("#FFFFFF"),
        cursor=Color.from_hex("#A5B4FC"),
        selection=Color.from_hex("#334155"),
        selected_text=Color.from_hex("#FFFFFF"),
        ansi_black=Color.from_hex("#94A3B8"),
        ansi_bright_black=Color.from_hex("#CBD5E1"),
        ansi_white=Color.from_hex("#E2E8F0"),
        ansi_bright_white=Color.from_hex("#FFFFFF"),
        transparency=0.05,
        blur=True,
        blur_radius=24,
        minimum_contrast=0.45,
    ),
    "presentation": Preset(
        name="presentation",
        background=Color.from_hex("#090C16"),
        foreground=Color.from_hex("#F8FAFC"),
        bold=Color.from_hex("#FFFFFF"),
        cursor=Color.from_hex("#A5B4FC"),
        selection=Color.from_hex("#334155"),
        selected_text=Color.from_hex("#FFFFFF"),
        ansi_black=Color.from_hex("#94A3B8"),
        ansi_bright_black=Color.from_hex("#CBD5E1"),
        ansi_white=Color.from_hex("#E2E8F0"),
        ansi_bright_white=Color.from_hex("#FFFFFF"),
        transparency=0.00,
        blur=False,
        blur_radius=0,
        minimum_contrast=0.45,
    ),
    "accessibility": Preset(
        name="accessibility",
        background=Color.from_hex("#050814"),
        foreground=Color.from_hex("#FFFFFF"),
        bold=Color.from_hex("#FFFFFF"),
        cursor=Color.from_hex("#FFFFFF"),
        selection=Color.from_hex("#1E3A8A"),
        selected_text=Color.from_hex("#FFFFFF"),
        ansi_black=Color.from_hex("#CBD5E1"),
        ansi_bright_black=Color.from_hex("#E2E8F0"),
        ansi_white=Color.from_hex("#F8FAFC"),
        ansi_bright_white=Color.from_hex("#FFFFFF"),
        transparency=0.00,
        blur=False,
        blur_radius=0,
        minimum_contrast=0.55,
    ),
}

# The glassiness ladder: presets ordered most-translucent -> most-opaque. Each rung
# trades transparency for readability headroom — as transparency drops, minimum
# contrast rises and blur increases — so the watcher can step toward opacity exactly
# as far as a brighter/colliding backdrop demands and no further. This ordering is
# the auditable spine of the worst-case-background strategy; the invariant that
# transparency is non-increasing while minimum-contrast is non-decreasing across the
# ladder is enforced by tests.
GLASSINESS_LADDER: tuple[str, ...] = (
    "dark-glass",
    "balanced",
    "high-variance-safe",
    "bright-safe",
    "presentation",
    "accessibility",
)

BALANCED = PRESETS["balanced"].as_legacy_dict()
COLOR_FIELD_MAP = {
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


def get_preset(name: str) -> Preset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        known = ", ".join(sorted(PRESETS))
        raise ValueError(f"unknown preset {name!r}; known presets: {known}") from exc


def apply_preset_to_profile_dict(profile: dict, preset: Preset) -> None:
    profile["Use Separate Colors for Light and Dark Mode"] = False
    for field, attr in COLOR_FIELD_MAP.items():
        color = getattr(preset, attr)
        profile[field] = color.to_iterm_dict()
        profile[field + " (Light)"] = color.to_iterm_dict()
        profile[field + " (Dark)"] = color.to_iterm_dict()
    profile["Transparency"] = preset.transparency
    profile["Blur"] = preset.blur
    profile["Blur Radius"] = preset.blur_radius
    profile["Minimum Contrast"] = preset.minimum_contrast
    profile["Only The Default BG Color Uses Transparency"] = preset.only_default_bg_transparent
