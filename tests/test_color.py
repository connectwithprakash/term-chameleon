
import pytest
from pytest import approx

from term_chameleon.color import Color, _quantize_byte
from term_chameleon.contrast import contrast_ratio, format_ratio


def test_hex_roundtrip():
    color = Color.from_hex("#090C16")
    assert color.to_hex() == "#090C16"


def test_iterm_dict_roundtrip():
    color = Color.from_hex("#6B7280")
    assert Color.from_iterm_dict(color.to_iterm_dict()).to_hex() == "#6B7280"


def test_black_white_contrast():
    assert contrast_ratio(Color.from_hex("#000000"), Color.from_hex("#FFFFFF")) == approx(21.0)


# --- from_iterm_dict TypeError-to-ValueError conversion ---


def test_from_iterm_dict_raises_value_error_for_list_component():
    """A JSON list component must raise ValueError, not TypeError."""
    bad = {"Red Component": [1, 2], "Green Component": 0.5, "Blue Component": 0.5}
    with pytest.raises(ValueError, match="invalid color component"):
        Color.from_iterm_dict(bad)


def test_from_iterm_dict_raises_value_error_for_dict_component():
    """A JSON object component must raise ValueError, not TypeError."""
    bad = {"Red Component": {"x": 1}, "Green Component": 0.0, "Blue Component": 0.0}
    with pytest.raises(ValueError, match="invalid color component"):
        Color.from_iterm_dict(bad)


def test_from_iterm_dict_raises_value_error_not_type_error():
    """The raised exception must be ValueError (caught by CLI handler), not TypeError."""
    bad = {"Red Component": [0.5], "Green Component": 0.0, "Blue Component": 0.0}
    exc = None
    try:
        Color.from_iterm_dict(bad)
    except Exception as e:
        exc = e
    assert exc is not None
    assert isinstance(exc, ValueError), f"expected ValueError, got {type(exc).__name__}"
    assert not isinstance(exc, TypeError)


# --- contrast_ratio background-alpha fix ---


def test_contrast_ratio_transparent_background_composited_over_black():
    """A fully-transparent background composites to black; contrast with white equals 21."""
    white = Color(1.0, 1.0, 1.0, 1.0)
    transparent = Color(0.0, 0.0, 0.0, 0.0)  # transparent black -> composites to opaque black
    assert contrast_ratio(white, transparent) == approx(21.0)


def test_contrast_ratio_opaque_background_unchanged():
    """Opaque backgrounds must produce the same result as before the fix."""
    white = Color(1.0, 1.0, 1.0, 1.0)
    black = Color(0.0, 0.0, 0.0, 1.0)
    assert contrast_ratio(white, black) == approx(21.0)
    assert contrast_ratio(black, white) == approx(21.0)


def test_contrast_ratio_semitransparent_background_blended():
    """A 50%-transparent white background composites to 50% grey over black."""
    white50 = Color(1.0, 1.0, 1.0, 0.5)  # composites to Color(0.5, 0.5, 0.5, 1.0) over black
    black = Color(0.0, 0.0, 0.0, 1.0)
    ratio = contrast_ratio(black, white50)
    # expected: black (lum=0) vs grey-0.5 (lum≈0.2140); ratio = (0.2140+0.05)/(0+0.05)
    grey_lum = Color(0.5, 0.5, 0.5, 1.0).relative_luminance()
    expected = (grey_lum + 0.05) / (0.0 + 0.05)
    assert ratio == approx(expected, rel=1e-4)


# ---------------------------------------------------------------------------
# Fix: from_iterm_dict requires all three RGB components (no silent defaults)
# ---------------------------------------------------------------------------


def test_from_iterm_dict_raises_when_red_missing():
    """Missing Red Component must raise ValueError, not silently default to 0."""
    bad = {"Green Component": 0.5, "Blue Component": 0.5}
    with pytest.raises(ValueError, match="missing required key.*Red Component"):
        Color.from_iterm_dict(bad)


def test_from_iterm_dict_raises_when_green_missing():
    """Missing Green Component must raise ValueError."""
    bad = {"Red Component": 0.5, "Blue Component": 0.5}
    with pytest.raises(ValueError, match="missing required key.*Green Component"):
        Color.from_iterm_dict(bad)


def test_from_iterm_dict_raises_when_blue_missing():
    """Missing Blue Component must raise ValueError."""
    bad = {"Red Component": 0.5, "Green Component": 0.5}
    with pytest.raises(ValueError, match="missing required key.*Blue Component"):
        Color.from_iterm_dict(bad)


def test_from_iterm_dict_partial_dict_only_red_raises():
    """A partial dict with only Red Component must raise ValueError."""
    bad = {"Red Component": 0.5}
    with pytest.raises(ValueError):
        Color.from_iterm_dict(bad)


def test_from_iterm_dict_empty_dict_raises():
    """An empty dict must raise ValueError (all three RGB keys missing)."""
    with pytest.raises(ValueError, match="missing required key"):
        Color.from_iterm_dict({})


def test_from_iterm_dict_alpha_defaults_to_1_when_absent():
    """Alpha Component may be absent and defaults to 1.0 (backwards-compat)."""
    d = {"Red Component": 0.1, "Green Component": 0.2, "Blue Component": 0.3}
    color = Color.from_iterm_dict(d)
    assert color.a == approx(1.0)


def test_from_iterm_dict_complete_dict_still_works():
    """A fully-populated dict must still parse correctly."""
    d = {
        "Red Component": 0.1,
        "Green Component": 0.2,
        "Blue Component": 0.3,
        "Alpha Component": 0.9,
        "Color Space": "sRGB",
    }
    color = Color.from_iterm_dict(d)
    assert color.r == approx(0.1)
    assert color.g == approx(0.2)
    assert color.b == approx(0.3)
    assert color.a == approx(0.9)


# ---------------------------------------------------------------------------
# Fix: _quantize_byte and to_hex use round-half-up (unified with _clamp_byte)
# ---------------------------------------------------------------------------


def test_quantize_byte_normal_values():
    """_quantize_byte must correctly round typical [0,1] components."""
    assert _quantize_byte(0.0) == 0
    assert _quantize_byte(1.0) == 255
    assert _quantize_byte(0.5) == 128  # 127.5 -> floor(128.0) = 128


def test_quantize_byte_exact_half_rounds_up():
    """_quantize_byte uses round-half-up, not banker's rounding."""
    # 126.5/255 -> value*255 = 126.5 -> floor(126.5+0.5)=floor(127)=127 (half-up)
    assert _quantize_byte(126.5 / 255.0) == 127
    # 0.5/255 -> value*255 = 0.00196... * 255 = 0.5 -> floor(0.5+0.5)=1
    assert _quantize_byte(0.5 / 255.0) == 1
    # 2.5/255 -> value*255 = 2.5 -> floor(3.0) = 3
    assert _quantize_byte(2.5 / 255.0) == 3


def test_to_hex_uses_round_half_up():
    """to_hex must agree with _quantize_byte for exact-half components."""
    # 126.5/255 should produce byte 127 (round-half-up)
    c = Color(126.5 / 255.0, 0.0, 0.0)
    hex_str = c.to_hex()
    red_byte = int(hex_str[1:3], 16)
    assert red_byte == 127, f"expected 127 (round-half-up), got {red_byte}"


def test_to_hex_round_half_up_vs_banker():
    """to_hex must not use banker's rounding (Python built-in round())."""
    # Python round(126.5) = 126 (banker's: rounds to even)
    # _quantize_byte(126.5/255) = 127 (round-half-up)
    c = Color(126.5 / 255.0, 0.0, 0.0)
    red_byte = _quantize_byte(c.r)
    assert red_byte == 127
    # Confirm this differs from banker's rounding
    assert round(126.5) == 126  # Python banker's rounds to even


def test_to_hex_and_quantize_byte_agree_on_exact_half_components():
    """to_hex byte values must match _quantize_byte for edge-case components."""
    for n_half in [0.5, 2.5, 4.5, 126.5, 128.5, 254.5]:
        component = n_half / 255.0
        expected_byte = _quantize_byte(component)
        c = Color(component, 0.0, 0.0)
        actual_byte = int(c.to_hex()[1:3], 16)
        assert actual_byte == expected_byte, (
            f"component {component}: to_hex byte {actual_byte} != "
            f"_quantize_byte {expected_byte}"
        )


# ---------------------------------------------------------------------------
# Fix: format_ratio truncates toward the failing side (floor to 2 decimals)
# ---------------------------------------------------------------------------


def test_format_ratio_does_not_display_as_passing_when_failing_near_4_5():
    """A ratio just below 4.5 must display as < 4.5, not as 4.50:1.

    Before the fix, format_ratio(4.497) returned '4.50:1', producing the
    self-contradictory message 'contrast is low (4.50:1 < 4.5:1)'.
    """
    # 4.497 fails the 4.5 check but old code displayed '4.50:1'
    result = format_ratio(4.497)
    displayed = float(result.rstrip(":1"))
    assert displayed < 4.5, f"format_ratio(4.497) = {result!r}, must display < 4.5"
    assert result == "4.49:1", f"expected '4.49:1', got {result!r}"


def test_format_ratio_does_not_display_as_passing_when_failing_near_3_0():
    """A ratio just below 3.0 must display as < 3.0, not as 3.00:1."""
    result = format_ratio(2.996)
    displayed = float(result.rstrip(":1"))
    assert displayed < 3.0, f"format_ratio(2.996) = {result!r}, must display < 3.0"
    assert result == "2.99:1", f"expected '2.99:1', got {result!r}"


def test_format_ratio_exact_threshold_values():
    """Exact threshold values (4.5, 3.0) should display correctly."""
    assert format_ratio(4.5) == "4.50:1"
    assert format_ratio(3.0) == "3.00:1"


def test_format_ratio_well_below_threshold_unchanged():
    """Values well below threshold are unaffected by the floor fix."""
    assert format_ratio(1.05) == "1.05:1"
    assert format_ratio(5.0) == "5.00:1"
    assert format_ratio(21.0) == "21.00:1"


def test_format_ratio_floor_truncates_not_rounds():
    """format_ratio must truncate (floor), not round, to 2 decimal places."""
    # 4.499 would round to 4.50 but must truncate to 4.49
    result = format_ratio(4.499)
    assert result == "4.49:1", f"expected '4.49:1' (floor), got {result!r}"
    # 1.055 must truncate to 1.05, not round to 1.06
    result = format_ratio(1.055)
    assert result == "1.05:1", f"expected '1.05:1' (floor), got {result!r}"
