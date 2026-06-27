import subprocess

import pytest

from term_chameleon.cli import main
from term_chameleon.images import Region
from term_chameleon.iterm_window import (
    WindowBoundsResult,
    _desktop_bounds_points,
    _points_region_to_screenshot_pixels,
    _raw_iterm_window_bounds_points,
    get_iterm_window_bounds,
)


def test_raw_iterm_window_bounds_parses_success(monkeypatch):
    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(["osascript"], 0, "OK|10,20,300,400\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = _raw_iterm_window_bounds_points()
    assert result.available is True
    assert result.region == Region(10, 20, 300, 400)


def test_iterm_window_bounds_converts_points_to_pixels(monkeypatch):
    import term_chameleon.iterm_window as iw

    monkeypatch.setattr(iw, "_desktop_bounds_points", lambda: (0, 0, 100, 50))
    monkeypatch.setattr(iw, "_screenshot_size_pixels", lambda: (200, 100))
    assert _points_region_to_screenshot_pixels(Region(10, 5, 20, 10)) == Region(20, 10, 40, 20)


def test_get_iterm_window_bounds_uses_pixel_conversion(monkeypatch):
    import term_chameleon.iterm_window as iw

    monkeypatch.setattr(
        iw,
        "_raw_iterm_window_bounds_points",
        lambda: WindowBoundsResult(True, Region(10, 5, 20, 10), "OK|10,5,20,10"),
    )
    monkeypatch.setattr(
        iw, "_points_region_to_screenshot_pixels", lambda region: Region(20, 10, 40, 20)
    )
    result = get_iterm_window_bounds()
    assert result.available is True
    assert result.region == Region(20, 10, 40, 20)


def test_get_iterm_window_bounds_reports_error(monkeypatch):
    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(["osascript"], 0, "ERROR|no window\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = get_iterm_window_bounds()
    assert result.available is False
    assert result.message == "no window"


def test_get_iterm_window_bounds_reports_timeout(monkeypatch):
    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["osascript"], timeout=10)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = get_iterm_window_bounds()
    assert result.available is False
    assert "timed out" in result.message


def test_iterm_window_bounds_cli_success(monkeypatch, capsys):
    import term_chameleon.cli as cli

    monkeypatch.setattr(
        cli,
        "get_iterm_window_bounds",
        lambda: WindowBoundsResult(True, Region(1, 2, 3, 4), "OK"),
    )
    assert main(["iterm-window-bounds"]) == 0
    assert "1,2,3,4" in capsys.readouterr().out


def test_desktop_bounds_points_raises_runtime_error_on_non_numeric_output(monkeypatch):
    """_desktop_bounds_points raises RuntimeError (not bare ValueError) on bad Finder output."""

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(["osascript"], 0, "not, valid, numbers, here\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="could not parse desktop bounds from Finder"):
        _desktop_bounds_points()


def test_desktop_bounds_points_propagates_finder_error(monkeypatch):
    """A non-zero return code from Finder produces a RuntimeError with the raw message."""

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(["osascript"], 1, "", "Finder not running")

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="Finder not running"):
        _desktop_bounds_points()


# ---------------------------------------------------------------------------
# Regression tests — HIGH: negative-origin secondary-monitor window
# ---------------------------------------------------------------------------


def test_raw_iterm_window_bounds_negative_origin_returns_available_false(monkeypatch):
    """osascript returning a negative left/top (secondary monitor to the left/above)
    must NOT raise ValueError; it must return WindowBoundsResult(available=False)."""

    def fake_run(*_args, **_kwargs):
        # Simulate an iTerm2 window on a secondary monitor placed to the left of main
        return subprocess.CompletedProcess(["osascript"], 0, "OK|-1440,300,980,760\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = _raw_iterm_window_bounds_points()
    assert result.available is False
    assert result.region is None
    assert "negative screen origin" in result.message
    assert "--region" in result.message


def test_get_iterm_window_bounds_negative_origin_does_not_raise(monkeypatch):
    """get_iterm_window_bounds() must honour its soft-probe contract and return
    WindowBoundsResult(available=False) when the iTerm2 window has a negative
    AppleScript origin — never propagate a ValueError to callers."""

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(["osascript"], 0, "OK|-2560,100,1280,800\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = get_iterm_window_bounds()
    assert result.available is False
    assert result.region is None
    # Callers must get a human-readable hint, not a bare exception message
    assert "--region" in result.message


def test_raw_iterm_window_bounds_negative_y_only_returns_available_false(monkeypatch):
    """A window above the main display (negative top, non-negative left) also
    returns available=False gracefully."""

    def fake_run(*_args, **_kwargs):
        return subprocess.CompletedProcess(["osascript"], 0, "OK|100,-200,1280,800\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = _raw_iterm_window_bounds_points()
    assert result.available is False
    assert "negative screen origin" in result.message


# ---------------------------------------------------------------------------
# Regression tests — MEDIUM: multi-monitor scale-factor mismatch
# ---------------------------------------------------------------------------


def test_points_region_to_screenshot_pixels_multi_monitor_raises_runtime_error(monkeypatch):
    """When Finder desktop origin is non-zero (secondary monitor extends to the left),
    _points_region_to_screenshot_pixels must raise RuntimeError, not silently mis-scale."""
    import term_chameleon.iterm_window as iw

    # Simulate a desktop that starts at x=-1440 (secondary display to the left of main)
    monkeypatch.setattr(iw, "_desktop_bounds_points", lambda: (-1440, 0, 1470, 956))
    monkeypatch.setattr(iw, "_screenshot_size_pixels", lambda: (2940, 1912))
    with pytest.raises(RuntimeError, match="multi-monitor layout detected"):
        _points_region_to_screenshot_pixels(Region(100, 200, 300, 400))


def test_points_region_to_screenshot_pixels_desktop_above_main_raises(monkeypatch):
    """Secondary display above main (top != 0) also triggers the multi-monitor guard."""
    import term_chameleon.iterm_window as iw

    monkeypatch.setattr(iw, "_desktop_bounds_points", lambda: (0, -800, 1470, 956))
    monkeypatch.setattr(iw, "_screenshot_size_pixels", lambda: (2940, 1912))
    with pytest.raises(RuntimeError, match="multi-monitor layout detected"):
        _points_region_to_screenshot_pixels(Region(10, 5, 100, 50))


def test_get_iterm_window_bounds_multi_monitor_returns_available_false(monkeypatch):
    """get_iterm_window_bounds() must return available=False (not raise) when
    _points_region_to_screenshot_pixels detects a multi-monitor mismatch."""
    import term_chameleon.iterm_window as iw

    monkeypatch.setattr(
        iw,
        "_raw_iterm_window_bounds_points",
        lambda: WindowBoundsResult(True, Region(100, 200, 300, 400), "OK|100,200,300,400"),
    )
    # Finder desktop spans all displays — origin is non-zero
    monkeypatch.setattr(iw, "_desktop_bounds_points", lambda: (-1440, 0, 1470, 956))
    monkeypatch.setattr(iw, "_screenshot_size_pixels", lambda: (2940, 1912))
    result = get_iterm_window_bounds()
    assert result.available is False
    assert result.region is None
    assert "--region" in result.message


def test_points_region_to_screenshot_pixels_single_monitor_still_works(monkeypatch):
    """Single-monitor layout (desktop origin at 0,0) must still scale correctly."""
    import term_chameleon.iterm_window as iw

    monkeypatch.setattr(iw, "_desktop_bounds_points", lambda: (0, 0, 1470, 956))
    monkeypatch.setattr(iw, "_screenshot_size_pixels", lambda: (2940, 1912))
    result = _points_region_to_screenshot_pixels(Region(10, 5, 20, 10))
    assert result == Region(20, 10, 40, 20)
