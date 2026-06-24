import json

from term_chameleon.cli import main
from term_chameleon.e2e_stage import run_e2e_stage

FIXTURE = "tests/fixtures/iterm/good-dark-glass.json"


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
