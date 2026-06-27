import json

import pytest

from term_chameleon.cli import main
from term_chameleon.color import Color
from term_chameleon.images import RasterImage, Region, write_ppm
from term_chameleon.text_contrast import (
    detect_text_row_bands,
    estimate_raster_text_contrast,
    estimate_text_contrast,
    write_text_contrast_report,
)


def text_like_image(*, foreground: str = "#FFFFFF", background: str = "#000000") -> RasterImage:
    fg = Color.from_hex(foreground)
    bg = Color.from_hex(background)
    pixels = []
    for y in range(8):
        for x in range(20):
            pixels.append(fg if y in {2, 3} and 3 <= x <= 7 else bg)
    return RasterImage(20, 8, tuple(pixels))


def test_detect_text_row_bands_finds_high_delta_rows():
    bands = detect_text_row_bands(text_like_image(), min_row_delta=0.2)
    assert len(bands) == 1
    assert bands[0].y == 2
    assert bands[0].height == 2


def test_estimate_raster_text_contrast_adaptive_threshold():
    """Otsu adaptive thresholding should separate fg/bg even with mid-tones."""
    from term_chameleon.text_contrast import _otsu_threshold

    # Two clear clusters: 0.0 and 1.0
    values = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
    threshold = _otsu_threshold(values)
    assert 0.0 < threshold < 1.0

    estimate = estimate_raster_text_contrast(
        text_like_image(), min_row_delta=0.2, glyph_delta=0.1, adaptive=True
    )
    assert estimate.foreground_color == "#FFFFFF"
    assert estimate.background_color == "#000000"
    assert estimate.glyph_pixels == 10


def test_estimate_raster_text_contrast_detects_foreground_background():
    estimate = estimate_raster_text_contrast(text_like_image(), min_row_delta=0.2, glyph_delta=0.2)
    assert estimate.foreground_color == "#FFFFFF"
    assert estimate.background_color == "#000000"
    assert estimate.contrast == 21.0
    assert estimate.passed is True
    assert estimate.glyph_pixels == 10


def test_estimate_text_contrast_supports_region(tmp_path):
    path = write_ppm(tmp_path / "text.ppm", text_like_image())
    estimate = estimate_text_contrast(
        path,
        region=Region(0, 0, 20, 4),
        min_row_delta=0.2,
        glyph_delta=0.2,
    )
    assert estimate.region == "0,0,20,4"
    assert len(estimate.bands) == 1


def test_estimate_text_contrast_errors_without_text_rows():
    with pytest.raises(ValueError, match="no text-like rows"):
        estimate_raster_text_contrast(
            RasterImage(4, 4, tuple(Color.from_hex("#000000") for _ in range(16)))
        )


def test_write_text_contrast_report(tmp_path):
    path = write_ppm(tmp_path / "text.ppm", text_like_image())
    json_path, md_path, estimate = write_text_contrast_report(
        path,
        tmp_path / "report",
        min_row_delta=0.2,
        glyph_delta=0.2,
    )
    assert json_path.exists()
    assert md_path.exists()
    data = json.loads(json_path.read_text())
    assert data["glyph_pixels"] == 10
    assert estimate.passed is True


def test_background_fallback_uses_set_based_lookup():
    """Regression: background-pixel fallback must use O(1) set membership, not O(n) list scan.

    When every band pixel is classified as glyph (both fg and bg are far from the
    adaptive/median threshold), background_pixels from the band loop stays empty and
    the fallback scans image.pixels.  The fallback should still correctly find
    background pixels that live outside the bands.
    """
    fg = Color(1.0, 1.0, 1.0)  # white
    bg = Color(0.0, 0.0, 0.0)  # black
    gray = Color(0.5, 0.5, 0.5)  # mid-gray — only present outside the text band

    # 4 wide x 4 high:
    #   row 0: gray  gray  gray  gray  <- outside band
    #   row 1: fg    bg    fg    bg    <- text band row (high row delta)
    #   row 2: fg    bg    fg    bg    <- text band row
    #   row 3: gray  gray  gray  gray  <- outside band
    pixels = (
        gray, gray, gray, gray,  # row 0
        fg, bg, fg, bg,           # row 1
        fg, bg, fg, bg,           # row 2
        gray, gray, gray, gray,  # row 3
    )
    image = RasterImage(4, 4, pixels)

    # With adaptive=False and glyph_delta=0.4:
    #   band luminances: 0.0 (bg) and 1.0 (fg), median = 0.5
    #   abs(1.0 - 0.5) = 0.5 >= 0.4 -> fg is glyph
    #   abs(0.0 - 0.5) = 0.5 >= 0.4 -> bg is glyph
    # => background_pixels from band loop is empty; fallback runs.
    # Fallback: glyph_set = {fg, bg}; gray not in glyph_set -> 8 gray pixels = background.
    estimate = estimate_raster_text_contrast(
        image, min_row_delta=0.1, glyph_delta=0.4, adaptive=False
    )

    # 8 band pixels (all classified glyph), 8 gray pixels collected via fallback
    assert estimate.glyph_pixels == 8
    assert estimate.background_pixels == 8
    # Background mean must be gray (the outside-band pixels), not black or white
    assert estimate.background_color == "#808080"


def test_otsu_threshold_lands_between_clusters():
    """Regression: _otsu_threshold must return the inter-class boundary, not a bin center.

    A bimodal histogram with two clearly separated clusters must produce a threshold
    that lies strictly BETWEEN the two cluster means, not at or near either cluster.
    """
    from term_chameleon.text_contrast import _otsu_threshold

    # Symmetric bimodal: cluster A centred at 0.2, cluster B centred at 0.8.
    values = [0.2] * 100 + [0.8] * 100
    t = _otsu_threshold(values)
    assert 0.2 < t < 0.8, f"threshold {t} not between clusters 0.2 and 0.8"
    # Should be very close to the midpoint 0.5.
    assert abs(t - 0.5) < 0.05, f"threshold {t} too far from expected midpoint 0.5"

    # Asymmetric bimodal: minority dark cluster vs majority light cluster.
    dark_values = [0.02] * 100
    light_values = [0.9] * 900
    t2 = _otsu_threshold(dark_values + light_values)
    assert 0.02 < t2 < 0.9, f"threshold {t2} not between clusters 0.02 and 0.9"


def test_estimate_raster_text_contrast_dark_text_on_light_background():
    """Regression: dark glyphs on a light background must not be inverted.

    When the text colour is darker than the background, the Otsu-based adaptive
    classifier must identify the dark pixels as glyphs (foreground) and the light
    pixels as background — not the other way around.
    """
    dark_glyph = Color.from_hex("#202020")
    light_bg = Color.from_hex("#E8E8E8")

    # 10 wide x 3 tall; 2 dark glyph pixels per row, 8 light background pixels per row.
    pixels = tuple(
        dark_glyph if x < 2 else light_bg for y in range(3) for x in range(10)
    )
    image = RasterImage(10, 3, tuple(pixels))

    estimate = estimate_raster_text_contrast(
        image, min_row_delta=0.05, glyph_delta=0.08, adaptive=True
    )

    assert estimate.foreground_color == "#202020", (
        f"foreground was {estimate.foreground_color!r}, expected #202020 (dark glyph)"
    )
    assert estimate.background_color == "#E8E8E8", (
        f"background was {estimate.background_color!r}, expected #E8E8E8 (light bg)"
    )
    assert estimate.glyph_pixels == 6, (
        f"glyph_pixels={estimate.glyph_pixels}, expected 6 (2 per row * 3 rows)"
    )


def test_screenshot_text_contrast_cli(tmp_path, capsys):
    path = write_ppm(tmp_path / "text.ppm", text_like_image())
    assert (
        main(
            [
                "screenshot-text-contrast",
                str(path),
                "--output-dir",
                str(tmp_path / "out"),
                "--min-row-delta",
                "0.2",
                "--glyph-delta",
                "0.2",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "Detected row bands: 1" in out
    assert "Estimated contrast: 21.00:1" in out
