from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .contrast import contrast_ratio, format_ratio
from .iterm_profile import ItermProfile
from .presets import COLOR_FIELD_MAP

Severity = Literal["ok", "info", "warn", "fail"]


@dataclass(frozen=True)
class Diagnostic:
    severity: Severity
    code: str
    message: str
    detail: str
    suggestion: str | None = None


FAIL = "fail"
WARN = "warn"
INFO = "info"


def diagnose(profile: ItermProfile) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    p = profile.profile
    bg = profile.color("Background Color")
    fg = profile.color("Foreground Color")

    if not profile.guid:
        diagnostics.append(
            Diagnostic(
                FAIL,
                "MISSING_GUID",
                "Profile has no Guid",
                "Dynamic Profiles require a stable Guid.",
            )
        )
    if profile.name == "<unnamed>":
        diagnostics.append(
            Diagnostic(
                FAIL,
                "MISSING_NAME",
                "Profile has no Name",
                "Dynamic Profiles require a Name.",
            )
        )

    separate = p.get("Use Separate Colors for Light and Dark Mode")
    drift_keys = []
    for base_key in COLOR_FIELD_MAP:
        base = profile.color(base_key)
        if base is None:
            continue
        for suffix in [" (Light)", " (Dark)"]:
            variant = profile.color(base_key + suffix)
            if variant is not None and variant.to_hex() != base.to_hex():
                drift_keys.append(f"{base_key}{suffix}: {variant.to_hex()} != {base.to_hex()}")
    if separate is True or drift_keys:
        diagnostics.append(
            Diagnostic(
                FAIL,
                "ITERM_LIGHT_DARK_DRIFT",
                "Light/Dark color variants can override the intended palette",
                "; ".join(drift_keys) if drift_keys else "Separate Light/Dark colors are enabled.",
                "Disable separate Light/Dark colors or pin variants to the base palette.",
            )
        )

    if bg and fg:
        _check_pair(diagnostics, "LOW_FOREGROUND_CONTRAST", "Foreground", fg, bg, 4.5)
    bold = profile.color("Bold Color")
    if bg and bold:
        _check_pair(diagnostics, "LOW_BOLD_CONTRAST", "Bold", bold, bg, 4.5)
    ansi0 = profile.color("Ansi 0 Color")
    if bg and ansi0:
        _check_pair(diagnostics, "LOW_ANSI_BLACK_CONTRAST", "ANSI black", ansi0, bg, 3.0)
    ansi8 = profile.color("Ansi 8 Color")
    if bg and ansi8:
        _check_pair(
            diagnostics,
            "LOW_ANSI_BRIGHT_BLACK_CONTRAST",
            "ANSI bright black",
            ansi8,
            bg,
            3.0,
        )
    ansi7 = profile.color("Ansi 7 Color")
    if bg and ansi7:
        _check_pair(diagnostics, "LOW_ANSI_WHITE_CONTRAST", "ANSI white", ansi7, bg, 4.5)
    ansi15 = profile.color("Ansi 15 Color")
    if bg and ansi15:
        _check_pair(
            diagnostics,
            "LOW_ANSI_BRIGHT_WHITE_CONTRAST",
            "ANSI bright white",
            ansi15,
            bg,
            4.5,
        )

    selection = profile.color("Selection Color")
    selected = profile.color("Selected Text Color")
    if selection and selected:
        _check_pair(
            diagnostics,
            "LOW_SELECTION_CONTRAST",
            "Selected text",
            selected,
            selection,
            3.0,
        )

    transparency = profile.transparency()
    if transparency is not None and transparency > 0.10:
        diagnostics.append(
            Diagnostic(
                WARN,
                "HIGH_TRANSPARENCY_RISK",
                f"Transparency {transparency:.2f} may wash out over bright backgrounds",
                "Transparent terminals blend with wallpaper/windows, so static theme contrast "
                "may not match perceived contrast.",
                "For balanced glass, start around 0.08; dynamic mode can reduce transparency "
                "over bright backgrounds.",
            )
        )

    minimum = profile.minimum_contrast()
    if minimum is None:
        diagnostics.append(
            Diagnostic(
                WARN,
                "MISSING_MINIMUM_CONTRAST",
                "Minimum Contrast is not set",
                "iTerm2 can shift low-contrast foreground colors toward black/white for "
                "readability.",
                "Set Minimum Contrast around 0.35 for balanced translucent dark profiles.",
            )
        )
    elif minimum < 0.25:
        diagnostics.append(
            Diagnostic(
                WARN,
                "LOW_MINIMUM_CONTRAST",
                f"Minimum Contrast {minimum:.2f} may be too low for glassy profiles",
                "Dim and ANSI colors may become unreadable when transparency changes the "
                "effective background.",
                "Try 0.35 as a balanced starting point.",
            )
        )
    elif minimum > 0.60:
        diagnostics.append(
            Diagnostic(
                WARN,
                "HIGH_MINIMUM_CONTRAST",
                f"Minimum Contrast {minimum:.2f} may distort theme colors",
                "Very high minimum contrast can force text toward pure black/white.",
                "Use high values for accessibility/presentation modes, not balanced mode.",
            )
        )

    return diagnostics


def _check_pair(
    diagnostics: list[Diagnostic],
    code: str,
    label: str,
    foreground,
    background,
    threshold: float,
) -> None:
    ratio = contrast_ratio(foreground, background)
    if ratio < threshold:
        diagnostics.append(
            Diagnostic(
                FAIL if threshold >= 4.5 else WARN,
                code,
                f"{label} contrast is low ({format_ratio(ratio)} < {threshold:.1f}:1)",
                f"{label} {foreground.to_hex()} against background {background.to_hex()} "
                "is below the target threshold.",
                "Adjust luminance, use the balanced preset, or reduce transparency if the "
                "effective background is bright.",
            )
        )
