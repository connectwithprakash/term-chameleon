from __future__ import annotations

from .color import Color


def contrast_ratio(foreground: Color, background: Color) -> float:
    """WCAG 2 contrast ratio."""
    fg = foreground.blend_over(background) if foreground.a < 1 else foreground
    bg = background
    l1 = fg.relative_luminance()
    l2 = bg.relative_luminance()
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def format_ratio(value: float) -> str:
    return f"{value:.2f}:1"
