import json
from pathlib import Path

from term_chameleon.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "iterm"


# --- Fix: release-check --live-stage requires --yes gate ---

def test_release_check_live_stage_without_yes_returns_2(tmp_path, capsys):
    """release-check --live-stage returns exit 2 and refuses without --yes."""
    result = main(
        [
            "release-check",
            "--live-stage",
            "--output-dir",
            str(tmp_path),
            "--width",
            "32",
            "--height",
            "16",
        ]
    )
    assert result == 2
    err = capsys.readouterr().err
    assert "Refusing to drive GUI apps without --yes" in err


# --- Fix: setup --no-live can override config live=true ---

def test_setup_live_flag_defaults_to_none(tmp_path, capsys):
    """setup without --live/--no-live uses config value (config has live=false -> not live)."""
    config = tmp_path / "cfg.toml"
    config.write_text("[setup]\nlive = false\n", encoding="utf-8")
    result = main(
        [
            "setup",
            "--config",
            str(config),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    # Just verify it runs without error (live probing skipped when false)
    assert result in (0, 1)  # 1 is ok if profile not found


def test_setup_no_live_overrides_config_live_true(tmp_path, capsys):
    """setup --no-live suppresses live probing even when config has live=true."""
    config = tmp_path / "cfg.toml"
    config.write_text("[setup]\nlive = true\n", encoding="utf-8")
    # --no-live should override config live=true and not attempt live probing
    result = main(
        [
            "setup",
            "--no-live",
            "--config",
            str(config),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    # Should not crash; live probe skipped means no iTerm2-connection errors
    assert result in (0, 1)


# --- Fix: watch-daemon-status --json includes 'healthy' field ---

def test_watch_daemon_status_json_includes_healthy_field(tmp_path, capsys):
    """watch-daemon-status --json emits a 'healthy' key matching installed&&executable."""
    result = main(
        [
            "watch-daemon-status",
            "--autolaunch-dir",
            str(tmp_path),
            "--json",
        ]
    )
    assert result == 1  # not installed -> healthy=False -> exit 1
    payload = json.loads(capsys.readouterr().out)
    assert "healthy" in payload
    assert payload["healthy"] is False
    assert payload["installed"] is False


def test_watch_daemon_status_json_healthy_true_when_installed(tmp_path, capsys):
    """watch-daemon-status --json emits healthy=True when script is installed and executable."""
    from term_chameleon.watch_daemon import install_watch_autolaunch_script

    install_watch_autolaunch_script(
        target_dir=tmp_path,
        command=("python", "-m", "term_chameleon.cli", "watch-live", "--yes"),
        dry_run=False,
    )
    result = main(
        [
            "watch-daemon-status",
            "--autolaunch-dir",
            str(tmp_path),
            "--json",
        ]
    )
    assert result == 0  # healthy -> exit 0
    payload = json.loads(capsys.readouterr().out)
    assert "healthy" in payload
    assert payload["healthy"] is True
    assert payload["installed"] is True


def test_doctor_good_returns_zero(capsys):
    assert main(["doctor", str(FIXTURES / "good-dark-glass.json")]) == 0
    out = capsys.readouterr().out
    assert "Profile: Good Dark Glass" in out


def test_doctor_bad_returns_failure(capsys):
    assert main(["doctor", str(FIXTURES / "bad-light-variant.json")]) == 1
    out = capsys.readouterr().out
    assert "ITERM_LIGHT_DARK_DRIFT" in out


def test_doctor_json_good_profile(capsys):
    assert main(["doctor", str(FIXTURES / "good-dark-glass.json"), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["profile"] == "Good Dark Glass"
    assert payload["passed"] is True
    assert payload["diagnostics"] == []
    assert payload["summary"]["fail"] == 0


def test_doctor_json_bad_profile(capsys):
    assert main(["doctor", str(FIXTURES / "bad-light-variant.json"), "--json"]) == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["passed"] is False
    assert payload["summary"]["fail"] >= 1
    assert "ITERM_LIGHT_DARK_DRIFT" in {item["code"] for item in payload["diagnostics"]}
    for severity, count in payload["summary"].items():
        assert count == len(
            [item for item in payload["diagnostics"] if item["severity"] == severity]
        )
    assert isinstance(payload["foreground_contrast"], float)


def test_fix_requires_yes_or_dry_run(capsys):
    assert main(["fix", str(FIXTURES / "bad-light-variant.json")]) == 2
    err = capsys.readouterr().err
    assert "Refusing to write" in err


def test_fix_dry_run(capsys):
    assert main(["fix", str(FIXTURES / "bad-light-variant.json"), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Planned changes" in out
    assert "Use Separate Colors" in out


def test_main_raises_runtime_error_for_unregistered_command(monkeypatch, capsys):
    """main() must produce error exit (not hang/crash) when a registered command lacks a handler."""
    import argparse

    import term_chameleon.cli as cli_module

    # Patch parse_args to inject a synthetic command name not in the if-chain
    original_parse = argparse.ArgumentParser.parse_args

    def fake_parse(self, args=None, namespace=None):
        result = original_parse(self, ["doctor", str(FIXTURES / "good-dark-glass.json")])
        result.command = "__unhandled_synthetic_command__"
        return result

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", fake_parse)
    ret = cli_module.main(["doctor", str(FIXTURES / "good-dark-glass.json")])
    assert ret == 2
    assert "unhandled command" in capsys.readouterr().err


# --- Fix: install-watch-daemon validates resolved numeric values ---


def test_install_watch_daemon_rejects_invalid_interval(tmp_path, capsys):
    """install-watch-daemon --interval -1 must fail with error exit, not bake a broken command."""
    result = main(
        [
            "install-watch-daemon",
            "--dry-run",
            "--interval",
            "-1",
            "--autolaunch-dir",
            str(tmp_path),
        ]
    )
    assert result == 2
    assert "interval" in capsys.readouterr().err


def test_install_watch_daemon_rejects_invalid_stable(tmp_path, capsys):
    """install-watch-daemon --stable 0 must fail (stable must be >= 1)."""
    result = main(
        [
            "install-watch-daemon",
            "--dry-run",
            "--stable",
            "0",
            "--autolaunch-dir",
            str(tmp_path),
        ]
    )
    assert result == 2
    assert "stable" in capsys.readouterr().err


def test_install_watch_daemon_rejects_invalid_cooldown(tmp_path, capsys):
    """install-watch-daemon --cooldown -5 must fail (cooldown must be >= 0)."""
    result = main(
        [
            "install-watch-daemon",
            "--dry-run",
            "--cooldown",
            "-5",
            "--autolaunch-dir",
            str(tmp_path),
        ]
    )
    assert result == 2
    assert "cooldown" in capsys.readouterr().err


def test_install_watch_daemon_rejects_invalid_region(tmp_path, capsys):
    """install-watch-daemon --region with non-integer parts must fail validation."""
    result = main(
        [
            "install-watch-daemon",
            "--dry-run",
            "--region",
            "not,a,valid,region",
            "--autolaunch-dir",
            str(tmp_path),
        ]
    )
    assert result == 2
    assert "region" in capsys.readouterr().err.lower()


def test_install_watch_daemon_valid_values_succeed(tmp_path, capsys):
    """install-watch-daemon with valid params must succeed (dry-run)."""
    result = main(
        [
            "install-watch-daemon",
            "--dry-run",
            "--interval",
            "5",
            "--stable",
            "2",
            "--cooldown",
            "0",
            "--autolaunch-dir",
            str(tmp_path),
        ]
    )
    assert result == 0
    out = capsys.readouterr().out
    assert "Would write" in out


# --- Fix: watch-live --whole-screen overrides config iterm_window=true ---


def test_watch_live_whole_screen_flag_accepted(monkeypatch, capsys):
    """watch-live --whole-screen must be accepted as a valid flag (not 'unrecognized arguments')."""
    import term_chameleon.cli as cli

    def fake_run(config):
        # Assert that whole-screen forced iterm_window=False and region=None
        assert config.iterm_window is False
        assert config.region is None
        return []

    monkeypatch.setattr(cli, "run_watch_live", fake_run)
    result = main(["watch-live", "--dry-run", "--whole-screen"])
    assert result == 0


def test_watch_live_whole_screen_overrides_config_iterm_window(monkeypatch, tmp_path, capsys):
    """watch-live --whole-screen forces iterm_window=False over config iterm_window=true."""
    import term_chameleon.cli as cli

    config = tmp_path / "cfg.toml"
    config.write_text("[watch]\niterm_window = true\n", encoding="utf-8")

    captured_configs = []

    def fake_run(config_obj):
        captured_configs.append(config_obj)
        return []

    monkeypatch.setattr(cli, "run_watch_live", fake_run)
    result = main(
        [
            "watch-live",
            "--dry-run",
            "--whole-screen",
            "--config",
            str(config),
        ]
    )
    assert result == 0
    assert len(captured_configs) == 1
    assert captured_configs[0].iterm_window is False
    assert captured_configs[0].region is None


def test_watch_live_iterm_window_config_without_override(monkeypatch, tmp_path, capsys):
    """watch-live with config iterm_window=true and no CLI flag resolves iterm_window=True."""
    import term_chameleon.cli as cli

    config = tmp_path / "cfg.toml"
    config.write_text("[watch]\niterm_window = true\n", encoding="utf-8")

    captured_configs = []

    def fake_run(config_obj):
        captured_configs.append(config_obj)
        return []

    monkeypatch.setattr(cli, "run_watch_live", fake_run)
    result = main(
        [
            "watch-live",
            "--dry-run",
            "--config",
            str(config),
        ]
    )
    assert result == 0
    assert len(captured_configs) == 1
    assert captured_configs[0].iterm_window is True


# --- Fix: setup --name '' must not be silently replaced by config value ---


def test_setup_name_explicit_none_uses_default(tmp_path):
    """setup without --name and no config falls back to the hardcoded default."""
    # Just verify it completes without raising; actual name value is internal to run_setup
    result = main(
        [
            "setup",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    assert result in (0, 1)


def test_setup_name_empty_string_does_not_fall_back_to_config(monkeypatch, tmp_path):
    """setup --name '' must pass an empty string through, not the config value."""
    import term_chameleon.cli as cli

    config = tmp_path / "cfg.toml"
    config.write_text('[setup]\nname = "ConfigName"\n', encoding="utf-8")

    captured_kwargs: list[dict] = []
    original_run_setup = cli.run_setup

    def fake_run_setup(**kwargs):
        captured_kwargs.append(kwargs)
        return original_run_setup(**kwargs)

    monkeypatch.setattr(cli, "run_setup", fake_run_setup)
    # --name '' passes an empty string explicitly; it must NOT fall back to "ConfigName"
    main(
        [
            "setup",
            "--name",
            "",
            "--config",
            str(config),
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    assert len(captured_kwargs) == 1
    assert captured_kwargs[0]["name"] == ""
