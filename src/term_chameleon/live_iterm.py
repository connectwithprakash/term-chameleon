from __future__ import annotations

from dataclasses import dataclass

from .iterm_api import setter_mappings
from .iterm_connection import DEFAULT_APPLY_TIMEOUT, run_iterm_bounded
from .presets import get_preset


@dataclass(frozen=True)
class LiveApplyResult:
    preset: str
    applied: bool
    setters: tuple[str, ...]
    message: str


def apply_preset_to_current_session(
    preset_name: str,
    *,
    timeout: float = DEFAULT_APPLY_TIMEOUT,
    background_override: str | None = None,
) -> LiveApplyResult:
    """Apply a preset to the current iTerm2 session-local profile.

    This mutates only the current session's LocalWriteOnlyProfile. It does not
    rewrite Dynamic Profile JSON or global iTerm2 preferences.

    *background_override* replaces the preset's background color with the given
    hex value. The real presets share a near-identical dark background and adapt
    via transparency, which is invisible on an opaque window; the demo cycle uses
    this override to make the switch obvious on screen. It is demo-only and never
    changes what the real presets apply.

    Runs the iterm2 websocket call on a daemon thread bounded by *timeout*
    seconds so a hung or unresponsive iTerm2 daemon never blocks the
    long-running watch loop.  Raises ``RuntimeError`` on timeout (the watch
    loop already catches RuntimeError and continues).  Also closes the asyncio
    event loop created by iterm2 after each call to prevent fd leaks in the
    multi-year watch daemon.
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
            if setter_name == "set_background_color" and background_override is not None:
                value = background_override
            maybe_set(change, setter_name, value)
        await session.async_set_profile_properties(change)

    # run_iterm_bounded drives iterm2.run_until_complete on a daemon thread
    # bounded by *timeout* and closes the event loop afterward (fd reclamation).
    try:
        run_iterm_bounded(main, timeout=timeout)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"iTerm2 live apply failed: {exc}") from exc

    if not applied_setters:
        raise RuntimeError(
            f"iTerm2 live apply set no properties for preset {preset_name!r}; "
            "LocalWriteOnlyProfile setters are missing — "
            "run `term-chameleon live` to check environment compatibility"
        )

    return LiveApplyResult(
        preset=preset_name,
        applied=True,
        setters=tuple(applied_setters),
        message=f"applied {preset_name} to current iTerm2 session-local profile",
    )
