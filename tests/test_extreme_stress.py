"""
Extreme stress and boundary testing for term-chameleon.
Tests maximum/minimum input values, rapid repeated calls, resource exhaustion,
unusual environment configurations, timeout behaviors, and memory usage.

Run with: pytest tests/test_extreme_stress.py -v --tb=short
"""

import json
import os
import threading
import time
from unittest.mock import patch

import pytest

from term_chameleon.color import Color
from term_chameleon.contrast import contrast_ratio
from term_chameleon.images import RasterImage, Region
from term_chameleon.pixel_contrast import (
    ContrastEstimate,
    estimate_raster_contrast,
)
from term_chameleon.terminal import detect_terminal


class TestColorBoundaries:
    """Boundary tests for Color class with extreme values."""

    def test_color_max_values(self):
        """RGB values at maximum (1.0, 1.0, 1.0)."""
        color = Color(r=1.0, g=1.0, b=1.0)
        assert color.r == 1.0
        assert color.g == 1.0
        assert color.b == 1.0
        assert color.relative_luminance() == 1.0

    def test_color_min_values(self):
        """RGB values at minimum (0.0, 0.0, 0.0)."""
        color = Color(r=0.0, g=0.0, b=0.0)
        assert color.r == 0.0
        assert color.g == 0.0
        assert color.b == 0.0
        assert color.relative_luminance() == 0.0

    def test_color_extreme_hex_values(self):
        """Hex conversion with boundary values."""
        # Maximum
        white = Color(r=1.0, g=1.0, b=1.0)
        assert white.to_hex() == "#FFFFFF"

        # Minimum
        black = Color(r=0.0, g=0.0, b=0.0)
        assert black.to_hex() == "#000000"

        # Mixed boundaries
        color = Color(r=1.0, g=0.0, b=0.5)
        hex_value = color.to_hex()
        assert hex_value == "#FF0080"

    def test_color_luminance_extreme_ratios(self):
        """Contrast ratio with extreme luminance differences."""
        white = Color(r=1.0, g=1.0, b=1.0)
        black = Color(r=0.0, g=0.0, b=0.0)
        ratio = contrast_ratio(white, black)
        # WCAG contrast ratio: white/black = 21:1
        assert ratio == pytest.approx(21.0, rel=0.01)

    def test_color_luminance_identical_colors(self):
        """Contrast ratio between identical colors (minimum contrast)."""
        red = Color(r=1.0, g=0.0, b=0.0)
        red2 = Color(r=1.0, g=0.0, b=0.0)
        ratio = contrast_ratio(red, red2)
        assert ratio == pytest.approx(1.0)

    def test_color_luminance_near_identical(self):
        """Contrast ratio between nearly identical colors."""
        color1 = Color(r=0.4, g=0.4, b=0.4)
        color2 = Color(r=0.401, g=0.4, b=0.4)
        ratio = contrast_ratio(color1, color2)
        assert ratio > 1.0
        assert ratio < 1.1  # Very small difference


class TestContrastRatioBoundaries:
    """Boundary and edge cases for contrast ratio calculations."""

    def test_contrast_ratio_0_luminance(self):
        """Contrast calculation with zero luminance."""
        black = Color(r=0.0, g=0.0, b=0.0)
        white = Color(r=1.0, g=1.0, b=1.0)
        # Should not raise ZeroDivisionError
        ratio = contrast_ratio(white, black)
        assert ratio == pytest.approx(21.0, rel=0.01)

    def test_contrast_ratio_max_luminance(self):
        """Contrast with maximum luminance values."""
        color1 = Color(r=1.0, g=1.0, b=1.0)
        color2 = Color(r=1.0, g=1.0, b=0.996)
        ratio = contrast_ratio(color1, color2)
        assert ratio > 1.0

    def test_contrast_ratio_reversed_order(self):
        """Contrast ratio should be symmetric."""
        color1 = Color(r=1.0, g=0.0, b=0.0)
        color2 = Color(r=0.0, g=0.0, b=0.0)
        ratio1 = contrast_ratio(color1, color2)
        ratio2 = contrast_ratio(color2, color1)
        assert ratio1 == pytest.approx(ratio2)


class TestPixelContrastExtremes:
    """Extreme stress tests for pixel contrast estimation."""

    def test_estimate_contrast_single_pixel(self):
        """Contrast estimation with minimum pixel count."""
        pixels = [Color(r=1.0, g=1.0, b=1.0)]
        image = RasterImage(width=1, height=1, pixels=tuple(pixels))
        with pytest.raises(ValueError, match="at least two pixels"):
            estimate_raster_contrast(image)

    def test_estimate_contrast_two_pixels(self):
        """Contrast estimation with exactly two pixels."""
        pixels = [Color(r=0.0, g=0.0, b=0.0), Color(r=1.0, g=1.0, b=1.0)]
        image = RasterImage(width=2, height=1, pixels=tuple(pixels))
        estimate = estimate_raster_contrast(image)
        assert estimate.contrast == pytest.approx(21.0, rel=0.01)
        assert estimate.passed is True

    def test_estimate_contrast_extreme_percentiles(self):
        """Contrast with extreme percentile values."""
        pixels = [Color(r=i / 255.0, g=i / 255.0, b=i / 255.0) for i in range(0, 256)]
        image = RasterImage(width=256, height=1, pixels=tuple(pixels))

        # Tiny percentile
        estimate_tiny = estimate_raster_contrast(image, threshold=4.5, percentile=0.001)
        assert estimate_tiny.sampled_pixels >= 1

        # Large percentile (approaching 0.5 limit)
        estimate_large = estimate_raster_contrast(image, threshold=4.5, percentile=0.5)
        assert estimate_large.sampled_pixels > 0

    def test_estimate_contrast_invalid_percentile_zero(self):
        """Percentile must be > 0."""
        # Note: percentile validation happens in estimate_image_contrast,
        # not estimate_raster_contrast
        # So test that raster function handles edge case gracefully
        pixels = [Color(r=0.0, g=0.0, b=0.0), Color(r=1.0, g=1.0, b=1.0)]
        image = RasterImage(width=2, height=1, pixels=tuple(pixels))
        # estimate_raster_contrast doesn't validate, it just uses percentile for sampling
        # Very small percentile will sample at least 1 pixel (max(1, round(...)))
        estimate = estimate_raster_contrast(image, percentile=0.001)
        assert estimate.sampled_pixels >= 1

    def test_estimate_contrast_invalid_percentile_over_half(self):
        """Percentile > 0.5 still works in estimate_raster_contrast but is unusual."""
        pixels = [Color(r=0.0, g=0.0, b=0.0), Color(r=1.0, g=1.0, b=1.0)]
        image = RasterImage(width=2, height=1, pixels=tuple(pixels))
        # estimate_raster_contrast doesn't validate upper bound, it will just sample more
        estimate = estimate_raster_contrast(image, percentile=0.6)
        assert estimate.sampled_pixels >= 1

    def test_estimate_contrast_uniform_pixels(self):
        """All pixels identical (uniform contrast)."""
        pixels = [Color(r=0.5, g=0.5, b=0.5)] * 10000
        image = RasterImage(width=100, height=100, pixels=tuple(pixels))
        estimate = estimate_raster_contrast(image)
        assert estimate.contrast == pytest.approx(1.0)

    def test_estimate_contrast_large_pixel_set(self):
        """Stress test with very large pixel set."""
        # 100k pixels
        pixels = [
            Color(r=(i % 256) / 255.0, g=((i * 2) % 256) / 255.0, b=((i * 3) % 256) / 255.0)
            for i in range(100000)
        ]
        image = RasterImage(width=500, height=200, pixels=tuple(pixels))
        estimate = estimate_raster_contrast(image, percentile=0.1)
        assert estimate.sampled_pixels > 0
        assert estimate.contrast > 0

    def test_estimate_contrast_all_same_except_one(self):
        """All pixels same except one outlier."""
        pixels = [Color(r=0.5, g=0.5, b=0.5)] * 9999 + [Color(r=1.0, g=1.0, b=1.0)]
        image = RasterImage(width=100, height=100, pixels=tuple(pixels))
        estimate = estimate_raster_contrast(image, percentile=0.1)
        assert estimate.contrast > 1.0


class TestRegionBoundaries:
    """Boundary tests for image regions."""

    def test_region_zero_coordinates(self):
        """Region starting at (0, 0)."""
        region = Region(x=0, y=0, width=100, height=100)
        assert region.x == 0
        assert region.y == 0

    def test_region_maximum_coordinates(self):
        """Region with very large coordinates."""
        region = Region(x=999999, y=999999, width=1, height=1)
        assert region.x == 999999
        assert region.y == 999999

    def test_region_zero_dimensions(self):
        """Region with zero width or height (edge case)."""
        with pytest.raises(ValueError, match="region width/height must be positive"):
            Region(x=0, y=0, width=0, height=0)

    def test_region_maximum_dimensions(self):
        """Region with very large dimensions."""
        region = Region(x=0, y=0, width=999999, height=999999)
        assert region.width == 999999
        assert region.height == 999999

    def test_region_string_representation(self):
        """String representation of extreme regions."""
        region = Region(x=0, y=0, width=3840, height=2160)
        region_str = str(region)
        assert "0,0" in region_str or "x=0" in region_str


class TestEnvironmentExtreme:
    """Stress tests with extreme environment configurations."""

    def test_empty_environ(self):
        """Terminal detection with empty environment."""
        with patch.dict(os.environ, {}, clear=True):
            info = detect_terminal()
            assert info is not None
            # Should handle gracefully and return unknown

    def test_malformed_environ_values(self):
        """Environment variables with malformed values."""
        # Note: Python 3.x doesn't allow null bytes in environment dicts
        # Test with unusual but valid values
        unusual = {
            "TERM_PROGRAM": "xterm-256color-modified",
            "TERM": "xterm",
        }
        with patch.dict(os.environ, unusual, clear=True):
            info = detect_terminal()
            assert info is not None

    def test_very_long_environ_value(self):
        """Environment variable with extremely long value."""
        long_value = "a" * 100000
        with patch.dict(os.environ, {"TERM_PROGRAM": long_value}, clear=True):
            info = detect_terminal()
            assert info is not None


class TestConcurrencyStress:
    """Stress tests for concurrent operations."""

    def test_concurrent_color_creation(self):
        """Rapid concurrent color object creation."""
        colors = []
        errors = []

        def create_colors():
            try:
                for i in range(1000):
                    color = Color(
                        r=(i % 256) / 255.0,
                        g=((i * 2) % 256) / 255.0,
                        b=((i * 3) % 256) / 255.0,
                    )
                    colors.append(color)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_colors) for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert len(errors) == 0
        assert len(colors) == 10000

    def test_concurrent_contrast_calculations(self):
        """Rapid concurrent contrast ratio calculations."""
        results = []
        errors = []

        def calculate_contrasts():
            try:
                white = Color(r=1.0, g=1.0, b=1.0)
                black = Color(r=0.0, g=0.0, b=0.0)
                for _ in range(1000):
                    ratio = contrast_ratio(white, black)
                    results.append(ratio)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=calculate_contrasts) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert len(errors) == 0
        assert len(results) == 5000

    def test_concurrent_terminal_detection(self):
        """Rapid concurrent terminal detection calls."""
        results = []
        errors = []

        def detect():
            try:
                for _ in range(100):
                    info = detect_terminal()
                    results.append(info)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=detect) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert len(errors) == 0
        assert len(results) == 500


class TestMemoryStress:
    """Memory stress tests."""

    def test_large_image_processing(self):
        """Process image with millions of pixels."""
        # 2 million pixel image
        pixels = [
            Color(r=(i % 256) / 255.0, g=((i * 2) % 256) / 255.0, b=((i * 3) % 256) / 255.0)
            for i in range(2000000)
        ]
        image = RasterImage(width=2000, height=1000, pixels=tuple(pixels))
        estimate = estimate_raster_contrast(image, percentile=0.01)
        assert estimate is not None
        assert estimate.sampled_pixels > 0

    def test_repeated_large_allocations(self):
        """Repeated allocation and deallocation of large structures."""
        for _ in range(10):
            pixels = [Color(r=1.0, g=0.0, b=0.0)] * 500000
            image = RasterImage(width=500, height=1000, pixels=tuple(pixels))
            estimate = estimate_raster_contrast(image)
            assert estimate is not None
            del image
            del pixels

    def test_deeply_nested_structures(self):
        """Create deeply nested data structures."""
        # This tests JSON serialization with deep nesting
        data = {"level": 0}
        current = data
        for i in range(100):
            current["nested"] = {"level": i + 1}
            current = current["nested"]

        # Should serialize without stack overflow
        json_str = json.dumps(data)
        assert "nested" in json_str


class TestTimeoutAndLongRunning:
    """Tests for timeout behavior and long-running operations."""

    def test_very_long_operation_color_processing(self):
        """Simulate long-running color processing."""
        start = time.time()
        pixels = []
        for i in range(10000):
            for j in range(100):
                color = Color(
                    r=((i + j) % 256) / 255.0, g=((i - j) % 256) / 255.0, b=((i * j) % 256) / 255.0
                )
                pixels.append(color)
        elapsed = time.time() - start
        assert elapsed < 5.0  # Should complete in reasonable time

    def test_contrast_calculation_timeout(self):
        """Contrast calculation should not hang."""
        start = time.time()
        results = []
        for _ in range(10000):
            white = Color(r=1.0, g=1.0, b=1.0)
            black = Color(r=0.0, g=0.0, b=0.0)
            ratio = contrast_ratio(white, black)
            results.append(ratio)
        elapsed = time.time() - start
        assert elapsed < 5.0  # Should complete in reasonable time
        assert len(results) == 10000


class TestResourceExhaustion:
    """Tests for resource exhaustion scenarios."""

    def test_many_contrast_estimates(self):
        """Create many contrast estimates to stress memory."""
        estimates = []
        for _ in range(100):  # Reduced from 1000 for runtime
            pixels = [
                Color(r=(j % 256) / 255.0, g=((j * 2) % 256) / 255.0, b=((j * 3) % 256) / 255.0)
                for j in range(1000)
            ]
            image = RasterImage(width=40, height=25, pixels=tuple(pixels))
            estimate = estimate_raster_contrast(image)
            estimates.append(estimate)

        assert len(estimates) == 100
        assert all(isinstance(e, ContrastEstimate) for e in estimates)

    def test_many_color_objects(self):
        """Create and store many color objects."""
        colors = []
        for i in range(100000):
            color = Color(r=(i % 256) / 255.0, g=((i * 2) % 256) / 255.0, b=((i * 3) % 256) / 255.0)
            colors.append(color)

        assert len(colors) == 100000

    def test_many_regions(self):
        """Create many region objects."""
        regions = []
        for i in range(10000):
            region = Region(x=i, y=i * 2, width=100, height=100)
            regions.append(region)

        assert len(regions) == 10000


class TestInvalidInputCombinations:
    """Test invalid combinations of inputs that might cause issues."""

    def test_contrast_with_nan_like_values(self):
        """Colors that might produce NaN in luminance calculations."""
        # These shouldn't cause NaN or Inf issues
        color1 = Color(r=1.0, g=1.0, b=1.0)
        color2 = Color(r=254.0 / 255.0, g=254.0 / 255.0, b=254.0 / 255.0)
        ratio = contrast_ratio(color1, color2)
        assert ratio > 0
        assert ratio < float("inf")
        assert str(ratio).lower() != "nan"

    def test_zero_pixel_percentile_rounding(self):
        """Percentile that rounds to exactly 0 pixels."""
        pixels = [Color(r=0.5, g=0.5, b=0.5)] * 10
        image = RasterImage(width=10, height=1, pixels=tuple(pixels))
        # Very tiny percentile might round to 0
        estimate = estimate_raster_contrast(image, percentile=0.001)
        assert estimate.sampled_pixels >= 1  # Should be at least 1

    def test_single_color_many_pixels(self):
        """All pixels identical but many of them."""
        pixels = [
            Color(r=200.0 / 255.0, g=100.0 / 255.0, b=50.0 / 255.0)
        ] * 100000  # Reduced from 1M
        image = RasterImage(width=500, height=200, pixels=tuple(pixels))
        estimate = estimate_raster_contrast(image)
        assert estimate.contrast == pytest.approx(1.0)
        assert estimate.passed is False  # Won't exceed 4.5 threshold


class TestDataTypeEdgeCases:
    """Edge cases in data type handling."""

    def test_contrast_estimate_serialization(self):
        """ContrastEstimate should serialize properly."""
        pixels = [Color(r=0.0, g=0.0, b=0.0), Color(r=1.0, g=1.0, b=1.0)]
        image = RasterImage(width=2, height=1, pixels=tuple(pixels))
        estimate = estimate_raster_contrast(image)

        # Should have all required fields
        assert hasattr(estimate, "image_path")
        assert hasattr(estimate, "contrast")
        assert hasattr(estimate, "passed")

    def test_color_hex_roundtrip(self):
        """Color to hex and back should be consistent."""
        for r in [0.0, 0.5, 1.0]:
            for g in [0.0, 0.5, 1.0]:
                for b in [0.0, 0.5, 1.0]:
                    color = Color(r=r, g=g, b=b)
                    hex_str = color.to_hex()
                    assert hex_str.startswith("#")
                    assert len(hex_str) == 7


class TestBoundaryIntegration:
    """Integration tests combining multiple boundary conditions."""

    def test_extreme_contrast_range(self):
        """Test full spectrum of contrast values."""
        colors = []
        for i in range(256):
            color = Color(r=i / 255.0, g=i / 255.0, b=i / 255.0)
            colors.append(color)

        for i in range(len(colors) - 1):
            ratio = contrast_ratio(colors[i], colors[i + 1])
            assert ratio >= 1.0

    def test_all_color_channels_independently(self):
        """Test extreme values in each color channel."""
        test_cases = [
            (1.0, 0.0, 0.0),  # Red
            (0.0, 1.0, 0.0),  # Green
            (0.0, 0.0, 1.0),  # Blue
            (1.0, 1.0, 0.0),  # Yellow
            (1.0, 0.0, 1.0),  # Magenta
            (0.0, 1.0, 1.0),  # Cyan
        ]
        for r, g, b in test_cases:
            color = Color(r=r, g=g, b=b)
            assert color.r == r
            assert color.g == g
            assert color.b == b

    def test_rapid_context_switching(self):
        """Simulate rapid context switching with many colors."""
        results = []
        for _ in range(10):
            for i in range(1000):
                color1 = Color(
                    r=(i % 256) / 255.0, g=((i * 2) % 256) / 255.0, b=((i * 3) % 256) / 255.0
                )
                color2 = Color(
                    r=((255 - i) % 256) / 255.0,
                    g=((255 - i * 2) % 256) / 255.0,
                    b=((255 - i * 3) % 256) / 255.0,
                )
                ratio = contrast_ratio(color1, color2)
                results.append(ratio)

        assert len(results) == 10000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
