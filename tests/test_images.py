from term_chameleon.color import Color
from term_chameleon.images import (
    RasterImage,
    Region,
    checkerboard_image,
    crop_image,
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


def test_image_stats_can_sample_large_images():
    image = horizontal_gradient_image(
        100,
        100,
        left=Color.from_hex("#000000"),
        right=Color.from_hex("#FFFFFF"),
    )
    exact = image_stats(image)
    sampled = image_stats(image, max_pixels=250)
    assert abs(sampled.average_luminance - exact.average_luminance) < 0.02
    assert sampled.min_luminance == exact.min_luminance
    assert sampled.max_luminance > 0.95


def test_image_stats_rejects_invalid_sample_limit():
    image = solid_image(2, 2, Color.from_hex("#FFFFFF"))
    try:
        image_stats(image, max_pixels=0)
    except ValueError as exc:
        assert "max_pixels must be positive" in str(exc)
    else:
        raise AssertionError("expected ValueError")


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


def test_region_parse_and_crop_image():
    image = RasterImage(
        3,
        2,
        (
            Color.from_hex("#000000"),
            Color.from_hex("#111111"),
            Color.from_hex("#222222"),
            Color.from_hex("#333333"),
            Color.from_hex("#444444"),
            Color.from_hex("#555555"),
        ),
    )
    region = Region.parse("1,0,2,2")
    cropped = crop_image(image, region)
    assert cropped.width == 2
    assert cropped.height == 2
    assert [pixel.to_hex() for pixel in cropped.pixels] == [
        "#111111",
        "#222222",
        "#444444",
        "#555555",
    ]


def test_region_clamps_to_image_bounds():
    image = solid_image(4, 4, Color.from_hex("#000000"))
    assert Region(2, 2, 10, 10).clamp_to(image) == Region(2, 2, 2, 2)
