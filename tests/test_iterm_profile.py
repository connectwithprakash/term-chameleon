from __future__ import annotations

import json
from pathlib import Path

import pytest

from term_chameleon.diagnostics import diagnose
from term_chameleon.iterm_profile import color_hex, loads_document

FIXTURES = Path(__file__).parent / "fixtures" / "iterm"

MINIMAL_PROFILE_JSON = json.dumps(
    {
        "Profiles": [
            {
                "Name": "Test Profile",
                "Guid": "test-guid-1234",
                "Background Color": {
                    "Red Component": 0.0,
                    "Green Component": 0.0,
                    "Blue Component": 0.0,
                    "Alpha Component": 1.0,
                },
            }
        ]
    }
)


def test_color_returns_none_on_malformed_list_component():
    """color() must return None (not raise) when a color component is a list."""
    profile_json = json.dumps(
        {
            "Profiles": [
                {
                    "Name": "Test",
                    "Background Color": {
                        "Red Component": [1.0, 2.0],
                        "Green Component": 0.0,
                        "Blue Component": 0.0,
                        "Alpha Component": 1.0,
                    },
                }
            ]
        }
    )
    profile = loads_document(profile_json)
    # Should not raise — malformed color component returns None
    result = profile.color("Background Color")
    assert result is None


def test_color_returns_none_on_malformed_dict_component():
    """color() must return None when a component is a dict (not a number)."""
    profile_json = json.dumps(
        {
            "Profiles": [
                {
                    "Name": "Test",
                    "Background Color": {
                        "Red Component": {"nested": 1},
                        "Green Component": 0.5,
                        "Blue Component": 0.5,
                        "Alpha Component": 1.0,
                    },
                }
            ]
        }
    )
    profile = loads_document(profile_json)
    assert profile.color("Background Color") is None


def test_color_returns_none_on_missing_key():
    """color() returns None when the color key is absent from the profile."""
    profile = loads_document(MINIMAL_PROFILE_JSON)
    assert profile.color("Nonexistent Color") is None


def test_color_returns_color_on_valid_dict():
    """color() returns a Color for a well-formed color dict."""
    profile = loads_document(MINIMAL_PROFILE_JSON)
    result = profile.color("Background Color")
    assert result is not None
    assert result.r == 0.0
    assert result.g == 0.0
    assert result.b == 0.0


def test_write_uses_atomic_write(tmp_path, monkeypatch):
    """ItermProfile.write() must use atomic_write_text, not raw write_text."""
    calls: list[tuple[Path, str]] = []

    def fake_atomic_write(target: Path, content: str) -> None:
        calls.append((target, content))

    import term_chameleon.iterm_profile as itp_module

    monkeypatch.setattr(itp_module, "atomic_write_text", fake_atomic_write)

    profile = loads_document(MINIMAL_PROFILE_JSON, path=tmp_path / "test.json")
    profile.write()

    assert len(calls) == 1
    written_path, written_content = calls[0]
    assert written_path == tmp_path / "test.json"
    assert "Test Profile" in written_content


def test_write_raises_when_no_path():
    """write() must raise ValueError when neither path arg nor self.path is set."""
    profile = loads_document(MINIMAL_PROFILE_JSON, path=None)
    with pytest.raises(ValueError, match="no path supplied"):
        profile.write()


def test_write_writes_correct_content(tmp_path):
    """write() must produce valid JSON matching the profile document."""
    target = tmp_path / "profile.json"
    profile = loads_document(MINIMAL_PROFILE_JSON, path=target)
    profile.write()
    assert target.exists()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["Profiles"][0]["Name"] == "Test Profile"


# ---------------------------------------------------------------------------
# is_color_malformed — distinguishes absent vs present-but-unparseable
# ---------------------------------------------------------------------------


def test_is_color_malformed_absent_key_returns_false():
    """Key not present in profile -> is_color_malformed returns False."""
    profile = loads_document(MINIMAL_PROFILE_JSON)
    assert profile.is_color_malformed("Foreground Color") is False


def test_is_color_malformed_valid_dict_returns_false():
    """Well-formed color dict -> is_color_malformed returns False."""
    profile = loads_document(MINIMAL_PROFILE_JSON)
    assert profile.is_color_malformed("Background Color") is False


def test_is_color_malformed_string_component_returns_true():
    """Color dict with a string component -> is_color_malformed returns True."""
    profile_json = json.dumps(
        {
            "Profiles": [
                {
                    "Name": "Test",
                    "Guid": "g1",
                    "Background Color": {
                        "Red Component": "oops",
                        "Green Component": 0.0,
                        "Blue Component": 0.0,
                        "Alpha Component": 1.0,
                    },
                }
            ]
        }
    )
    profile = loads_document(profile_json)
    assert profile.is_color_malformed("Background Color") is True


def test_is_color_malformed_non_dict_value_returns_false():
    """Non-dict value for a color key -> is_color_malformed returns False (not a color dict)."""
    profile_json = json.dumps(
        {"Profiles": [{"Name": "Test", "Guid": "g1", "Background Color": "not-a-dict"}]}
    )
    profile = loads_document(profile_json)
    assert profile.is_color_malformed("Background Color") is False


# ---------------------------------------------------------------------------
# diagnose() — MALFORMED_*_COLOR diagnostics
# ---------------------------------------------------------------------------


def _make_malformed_bg_profile() -> str:
    """Profile with Background Color present but containing a non-numeric component."""
    return json.dumps(
        {
            "Profiles": [
                {
                    "Name": "Malformed",
                    "Guid": "guid-malformed",
                    "Background Color": {
                        "Red Component": "oops",
                        "Green Component": 0.0,
                        "Blue Component": 0.0,
                        "Alpha Component": 1.0,
                    },
                    "Foreground Color": {
                        "Red Component": 0.0,
                        "Green Component": 0.0,
                        "Blue Component": 0.0,
                        "Alpha Component": 1.0,
                    },
                }
            ]
        }
    )


def test_diagnose_emits_malformed_background_color():
    """diagnose() must emit MALFORMED_BACKGROUND_COLOR when bg is present but unparseable."""
    profile = loads_document(_make_malformed_bg_profile())
    codes = {d.code for d in diagnose(profile)}
    assert "MALFORMED_BACKGROUND_COLOR" in codes


def test_diagnose_malformed_bg_diagnostic_is_fail_severity():
    """MALFORMED_BACKGROUND_COLOR diagnostic must have severity='fail'."""
    profile = loads_document(_make_malformed_bg_profile())
    diags = {d.code: d for d in diagnose(profile)}
    assert diags["MALFORMED_BACKGROUND_COLOR"].severity == "fail"


def test_diagnose_absent_bg_does_not_emit_malformed():
    """A profile with no Background Color key must not emit a MALFORMED_BACKGROUND_COLOR."""
    profile_json = json.dumps(
        {
            "Profiles": [
                {
                    "Name": "NoBg",
                    "Guid": "guid-nobg",
                }
            ]
        }
    )
    profile = loads_document(profile_json)
    codes = {d.code for d in diagnose(profile)}
    assert "MALFORMED_BACKGROUND_COLOR" not in codes


def test_diagnose_malformed_fg_emits_malformed_foreground_color():
    """diagnose() must emit MALFORMED_FOREGROUND_COLOR for a corrupt Foreground Color."""
    profile_json = json.dumps(
        {
            "Profiles": [
                {
                    "Name": "MalformedFg",
                    "Guid": "guid-fg",
                    "Background Color": {
                        "Red Component": 0.0,
                        "Green Component": 0.0,
                        "Blue Component": 0.0,
                        "Alpha Component": 1.0,
                    },
                    "Foreground Color": {
                        "Red Component": {"nested": 1},
                        "Green Component": 0.0,
                        "Blue Component": 0.0,
                        "Alpha Component": 1.0,
                    },
                }
            ]
        }
    )
    profile = loads_document(profile_json)
    codes = {d.code for d in diagnose(profile)}
    assert "MALFORMED_FOREGROUND_COLOR" in codes


# ---------------------------------------------------------------------------
# minimum_contrast / transparency — defensive coercion (Finding 1)
# ---------------------------------------------------------------------------


def test_minimum_contrast_returns_none_for_absent_key():
    """minimum_contrast() returns None when key is absent."""
    profile = loads_document(MINIMAL_PROFILE_JSON)
    assert profile.minimum_contrast() is None


def test_minimum_contrast_returns_float_for_valid_value():
    """minimum_contrast() returns a float for a well-formed numeric value."""
    profile_json = json.dumps({"Profiles": [{"Name": "T", "Guid": "g", "Minimum Contrast": 0.35}]})
    profile = loads_document(profile_json)
    assert profile.minimum_contrast() == pytest.approx(0.35)


def test_minimum_contrast_returns_none_for_string():
    """minimum_contrast() returns None (not raises) for a non-numeric string value."""
    profile_json = json.dumps(
        {"Profiles": [{"Name": "T", "Guid": "g", "Minimum Contrast": "not-a-number"}]}
    )
    profile = loads_document(profile_json)
    assert profile.minimum_contrast() is None


def test_minimum_contrast_returns_none_for_list():
    """minimum_contrast() returns None for a list value."""
    profile_json = json.dumps(
        {"Profiles": [{"Name": "T", "Guid": "g", "Minimum Contrast": [0.35]}]}
    )
    profile = loads_document(profile_json)
    assert profile.minimum_contrast() is None


def test_is_minimum_contrast_malformed_absent_returns_false():
    """is_minimum_contrast_malformed() returns False when key is absent."""
    profile = loads_document(MINIMAL_PROFILE_JSON)
    assert profile.is_minimum_contrast_malformed() is False


def test_is_minimum_contrast_malformed_valid_returns_false():
    """is_minimum_contrast_malformed() returns False for a valid numeric value."""
    profile_json = json.dumps({"Profiles": [{"Name": "T", "Guid": "g", "Minimum Contrast": 0.35}]})
    profile = loads_document(profile_json)
    assert profile.is_minimum_contrast_malformed() is False


def test_is_minimum_contrast_malformed_string_returns_true():
    """is_minimum_contrast_malformed() returns True for a non-numeric string."""
    profile_json = json.dumps({"Profiles": [{"Name": "T", "Guid": "g", "Minimum Contrast": "bad"}]})
    profile = loads_document(profile_json)
    assert profile.is_minimum_contrast_malformed() is True


def test_transparency_returns_none_for_absent_key():
    """transparency() returns None when key is absent."""
    profile = loads_document(MINIMAL_PROFILE_JSON)
    assert profile.transparency() is None


def test_transparency_returns_float_for_valid_value():
    """transparency() returns a float for a well-formed numeric value."""
    profile_json = json.dumps({"Profiles": [{"Name": "T", "Guid": "g", "Transparency": 0.08}]})
    profile = loads_document(profile_json)
    assert profile.transparency() == pytest.approx(0.08)


def test_transparency_returns_none_for_string():
    """transparency() returns None (not raises) for a non-numeric string value."""
    profile_json = json.dumps(
        {"Profiles": [{"Name": "T", "Guid": "g", "Transparency": "not-a-number"}]}
    )
    profile = loads_document(profile_json)
    assert profile.transparency() is None


def test_is_transparency_malformed_absent_returns_false():
    """is_transparency_malformed() returns False when key is absent."""
    profile = loads_document(MINIMAL_PROFILE_JSON)
    assert profile.is_transparency_malformed() is False


def test_is_transparency_malformed_string_returns_true():
    """is_transparency_malformed() returns True for a non-numeric string."""
    profile_json = json.dumps(
        {"Profiles": [{"Name": "T", "Guid": "g", "Transparency": "not-a-number"}]}
    )
    profile = loads_document(profile_json)
    assert profile.is_transparency_malformed() is True


def test_diagnose_emits_malformed_transparency():
    """diagnose() must emit MALFORMED_TRANSPARENCY when Transparency is a string."""
    profile_json = json.dumps(
        {
            "Profiles": [
                {
                    "Name": "Bad",
                    "Guid": "guid-bad",
                    "Transparency": "not-a-number",
                }
            ]
        }
    )
    profile = loads_document(profile_json)
    codes = {d.code for d in diagnose(profile)}
    assert "MALFORMED_TRANSPARENCY" in codes


def test_diagnose_emits_malformed_minimum_contrast():
    """diagnose() must emit MALFORMED_MINIMUM_CONTRAST when Minimum Contrast is a string."""
    profile_json = json.dumps(
        {
            "Profiles": [
                {
                    "Name": "Bad",
                    "Guid": "guid-bad2",
                    "Minimum Contrast": "bad",
                }
            ]
        }
    )
    profile = loads_document(profile_json)
    codes = {d.code for d in diagnose(profile)}
    assert "MALFORMED_MINIMUM_CONTRAST" in codes


def test_diagnose_malformed_transparency_is_fail_severity():
    """MALFORMED_TRANSPARENCY diagnostic must have severity='fail'."""
    profile_json = json.dumps(
        {
            "Profiles": [
                {
                    "Name": "Bad",
                    "Guid": "guid-bad3",
                    "Transparency": "not-a-number",
                }
            ]
        }
    )
    profile = loads_document(profile_json)
    diags = {d.code: d for d in diagnose(profile)}
    assert diags["MALFORMED_TRANSPARENCY"].severity == "fail"


def test_diagnose_malformed_minimum_contrast_is_fail_severity():
    """MALFORMED_MINIMUM_CONTRAST diagnostic must have severity='fail'."""
    profile_json = json.dumps(
        {
            "Profiles": [
                {
                    "Name": "Bad",
                    "Guid": "guid-bad4",
                    "Minimum Contrast": [0.5],
                }
            ]
        }
    )
    profile = loads_document(profile_json)
    diags = {d.code: d for d in diagnose(profile)}
    assert diags["MALFORMED_MINIMUM_CONTRAST"].severity == "fail"


# ---------------------------------------------------------------------------
# Fix: loads_document raises ValueError on non-dict JSON root
# ---------------------------------------------------------------------------


def test_loads_document_raises_on_integer_root():
    """loads_document must raise ValueError (not AttributeError) for a JSON integer root."""
    with pytest.raises(ValueError, match="root must be an object"):
        loads_document("5")


def test_loads_document_raises_on_array_root():
    """loads_document must raise ValueError for a JSON array root."""
    with pytest.raises(ValueError, match="root must be an object"):
        loads_document("[1, 2, 3]")


def test_loads_document_raises_on_string_root():
    """loads_document must raise ValueError for a JSON string root."""
    with pytest.raises(ValueError, match="root must be an object"):
        loads_document('"hello"')


def test_loads_document_raises_on_null_root():
    """loads_document must raise ValueError for a JSON null root."""
    with pytest.raises(ValueError, match="root must be an object"):
        loads_document("null")


def test_loads_document_raises_on_boolean_root():
    """loads_document must raise ValueError for a JSON boolean root."""
    with pytest.raises(ValueError, match="root must be an object"):
        loads_document("true")


# ---------------------------------------------------------------------------
# Fix: is_color_malformed detects partial dicts missing RGB components
# ---------------------------------------------------------------------------


def test_is_color_malformed_missing_green_returns_true():
    """A color dict missing Green Component must be flagged as malformed."""
    profile_json = json.dumps(
        {
            "Profiles": [
                {
                    "Name": "Test",
                    "Guid": "g1",
                    "Background Color": {
                        "Red Component": 0.5,
                        "Blue Component": 0.5,
                        "Alpha Component": 1.0,
                    },
                }
            ]
        }
    )
    profile = loads_document(profile_json)
    assert profile.is_color_malformed("Background Color") is True


def test_is_color_malformed_missing_red_returns_true():
    """A color dict missing Red Component must be flagged as malformed."""
    profile_json = json.dumps(
        {
            "Profiles": [
                {
                    "Name": "Test",
                    "Guid": "g1",
                    "Background Color": {
                        "Green Component": 0.5,
                        "Blue Component": 0.5,
                        "Alpha Component": 1.0,
                    },
                }
            ]
        }
    )
    profile = loads_document(profile_json)
    assert profile.is_color_malformed("Background Color") is True


def test_is_color_malformed_only_red_component_returns_true():
    """A dict with only Red Component must be flagged as malformed (partial)."""
    profile_json = json.dumps(
        {
            "Profiles": [
                {
                    "Name": "Test",
                    "Guid": "g1",
                    "Background Color": {"Red Component": 0.5},
                }
            ]
        }
    )
    profile = loads_document(profile_json)
    assert profile.is_color_malformed("Background Color") is True


def test_color_returns_none_for_partial_missing_green():
    """color() returns None (not a fabricated Color) when Green Component is absent."""
    profile_json = json.dumps(
        {
            "Profiles": [
                {
                    "Name": "Test",
                    "Background Color": {"Red Component": 0.5, "Blue Component": 0.5},
                }
            ]
        }
    )
    profile = loads_document(profile_json)
    assert profile.color("Background Color") is None


# ---------------------------------------------------------------------------
# Fix: color_hex returns None for out-of-range (wide-gamut) components
# ---------------------------------------------------------------------------


def test_color_hex_returns_none_for_out_of_range_component():
    """color_hex must return None (not raise) when a component is outside [0,1]."""
    profile_dict = {
        "Foreground Color": {
            "Red Component": 1.0931,
            "Green Component": -0.0227,
            "Blue Component": 0.0,
            "Alpha Component": 1.0,
            "Color Space": "P3",
        }
    }
    result = color_hex(profile_dict, "Foreground Color")
    assert result is None


def test_color_hex_returns_none_for_missing_rgb_component():
    """color_hex must return None for a partial color dict (missing Blue)."""
    profile_dict = {
        "Background Color": {
            "Red Component": 0.5,
            "Green Component": 0.5,
            # Blue Component absent
        }
    }
    result = color_hex(profile_dict, "Background Color")
    assert result is None


def test_color_hex_returns_hex_for_valid_color():
    """color_hex must return the hex string for a well-formed color dict."""
    profile_dict = {
        "Background Color": {
            "Red Component": 0.0,
            "Green Component": 0.0,
            "Blue Component": 0.0,
            "Alpha Component": 1.0,
            "Color Space": "sRGB",
        }
    }
    result = color_hex(profile_dict, "Background Color")
    assert result == "#000000"


def test_color_hex_returns_none_for_absent_key():
    """color_hex must return None when the key is not present."""
    assert color_hex({}, "Background Color") is None
