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


# --- delegation: deterministic_check delegates to e2e.passed / visual_checks_failed ---


def test_deterministic_e2e_step_delegates_to_e2e_passed(monkeypatch, tmp_path):
    """deterministic-e2e-stage step passed flag is sourced from e2e.passed, not re-parsed JSON."""
    from term_chameleon import deterministic_check as dc_module
    from term_chameleon.e2e_stage import E2EStageReport

    e2e_out = tmp_path / "e2e-stage"
    e2e_out.mkdir(parents=True)
    fake_e2e = E2EStageReport(
        output_dir=e2e_out,
        background_files=[],
        pattern_files=[],
        visual_report_json=str(e2e_out / "visual-report.json"),
        visual_report_md=str(e2e_out / "visual-report.md"),
        screenshot_report_json=str(e2e_out / "screenshot-report.json"),
        screenshot_report_md=str(e2e_out / "screenshot-report.md"),
        screenshot_captured=None,
        visual_checks_passed=False,
        visual_checks_failed=3,
    )
    assert fake_e2e.passed is False  # sanity: passed delegates to visual_checks_passed

    monkeypatch.setattr(dc_module, "run_e2e_stage", lambda *a, **kw: fake_e2e)

    report = run_deterministic_check(tmp_path, width=32, height=16)
    e2e_step = next(s for s in report.steps if s.name == "deterministic-e2e-stage")

    assert e2e_step.passed is False
    assert "3 visual contrast check(s) failed" in e2e_step.detail


def test_deterministic_e2e_step_passes_when_e2e_passes(monkeypatch, tmp_path):
    """deterministic-e2e-stage step passes when e2e.passed is True."""
    from term_chameleon import deterministic_check as dc_module
    from term_chameleon.e2e_stage import E2EStageReport

    e2e_out = tmp_path / "e2e-stage"
    e2e_out.mkdir(parents=True)
    fake_e2e = E2EStageReport(
        output_dir=e2e_out,
        background_files=[],
        pattern_files=[],
        visual_report_json=str(e2e_out / "visual-report.json"),
        visual_report_md=str(e2e_out / "visual-report.md"),
        screenshot_report_json=str(e2e_out / "screenshot-report.json"),
        screenshot_report_md=str(e2e_out / "screenshot-report.md"),
        screenshot_captured=None,
        visual_checks_passed=True,
        visual_checks_failed=0,
    )
    assert fake_e2e.passed is True

    monkeypatch.setattr(dc_module, "run_e2e_stage", lambda *a, **kw: fake_e2e)

    report = run_deterministic_check(tmp_path, width=32, height=16)
    e2e_step = next(s for s in report.steps if s.name == "deterministic-e2e-stage")

    assert e2e_step.passed is True
    assert "generated" in e2e_step.detail


def test_deterministic_e2e_step_respects_screenshot_captured_false(monkeypatch, tmp_path):
    """If screenshot_captured=False, e2e.passed is False and step fails (future-proof guard)."""
    from term_chameleon import deterministic_check as dc_module
    from term_chameleon.e2e_stage import E2EStageReport

    e2e_out = tmp_path / "e2e-stage"
    e2e_out.mkdir(parents=True)
    # Simulate a future path where capture=True is wired and fails
    fake_e2e = E2EStageReport(
        output_dir=e2e_out,
        background_files=[],
        pattern_files=[],
        visual_report_json=str(e2e_out / "visual-report.json"),
        visual_report_md=str(e2e_out / "visual-report.md"),
        screenshot_report_json=str(e2e_out / "screenshot-report.json"),
        screenshot_report_md=str(e2e_out / "screenshot-report.md"),
        screenshot_captured=False,   # capture was requested but failed
        visual_checks_passed=True,   # visuals passed
        visual_checks_failed=0,
    )
    # E2EStageReport.passed must be False because screenshot_captured=False
    assert fake_e2e.passed is False

    monkeypatch.setattr(dc_module, "run_e2e_stage", lambda *a, **kw: fake_e2e)

    report = run_deterministic_check(tmp_path, width=32, height=16)
    e2e_step = next(s for s in report.steps if s.name == "deterministic-e2e-stage")

    # Because we delegate to e2e.passed, the step correctly surfaces the failure
    assert e2e_step.passed is False
