import json

from term_chameleon.cli import main
from term_chameleon.e2e_stage import run_e2e_stage

FIXTURE = "tests/fixtures/iterm/good-dark-glass.json"
BAD_FIXTURE = "tests/fixtures/iterm/bad-ansi-black.json"


def test_run_e2e_stage_without_capture(tmp_path):
    report = run_e2e_stage(FIXTURE, tmp_path, capture=False, width=32, height=16)
    assert (tmp_path / "e2e-stage-report.json").exists()
    assert (tmp_path / "e2e-stage-report.md").exists()
    assert len(report.background_files) == 6
    assert len(report.pattern_files) == 2
    assert report.screenshot_captured is None
    data = json.loads((tmp_path / "e2e-stage-report.json").read_text())
    assert data["screenshot_captured"] is None


def test_e2e_stage_cli_without_capture(tmp_path, capsys):
    assert (
        main(
            [
                "e2e-stage",
                FIXTURE,
                "--output-dir",
                str(tmp_path),
                "--width",
                "32",
                "--height",
                "16",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "e2e staging bundle passed" in out
    assert (tmp_path / "background-html" / "index.html").exists()
    assert (tmp_path / "pattern" / "render-pattern.sh").exists()
    assert (tmp_path / "visual-test" / "report.json").exists()
    assert (tmp_path / "screenshot-test" / "report.json").exists()


# --- Fix: e2e-stage exit semantics ---


def test_run_e2e_stage_propagates_visual_checks_passed_for_good_profile(tmp_path):
    """run_e2e_stage reports visual_checks_passed=True for a well-contrasted profile."""
    report = run_e2e_stage(FIXTURE, tmp_path, capture=False, width=32, height=16)
    assert report.visual_checks_passed is True
    assert report.visual_checks_failed == 0
    assert report.passed is True


def test_run_e2e_stage_propagates_visual_checks_failed_for_bad_profile(tmp_path):
    """run_e2e_stage reports visual_checks_passed=False when contrast checks fail."""
    report = run_e2e_stage(BAD_FIXTURE, tmp_path, capture=False, width=32, height=16)
    assert report.visual_checks_passed is False
    assert report.visual_checks_failed > 0
    assert report.passed is False
    data = json.loads((tmp_path / "e2e-stage-report.json").read_text())
    assert data["visual_checks_passed"] is False
    assert data["visual_checks_failed"] > 0


def test_e2e_stage_cli_returns_1_when_visual_checks_fail(tmp_path, capsys):
    """_e2e_stage returns exit 1 when embedded visual checks fail."""
    result = main(
        [
            "e2e-stage",
            BAD_FIXTURE,
            "--output-dir",
            str(tmp_path),
            "--width",
            "32",
            "--height",
            "16",
        ]
    )
    assert result == 1
    captured = capsys.readouterr()
    assert "FAILED" in captured.out or "e2e stage visual checks failed" in captured.err


def test_e2e_stage_cli_returns_0_when_visual_checks_pass_no_capture(tmp_path, capsys):
    """_e2e_stage returns exit 0 for a passing profile with no --capture."""
    result = main(
        [
            "e2e-stage",
            FIXTURE,
            "--output-dir",
            str(tmp_path),
            "--width",
            "32",
            "--height",
            "16",
        ]
    )
    assert result == 0
    out = capsys.readouterr().out
    assert "e2e staging bundle passed" in out


def test_e2e_stage_passed_property_false_when_screenshot_captured_is_false(tmp_path):
    """E2EStageReport.passed is False when screenshot_captured is False."""
    from term_chameleon.e2e_stage import E2EStageReport

    report = E2EStageReport(
        output_dir=tmp_path,
        background_files=[],
        pattern_files=[],
        visual_report_json=str(tmp_path / "v.json"),
        visual_report_md=str(tmp_path / "v.md"),
        screenshot_report_json=str(tmp_path / "s.json"),
        screenshot_report_md=str(tmp_path / "s.md"),
        screenshot_captured=False,
        visual_checks_passed=True,
        visual_checks_failed=0,
    )
    assert report.passed is False


def test_e2e_stage_passed_property_true_when_screenshot_captured_is_none(tmp_path):
    """E2EStageReport.passed is True when screenshot_captured is None (no capture requested)."""
    from term_chameleon.e2e_stage import E2EStageReport

    report = E2EStageReport(
        output_dir=tmp_path,
        background_files=[],
        pattern_files=[],
        visual_report_json=str(tmp_path / "v.json"),
        visual_report_md=str(tmp_path / "v.md"),
        screenshot_report_json=str(tmp_path / "s.json"),
        screenshot_report_md=str(tmp_path / "s.md"),
        screenshot_captured=None,
        visual_checks_passed=True,
        visual_checks_failed=0,
    )
    assert report.passed is True
