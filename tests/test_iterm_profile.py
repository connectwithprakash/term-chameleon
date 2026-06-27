from __future__ import annotations

import json
from pathlib import Path

import pytest

from term_chameleon.iterm_profile import loads_document

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
