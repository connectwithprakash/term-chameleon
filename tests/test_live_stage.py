import json
import subprocess

from term_chameleon.cli import main
from term_chameleon.live_stage import (
    browser_stage_script,
    iterm_stage_script,
    run_live_stage,
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


def test_live_stage_cli_refuses_without_yes(tmp_path, capsys):
    assert main(["live-stage", "--output-dir", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "Refusing to drive GUI apps" in err


def test_live_stage_cli_dry_run(tmp_path, capsys):
    assert main(["live-stage", "--dry-run", "--output-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "[ok] live stage completed" in out
    assert (tmp_path / "live-stage-report.md").exists()
