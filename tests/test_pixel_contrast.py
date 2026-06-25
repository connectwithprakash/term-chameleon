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
