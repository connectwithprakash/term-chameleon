import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from term_chameleon.cli import main
from term_chameleon.images import Region
from term_chameleon.iterm_window import WindowBoundsResult
from term_chameleon.live_stage import (
    browser_stage_script,
    iterm_stage_script,
    run_live_stage,
)
from term_chameleon.pixel_contrast import ContrastEstimate
from term_chameleon.screenshot import ScreenshotResult
from term_chameleon.text_contrast import (
    TextContrastEstimate,
    TextContrastUnavailable,
    TextRowBand,
)


def pixel_estimate(contrast: float = 3.0, passed: bool = False) -> ContrastEstimate:
    return ContrastEstimate(
        image_path="screen.png",
        region="0,0,10,10",
        dark_color="#000000",
        light_color="#FFFFFF",
        dark_luminance=0.0,
        light_luminance=1.0,
        contrast=contrast,
        threshold=4.5,
        passed=passed,
        sampled_pixels=100,
    )


def text_estimate(contrast: float = 7.0, passed: bool = True) -> TextContrastEstimate:
    return TextContrastEstimate(
        image_path="screen.png",
        region="0,0,10,10",
        bands=[TextRowBand(2, 2, 1.0, 8)],
        foreground_color="#FFFFFF",
        background_color="#000000",
        foreground_luminance=1.0,
        background_luminance=0.0,
        contrast=contrast,
        threshold=4.5,
        passed=passed,
        glyph_pixels=8,
        background_pixels=92,
    )


def test_browser_stage_script_contains_file_url(tmp_path):
    background = tmp_path / "solid-light.html"
    background.write_text("<html></html>")
    script = browser_stage_script(background, bounds="1,2,300,400")
    assert 'tell application "Safari"' in script
    assert "file://" in script
    assert "{1, 2, 301, 402}" in script


def test_iterm_stage_script_writes_pattern_command(tmp_path):
    pattern = tmp_path / "render pattern; risky.sh"
    pattern.write_text("#!/usr/bin/env bash\n")
    script = iterm_stage_script(pattern, bounds="10,20,300,400")
    assert 'tell application "iTerm2"' in script
    assert "create window with default profile" in script
    assert "write text" in script
    assert "TERM_CHAMELEON_PATTERN_WAIT=0" in script
    assert "'" in script
    assert "{10, 20, 310, 420}" in script


def test_iterm_stage_script_escapes_double_quotes(tmp_path):
    """Verify that double quotes in the path are properly escaped for AppleScript."""
    from term_chameleon.live_stage import _escape_applescript_string

    # Test that double quotes are escaped
    escaped = _escape_applescript_string('hello "world"')
    # The function escapes quotes with backslash (AppleScript requires \")
    assert escaped == r"hello \"world\""
    # Verify the escaping prevents breaking out of the AppleScript string
    assert 'hello \\"world\\"' in escaped or escaped == r"hello \"world\""


def test_iterm_stage_script_escapes_backslashes(tmp_path):
    """Verify that backslashes in the path are properly escaped for AppleScript."""
    from term_chameleon.live_stage import _escape_applescript_string

    # Test that backslashes are escaped (important on Windows paths or shell escapes)
    escaped = _escape_applescript_string("C:\\Users\\test")
    assert escaped == "C:\\\\Users\\\\test"


def test_iterm_stage_script_rejects_injection_attempt(tmp_path):
    """Verify that command injection attempts through quotes are neutralized."""
    from term_chameleon.live_stage import _escape_applescript_string

    # Attempt to break out of the string and inject AppleScript commands
    injection = '" & activate & "echo'
    escaped = _escape_applescript_string(injection)
    # The quotes are escaped, making the injection harmless
    assert escaped == '\\" & activate & \\"echo'


def test_iterm_stage_script_rejects_newlines(tmp_path):
    """Verify that newlines in paths raise an error (not allowed in AppleScript strings)."""
    import pytest

    from term_chameleon.live_stage import _escape_applescript_string

    # Newlines are not allowed in AppleScript double-quoted strings
    with pytest.raises(ValueError, match="cannot contain newlines"):
        _escape_applescript_string("path\nwith\nnewlines")

    with pytest.raises(ValueError, match="cannot contain newlines"):
        _escape_applescript_string("path\rwith\rreturns")


def test_escape_applescript_newline_error_message_does_not_reference_shlex():
    """The newline error message must not reference shlex.quote (irrelevant to AppleScript)."""
    import pytest

    from term_chameleon.live_stage import _escape_applescript_string

    with pytest.raises(ValueError) as exc_info:
        _escape_applescript_string("text\nwith\nnewline")
    assert "shlex" not in str(exc_info.value), (
        "Error message must not reference shlex.quote (not an AppleScript function)"
    )


def test_run_live_stage_dry_run_writes_report(tmp_path):
    report = run_live_stage(tmp_path, dry_run=True, background="solid-dark")
    assert report.dry_run is True
    assert report.browser_returncode is None
    assert report.iterm_returncode is None
    assert (tmp_path / "live-stage-report.json").exists()
    data = json.loads((tmp_path / "live-stage-report.json").read_text())
    assert data["background"] == "solid-dark"


def test_run_live_stage_executes_when_not_dry_run(monkeypatch, tmp_path):
    calls = []
    sleeps = []

    def fake_run(script):
        calls.append(script)
        return subprocess.CompletedProcess(["osascript"], 0, "", "")

    monkeypatch.setattr("term_chameleon.live_stage.run_osascript", fake_run)
    monkeypatch.setattr("term_chameleon.live_stage.time.sleep", sleeps.append)
    report = run_live_stage(tmp_path, dry_run=False, capture=False)
    assert report.browser_returncode == 0
    assert report.iterm_returncode == 0
    assert len(calls) == 2
    assert sleeps == []


def test_run_live_stage_prefers_text_row_contrast(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "term_chameleon.live_stage.run_osascript",
        lambda _script: subprocess.CompletedProcess(["osascript"], 0, "", ""),
    )
    monkeypatch.setattr("term_chameleon.live_stage.time.sleep", lambda _delay: None)
    monkeypatch.setattr(
        "term_chameleon.live_stage.capture_screen",
        lambda path: ScreenshotResult(True, True, Path(path), "captured", 0),
    )
    monkeypatch.setattr(
        "term_chameleon.live_stage.get_iterm_window_bounds",
        lambda: WindowBoundsResult(True, Region(0, 0, 10, 10), "ok"),
    )
    monkeypatch.setattr(
        "term_chameleon.live_stage.decide_from_screen",
        lambda *_args, **_kwargs: SimpleNamespace(suggested_mode="dark-glass"),
    )
    monkeypatch.setattr(
        "term_chameleon.live_stage.write_contrast_report",
        lambda *_args, **_kwargs: (
            tmp_path / "pixel.json",
            tmp_path / "pixel.md",
            pixel_estimate(),
        ),
    )
    monkeypatch.setattr(
        "term_chameleon.live_stage.write_text_contrast_report",
        lambda *_args, **_kwargs: (tmp_path / "text.json", tmp_path / "text.md", text_estimate()),
    )

    report = run_live_stage(tmp_path, dry_run=False, capture=True, settle_delay=0)

    assert report.contrast_method == "text-row"
    assert report.estimated_contrast == 7.0
    assert report.contrast_passed is True
    assert report.pixel_estimated_contrast == 3.0
    assert report.text_estimated_contrast == 7.0


def test_run_live_stage_falls_back_to_pixel_contrast(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "term_chameleon.live_stage.run_osascript",
        lambda _script: subprocess.CompletedProcess(["osascript"], 0, "", ""),
    )
    monkeypatch.setattr(
        "term_chameleon.live_stage.capture_screen",
        lambda path: ScreenshotResult(True, True, Path(path), "captured", 0),
    )
    monkeypatch.setattr(
        "term_chameleon.live_stage.get_iterm_window_bounds",
        lambda: WindowBoundsResult(True, Region(0, 0, 10, 10), "ok"),
    )
    monkeypatch.setattr(
        "term_chameleon.live_stage.decide_from_screen",
        lambda *_args, **_kwargs: SimpleNamespace(suggested_mode="dark-glass"),
    )
    monkeypatch.setattr(
        "term_chameleon.live_stage.write_contrast_report",
        lambda *_args, **_kwargs: (
            tmp_path / "pixel.json",
            tmp_path / "pixel.md",
            pixel_estimate(5.0, True),
        ),
    )

    def fail_text(*_args, **_kwargs):
        raise TextContrastUnavailable("no text-like rows found")

    monkeypatch.setattr("term_chameleon.live_stage.write_text_contrast_report", fail_text)

    report = run_live_stage(tmp_path, dry_run=False, capture=True, settle_delay=0)

    assert report.contrast_method == "pixel-cluster"
    assert report.estimated_contrast == 5.0
    assert report.contrast_passed is True
    assert report.text_contrast_error == "no text-like rows found"


def test_live_stage_cli_refuses_without_yes(tmp_path, capsys):
    assert main(["live-stage", "--output-dir", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "Refusing to drive GUI apps" in err


def test_live_stage_cli_dry_run(tmp_path, capsys):
    assert main(["live-stage", "--dry-run", "--output-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "[ok] live stage completed" in out
    assert (tmp_path / "live-stage-report.md").exists()
