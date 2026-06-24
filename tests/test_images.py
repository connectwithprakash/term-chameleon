from term_chameleon.color import Color
from term_chameleon.images import (
    RasterImage,
    checkerboard_image,
    horizontal_gradient_image,
    image_stats,
    read_ppm,
    solid_image,
    write_ppm,
)


def test_solid_image_stats_are_stable():
    image = solid_image(4, 3, Color.from_hex("#FFFFFF"))
    stats = image_stats(image)
    assert stats.average_luminance == 1.0
    assert stats.luminance_variance == 0.0


def test_checkerboard_has_high_variance():
    image = checkerboard_image(
        8,
        8,
        color_a=Color.from_hex("#000000"),
        color_b=Color.from_hex("#FFFFFF"),
        cell_size=2,
    )
    stats = image_stats(image)
    assert 0.45 < stats.average_luminance < 0.55
    assert stats.luminance_variance > 0.20


def test_gradient_has_expected_luminance_range():
    image = horizontal_gradient_image(
        8,
        2,
        left=Color.from_hex("#000000"),
        right=Color.from_hex("#FFFFFF"),
    )
    stats = image_stats(image)
    assert stats.min_luminance == 0.0
    assert stats.max_luminance == 1.0
    assert stats.luminance_variance > 0.0


def test_ppm_roundtrip(tmp_path):
    image = RasterImage(
        2,
        1,
        (Color.from_hex("#000000"), Color.from_hex("#FFFFFF")),
    )
    path = write_ppm(tmp_path / "test.ppm", image)
    loaded = read_ppm(path)
    assert loaded.width == 2
    assert loaded.height == 1
    assert loaded.pixels[0].to_hex() == "#000000"
    assert loaded.pixels[1].to_hex() == "#FFFFFF"
