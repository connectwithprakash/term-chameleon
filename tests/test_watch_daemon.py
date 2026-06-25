from pathlib import Path

from term_chameleon.cli import main
from term_chameleon.watch_daemon import (
    install_watch_autolaunch_script,
    shell_command,
    watch_autolaunch_script,
    watch_live_command,
)


def test_watch_live_command_defaults_to_iterm_window():
    command = watch_live_command(executable="/tmp/python", interval=1, stable=2, cooldown=3)
    assert command[:4] == ("/tmp/python", "-m", "term_chameleon.cli", "watch-live")
    assert "--yes" in command
    assert "--iterm-window" in command
    assert "--duration" in command


def test_watch_live_command_supports_region_and_whole_screen():
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
    assert "--iterm-window" in out
    assert not (tmp_path / "term_chameleon_watch_live.py").exists()
