from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path

from .presets import Preset, get_preset
from .safe_io import atomic_write_text

ITERM_APP_PATHS = [Path("/Applications/iTerm.app"), Path.home() / "Applications" / "iTerm.app"]


@dataclass(frozen=True)
class ItermApiEnvironment:
    app_installed: bool
    python_package_available: bool
    app_paths_checked: tuple[str, ...]
    python_executable: str
    missing_setters: tuple[str, ...] = ()

    @property
    def ready_for_live_probe(self) -> bool:
        return self.app_installed and self.python_package_available and not self.missing_setters


def check_environment() -> ItermApiEnvironment:
    package_available = importlib.util.find_spec("iterm2") is not None
    return ItermApiEnvironment(
        app_installed=any(path.exists() for path in ITERM_APP_PATHS),
        python_package_available=package_available,
        app_paths_checked=tuple(str(path) for path in ITERM_APP_PATHS),
        python_executable=sys.executable,
        missing_setters=missing_live_adapter_setters() if package_available else (),
    )


def live_adapter_script(*, preset_name: str = "balanced") -> str:
    preset = get_preset(preset_name)
    color_assignments = _color_assignment_lines(preset)
    return f'''#!/usr/bin/env python3
"""Generated Term Chameleon iTerm2 live-adapter probe.

This script is intentionally conservative:
- It updates only the current session's local profile copy.
- It does not rewrite Dynamic Profile JSON or com.googlecode.iterm2.plist.
- It feature-detects LocalWriteOnlyProfile setter names before calling them.
"""

import iterm2

PRESET_NAME = {preset_name!r}


def color(hex_value):
    hex_value = hex_value.lstrip("#")
    return iterm2.Color(int(hex_value[0:2], 16), int(hex_value[2:4], 16), int(hex_value[4:6], 16))


def maybe_set(change, setter_name, value):
    setter = getattr(change, setter_name, None)
    if setter is None:
        print(f"missing LocalWriteOnlyProfile.{{setter_name}}")
        return False
    setter(value)
    print(f"set {{setter_name}}")
    return True


async def main(connection):
    app = await iterm2.async_get_app(connection)
    window = app.current_terminal_window
    if window is None or window.current_tab is None or window.current_tab.current_session is None:
        print("no current iTerm2 session")
        return
    session = window.current_tab.current_session
    change = iterm2.LocalWriteOnlyProfile()
{color_assignments}
    await session.async_set_profile_properties(change)
    print(f"applied Term Chameleon preset {{PRESET_NAME}} to current session-local profile")


iterm2.run_until_complete(main)
'''


def write_live_adapter_script(path: str | Path, *, preset_name: str = "balanced") -> Path:
    target = Path(path)
    content = live_adapter_script(preset_name=preset_name)
    compile(content, str(target), "exec")
    atomic_write_text(target, content)
    target.chmod(0o755)
    return target


def live_adapter_setters() -> tuple[str, ...]:
    return tuple(setter for setter, _value in setter_mappings(get_preset("balanced")))


def missing_live_adapter_setters() -> tuple[str, ...]:
    import iterm2  # type: ignore[import-not-found]

    change = iterm2.LocalWriteOnlyProfile()
    return tuple(
        setter for setter in live_adapter_setters() if getattr(change, setter, None) is None
    )


def _color_assignment_lines(preset: Preset) -> str:
    lines = []
    for setter, value in setter_mappings(preset):
        if isinstance(value, str):
            lines.append(f'    maybe_set(change, "{setter}", color("{value}"))')
        else:
            lines.append(f'    maybe_set(change, "{setter}", {value!r})')
    return "\n".join(lines)


def setter_mappings(preset: Preset) -> list[tuple[str, str | float | bool]]:
    return [
        # Disable Light/Dark-mode splitting first so the base-color setters below
        # are the ones iTerm2 actually renders.  Mirrors the profile-dict path in
        # apply_preset_to_profile_dict (presets.py), which sets
        # "Use Separate Colors for Light and Dark Mode" = False for the same reason.
        ("set_use_separate_colors_for_light_and_dark_mode", False),
        ("set_background_color", preset.background.to_hex()),
        ("set_foreground_color", preset.foreground.to_hex()),
        ("set_bold_color", preset.bold.to_hex()),
        ("set_cursor_color", preset.cursor.to_hex()),
        ("set_selection_color", preset.selection.to_hex()),
        ("set_selected_text_color", preset.selected_text.to_hex()),
        ("set_ansi_0_color", preset.ansi_black.to_hex()),
        ("set_ansi_7_color", preset.ansi_white.to_hex()),
        ("set_ansi_8_color", preset.ansi_bright_black.to_hex()),
        ("set_ansi_15_color", preset.ansi_bright_white.to_hex()),
        ("set_transparency", preset.transparency),
        ("set_blur", preset.blur),
        ("set_blur_radius", preset.blur_radius),
        ("set_minimum_contrast", preset.minimum_contrast),
        (
            "set_only_the_default_bg_color_uses_transparency",
            preset.only_default_bg_transparent,
        ),
    ]
