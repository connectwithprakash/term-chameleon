from __future__ import annotations

from .color import Color

BALANCED = {
    "background": Color.from_hex("#090C16"),
    "foreground": Color.from_hex("#E5EBF5"),
    "bold": Color.from_hex("#E5EBF5"),
    "cursor": Color.from_hex("#939FFB"),
    "selection": Color.from_hex("#31394F"),
    "selected_text": Color.from_hex("#E5EBF5"),
    "ansi_black": Color.from_hex("#6B7280"),
    "ansi_bright_black": Color.from_hex("#9CA3AF"),
    "ansi_white": Color.from_hex("#C7CDD8"),
    "ansi_bright_white": Color.from_hex("#F8FAFC"),
    "transparency": 0.08,
    "blur": True,
    "blur_radius": 18,
    "minimum_contrast": 0.35,
}
