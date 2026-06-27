from __future__ import annotations

import threading
from dataclasses import dataclass

DEFAULT_PROBE_TIMEOUT = 10.0


@dataclass(frozen=True)
class ItermConnectionProbe:
    connected: bool
    message: str


def probe_iterm_connection(*, timeout: float = DEFAULT_PROBE_TIMEOUT) -> ItermConnectionProbe:
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

    # iterm2.run_until_complete drives its own event loop with no timeout, so an
    # unresponsive daemon would block the CLI forever. Run it on a daemon thread
    # and bound the wait; a timed-out thread is left to die with the process.
    result: dict[str, ItermConnectionProbe] = {}

    def run() -> None:
        try:
            message = iterm2.run_until_complete(main)
        except SystemExit as exc:
            result["probe"] = ItermConnectionProbe(
                False, f"iTerm2 connection probe exited with status {exc.code}"
            )
        except Exception as exc:
            result["probe"] = ItermConnectionProbe(False, str(exc).strip())
        else:
            result["probe"] = ItermConnectionProbe(True, str(message))

    worker = threading.Thread(target=run, name="iterm-connection-probe", daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        return ItermConnectionProbe(
            False, f"iTerm2 connection probe timed out after {timeout:g}s"
        )
    return result.get(
        "probe", ItermConnectionProbe(False, "iTerm2 connection probe produced no result")
    )
