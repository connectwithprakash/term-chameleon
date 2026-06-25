from term_chameleon.cli import main
from term_chameleon.install import install_profile
from term_chameleon.setup import run_setup


def test_setup_without_yes_reports_missing_profile(tmp_path):
    report = run_setup(output_dir=tmp_path / "setup", profile_path=tmp_path / "missing.json")
    assert report.check_report.passed is True
    assert report.installed_profile is False
    assert report.passed is False
    assert "setup --yes" in report.next_command


def test_setup_with_yes_installs_profile(tmp_path):
    target = tmp_path / "term-chameleon-adaptive-glass.json"
    report = run_setup(
        output_dir=tmp_path / "setup",
        profile_path=target,
        yes=True,
        name="Setup Install",
    )
    assert report.check_report.passed is True
    assert report.installed_profile is True
    assert report.installed_profile_path == str(target)
    assert target.exists()
    assert report.status_after.profile_name == "Setup Install"
    assert report.passed is True


def test_setup_with_yes_honors_custom_profile_filename(tmp_path):
    target = tmp_path / "custom-profile.json"
    report = run_setup(
        output_dir=tmp_path / "setup",
        profile_path=target,
        yes=True,
        name="Custom Filename",
    )
    assert report.installed_profile_path == str(target)
    assert target.exists()
    assert not (tmp_path / "term-chameleon-adaptive-glass.json").exists()
    assert report.status_after.profile_name == "Custom Filename"


def test_setup_with_yes_replaces_bad_custom_profile_in_place(tmp_path):
    target = tmp_path / "custom-bad.json"
    target.write_text('{"Profiles": []}', encoding="utf-8")
    report = run_setup(
        output_dir=tmp_path / "setup",
        profile_path=target,
        yes=True,
        name="Replaced Custom",
    )
    assert report.installed_profile_path == str(target)
    assert target.exists()
    assert report.status_after.profile_name == "Replaced Custom"
    assert not (tmp_path / "term-chameleon-adaptive-glass.json").exists()


def test_setup_existing_profile_does_not_reinstall(tmp_path):
    target, _content = install_profile(target_dir=tmp_path, name="Existing Setup", dry_run=False)
    report = run_setup(output_dir=tmp_path / "setup", profile_path=target, yes=True)
    assert report.installed_profile is False
    assert report.status_after.profile_name == "Existing Setup"
    assert report.passed is True


def test_setup_cli_without_yes_returns_failure_for_missing_profile(tmp_path, capsys):
    target = tmp_path / "missing.json"
    assert main(["setup", "--profile", str(target), "--output-dir", str(tmp_path / "setup")]) == 1
    out = capsys.readouterr().out
    assert "rerun with --yes" in out
    assert "Recommended next command: term-chameleon setup --yes" in out


def test_setup_cli_with_yes_installs_profile(tmp_path, capsys):
    target = tmp_path / "term-chameleon-adaptive-glass.json"
    assert (
        main(
            [
                "setup",
                "--profile",
                str(target),
                "--output-dir",
                str(tmp_path / "setup"),
                "--yes",
                "--name",
                "CLI Setup",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "[ok] installed profile:" in out
    assert "Traceback" not in out
    assert target.exists()
