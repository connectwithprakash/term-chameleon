import json
from pathlib import Path

from term_chameleon.cli import main
from term_chameleon.install import install_balanced_profile
from term_chameleon.iterm_profile import loads_document
from term_chameleon.visual import write_visual_report

FIXTURES = Path(__file__).parent / "fixtures" / "iterm"


def test_install_balanced_profile_dry_run_validates(tmp_path):
    target, content = install_balanced_profile(target_dir=tmp_path, dry_run=True)
    assert target == tmp_path / "term-chameleon-adaptive-glass.json"
    parsed = loads_document(content)
    assert parsed.name == "Adaptive Glass"
    assert not target.exists()


def test_install_command_writes_profile(tmp_path, capsys):
    assert main(["install", "--target-dir", str(tmp_path), "--name", "Test Glass"]) == 0
    out = capsys.readouterr().out
    assert "[ok] generated Dynamic Profile JSON is valid" in out
    written = tmp_path / "term-chameleon-adaptive-glass.json"
    assert written.exists()
    assert loads_document(written.read_text()).name == "Test Glass"


def test_visual_report_writes_artifacts(tmp_path):
    json_path, md_path, checks = write_visual_report(FIXTURES / "good-dark-glass.json", tmp_path)
    assert json_path.exists()
    assert md_path.exists()
    data = json.loads(json_path.read_text())
    assert len(data) == len(checks)
    assert all(item["passed"] for item in data)


def test_visual_test_command(tmp_path, capsys):
    assert (
        main(
            [
                "visual-test",
                str(FIXTURES / "good-dark-glass.json"),
                "--output-dir",
                str(tmp_path),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "visual contrast simulation passed" in out
