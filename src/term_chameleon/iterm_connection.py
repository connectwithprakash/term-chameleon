from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ItermConnectionProbe:
    connected: bool
    message: str


def probe_iterm_connection() -> ItermConnectionProbe:
    try:
        import iterm2  # type: ignore[import-not-found]
    except Exception as exc:
        return ItermConnectionProbe(False, f"iterm2 package import failed: {exc}")

    async def main(connection):
        app = await iterm2.async_get_app(connection)
        window = app.current_terminal_window
        if window is None:
            return "connected to iTerm2 Python API; no current terminal window"
        return "connected to iTerm2 Python API; current terminal window is available"

    try:
        message = iterm2.run_until_complete(main)
    except SystemExit as exc:
        return ItermConnectionProbe(False, f"iTerm2 connection probe exited with status {exc.code}")
    except Exception as exc:
        return ItermConnectionProbe(False, str(exc).strip())
    return ItermConnectionProbe(True, str(message))
