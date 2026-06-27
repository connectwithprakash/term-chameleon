import asyncio
import sys
import time
import types

import pytest

from term_chameleon.iterm_connection import (
    ItermConnectionProbe,
    probe_iterm_connection,
    run_iterm_bounded,
)

# ---------------------------------------------------------------------------
# run_iterm_bounded — unit tests for the shared helper
# ---------------------------------------------------------------------------

def _make_fake_iterm2_for_bounded(*, hang: bool = False):
    """Minimal fake iterm2 module for run_iterm_bounded tests."""
    fake = types.ModuleType("iterm2")

    if hang:
        def run_until_complete(coro_fn):
            time.sleep(30)
    else:
        def run_until_complete(coro_fn):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro_fn(object()))
            finally:
                pass  # intentionally NOT closing — simulates iterm2 bug

    fake.run_until_complete = run_until_complete
    return fake


def test_run_iterm_bounded_raises_on_timeout(monkeypatch):
    """run_iterm_bounded raises RuntimeError when the operation hangs."""
    fake = _make_fake_iterm2_for_bounded(hang=True)
    monkeypatch.setitem(sys.modules, "iterm2", fake)

    async def noop(connection):
        pass

    start = time.monotonic()
    with pytest.raises(RuntimeError, match="timed out"):
        run_iterm_bounded(noop, timeout=0.2)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0


def test_run_iterm_bounded_closes_event_loop_on_success(monkeypatch):
    """The event loop created by iterm2 is closed by the helper after success."""
    captured_loops: list[asyncio.AbstractEventLoop] = []

    class CapturingFakeIterm2:
        @staticmethod
        def run_until_complete(coro_fn):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            captured_loops.append(loop)
            try:
                return loop.run_until_complete(coro_fn(object()))
            finally:
                pass  # intentionally NOT closing — simulates iterm2 bug

    fake = types.ModuleType("iterm2")
    fake.run_until_complete = CapturingFakeIterm2.run_until_complete
    monkeypatch.setitem(sys.modules, "iterm2", fake)

    async def echo(connection):
        return "ok"

    run_iterm_bounded(echo, timeout=5.0)

    # Allow the worker's finally block to execute
    time.sleep(0.05)

    assert all(loop.is_closed() for loop in captured_loops), (
        "Event loops were not closed by run_iterm_bounded; fd leak detected"
    )


def test_run_iterm_bounded_closes_event_loop_on_exception(monkeypatch):
    """The event loop is also closed when the coroutine raises."""
    captured_loops: list[asyncio.AbstractEventLoop] = []

    class CapturingFakeIterm2:
        @staticmethod
        def run_until_complete(coro_fn):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            captured_loops.append(loop)
            try:
                return loop.run_until_complete(coro_fn(object()))
            finally:
                pass  # intentionally NOT closing

    fake = types.ModuleType("iterm2")
    fake.run_until_complete = CapturingFakeIterm2.run_until_complete
    monkeypatch.setitem(sys.modules, "iterm2", fake)

    async def fail(connection):
        raise ValueError("simulated iterm2 error")

    with pytest.raises(ValueError, match="simulated iterm2 error"):
        run_iterm_bounded(fail, timeout=5.0)

    time.sleep(0.05)

    assert all(loop.is_closed() for loop in captured_loops), (
        "Event loops were not closed by run_iterm_bounded after exception"
    )


def test_run_iterm_bounded_wraps_system_exit(monkeypatch):
    """SystemExit from iterm2 is wrapped as RuntimeError."""
    fake = types.ModuleType("iterm2")
    fake.run_until_complete = lambda coro_fn: (_ for _ in ()).throw(SystemExit(1))
    monkeypatch.setitem(sys.modules, "iterm2", fake)

    async def noop(connection):
        pass

    with pytest.raises(RuntimeError, match="exited with status 1"):
        run_iterm_bounded(noop, timeout=5.0)


def test_run_iterm_bounded_raises_when_iterm2_missing(monkeypatch):
    """Raises RuntimeError when the iterm2 package is not installed."""
    monkeypatch.setitem(sys.modules, "iterm2", None)

    async def noop(connection):
        pass

    with pytest.raises(RuntimeError, match="iterm2 package import failed"):
        run_iterm_bounded(noop, timeout=5.0)


# ---------------------------------------------------------------------------
# probe_iterm_connection — integration tests (use run_iterm_bounded internally)
# ---------------------------------------------------------------------------

def test_probe_iterm_connection_returns_structured_result():
    result = probe_iterm_connection()
    assert isinstance(result.connected, bool)
    assert isinstance(result.message, str)
    assert result.message


def test_probe_iterm_connection_times_out_on_unresponsive_daemon(monkeypatch):
    """A hung iterm2.run_until_complete must not block the probe indefinitely."""
    fake = types.ModuleType("iterm2")

    def hang(_main):
        time.sleep(30)  # simulate an unresponsive daemon; should be abandoned by timeout

    fake.run_until_complete = hang
    fake.async_get_app = None
    monkeypatch.setitem(sys.modules, "iterm2", fake)

    start = time.monotonic()
    result = probe_iterm_connection(timeout=0.2)
    elapsed = time.monotonic() - start

    assert result.connected is False
    assert "timed out" in result.message
    assert elapsed < 5  # returned promptly rather than waiting out the 30s sleep


def test_iterm_connect_probe_cli_with_monkeypatch(monkeypatch, capsys):
    import term_chameleon.cli as cli

    monkeypatch.setattr(
        cli,
        "probe_iterm_connection",
        lambda: ItermConnectionProbe(True, "connected"),
    )
    assert cli.main(["iterm-connect-probe"]) == 0
    assert "connected to live iTerm2 Python API" in capsys.readouterr().out
