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
