from pathlib import Path

from term_chameleon.cli import main
from term_chameleon.watch_daemon import (
    get_watch_daemon_status,
    install_watch_autolaunch_script,
    shell_command,
    uninstall_watch_autolaunch_script,
    watch_autolaunch_script,
    watch_live_command,
)


def test_watch_live_command_defaults_to_whole_screen():
    command = watch_live_command(executable="/tmp/python", interval=1, stable=2, cooldown=3)
    assert command[:4] == ("/tmp/python", "-m", "term_chameleon.cli", "watch-live")
    assert "--yes" in command
    assert "--iterm-window" not in command
    assert "--region" not in command
    assert "--duration" in command


def test_watch_live_command_supports_iterm_window_region_and_whole_screen():
    iterm_command = watch_live_command(executable="python", iterm_window=True)
    assert "--iterm-window" in iterm_command
    region_command = watch_live_command(executable="python", region="1,2,3,4")
    assert "--region" in region_command
    assert "--iterm-window" not in region_command
    whole_command = watch_live_command(executable="python", iterm_window=False)
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
                "/tmp/python",
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
                "/tmp/python",
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
