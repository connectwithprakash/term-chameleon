from pathlib import Path

from term_chameleon.cli import _watch_live, main
from term_chameleon.config import EXAMPLE_CONFIG, ConfigError, load_config, validate_config


def test_config_example_cli_prints_toml(capsys):
    assert main(["config-example"]) == 0
    out = capsys.readouterr().out
    assert "[watch]" in out
    assert "[daemon]" in out
    assert "[setup]" in out


def test_config_example_cli_writes_file(tmp_path, capsys):
    target = tmp_path / "config.toml"
    assert main(["config-example", "--output", str(target)]) == 0
    assert target.read_text(encoding="utf-8") == EXAMPLE_CONFIG
    assert f"Wrote: {target}" in capsys.readouterr().out


def test_load_config_rejects_missing_file(tmp_path):
    try:
        load_config(tmp_path / "missing.toml")
    except ConfigError as exc:
        assert "config file not found" in str(exc)
    else:
        raise AssertionError("expected ConfigError")


def test_validate_config_reports_errors_and_warnings():
    validation = validate_config(
        {
            "watch": {
                "interval": "fast",
                "initial_mode": "bogus",
                "region": "1,2,0,4",
                "iterm_window": True,
                "extra": 123,
            },
            "unknown": {},
        },
        path="/tmp/config.toml",
    )
    assert validation.passed is False
    joined_errors = "\n".join(validation.errors)
    joined_warnings = "\n".join(validation.warnings)
    assert "[watch].interval" in joined_errors
    assert "unknown preset/mode 'bogus'" in joined_errors
    assert "width and height must be positive" in joined_errors
    assert "unknown top-level section [unknown]" in joined_errors
    assert "unknown key [watch].extra" in joined_errors
    assert "region takes precedence" in joined_warnings


def test_config_check_cli_success_json(tmp_path, capsys):
    config_path = tmp_path / "config.toml"
    config_path.write_text(EXAMPLE_CONFIG, encoding="utf-8")
    assert main(["config-check", "--config", str(config_path), "--json"]) == 0
    out = capsys.readouterr().out
    assert '"passed": true' in out
    assert '"errors": []' in out


def test_config_check_cli_validation_failure(tmp_path, capsys):
    config_path = tmp_path / "config.toml"
    config_path.write_text('[watch]\ninterval = "fast"\n', encoding="utf-8")
    assert main(["config-check", "--config", str(config_path)]) == 1
    out = capsys.readouterr().out
    assert "[fail] [watch].interval" in out
    assert "config has validation errors" in out


def test_config_check_rejects_runtime_range_mismatches(tmp_path, capsys):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[watch]
interval = -1.0
duration = 0.0
stable = 0
cooldown = -0.1
""".strip(),
        encoding="utf-8",
    )
    assert main(["config-check", "--config", str(config_path)]) == 1
    out = capsys.readouterr().out
    assert "[watch].interval: expected number > 0" in out
    assert "[watch].duration: expected number > 0" in out
    assert "[watch].stable: expected integer >= 1" in out
    assert "[watch].cooldown: expected number >= 0" in out


def test_config_check_rejects_unknown_section_and_key(tmp_path, capsys):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[watc]
interval = 1.0

[watch]
intervl = 1.0
""".strip(),
        encoding="utf-8",
    )
    assert main(["config-check", "--config", str(config_path)]) == 1
    out = capsys.readouterr().out
    assert "unknown top-level section [watc]" in out
    assert "unknown key [watch].intervl" in out


def test_config_check_rejects_daemon_duration_as_unused(tmp_path, capsys):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[daemon]\nduration = 5\n", encoding="utf-8")
    assert main(["config-check", "--config", str(config_path)]) == 1
    assert "unknown key [daemon].duration" in capsys.readouterr().out


def test_config_check_cli_missing_file_returns_usage_error(tmp_path, capsys):
    assert main(["config-check", "--config", str(tmp_path / "missing.toml")]) == 2
    assert "config file not found" in capsys.readouterr().err


def test_watch_live_uses_config_values(monkeypatch, tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[watch]
interval = 0.5
duration = 3.5
stable = 2
cooldown = 4.0
output_dir = "configured-output"
initial_mode = "dark-glass"
region = "1,2,3,4"
""".strip(),
        encoding="utf-8",
    )
    seen = {}

    def fake_run_watch_live(config):
        seen["config"] = config
        return []

    import term_chameleon.cli as cli_module

    monkeypatch.setattr(cli_module, "run_watch_live", fake_run_watch_live)
    assert (
        _watch_live(
            interval=None,
            duration=None,
            stable=None,
            cooldown=None,
            output_dir=None,
            initial_mode=None,
            region=None,
            iterm_window=False,
            dry_run=True,
            yes=False,
            config=config_path,
        )
        == 0
    )
    cfg = seen["config"]
    assert cfg.interval == 0.5
    assert cfg.duration == 3.5
    assert cfg.stable == 2
    assert cfg.cooldown == 4.0
    assert cfg.output_dir == Path("configured-output")
    assert cfg.initial_mode == "dark-glass"
    assert str(cfg.region) == "1,2,3,4"


def test_watch_live_cli_flags_override_config(monkeypatch, tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[watch]
interval = 9.0
duration = 9.0
stable = 9
cooldown = 9.0
output_dir = "configured-output"
initial_mode = "dark-glass"
iterm_window = true
""".strip(),
        encoding="utf-8",
    )
    seen = {}

    def fake_run_watch_live(config):
        seen["config"] = config
        return []

    import term_chameleon.cli as cli_module

    monkeypatch.setattr(cli_module, "run_watch_live", fake_run_watch_live)
    assert (
        main(
            [
                "watch-live",
                "--config",
                str(config_path),
                "--dry-run",
                "--interval",
                "1.0",
                "--duration",
                "1.5",
                "--stable",
                "1",
                "--cooldown",
                "0",
                "--output-dir",
                str(tmp_path / "out"),
                "--initial-mode",
                "balanced",
                "--region",
                "5,6,7,8",
            ]
        )
        == 0
    )
    cfg = seen["config"]
    assert cfg.interval == 1.0
    assert cfg.duration == 1.5
    assert cfg.stable == 1
    assert cfg.cooldown == 0.0
    assert cfg.output_dir == tmp_path / "out"
    assert cfg.initial_mode == "balanced"
    assert str(cfg.region) == "5,6,7,8"
    assert cfg.iterm_window is False


def test_watch_live_iterm_window_flag_clears_config_region(monkeypatch, tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[watch]
region = "1,2,3,4"
iterm_window = false
""".strip(),
        encoding="utf-8",
    )
    seen = {}

    def fake_run_watch_live(config):
        seen["config"] = config
        return []

    import term_chameleon.cli as cli_module

    monkeypatch.setattr(cli_module, "run_watch_live", fake_run_watch_live)
    assert main(["watch-live", "--config", str(config_path), "--dry-run", "--iterm-window"]) == 0
    cfg = seen["config"]
    assert cfg.region is None
    assert cfg.iterm_window is True


def test_watch_live_rejects_invalid_config_initial_mode(monkeypatch, tmp_path, capsys):
    config_path = tmp_path / "config.toml"
    config_path.write_text('[watch]\ninitial_mode = "bogus"\n', encoding="utf-8")

    import term_chameleon.cli as cli_module

    monkeypatch.setattr(cli_module, "run_watch_live", lambda _config: [])
    assert main(["watch-live", "--config", str(config_path), "--dry-run"]) == 2
    assert "unknown preset/mode" in capsys.readouterr().err


def test_install_watch_daemon_rejects_invalid_config_initial_mode(tmp_path, capsys):
    config_path = tmp_path / "config.toml"
    config_path.write_text('[daemon]\ninitial_mode = "bogus"\n', encoding="utf-8")
    assert main(["install-watch-daemon", "--config", str(config_path), "--dry-run"]) == 2
    assert "unknown preset/mode" in capsys.readouterr().err


def test_install_watch_daemon_uses_config_in_dry_run(tmp_path, capsys):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
[watch]
interval = 7.0
stable = 4
cooldown = 11.0
output_dir = "{tmp_path / "watch-artifacts"}"
initial_mode = "bright-safe"
region = "10,20,30,40"

[daemon]
autolaunch_dir = "{tmp_path / "autolaunch"}"
log_path = "{tmp_path / "watch.log"}"
pid_path = "{tmp_path / "watch.pid"}"
python = "/usr/bin/python3"
""".strip(),
        encoding="utf-8",
    )
    assert main(["install-watch-daemon", "--config", str(config_path), "--dry-run"]) == 0
    out = capsys.readouterr().out
    expected_target = tmp_path / "autolaunch" / "term_chameleon_watch_live.py"
    assert f"Would write watch AutoLaunch script: {expected_target}" in out
    assert "--interval 7.0" in out
    assert "--stable 4" in out
    assert "--cooldown 11.0" in out
    assert "--initial-mode bright-safe" in out
    assert "--region 10,20,30,40" in out
    assert f"Log path: {tmp_path / 'watch.log'}" in out
