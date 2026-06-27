from __future__ import annotations

import math

from .color import Color


def contrast_ratio(foreground: Color, background: Color) -> float:
    """WCAG 2 contrast ratio.

    Both foreground and background are composited to opaque before computing
    luminance: foreground is blended over background, and background is blended
    over opaque black.  This ensures a translucent background does not produce a
    misleading ratio by having its alpha silently ignored.
    """
    opaque_black = Color(0.0, 0.0, 0.0, 1.0)
    bg = background.blend_over(opaque_black) if background.a < 1 else background
    fg = foreground.blend_over(bg) if foreground.a < 1 else foreground
    l1 = fg.relative_luminance()
    l2 = bg.relative_luminance()
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def format_ratio(value: float) -> str:
    """Format a contrast ratio for display, truncating toward the failing side.

    Uses floor-to-2-decimals so a failing ratio never displays as >= the
    threshold.  For example, 4.497 (which fails the 4.5:1 check) displays as
    ``4.49:1``, not ``4.50:1``.
    """
    truncated = math.floor(value * 100) / 100
    return f"{truncated:.2f}:1"
