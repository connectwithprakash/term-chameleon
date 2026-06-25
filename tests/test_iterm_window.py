import subprocess

from term_chameleon.cli import main
from term_chameleon.images import Region
from term_chameleon.iterm_window import (
    WindowBoundsResult,
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
