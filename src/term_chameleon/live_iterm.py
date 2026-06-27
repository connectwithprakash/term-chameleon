from __future__ import annotations

from dataclasses import dataclass

from .iterm_api import setter_mappings
from .presets import get_preset


@dataclass(frozen=True)
class LiveApplyResult:
    preset: str
    applied: bool
    setters: tuple[str, ...]
    message: str


def apply_preset_to_current_session(preset_name: str) -> LiveApplyResult:
    """Apply a preset to the current iTerm2 session-local profile.

    This mutates only the current session's LocalWriteOnlyProfile. It does not
    rewrite Dynamic Profile JSON or global iTerm2 preferences.
    """
    try:
        import iterm2  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError(f"iterm2 package import failed: {exc}") from exc

    preset = get_preset(preset_name)
    applied_setters: list[str] = []

    def color(hex_value: str):
        hex_value = hex_value.lstrip("#")
        return iterm2.Color(
            int(hex_value[0:2], 16),
            int(hex_value[2:4], 16),
            int(hex_value[4:6], 16),
        )

    def maybe_set(change, setter_name: str, value: str | float | bool) -> None:
        setter = getattr(change, setter_name, None)
        if setter is None:
            return
        setter(color(value) if isinstance(value, str) else value)
        applied_setters.append(setter_name)

    async def main(connection) -> None:
        app = await iterm2.async_get_app(connection)
        window = app.current_terminal_window
        if (
            window is None
            or window.current_tab is None
            or window.current_tab.current_session is None
        ):
            raise RuntimeError("no current iTerm2 session")
        session = window.current_tab.current_session
        change = iterm2.LocalWriteOnlyProfile()
        for setter_name, value in setter_mappings(preset):
            maybe_set(change, setter_name, value)
        await session.async_set_profile_properties(change)

    try:
        iterm2.run_until_complete(main)
    except SystemExit as exc:
        raise RuntimeError(f"iTerm2 connection exited with status {exc.code}") from exc
    except Exception as exc:
        raise RuntimeError(f"iTerm2 live apply failed: {exc}") from exc

    return LiveApplyResult(
        preset=preset_name,
        applied=True,
        setters=tuple(applied_setters),
        message=f"applied {preset_name} to current iTerm2 session-local profile",
    )
