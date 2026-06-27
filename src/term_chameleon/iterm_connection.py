from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

DEFAULT_PROBE_TIMEOUT = 10.0
DEFAULT_APPLY_TIMEOUT = 15.0

# Lock that serializes run_iterm_bounded callers so that at most one worker
# thread is active at a time.  When a previous worker timed out and was
# abandoned, the next caller must wait for the lock rather than launching a
# second concurrent worker.  This prevents two failure modes:
#
# 1. Thread/fd accumulation: abandoned workers hold asyncio selector fds until
#    their finally block eventually runs.  Serializing ensures at most one
#    abandoned worker exists at any moment.
#
# 2. Stale out-of-order applies: an abandoned worker that completes after the
#    watch loop has moved on would silently overwrite the current session mode.
#    Serializing means the next apply waits for the prior (abandoned) worker to
#    finish before proceeding, so mode changes are always applied in order.
#
# The lock is process-global because iterm2's event loop is thread-local and
# there is only one meaningful "current session" per process.
_apply_lock = threading.Lock()


@dataclass(frozen=True)
class ItermConnectionProbe:
    connected: bool
    message: str


def run_iterm_bounded(coro_fn: Callable[..., Any], timeout: float) -> Any:
    """Run ``iterm2.run_until_complete(coro_fn)`` on a daemon thread.

    *coro_fn* is an ``async def`` function that accepts a single
    ``iterm2.Connection`` argument — the same contract as
    ``iterm2.run_until_complete``.

    Joins the worker with *timeout* seconds.  After the worker finishes
    (success **or** exception) the asyncio event loop that iterm2 created on
    that thread is explicitly closed so the underlying selector fd is reclaimed
    immediately rather than waiting for the garbage collector.

    On timeout the worker thread is abandoned (it is a daemon thread so it
    dies with the process) and ``RuntimeError`` is raised.  The module-level
    ``_apply_lock`` serializes callers so that a new call blocks until any prior
    (possibly abandoned) worker thread finishes, preventing both fd accumulation
    and stale out-of-order session mutations.

    Returns the value returned by the coroutine.  Re-raises any exception
    raised inside the coroutine.
    """
    try:
        import iterm2  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError(f"iterm2 package import failed: {exc}") from exc

    result_box: dict[str, Any] = {}

    def run() -> None:
        try:
            result_box["value"] = iterm2.run_until_complete(coro_fn)
        except SystemExit as exc:
            result_box["error"] = RuntimeError(f"iTerm2 connection exited with status {exc.code}")
        except Exception as exc:  # noqa: BLE001
            result_box["error"] = exc
        finally:
            # iterm2's Connection.run() calls asyncio.set_event_loop(loop) but
            # never calls loop.close().  Each unclosed loop retains its
            # selector (epoll/kqueue) plus self-pipe socketpair fds.  Closing
            # the thread-local event loop here reclaims those fds immediately
            # so the long-running watch daemon does not exhaust the fd table.
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_closed():
                    loop.close()
            except RuntimeError:
                pass
            # Release the serialization lock so the next caller can proceed.
            with suppress(RuntimeError):
                _apply_lock.release()

    # Acquire the lock before launching the worker.  This blocks if a prior
    # worker is still alive (e.g. was abandoned on a previous timeout), ensuring
    # at most one worker runs at a time.
    _apply_lock.acquire()
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout)

    if worker.is_alive():
        # Worker timed out but is still running.  The lock will be released by
        # the worker's finally block when it eventually finishes.  We do NOT
        # release it here so the next caller is blocked until that happens.
        raise RuntimeError(f"iTerm2 operation timed out after {timeout:g}s")

    if "error" in result_box:
        raise result_box["error"]
    return result_box.get("value")


def probe_iterm_connection(*, timeout: float = DEFAULT_PROBE_TIMEOUT) -> ItermConnectionProbe:
    try:
        import iterm2  # type: ignore[import-not-found]
    except Exception as exc:
        return ItermConnectionProbe(False, f"iterm2 package import failed: {exc}")

    async def main(connection) -> str:
        app = await iterm2.async_get_app(connection)
        window = app.current_terminal_window
        if window is None:
            return "connected to iTerm2 Python API; no current terminal window"
        return "connected to iTerm2 Python API; current terminal window is available"

    # run_iterm_bounded drives iterm2.run_until_complete on a daemon thread
    # bounded by *timeout*.  The helper also closes the event loop on the
    # worker thread after each call so no fds are leaked.
    try:
        message = run_iterm_bounded(main, timeout=timeout)
        return ItermConnectionProbe(True, str(message))
    except RuntimeError as exc:
        msg = str(exc).strip()
        if "timed out" in msg:
            return ItermConnectionProbe(
                False, f"iTerm2 connection probe timed out after {timeout:g}s"
            )
        return ItermConnectionProbe(False, msg)
    except Exception as exc:  # noqa: BLE001
        return ItermConnectionProbe(False, str(exc).strip())
