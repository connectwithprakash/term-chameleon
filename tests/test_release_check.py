import json
from pathlib import Path

from term_chameleon.cli import main
from term_chameleon.deterministic_check import CheckStep, DeterministicCheckReport
from term_chameleon.release_check import run_release_check
from term_chameleon.status import StatusCheck, StatusReport


def test_run_release_check_permission_free_generates_report(tmp_path):
    report = run_release_check(output_dir=tmp_path, width=32, height=16)
    assert report.passed
    assert [step.name for step in report.steps] == ["deterministic-check", "status"]
    data = json.loads((tmp_path / "release-check-report.json").read_text(encoding="utf-8"))
    assert data["passed"] is True
    assert (tmp_path / "release-check-report.md").exists()


def test_release_check_includes_config_validation(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[watch]\ninterval = "fast"\n', encoding="utf-8")
    report = run_release_check(output_dir=tmp_path / "out", config_path=config, width=32, height=16)
    assert not report.passed
    config_step = next(step for step in report.steps if step.name == "config-check")
    assert not config_step.passed
    assert "config validation error" in config_step.detail


def test_release_check_cli_success(monkeypatch, tmp_path, capsys):
    import term_chameleon.cli as cli_module

    def fake_check(output_dir: Path, *, width: int, height: int) -> DeterministicCheckReport:
        assert width == 32
        assert height == 16
        return DeterministicCheckReport(
            output_dir=Path(output_dir),
            steps=[CheckStep("synthetic", True, "ok", [])],
        )

    monkeypatch.setattr("term_chameleon.release_check.run_deterministic_check", fake_check)
    monkeypatch.setattr(cli_module, "run_deterministic_check", fake_check)
    assert (
        main(["release-check", "--output-dir", str(tmp_path), "--width", "32", "--height", "16"])
        == 0
    )
    out = capsys.readouterr().out
    assert "[ok] deterministic-check" in out
    assert "[ok] release check passed" in out
    assert (tmp_path / "release-check-report.json").exists()


def test_release_check_daemon_invalid_config_writes_report(tmp_path, capsys):
    config = tmp_path / "bad-daemon.toml"
    config.write_text("[daemon]\nautolaunch_dir = 123\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    assert (
        main(
            [
                "release-check",
                "--output-dir",
                str(out_dir),
                "--config",
                str(config),
                "--daemon",
                "--width",
                "32",
                "--height",
                "16",
            ]
        )
        == 1
    )
    out = capsys.readouterr().out
    assert "[fail] config-check" in out
    assert "[fail] watch-daemon-status" in out
    assert (out_dir / "release-check-report.json").exists()
    data = json.loads((out_dir / "release-check-report.json").read_text(encoding="utf-8"))
    assert data["passed"] is False


def test_release_check_daemon_missing_config_writes_report(tmp_path, capsys):
    out_dir = tmp_path / "out"
    assert (
        main(
            [
                "release-check",
                "--output-dir",
                str(out_dir),
                "--config",
                str(tmp_path / "missing.toml"),
                "--daemon",
                "--width",
                "32",
                "--height",
                "16",
            ]
        )
        == 1
    )
    out = capsys.readouterr().out
    assert "[fail] config-check" in out
    assert "[fail] watch-daemon-status" in out
    assert (out_dir / "release-check-report.json").exists()


def test_release_check_cli_failure_when_live_status_fails(monkeypatch, tmp_path, capsys):
    def fake_status(*, profile_path=None, live=False):
        assert live is True
        return StatusReport(
            version="0.0",
            profile_path="/tmp/profile.json",
            profile_installed=False,
            profile_name=None,
            checks=[
                StatusCheck("profile", False, "missing"),
                StatusCheck("screencapture", True, "ok"),
                StatusCheck("iterm-app", True, "ok"),
                StatusCheck("iterm-python-package", True, "ok"),
                StatusCheck("iterm-api-connect", False, "not connected"),
                StatusCheck("iterm-window-bounds", False, "missing"),
            ],
            recommended_next_command="term-chameleon setup --yes",
        )

    monkeypatch.setattr("term_chameleon.release_check.collect_status", fake_status)
    assert main(["release-check", "--output-dir", str(tmp_path), "--live"]) == 1
    out = capsys.readouterr().out
    assert "[fail] status-live" in out
    assert "release check failed" in out
