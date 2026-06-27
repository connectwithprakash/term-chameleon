from pathlib import Path

from term_chameleon.diagnostics import diagnose
from term_chameleon.fixes import apply_balanced_fix
from term_chameleon.iterm_profile import load_profile

FIXTURES = Path(__file__).parent / "fixtures" / "iterm"


def codes(profile_name: str) -> set[str]:
    profile = load_profile(FIXTURES / profile_name)
    return {d.code for d in diagnose(profile)}


def _severity(profile_name: str) -> dict[str, str]:
    profile = load_profile(FIXTURES / profile_name)
    return {d.code: d.severity for d in diagnose(profile)}


def test_good_profile_has_no_failures():
    profile = load_profile(FIXTURES / "good-dark-glass.json")
    diagnostics = diagnose(profile)
    assert not [d for d in diagnostics if d.severity == "fail"]


def test_detects_light_variant_drift():
    assert "ITERM_LIGHT_DARK_DRIFT" in codes("bad-light-variant.json")


def test_detects_bad_ansi_black():
    assert "LOW_ANSI_BLACK_CONTRAST" in codes("bad-ansi-black.json")


def test_ansi_black_contrast_is_blocking_fail():
    """LOW_ANSI_BLACK_CONTRAST must be severity='fail', not 'warn'.

    A profile with invisible ANSI black (no light/dark drift) must yield a
    nonzero doctor exit and passed=False.  This is the regression test for the
    R3 bug where severity was hard-coded to WARN for sub-4.5 thresholds.
    """
    profile = load_profile(FIXTURES / "bad-ansi-black-only.json")
    diagnostics = diagnose(profile)
    by_code = {d.code: d for d in diagnostics}

    # ANSI black and bright-black contrast failures must be 'fail', not 'warn'
    assert "LOW_ANSI_BLACK_CONTRAST" in by_code, "expected LOW_ANSI_BLACK_CONTRAST diagnostic"
    assert by_code["LOW_ANSI_BLACK_CONTRAST"].severity == "fail"
    assert "LOW_ANSI_BRIGHT_BLACK_CONTRAST" in by_code
    assert by_code["LOW_ANSI_BRIGHT_BLACK_CONTRAST"].severity == "fail"

    # No light/dark drift — the ANSI contrast check alone must block the profile
    assert "ITERM_LIGHT_DARK_DRIFT" not in by_code

    # Simulate the CLI pass/fail gate: any fail → exit code 1, passed=False
    any_fail = any(d.severity == "fail" for d in diagnostics)
    assert any_fail, "expected at least one fail diagnostic; profile must not pass"


def test_selection_contrast_is_blocking_fail(tmp_path):
    """LOW_SELECTION_CONTRAST must also be severity='fail' (3.0:1 threshold).

    Constructs a profile where Selection/Selected Text contrast is very low
    but all other pairs are fine, and verifies the diagnostic blocks.
    """
    import json

    source = json.loads((FIXTURES / "good-dark-glass.json").read_text())
    p = source["Profiles"][0]
    # Make Selection and Selected Text nearly identical (very low contrast)
    same_color = {
        "Alpha Component": 1,
        "Blue Component": 0.18,
        "Color Space": "sRGB",
        "Green Component": 0.16,
        "Red Component": 0.15,
    }
    p["Selection Color"] = same_color
    p["Selected Text Color"] = {
        **same_color,
        "Blue Component": 0.20,  # trivially different, still < 3.0:1
    }
    target = tmp_path / "bad-selection.json"
    target.write_text(json.dumps(source))

    profile = load_profile(target)
    diagnostics = diagnose(profile)
    by_code = {d.code: d for d in diagnostics}

    assert "LOW_SELECTION_CONTRAST" in by_code
    assert by_code["LOW_SELECTION_CONTRAST"].severity == "fail"


def test_detects_ansi_light_variant_drift(tmp_path):
    import json

    source = json.loads((FIXTURES / "good-dark-glass.json").read_text())
    source["Profiles"][0]["Ansi 0 Color (Light)"] = source["Profiles"][0]["Ansi 15 Color"]
    target = tmp_path / "ansi-drift.json"
    target.write_text(json.dumps(source))
    profile = load_profile(target)
    assert "ITERM_LIGHT_DARK_DRIFT" in {d.code for d in diagnose(profile)}


def test_balanced_fix_removes_failures():
    profile = load_profile(FIXTURES / "bad-light-variant.json")
    changes = apply_balanced_fix(profile)
    assert changes
    remaining = diagnose(profile)
    assert not [d for d in remaining if d.severity == "fail"]
