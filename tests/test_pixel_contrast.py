import json

from term_chameleon.cli import main
from term_chameleon.color import Color
from term_chameleon.images import RasterImage, Region, solid_image, write_ppm
from term_chameleon.pixel_contrast import (
    estimate_image_contrast,
    estimate_raster_contrast,
    write_contrast_report,
)


def test_estimate_raster_contrast_detects_black_and_white():
    image = RasterImage(
        4,
        1,
        (
            Color.from_hex("#000000"),
            Color.from_hex("#000000"),
            Color.from_hex("#FFFFFF"),
            Color.from_hex("#FFFFFF"),
        ),
    )
    estimate = estimate_raster_contrast(image, percentile=0.5)
    assert estimate.dark_color == "#000000"
    assert estimate.light_color == "#FFFFFF"
    assert estimate.contrast == 21.0
    assert estimate.passed is True


def test_estimate_image_contrast_supports_region(tmp_path):
    image = RasterImage(
        4,
        1,
        (
            Color.from_hex("#000000"),
            Color.from_hex("#FFFFFF"),
            Color.from_hex("#777777"),
            Color.from_hex("#777777"),
        ),
    )
    path = write_ppm(tmp_path / "mixed.ppm", image)
    estimate = estimate_image_contrast(path, region=Region(0, 0, 2, 1), percentile=0.5)
    assert estimate.region == "0,0,2,1"
    assert estimate.passed is True


def test_write_contrast_report(tmp_path):
    path = write_ppm(tmp_path / "image.ppm", solid_image(2, 1, Color.from_hex("#000000")))
    json_path, md_path, estimate = write_contrast_report(path, tmp_path / "report", threshold=1.0)
    assert json_path.exists()
    assert md_path.exists()
    data = json.loads(json_path.read_text())
    assert data["sampled_pixels"] == 2
    assert estimate.passed is True


def test_estimate_raster_contrast_percentile_half_odd_pixels_no_overlap():
    """Regression: percentile=0.5 on an odd-pixel-count image must not double-count.

    When len(pixels) is odd and percentile=0.5, round() rounds sample_size up,
    which would cause the dark and light slices to overlap at the middle index,
    biasing both cluster means toward the median and understating contrast.
    The cap `min(..., len(pixels) // 2)` must prevent this.
    """
    # 3 pixels sorted by luminance: black, mid-gray, white.
    # With the bug: sample_size=round(1.5)=2; dark=[:2], light=[-2:] share index 1.
    # With the fix: sample_size=max(1, min(2, 1))=1; dark=[:1]=[black], light=[-1:]=[white].
    image = RasterImage(
        3,
        1,
        (
            Color.from_hex("#000000"),
            Color.from_hex("#808080"),
            Color.from_hex("#FFFFFF"),
        ),
    )
    estimate = estimate_raster_contrast(image, percentile=0.5)

    # Clusters must be disjoint: dark=[black], light=[white] => true max contrast.
    assert estimate.dark_color == "#000000", (
        f"dark_color={estimate.dark_color!r}, expected #000000 (pure black)"
    )
    assert estimate.light_color == "#FFFFFF", (
        f"light_color={estimate.light_color!r}, expected #FFFFFF (pure white)"
    )
    assert estimate.contrast == 21.0, (
        f"contrast={estimate.contrast}, expected 21.0 (full black-white range)"
    )


def test_screenshot_contrast_cli(tmp_path, capsys):
    path = write_ppm(
        tmp_path / "mixed.ppm",
        RasterImage(
            2,
            1,
            (Color.from_hex("#000000"), Color.from_hex("#FFFFFF")),
        ),
    )
    assert main(["screenshot-contrast", str(path), "--output-dir", str(tmp_path / "out")]) == 0
    out = capsys.readouterr().out
    assert "Estimated contrast: 21.00:1" in out
    assert (tmp_path / "out" / "contrast-report.json").exists()
