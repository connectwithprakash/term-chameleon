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


# ---------------------------------------------------------------------------
# run_iterm_bounded — serialization via _apply_lock
# ---------------------------------------------------------------------------


def test_run_iterm_bounded_serializes_concurrent_callers(monkeypatch):
    """A second run_iterm_bounded call must not start its worker while a prior
    (timed-out) worker is still alive.

    This tests the R4-concurrency-io fix: _apply_lock prevents the second
    caller from launching a new worker until the first (abandoned-on-timeout)
    worker releases the lock in its finally block.

    Sequence under test:
      - T=0   first_call acquires lock, starts worker-1 (slow, hangs)
      - T=0.15 first_call join times out, raises RuntimeError, returns
              (lock is still held by worker-1's thread)
      - T=0.3 second_call tries to acquire lock — must BLOCK until worker-1
              finishes (not start a second concurrent worker)
      - T=0.5 barrier.set() lets worker-1 finish; it releases the lock
      - T≈0.5 second_call acquires lock and starts worker-2

    The key observable: "second-acquired-lock" must appear AFTER "worker-1-done"
    in call_order.
    """
    import term_chameleon.iterm_connection as conn_module

    # Reset the lock to a known clean state before the test.
    conn_module._apply_lock = __import__("threading").Lock()

    call_order: list[str] = []
    call_order_lock = __import__("threading").Lock()
    barrier = __import__("threading").Event()

    def append(item: str) -> None:
        with call_order_lock:
            call_order.append(item)

    fake = types.ModuleType("iterm2")

    def run_until_complete(coro_fn):
        append("worker-started")
        barrier.wait(timeout=5.0)
        append("worker-done")

    fake.run_until_complete = run_until_complete
    monkeypatch.setitem(sys.modules, "iterm2", fake)

    errors: list[Exception] = []

    async def noop(connection):
        pass

    def first_call():
        try:
            run_iterm_bounded(noop, timeout=0.15)
        except RuntimeError:
            append("first-timeout")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    def second_call():
        # Give the first call time to start and time out.
        time.sleep(0.3)
        append("second-acquiring-lock")
        try:
            run_iterm_bounded(noop, timeout=5.0)
            append("second-done")
        except RuntimeError:
            append("second-timeout")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threading_mod = __import__("threading")
    t1 = threading_mod.Thread(target=first_call)
    t2 = threading_mod.Thread(target=second_call)
    t1.start()
    t2.start()

    # Let the first worker's slow work start, then let it finish.
    time.sleep(0.5)
    barrier.set()

    t1.join(timeout=3.0)
    t2.join(timeout=3.0)

    assert errors == [], f"unexpected exceptions: {errors}"

    # Key assertion: "worker-done" (first worker releasing lock) must appear
    # BEFORE the second "worker-started" in call_order, proving that the second
    # caller waited for the first worker to finish rather than running concurrently.
    worker_starts = [i for i, e in enumerate(call_order) if e == "worker-started"]
    worker_dones = [i for i, e in enumerate(call_order) if e == "worker-done"]
    assert len(worker_starts) == 2, f"expected 2 worker-started events; got {call_order}"
    assert len(worker_dones) == 2, f"expected 2 worker-done events; got {call_order}"
    # The first "worker-done" must precede the second "worker-started".
    first_done_idx = worker_dones[0]
    second_start_idx = worker_starts[1]
    assert first_done_idx < second_start_idx, (
        f"second worker started before first was done; call_order={call_order}"
    )


def test_run_iterm_bounded_lock_released_after_success(monkeypatch):
    """_apply_lock must be released after a successful run so a follow-up call
    does not deadlock.
    """
    import term_chameleon.iterm_connection as conn_module

    conn_module._apply_lock = __import__("threading").Lock()

    fake = types.ModuleType("iterm2")

    def run_until_complete(coro_fn):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro_fn(object()))
        finally:
            pass

    fake.run_until_complete = run_until_complete
    monkeypatch.setitem(sys.modules, "iterm2", fake)

    async def echo(connection):
        return "ok"

    # First call — must succeed and release the lock.
    result = run_iterm_bounded(echo, timeout=5.0)
    assert result == "ok"

    # Second call — must NOT deadlock (lock was properly released).
    result2 = run_iterm_bounded(echo, timeout=5.0)
    assert result2 == "ok"


def test_run_iterm_bounded_lock_released_after_exception(monkeypatch):
    """_apply_lock must be released even when the coroutine raises, so a
    follow-up call does not deadlock.
    """
    import term_chameleon.iterm_connection as conn_module

    conn_module._apply_lock = __import__("threading").Lock()

    fake = types.ModuleType("iterm2")

    def run_until_complete(coro_fn):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro_fn(object()))
        finally:
            pass

    fake.run_until_complete = run_until_complete
    monkeypatch.setitem(sys.modules, "iterm2", fake)

    async def fail(connection):
        raise ValueError("boom")

    async def echo(connection):
        return "ok"

    with pytest.raises(ValueError, match="boom"):
        run_iterm_bounded(fail, timeout=5.0)

    # Lock must be released; follow-up call must not deadlock.
    result = run_iterm_bounded(echo, timeout=5.0)
    assert result == "ok"
