import subprocess

from term_chameleon.cli import main
from term_chameleon.screenshot import ScreenshotResult, capture_screen, probe_screenshot


def test_screenshot_probe_without_capture_reports_availability():
    result = probe_screenshot(capture=False)
    if result.available:
        assert "screencapture available" in result.message
    else:
        assert "not found" in result.message


def test_capture_screen_success_with_monkeypatch(tmp_path, monkeypatch):
    target = tmp_path / "screen.png"

    def fake_which(name):
        assert name == "screencapture"
        return "/usr/bin/screencapture"

    def fake_run(args, check, text, capture_output, timeout):
        assert args[-1] == str(target)
        target.write_bytes(b"fakepng")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("term_chameleon.screenshot.shutil.which", fake_which)
    monkeypatch.setattr("term_chameleon.screenshot.subprocess.run", fake_run)
    result = capture_screen(target)
    assert result.available is True
    assert result.captured is True
    assert result.output_path == target


def test_capture_screen_failure_with_monkeypatch(tmp_path, monkeypatch):
    target = tmp_path / "screen.png"

    monkeypatch.setattr(
        "term_chameleon.screenshot.shutil.which", lambda _name: "/usr/bin/screencapture"
    )

    def fake_run(args, check, text, capture_output, timeout):
        return subprocess.CompletedProcess(args, 1, "", "could not create image from display")

    monkeypatch.setattr("term_chameleon.screenshot.subprocess.run", fake_run)
    result = capture_screen(target)
    assert result.available is True
    assert result.captured is False
    assert "could not create image" in result.message


def test_capture_screen_timeout_returns_non_fatal_result(tmp_path, monkeypatch):
    """A subprocess.TimeoutExpired from screencapture must return a non-fatal
    ScreenshotResult(captured=False) rather than propagating the exception,
    so the watch-live daemon loop is not killed by a transient capture timeout.
    """
    target = tmp_path / "screen.png"

    monkeypatch.setattr(
        "term_chameleon.screenshot.shutil.which", lambda _name: "/usr/bin/screencapture"
    )

    def fake_run(args, **_kwargs):
        raise subprocess.TimeoutExpired(args, 10)

    monkeypatch.setattr("term_chameleon.screenshot.subprocess.run", fake_run)
    result = capture_screen(target, timeout=10)
    assert isinstance(result, ScreenshotResult)
    assert result.available is True
    assert result.captured is False
    assert "timed out" in result.message


def test_capture_screen_oserror_returns_non_fatal_result(tmp_path, monkeypatch):
    """An OSError from launching screencapture must return a non-fatal
    ScreenshotResult(captured=False) so the daemon loop is not killed.
    """
    target = tmp_path / "screen.png"

    monkeypatch.setattr(
        "term_chameleon.screenshot.shutil.which", lambda _name: "/usr/bin/screencapture"
    )

    def fake_run(args, **_kwargs):
        raise OSError("exec format error")

    monkeypatch.setattr("term_chameleon.screenshot.subprocess.run", fake_run)
    result = capture_screen(target)
    assert isinstance(result, ScreenshotResult)
    assert result.available is True
    assert result.captured is False
    assert "process error" in result.message


def test_screenshot_probe_cli_without_capture(capsys):
    status = main(["screenshot-probe"])
    out = capsys.readouterr().out
    assert "screencapture" in out
    assert status in {0, 1}
