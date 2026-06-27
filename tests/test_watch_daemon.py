import sys
from pathlib import Path

from term_chameleon.cli import main
from term_chameleon.watch import Sample
from term_chameleon.watch_daemon import (
    get_watch_daemon_status,
    install_watch_autolaunch_script,
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


def test_watch_live_command_supports_iterm_window_region_and_whole_screen():
    iterm_command = watch_live_command(executable=sys.executable, iterm_window=True)
    assert "--iterm-window" in iterm_command
    region_command = watch_live_command(executable=sys.executable, region="1,2,3,4")
    assert "--region" in region_command
    assert "--iterm-window" not in region_command
    whole_command = watch_live_command(executable=sys.executable, iterm_window=False)
    assert "--iterm-window" not in whole_command
    assert "--region" not in whole_command


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
