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


def test_fix_requires_yes_or_dry_run(capsys):
    assert main(["fix", str(FIXTURES / "bad-light-variant.json")]) == 2
    err = capsys.readouterr().err
    assert "Refusing to write" in err


def test_fix_dry_run(capsys):
    assert main(["fix", str(FIXTURES / "bad-light-variant.json"), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Planned changes" in out
    assert "Use Separate Colors" in out
