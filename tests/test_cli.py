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
