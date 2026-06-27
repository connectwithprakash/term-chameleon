from __future__ import annotations

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
    return f"{value:.2f}:1"
