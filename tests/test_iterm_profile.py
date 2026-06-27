from __future__ import annotations

import json
from pathlib import Path

import pytest

from term_chameleon.color import Color
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
# Fix: set_color preserves original Color Space and unknown extra keys
# ---------------------------------------------------------------------------


def _p3_profile_json() -> str:
    """A minimal profile with a P3 Background Color."""
    return json.dumps(
        {
            "Profiles": [
                {
                    "Name": "P3 Test",
                    "Guid": "guid-p3",
                    "Background Color": {
                        "Color Space": "P3",
                        "Red Component": 0.1,
                        "Green Component": 0.2,
                        "Blue Component": 0.3,
                        "Alpha Component": 1.0,
                        "Extra iTerm Key": "keep-me",
                    },
                }
            ]
        }
    )


def test_set_color_preserves_color_space():
    """set_color must not overwrite the original Color Space with sRGB."""
    profile = loads_document(_p3_profile_json())
    original_color = profile.color("Background Color")
    assert original_color is not None
    profile.set_color("Background Color", original_color)
    stored = profile.profile["Background Color"]
    assert stored["Color Space"] == "P3", (
        f"Color Space was clobbered: expected 'P3', got {stored['Color Space']!r}"
    )


def test_set_color_preserves_unknown_extra_keys():
    """set_color must preserve unknown extra keys alongside the new component values."""
    profile = loads_document(_p3_profile_json())
    original_color = profile.color("Background Color")
    assert original_color is not None
    profile.set_color("Background Color", original_color)
    stored = profile.profile["Background Color"]
    assert "Extra iTerm Key" in stored, "Extra iTerm Key was dropped by set_color"
    assert stored["Extra iTerm Key"] == "keep-me"


def test_set_color_updates_component_values():
    """set_color must write the new color component values."""
    profile = loads_document(_p3_profile_json())
    new_color = Color(0.9, 0.8, 0.7)
    profile.set_color("Background Color", new_color)
    stored = profile.profile["Background Color"]
    assert stored["Red Component"] == 0.9
    assert stored["Green Component"] == 0.8
    assert stored["Blue Component"] == 0.7


def test_set_color_on_new_key_uses_srdb_default():
    """set_color on a key that has no existing dict uses sRGB as Color Space."""
    profile = loads_document(MINIMAL_PROFILE_JSON)
    new_color = Color(0.5, 0.5, 0.5)
    profile.set_color("Foreground Color", new_color)
    stored = profile.profile["Foreground Color"]
    assert stored["Color Space"] == "sRGB"


def test_set_color_idempotent_round_trip_preserves_space():
    """Calling set_color(key, color(key)) must be idempotent for Color Space."""
    profile = loads_document(_p3_profile_json())
    before = dict(profile.profile["Background Color"])
    color = profile.color("Background Color")
    assert color is not None
    profile.set_color("Background Color", color)
    after = profile.profile["Background Color"]
    assert after["Color Space"] == before["Color Space"]


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
