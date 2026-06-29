import sys
from pathlib import Path

from term_chameleon.cli import main
from term_chameleon.watch import Sample
from term_chameleon.watch_daemon import (
    get_watch_daemon_status,
    install_watch_autolaunch_script,
    pid_is_running,
    read_pid,
    shell_command,
    uninstall_watch_autolaunch_script,
    watch_autolaunch_script,
    watch_live_command,
)
from term_chameleon.watch_live import WatchLiveConfig, run_watch_live


def test_watch_live_command_defaults_to_whole_screen():
    command = watch_live_command(executable=sys.executable, interval=1, stable=2, cooldown=3)
    assert command[:4] == (sys.executable, "-m", "term_chameleon.cli", "watch-live")
    assert "--yes" in command
    assert "--iterm-window" not in command
    assert "--region" not in command
    assert "--duration" in command
    # Whole-screen mode must be pinned explicitly so the child cannot re-derive
    # the sampling mode from [watch] config (seam fix).
    assert "--whole-screen" in command


def test_watch_live_command_supports_iterm_window_region_and_whole_screen():
    iterm_command = watch_live_command(executable=sys.executable, iterm_window=True)
    assert "--iterm-window" in iterm_command
    assert "--whole-screen" not in iterm_command
    region_command = watch_live_command(executable=sys.executable, region="1,2,3,4")
    assert "--region" in region_command
    assert "--iterm-window" not in region_command
    assert "--whole-screen" not in region_command
    whole_command = watch_live_command(executable=sys.executable, iterm_window=False)
    assert "--iterm-window" not in whole_command
    assert "--region" not in whole_command
    assert "--whole-screen" in whole_command


def test_watch_live_command_whole_screen_pins_sampling_mode():
    """--whole-screen must be emitted when neither --region nor --iterm-window
    is set, so the child cannot re-derive the sampling mode from [watch] config.
    Regression: without this flag the child read [watch] iterm_window=true and
    silently switched to iTerm-window sampling while the installer had resolved
    whole-screen mode from [daemon] config.
    """
    cmd = watch_live_command(executable=sys.executable)
    assert "--whole-screen" in cmd
    assert "--iterm-window" not in cmd
    assert "--region" not in cmd


def test_watch_autolaunch_script_compiles():
    script = watch_autolaunch_script(
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        log_path=Path("/tmp/watch.log"),
        pid_path=Path("/tmp/watch.pid"),
    )
    compile(script, "watch.py", "exec")
    assert "subprocess.Popen" in script
    assert "PID_PATH" in script


def test_install_watch_autolaunch_script_dry_run(tmp_path):
    result = install_watch_autolaunch_script(
        target_dir=tmp_path,
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        dry_run=True,
    )
    assert result.target == tmp_path / "term_chameleon_watch_live.py"
    assert not result.target.exists()
    assert shell_command(result.command).startswith("python -m term_chameleon.cli")


def test_watch_daemon_status_reports_missing_script(tmp_path):
    status = get_watch_daemon_status(target_dir=tmp_path)
    assert status.installed is False
    assert status.executable is False
    assert status.healthy is False


def test_watch_daemon_status_reports_installed_script(tmp_path):
    install_watch_autolaunch_script(
        target_dir=tmp_path,
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        dry_run=False,
    )
    status = get_watch_daemon_status(target_dir=tmp_path)
    assert status.installed is True
    assert status.executable is True
    assert status.healthy is True


def test_uninstall_watch_autolaunch_script_removes_with_backup(tmp_path):
    install_watch_autolaunch_script(
        target_dir=tmp_path,
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        dry_run=False,
    )
    target = tmp_path / "term_chameleon_watch_live.py"
    result = uninstall_watch_autolaunch_script(target_dir=tmp_path, dry_run=False, backup=True)
    assert result.removed is True
    assert not target.exists()
    assert result.backup_path is not None
    assert result.backup_path.exists()


def test_backup_does_not_land_in_autolaunch_dir(tmp_path, monkeypatch):
    """iTerm2 runs every file in AutoLaunch on launch, so a .backup file left there
    triggers an error dialog. Backups must go to the app-state script-backups dir."""
    import term_chameleon.watch_daemon as wd

    backup_dir = tmp_path / "script-backups"
    monkeypatch.setattr(wd, "SCRIPT_BACKUP_DIR", backup_dir)

    install_watch_autolaunch_script(
        target_dir=tmp_path,
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        dry_run=False,
    )
    # Reinstall (creates a backup of the existing script) and uninstall (another backup).
    install_watch_autolaunch_script(
        target_dir=tmp_path,
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        dry_run=False,
    )
    uninstall_watch_autolaunch_script(target_dir=tmp_path, dry_run=False, backup=True)

    # No .backup files may remain in the AutoLaunch directory.
    assert not list(tmp_path.glob("*.backup.*"))
    # The backups live in the dedicated app-state dir instead.
    assert backup_dir.exists()
    assert list(backup_dir.glob("term_chameleon_watch_live.py.backup.*"))


def test_uninstall_watch_autolaunch_script_dry_run(tmp_path):
    install_watch_autolaunch_script(
        target_dir=tmp_path,
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        dry_run=False,
    )
    target = tmp_path / "term_chameleon_watch_live.py"
    result = uninstall_watch_autolaunch_script(target_dir=tmp_path, dry_run=True)
    assert result.removed is True
    assert target.exists()
    assert result.backup_path is None


def test_uninstall_watch_daemon_cli_no_backup(tmp_path):
    install_watch_autolaunch_script(
        target_dir=tmp_path,
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        dry_run=False,
    )
    assert main(["uninstall-watch-daemon", "--autolaunch-dir", str(tmp_path), "--no-backup"]) == 0
    assert not (tmp_path / "term_chameleon_watch_live.py").exists()
    assert not list(tmp_path.glob("*.backup.*"))


def test_watch_daemon_status_and_uninstall_use_config_paths(tmp_path, capsys):
    autolaunch = tmp_path / "configured-autolaunch"
    log_path = tmp_path / "configured.log"
    pid_path = tmp_path / "configured.pid"
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
[daemon]
autolaunch_dir = "{autolaunch}"
log_path = "{log_path}"
pid_path = "{pid_path}"
""".strip(),
        encoding="utf-8",
    )
    install_watch_autolaunch_script(
        target_dir=autolaunch,
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        dry_run=False,
    )
    assert main(["watch-daemon-status", "--config", str(config)]) == 0
    status_out = capsys.readouterr().out
    assert f"AutoLaunch script: {autolaunch / 'term_chameleon_watch_live.py'}" in status_out
    assert main(["uninstall-watch-daemon", "--config", str(config), "--no-backup"]) == 0
    assert not (autolaunch / "term_chameleon_watch_live.py").exists()


def test_install_watch_daemon_cli_dry_run(tmp_path, capsys):
    assert (
        main(
            [
                "install-watch-daemon",
                "--autolaunch-dir",
                str(tmp_path),
                "--python",
                sys.executable,
                "--interval",
                "1",
                "--stable",
                "2",
                "--cooldown",
                "3",
                "--dry-run",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "Would write watch AutoLaunch script" in out
    assert "--iterm-window" not in out
    assert not (tmp_path / "term_chameleon_watch_live.py").exists()


def test_install_watch_daemon_cli_iterm_window_opt_in(tmp_path, capsys):
    assert (
        main(
            [
                "install-watch-daemon",
                "--autolaunch-dir",
                str(tmp_path),
                "--python",
                sys.executable,
                "--iterm-window",
                "--dry-run",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "--iterm-window" in out


def test_watch_daemon_status_cli_json(tmp_path, capsys):
    install_watch_autolaunch_script(
        target_dir=tmp_path,
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        dry_run=False,
    )
    assert main(["watch-daemon-status", "--autolaunch-dir", str(tmp_path), "--json"]) == 0
    out = capsys.readouterr().out
    assert '"installed": true' in out
    assert '"executable": true' in out


def test_watch_daemon_status_cli_missing_returns_one(tmp_path, capsys):
    assert main(["watch-daemon-status", "--autolaunch-dir", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "Installed: no" in out
    assert "[warn]" in out


def test_uninstall_watch_daemon_cli_removes(tmp_path, capsys):
    install_watch_autolaunch_script(
        target_dir=tmp_path,
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        dry_run=False,
    )
    assert main(["uninstall-watch-daemon", "--autolaunch-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Removed:" in out
    assert not (tmp_path / "term_chameleon_watch_live.py").exists()


def test_uninstall_watch_daemon_cli_missing_returns_one(tmp_path, capsys):
    assert main(["uninstall-watch-daemon", "--autolaunch-dir", str(tmp_path)]) == 1
    assert "Not installed:" in capsys.readouterr().out


class _FakeClock:
    """Minimal fake clock for watch_live regression tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_cooldown_revert_preserves_candidate_state(tmp_path):
    """Regression: after a cooldown-blocked switch, the debounce candidate count must
    be preserved so the watcher switches to the new mode at the first sample after the
    cooldown expires, not after re-accumulating ``stable`` samples from scratch.

    Scenario (stable=2, cooldown=6, interval=2):
      s1 (bright 0.80, t=0): candidate_count→1; no switch
      s2 (bright 0.80, t=2): candidate_count→2 → switches to bright-safe;
                               next_allowed_switch = 2+6 = 8
      s3 (dark  0.20, t=4): candidate_count→1; switched=False (count<2)
      s4 (dark  0.20, t=6): candidate_count→2 → switched=True, BUT 6<8 → cooldown block;
                               with fix: candidate_count preserved at 1;
                               without fix: candidate_count reset to 0
      s5 (dark  0.20, t=8): cooldown has expired (8≥8)
                               with fix: count→2 → switches immediately to dark-glass ✓
                               without fix: count→1 → switched=False ✗ (one extra sample needed)
    """
    clock = _FakeClock()
    bright = Sample(0.80)
    dark = Sample(0.20)

    sequence = [bright, bright, dark, dark, dark]

    def provider(index: int, _output_dir: Path, _region):
        return sequence[index - 1], f"s{index}"

    events = run_watch_live(
        WatchLiveConfig(
            interval=2,
            duration=9,
            stable=2,
            cooldown=6,
            output_dir=tmp_path,
            dry_run=True,
            initial_mode="balanced",
        ),
        sample_provider=provider,
        sleep=clock.sleep,
        clock=clock,
    )

    assert len(events) == 5, f"expected 5 events, got {len(events)}: {events}"

    # s1: accumulating candidate, no switch
    assert events[0].mode == "balanced"
    assert events[0].switched is False

    # s2: candidate_count reaches stable=2 → first switch
    assert events[1].mode == "bright-safe"
    assert events[1].switched is True

    # s3: first dark sample, candidate_count=1 (< stable=2), no switch
    assert events[2].mode == "bright-safe"
    assert events[2].switched is False

    # s4: candidate_count=2 → would switch, but cooldown active → blocked
    assert events[3].mode == "bright-safe"
    assert events[3].switched is False
    assert "cooldown active" in events[3].message

    # s5: cooldown has just expired; because candidate state was preserved across
    # the s4 revert, candidate_count re-accumulates to 2 and the switch fires here.
    # Without the fix this event would be switched=False (only count=1 accumulated).
    assert events[4].switched is True, (
        "Expected switch at s5 (first sample after cooldown expiry) because the "
        "candidate count should have been preserved by the cooldown revert fix."
    )
    assert events[4].mode == "dark-glass"


# ---------------------------------------------------------------------------
# pid_is_running: reject non-positive PIDs (Finding R2-watch #7)
# ---------------------------------------------------------------------------


def test_pid_is_running_rejects_zero():
    """pid_is_running(0) must return False without calling os.kill(0, 0),
    which would target the current process group and always succeed.
    """
    assert pid_is_running(0) is False


def test_pid_is_running_rejects_negative():
    """pid_is_running(-1) must return False; os.kill(-1, 0) targets all
    signalable processes and always succeeds.
    """
    assert pid_is_running(-1) is False


def test_pid_is_running_accepts_current_process():
    """pid_is_running returns True for the current process (a valid positive PID)."""
    import os

    assert pid_is_running(os.getpid()) is True


# ---------------------------------------------------------------------------
# read_pid: reject non-positive PIDs written to file
# ---------------------------------------------------------------------------


def test_read_pid_rejects_zero(tmp_path):
    pid_file = tmp_path / "watch.pid"
    pid_file.write_text("0\n", encoding="utf-8")
    assert read_pid(pid_file) is None


def test_read_pid_rejects_negative(tmp_path):
    pid_file = tmp_path / "watch.pid"
    pid_file.write_text("-1\n", encoding="utf-8")
    assert read_pid(pid_file) is None


def test_read_pid_accepts_valid(tmp_path):
    import os

    pid_file = tmp_path / "watch.pid"
    pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
    assert read_pid(pid_file) == os.getpid()


# ---------------------------------------------------------------------------
# Generated autolaunch script: pid<=0 guard + TC_WATCH_PID_PATH env var
# (Finding R2-watch #5 and #7)
# ---------------------------------------------------------------------------


def test_autolaunch_script_has_pid_le_zero_guard():
    """The generated script must guard against non-positive PIDs in both
    _pid_is_running and _existing_watcher_running.
    """
    script = watch_autolaunch_script(
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        log_path=Path("/tmp/watch.log"),
        pid_path=Path("/tmp/watch.pid"),
    )
    assert "if pid <= 0:" in script, "generated script must reject pid <= 0"


def test_autolaunch_script_sets_tc_watch_pid_path_env():
    """The generated script must pass TC_WATCH_PID_PATH to the child process
    so that the watch-live process owns and cleans up the PID file.
    """
    script = watch_autolaunch_script(
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        log_path=Path("/tmp/watch.log"),
        pid_path=Path("/tmp/watch.pid"),
    )
    assert "TC_WATCH_PID_PATH" in script, (
        "generated script must set TC_WATCH_PID_PATH so the child owns its PID file"
    )
    assert 'env["TC_WATCH_PID_PATH"]' in script or "env['TC_WATCH_PID_PATH']" in script


def test_autolaunch_script_does_not_write_pid_itself():
    """The generated script must NOT write the PID file directly; the child
    process (watch-live) owns the PID file via TC_WATCH_PID_PATH.
    """
    script = watch_autolaunch_script(
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        log_path=Path("/tmp/watch.log"),
        pid_path=Path("/tmp/watch.pid"),
    )
    # PID_PATH.write_text must not appear after the main() function body
    main_body = script.split("def main()")[1]
    assert "PID_PATH.write_text" not in main_body, (
        "generated script must not write PID itself; child process owns the PID file"
    )


def test_autolaunch_script_compiles_with_new_guards():
    """Ensure the updated generated script is still valid Python."""
    script = watch_autolaunch_script(
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        log_path=Path("/tmp/watch.log"),
        pid_path=Path("/tmp/watch.pid"),
    )
    compile(script, "watch_autolaunch.py", "exec")


# ---------------------------------------------------------------------------
# _setup_pid_ownership: writes PID and registers atexit cleanup
# (Finding R2-watch #5)
# ---------------------------------------------------------------------------


def test_setup_pid_ownership_writes_pid_from_env(tmp_path, monkeypatch):
    """When TC_WATCH_PID_PATH is set, _setup_pid_ownership writes the current
    PID to that path at startup.
    """
    import os

    pid_file = tmp_path / "test.pid"
    monkeypatch.setenv("TC_WATCH_PID_PATH", str(pid_file))

    from term_chameleon.watch_live import _setup_pid_ownership

    _setup_pid_ownership()

    assert pid_file.exists(), "PID file must be written when TC_WATCH_PID_PATH is set"
    written = pid_file.read_text(encoding="utf-8").strip()
    assert written == str(os.getpid()), f"PID file must contain current PID; got {written!r}"


def test_setup_pid_ownership_noop_without_env(tmp_path, monkeypatch):
    """When TC_WATCH_PID_PATH is not set, _setup_pid_ownership is a no-op."""
    monkeypatch.delenv("TC_WATCH_PID_PATH", raising=False)

    from term_chameleon.watch_live import _setup_pid_ownership

    _setup_pid_ownership()
    assert not list(tmp_path.iterdir()), "no files should be created without TC_WATCH_PID_PATH"
