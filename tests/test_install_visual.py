import json
import shutil
from pathlib import Path

from term_chameleon.cli import main
from term_chameleon.install import (
    _guid_for_name,
    install_autolaunch_script,
    install_balanced_profile,
    install_profile,
    uninstall_profile,
)
from term_chameleon.iterm_profile import load_profile, loads_document
from term_chameleon.modes import apply_mode
from term_chameleon.osc import OscSequence, sequences_for_preset, shell_printf, tmux_wrap
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


def test_install_existing_profile_creates_backup(tmp_path):
    assert main(["install", "--target-dir", str(tmp_path), "--name", "One"]) == 0
    assert main(["install", "--target-dir", str(tmp_path), "--name", "Two"]) == 0
    backups = list(tmp_path.glob("term-chameleon-adaptive-glass.json.backup.*"))
    assert len(backups) == 1
    assert (
        loads_document((tmp_path / "term-chameleon-adaptive-glass.json").read_text()).name == "Two"
    )


def test_install_make_default_writes_compiling_autolaunch(tmp_path, capsys):
    profiles = tmp_path / "profiles"
    autolaunch = tmp_path / "autolaunch"
    assert (
        main(
            [
                "install",
                "--target-dir",
                str(profiles),
                "--autolaunch-dir",
                str(autolaunch),
                "--name",
                "Test Glass",
                "--make-default",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "AutoLaunch script compiles" in out
    script = autolaunch / "term_chameleon_default_profile.py"
    assert script.exists()
    assert "PROFILE_NAME = 'Test Glass'" in script.read_text()


def test_autolaunch_script_dry_run_compiles(tmp_path):
    target, content = install_autolaunch_script(target_dir=tmp_path, dry_run=True)
    assert target.name == "term_chameleon_default_profile.py"
    compile(content, str(target), "exec")
    assert not target.exists()


def test_apply_mode_to_profile_copy(tmp_path):
    target = tmp_path / "profile.json"
    shutil.copy2(FIXTURES / "good-dark-glass.json", target)
    changes, remaining = apply_mode(target, "presentation", dry_run=False, yes=True)
    assert changes
    assert not [d for d in remaining if d.severity == "fail"]
    profile = load_profile(target)
    assert profile.transparency() == 0.0
    assert list(tmp_path.glob("profile.json.backup.*"))


def test_repeated_mode_writes_create_unique_backups(tmp_path):
    target = tmp_path / "profile.json"
    shutil.copy2(FIXTURES / "good-dark-glass.json", target)
    apply_mode(target, "presentation", dry_run=False, yes=True)
    apply_mode(target, "balanced", dry_run=False, yes=True)
    assert len(list(tmp_path.glob("profile.json.backup.*"))) == 2


def test_mode_command_requires_yes_or_dry_run(capsys):
    assert main(["mode", "presentation", str(FIXTURES / "good-dark-glass.json")]) == 2
    assert "Refusing to write" in capsys.readouterr().err


def test_multi_profile_document_is_rejected(tmp_path, capsys):
    good = json.loads((FIXTURES / "good-dark-glass.json").read_text())["Profiles"][0]
    bad = json.loads((FIXTURES / "bad-light-variant.json").read_text())["Profiles"][0]
    multi = tmp_path / "multi.json"
    multi.write_text(json.dumps({"Profiles": [good, bad]}))
    assert main(["doctor", str(multi)]) == 2
    assert "exactly one profile" in capsys.readouterr().err


def test_osc_sequences_include_core_controls():
    seqs = sequences_for_preset("balanced")
    escaped = "".join(s.escaped() for s in seqs)
    assert r"\x1b]10;#E5EBF5" in escaped
    assert r"\x1b]11;#090C16" in escaped
    assert r"\x1b]4;0;#6B7280" in escaped
    assert r"\x1b]4;8;#9CA3AF" in escaped


def test_tmux_wrap_and_shell_printf():
    wrapped = tmux_wrap("\x1b]11;#090C16\x1b\\")
    assert wrapped.startswith("\x1bPtmux;")
    assert "\x1b\x1b]11" in wrapped
    command = shell_printf(sequences_for_preset("balanced"), tmux=True)
    assert command.startswith("printf %b ")
    assert "Ptmux" in command


def test_shell_printf_quotes_payloads():
    command = shell_printf([OscSequence("synthetic", "abc'def")])
    assert "'\"'\"'" in command


def test_osc_cli(capsys):
    assert main(["osc", "apply", "balanced", "--shell"]) == 0
    out = capsys.readouterr().out
    assert "printf" in out
    assert r"\x1b]10;#E5EBF5" in out


def test_visual_report_writes_artifacts(tmp_path):
    json_path, md_path, checks = write_visual_report(FIXTURES / "good-dark-glass.json", tmp_path)
    assert json_path.exists()
    assert md_path.exists()
    assert (tmp_path / "ansi-pattern.txt").exists()
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


# --- Fix: derive GUID deterministically from profile name ---


def test_guid_for_same_name_is_stable():
    """Same name always produces the same GUID."""
    assert _guid_for_name("Adaptive Glass") == _guid_for_name("Adaptive Glass")


def test_guid_for_different_names_differ():
    """Different names produce different GUIDs."""
    assert _guid_for_name("Adaptive Glass") != _guid_for_name("Custom Name")


def test_profile_document_guid_is_derived_from_name():
    """profile_document derives GUID from name, not a hardcoded literal."""
    from term_chameleon.install import profile_document

    doc1 = profile_document(name="Adaptive Glass")
    doc2 = profile_document(name="My Profile")
    g1 = doc1["Profiles"][0]["Guid"]
    g2 = doc2["Profiles"][0]["Guid"]
    assert g1 != g2
    assert g1.startswith("TERM-CHAMELEON-")
    assert g2.startswith("TERM-CHAMELEON-")


def test_profile_document_explicit_guid_is_respected():
    """Passing guid= overrides derived GUID."""
    from term_chameleon.install import profile_document

    doc = profile_document(name="Adaptive Glass", guid="MY-CUSTOM-GUID")
    assert doc["Profiles"][0]["Guid"] == "MY-CUSTOM-GUID"


# --- Fix: skip backup when re-install content is byte-identical ---


def test_identical_reinstall_does_not_create_backup(tmp_path):
    """Installing the same profile twice must not create a backup on the second install."""
    install_profile(target_dir=tmp_path, name="Glass")
    install_profile(target_dir=tmp_path, name="Glass")
    backups = list(tmp_path.glob("term-chameleon-adaptive-glass.json.backup.*"))
    assert len(backups) == 0


def test_changed_reinstall_creates_backup(tmp_path):
    """Installing a different profile name should produce a backup."""
    install_profile(target_dir=tmp_path, name="First")
    install_profile(target_dir=tmp_path, name="Second")
    backups = list(tmp_path.glob("term-chameleon-adaptive-glass.json.backup.*"))
    assert len(backups) == 1


def test_identical_autolaunch_reinstall_does_not_create_backup(tmp_path):
    """Re-installing the same AutoLaunch script must not create a backup."""
    install_autolaunch_script(target_dir=tmp_path, profile_name="Glass")
    install_autolaunch_script(target_dir=tmp_path, profile_name="Glass")
    backups = list(tmp_path.glob("term_chameleon_default_profile.py.backup.*"))
    assert len(backups) == 0


def test_changed_autolaunch_reinstall_creates_backup(tmp_path):
    """Re-installing AutoLaunch with a different profile name should produce a backup."""
    install_autolaunch_script(target_dir=tmp_path, profile_name="First")
    install_autolaunch_script(target_dir=tmp_path, profile_name="Second")
    backups = list(tmp_path.glob("term_chameleon_default_profile.py.backup.*"))
    assert len(backups) == 1


# --- Fix: uninstall_profile function ---


def test_uninstall_profile_removes_profile_and_script(tmp_path):
    """uninstall_profile removes both the profile JSON and the AutoLaunch script."""
    profiles_dir = tmp_path / "profiles"
    autolaunch_dir = tmp_path / "autolaunch"
    state_dir = tmp_path / "state"
    install_profile(target_dir=profiles_dir, name="Glass")
    install_autolaunch_script(target_dir=autolaunch_dir, profile_name="Glass")
    result = uninstall_profile(
        target_dir=profiles_dir,
        autolaunch_dir=autolaunch_dir,
        app_state_dir=state_dir,
        dry_run=False,
        backup=True,
    )
    assert result.profile_removed is True
    assert result.autolaunch_removed is True
    assert not result.profile_target.exists()
    assert not result.autolaunch_target.exists()
    assert result.profile_backup_path is not None
    assert result.profile_backup_path.exists()
    assert result.autolaunch_backup_path is not None
    assert result.autolaunch_backup_path.exists()


def test_uninstall_profile_never_installed_is_graceful(tmp_path):
    """uninstall_profile on a never-installed state returns removed=False without error."""
    result = uninstall_profile(
        target_dir=tmp_path / "profiles",
        autolaunch_dir=tmp_path / "autolaunch",
        app_state_dir=tmp_path / "state",
        dry_run=False,
        backup=True,
    )
    assert result.profile_removed is False
    assert result.autolaunch_removed is False
    assert result.profile_backup_path is None
    assert result.autolaunch_backup_path is None


def test_uninstall_profile_dry_run_does_not_remove(tmp_path):
    """uninstall_profile --dry-run reports what would be removed but leaves files intact."""
    profiles_dir = tmp_path / "profiles"
    autolaunch_dir = tmp_path / "autolaunch"
    install_profile(target_dir=profiles_dir, name="Glass")
    install_autolaunch_script(target_dir=autolaunch_dir, profile_name="Glass")
    result = uninstall_profile(
        target_dir=profiles_dir,
        autolaunch_dir=autolaunch_dir,
        app_state_dir=tmp_path / "state",
        dry_run=True,
        backup=True,
    )
    # Reports removed=True (would remove) but files are still present.
    assert result.profile_removed is True
    assert result.autolaunch_removed is True
    assert result.profile_target.exists()
    assert result.autolaunch_target.exists()
    # No backup created on dry-run.
    assert result.profile_backup_path is None
    assert result.autolaunch_backup_path is None


def test_uninstall_profile_no_backup_option(tmp_path):
    """uninstall_profile with backup=False removes files without creating backups."""
    profiles_dir = tmp_path / "profiles"
    autolaunch_dir = tmp_path / "autolaunch"
    install_profile(target_dir=profiles_dir, name="Glass")
    install_autolaunch_script(target_dir=autolaunch_dir, profile_name="Glass")
    result = uninstall_profile(
        target_dir=profiles_dir,
        autolaunch_dir=autolaunch_dir,
        app_state_dir=tmp_path / "state",
        dry_run=False,
        backup=False,
    )
    assert result.profile_removed is True
    assert result.autolaunch_removed is True
    assert result.profile_backup_path is None
    assert result.autolaunch_backup_path is None


def test_uninstall_profile_reads_previous_default_guid(tmp_path):
    """uninstall_profile reads the persisted previous-default GUID if it exists."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "previous-default-guid.txt").write_text("MY-GUID-BEFORE", encoding="utf-8")
    result = uninstall_profile(
        target_dir=tmp_path / "profiles",
        autolaunch_dir=tmp_path / "autolaunch",
        app_state_dir=state_dir,
        dry_run=False,
        backup=False,
    )
    assert result.previous_default_guid == "MY-GUID-BEFORE"


def test_uninstall_profile_missing_guid_file_returns_none(tmp_path):
    """uninstall_profile returns previous_default_guid=None if the GUID file is absent."""
    result = uninstall_profile(
        target_dir=tmp_path / "profiles",
        autolaunch_dir=tmp_path / "autolaunch",
        app_state_dir=tmp_path / "state",
        dry_run=False,
        backup=False,
    )
    assert result.previous_default_guid is None


def test_uninstall_profile_partial_install_only_profile(tmp_path):
    """uninstall_profile handles partial installs: only profile present, no AutoLaunch script."""
    profiles_dir = tmp_path / "profiles"
    install_profile(target_dir=profiles_dir, name="Glass")
    result = uninstall_profile(
        target_dir=profiles_dir,
        autolaunch_dir=tmp_path / "autolaunch",
        app_state_dir=tmp_path / "state",
        dry_run=False,
        backup=True,
    )
    assert result.profile_removed is True
    assert result.autolaunch_removed is False
    assert not result.profile_target.exists()


def test_uninstall_profile_partial_install_only_autolaunch(tmp_path):
    """uninstall_profile handles partial installs: only AutoLaunch script present."""
    autolaunch_dir = tmp_path / "autolaunch"
    install_autolaunch_script(target_dir=autolaunch_dir, profile_name="Glass")
    result = uninstall_profile(
        target_dir=tmp_path / "profiles",
        autolaunch_dir=autolaunch_dir,
        app_state_dir=tmp_path / "state",
        dry_run=False,
        backup=True,
    )
    assert result.profile_removed is False
    assert result.autolaunch_removed is True
    assert not result.autolaunch_target.exists()
