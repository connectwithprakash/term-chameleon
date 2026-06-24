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
