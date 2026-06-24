from pathlib import Path

from term_chameleon.diagnostics import diagnose
from term_chameleon.fixes import apply_balanced_fix
from term_chameleon.iterm_profile import load_profile

FIXTURES = Path(__file__).parent / "fixtures" / "iterm"


def codes(profile_name: str) -> set[str]:
    profile = load_profile(FIXTURES / profile_name)
    return {d.code for d in diagnose(profile)}


def test_good_profile_has_no_failures():
    profile = load_profile(FIXTURES / "good-dark-glass.json")
    diagnostics = diagnose(profile)
    assert not [d for d in diagnostics if d.severity == "fail"]


def test_detects_light_variant_drift():
    assert "ITERM_LIGHT_DARK_DRIFT" in codes("bad-light-variant.json")


def test_detects_bad_ansi_black():
    assert "LOW_ANSI_BLACK_CONTRAST" in codes("bad-ansi-black.json")


def test_balanced_fix_removes_failures():
    profile = load_profile(FIXTURES / "bad-light-variant.json")
    changes = apply_balanced_fix(profile)
    assert changes
    remaining = diagnose(profile)
    assert not [d for d in remaining if d.severity == "fail"]
