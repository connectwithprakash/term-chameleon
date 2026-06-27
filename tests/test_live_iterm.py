"""Tests for live_iterm.apply_preset_to_current_session.

Covers:
- timeout: a hung iterm2.run_until_complete raises RuntimeError promptly
- fd reclamation: the asyncio event loop created by iterm2 is closed after apply
- happy path: successful apply returns LiveApplyResult(applied=True)
- error path: iterm2 exceptions are re-raised as RuntimeError
"""
from __future__ import annotations

import asyncio
import contextlib
import sys
import time
import types

import pytest

from term_chameleon.live_iterm import LiveApplyResult, apply_preset_to_current_session

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_iterm2(*, hang: bool = False, raises: Exception | None = None):
    """Build a minimal fake iterm2 module suitable for monkeypatching."""
    fake = types.ModuleType("iterm2")

    class FakeColor:
        def __init__(self, r, g, b):
            self.r, self.g, self.b = r, g, b

    class FakeProfile:
        def __init__(self):
            self._calls: list[str] = []

        def __getattr__(self, name):
            def setter(value):
                self._calls.append(name)
            return setter

    class FakeSession:
        def __init__(self):
            self.profile = FakeProfile()

        async def async_set_profile_properties(self, change):
            pass

    class FakeTab:
        def __init__(self):
            self.current_session = FakeSession()

    class FakeWindow:
        def __init__(self):
            self.current_tab = FakeTab()

    class FakeApp:
        def __init__(self):
            self.current_terminal_window = FakeWindow()

    async def fake_async_get_app(connection):
        return FakeApp()

    fake.Color = FakeColor
    fake.LocalWriteOnlyProfile = FakeProfile
    fake.async_get_app = fake_async_get_app

    if hang:
        def run_until_complete(coro_fn):
            time.sleep(30)

        fake.run_until_complete = run_until_complete
    elif raises is not None:
        def run_until_complete(coro_fn):
            raise raises

        fake.run_until_complete = run_until_complete
    else:
        def run_until_complete(coro_fn):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro_fn(object()))
            finally:
                # Simulate iterm2 NOT closing the loop (the bug we fix)
                pass  # intentionally do not call loop.close()

        fake.run_until_complete = run_until_complete

    return fake


# ---------------------------------------------------------------------------
# Timeout test (Finding 1 HIGH)
# ---------------------------------------------------------------------------

def test_apply_preset_times_out_on_hung_daemon(monkeypatch):
    """A hung iterm2.run_until_complete must raise RuntimeError within the timeout."""
    fake = _make_fake_iterm2(hang=True)
    monkeypatch.setitem(sys.modules, "iterm2", fake)

    start = time.monotonic()
    with pytest.raises(RuntimeError, match="timed out"):
        apply_preset_to_current_session("dark-glass", timeout=0.3)
    elapsed = time.monotonic() - start

    assert elapsed < 5.0, f"apply_preset blocked for {elapsed:.1f}s; expected < 5s"


def test_apply_preset_timeout_result_is_runtime_error(monkeypatch):
    """Timeout surfaces as RuntimeError so the watch loop continues."""
    fake = _make_fake_iterm2(hang=True)
    monkeypatch.setitem(sys.modules, "iterm2", fake)

    with pytest.raises(RuntimeError):
        apply_preset_to_current_session("bright-safe", timeout=0.2)


# ---------------------------------------------------------------------------
# Fd-reclamation test (Finding 2 HIGH)
# ---------------------------------------------------------------------------

def test_apply_preset_closes_event_loop_after_each_call(monkeypatch):
    """The asyncio event loop must be closed after each apply to prevent fd leaks.

    We verify this by checking that the event loop left on the worker thread is
    closed, simulating repeated applies in the watch daemon.
    """

    closed_states: list[bool] = []

    real_loop: list[asyncio.AbstractEventLoop] = []

    class LoopCapturingFakeIterm2:
        """Fake that exposes the event loop state after run_until_complete."""

        @staticmethod
        def run_until_complete(coro_fn):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            real_loop.append(loop)
            try:
                return loop.run_until_complete(coro_fn(object()))
            finally:
                # Simulate iterm2 NOT closing the loop
                pass

    fake = _make_fake_iterm2()
    fake.run_until_complete = LoopCapturingFakeIterm2.run_until_complete
    monkeypatch.setitem(sys.modules, "iterm2", fake)

    # Run apply twice (simulating two mode switches in the watch daemon)
    for _ in range(2):
        real_loop.clear()
        with contextlib.suppress(RuntimeError):
            apply_preset_to_current_session("dark-glass", timeout=5.0)
        # Give the worker thread a moment to finish its finally block
        time.sleep(0.05)
        if real_loop:
            closed_states.append(real_loop[0].is_closed())

    # Every loop captured must have been closed by run_iterm_bounded
    assert all(closed_states), (
        f"Some event loops were not closed after apply: {closed_states}"
    )


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------

def test_apply_preset_propagates_iterm2_runtime_error(monkeypatch):
    """Exceptions from within the iterm2 coroutine surface as RuntimeError."""
    fake = _make_fake_iterm2(raises=Exception("iTerm2 connection refused"))
    monkeypatch.setitem(sys.modules, "iterm2", fake)

    with pytest.raises(RuntimeError):
        apply_preset_to_current_session("dark-glass", timeout=5.0)


def test_apply_preset_propagates_system_exit_as_runtime_error(monkeypatch):
    """SystemExit from iterm2 (connection refused) is wrapped as RuntimeError."""
    fake = _make_fake_iterm2(raises=SystemExit(1))
    monkeypatch.setitem(sys.modules, "iterm2", fake)

    with pytest.raises(RuntimeError, match="exited with status 1"):
        apply_preset_to_current_session("dark-glass", timeout=5.0)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_apply_preset_happy_path_returns_live_apply_result(monkeypatch):
    """A successful apply returns LiveApplyResult with applied=True."""
    fake = _make_fake_iterm2()
    monkeypatch.setitem(sys.modules, "iterm2", fake)

    result = apply_preset_to_current_session("dark-glass", timeout=5.0)

    assert isinstance(result, LiveApplyResult)
    assert result.applied is True
    assert result.preset == "dark-glass"
    assert isinstance(result.setters, tuple)


def test_apply_preset_missing_iterm2_raises_runtime_error(monkeypatch):
    """When the iterm2 package is absent, RuntimeError is raised."""
    monkeypatch.setitem(sys.modules, "iterm2", None)

    with pytest.raises(RuntimeError, match="iterm2 package import failed"):
        apply_preset_to_current_session("dark-glass")
