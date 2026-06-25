import json
from pathlib import Path

from term_chameleon.cli import main
from term_chameleon.deterministic_check import (
    CheckStep,
    DeterministicCheckReport,
    run_deterministic_check,
)


def test_run_deterministic_check_generates_reports(tmp_path):
    report = run_deterministic_check(tmp_path, width=32, height=16)
    assert report.passed
    assert {step.name for step in report.steps} == {
        "generated-profile-doctor",
        "deterministic-e2e-stage",
        "pixel-contrast",
        "text-row-contrast",
        "watch-hysteresis",
    }
    data = json.loads((tmp_path / "deterministic-check-report.json").read_text())
    assert data["passed"] is True
    assert len(data["steps"]) == 5
    assert (tmp_path / "deterministic-check-report.md").exists()
    assert (tmp_path / "generated-balanced-profile.json").exists()
    assert (tmp_path / "e2e-stage" / "e2e-stage-report.json").exists()
    assert (tmp_path / "screenshot-contrast" / "contrast-report.json").exists()
    assert (tmp_path / "screenshot-text-contrast" / "text-contrast-report.json").exists()


def test_check_cli_generates_self_check_report(tmp_path, capsys):
    assert main(["check", "--output-dir", str(tmp_path), "--width", "32", "--height", "16"]) == 0
    out = capsys.readouterr().out
    assert "deterministic self-check passed" in out
    assert "generated-profile-doctor" in out
    assert (tmp_path / "deterministic-check-report.json").exists()


def test_check_cli_returns_failure_when_step_fails(monkeypatch, tmp_path, capsys):
    def fake_check(output_dir: Path, *, width: int, height: int) -> DeterministicCheckReport:
        assert width == 32
        assert height == 16
        return DeterministicCheckReport(
            output_dir=output_dir,
            steps=[CheckStep("synthetic", False, "expected failure", [])],
        )

    monkeypatch.setattr("term_chameleon.cli.run_deterministic_check", fake_check)
    assert main(["check", "--output-dir", str(tmp_path), "--width", "32", "--height", "16"]) == 1
    out = capsys.readouterr().out
    assert "[fail] synthetic: expected failure" in out
