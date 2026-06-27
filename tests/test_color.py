import pytest
from pytest import approx

from term_chameleon.color import Color
from term_chameleon.contrast import contrast_ratio


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
