import json
from pathlib import Path

from term_chameleon.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "iterm"


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
