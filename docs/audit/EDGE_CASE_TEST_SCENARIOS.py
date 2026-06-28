"""
Comprehensive edge case test scenarios for term-chameleon.
These tests are designed to be placed in tests/ directory with pytest.

Run with: pytest tests/test_edge_cases_*.py -v
"""

import os
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from term_chameleon.color import Color
from term_chameleon.contrast import contrast_ratio
from term_chameleon.images import Region, RasterImage, checkerboard_image, solid_image
from term_chameleon.pixel_contrast import estimate_raster_contrast
from term_chameleon.safe_io import atomic_write_text, backup_file, unique_backup_path
from term_chameleon.terminal import detect_terminal
from term_chameleon.watch import Sample, classify_sample, ModeSelector


class TestTerminalDetectionEdgeCases:
    """Edge cases for terminal detection."""

    def test_terminal_program_empty_string(self):
        """TERM_PROGRAM is empty string (vs. unset)."""
        with patch.dict(os.environ, {"TERM_PROGRAM": ""}, clear=True):
            info = detect_terminal()
            assert info.is_supported is False
            assert info.name == "unknown"

    def test_terminal_program_mixed_case_variants(self):
        """Mixed case TERM_PROGRAM values."""
        variants = [
            ("iTerm.app", "iterm2"),
            ("iTerm.APP", "iterm2"),
            ("ITERM.app", "iterm2"),
            ("iterm.APP", "iterm2"),
            ("kitty", "kitty"),
            ("KITTY", "kitty"),
            ("Kitty", "kitty"),
            ("alacritty", "alacritty"),
            ("Alacritty", "alacritty"),
            ("ALACRITTY", "alacritty"),
        ]
        for variant, expected_name in variants:
            with patch.dict(os.environ, {"TERM_PROGRAM": variant}, clear=True):
                info = detect_terminal()
                assert info.name == expected_name, f"Failed for variant: {variant}"

    def test_kitty_substring_false_positive(self):
        """CRITICAL: 'kitty' in term matches unintended values."""
        # This is a false positive that should be documented or fixed
        with patch.dict(os.environ, {"TERM": "xterm-kitty-256color"}, clear=True):
            info = detect_terminal()
            # Currently: info.is_kitty is True (false positive)
            # Should be: info.is_kitty is False if TERM_PROGRAM not explicitly "kitty"
            assert info.is_kitty is True  # Documents current behavior
            # TODO: Consider fixing to require explicit TERM_PROGRAM="kitty"

    def test_ghostty_nonexistent_path(self):
        """GHOSTTY_RESOURCES_DIR points to nonexistent path."""
        with patch.dict(os.environ, {"GHOSTTY_RESOURCES_DIR": "/nonexistent/path"}, clear=True):
            info = detect_terminal()
            assert info.is_ghostty is True  # Detected despite path not existing
            # Later code might fail if it tries to access this path

    def test_ghostty_empty_string_path(self):
        """GHOSTTY_RESOURCES_DIR is empty string."""
        with patch.dict(os.environ, {"GHOSTTY_RESOURCES_DIR": ""}, clear=True):
            info = detect_terminal()
            # Empty string is falsy, so is_ghostty should be False
            assert info.is_ghostty is False

    def test_very_long_environment_values(self):
        """Environment variables with extreme lengths."""
        with patch.dict(os.environ, {"TERM_PROGRAM": "x" * 100000}, clear=True):
            # Should not hang or consume excessive memory
            start = time.time()
            info = detect_terminal()
            elapsed = time.time() - start
            assert elapsed < 0.1  # Should be nearly instant
            assert info.is_supported is False

    def test_all_environment_variables_empty(self):
        """All relevant env vars empty or missing."""
        with patch.dict(os.environ, {}, clear=True):
            info = detect_terminal()
            assert info.is_supported is False
            assert info.name == "unknown"


class TestColorEdgeCases:
    """Edge cases for Color class."""

    @pytest.mark.parametrize("hex_str,expected_r,expected_g,expected_b", [
        ("#000000", 0.0, 0.0, 0.0),  # Black
        ("#FFFFFF", 1.0, 1.0, 1.0),  # White
        ("#ffffff", 1.0, 1.0, 1.0),  # Lowercase
        ("  #FFFFFF  ", 1.0, 1.0, 1.0),  # Whitespace
        ("#aabbcc", 170/255, 187/255, 204/255),
    ])
    def test_hex_parsing_variants(self, hex_str, expected_r, expected_g, expected_b):
        """Various hex format inputs."""
        color = Color.from_hex(hex_str)
        assert color.r == pytest.approx(expected_r)
        assert color.g == pytest.approx(expected_g)
        assert color.b == pytest.approx(expected_b)

    def test_hex_with_invalid_characters(self):
        """Hex string with non-hex characters."""
        with pytest.raises(ValueError):
            Color.from_hex("#GGGGGG")
        with pytest.raises(ValueError):
            Color.from_hex("#12345G")

    def test_hex_with_alpha_format(self):
        """8-character hex (RGBA format) should fail."""
        with pytest.raises(ValueError):
            Color.from_hex("#FFFFFF80")

    def test_color_components_just_outside_bounds(self):
        """Components just outside [0, 1] bounds."""
        with pytest.raises(ValueError):
            Color(1.0000001, 0.5, 0.5)
        with pytest.raises(ValueError):
            Color(-0.0000001, 0.5, 0.5)
        with pytest.raises(ValueError):
            Color(0.5, 0.5, 0.5, 1.0000001)

    def test_color_components_at_boundaries(self):
        """Components exactly at boundaries."""
        # Should succeed
        c1 = Color(0.0, 0.0, 0.0, 0.0)
        c2 = Color(1.0, 1.0, 1.0, 1.0)
        assert c1.r == 0.0
        assert c2.r == 1.0

    def test_blend_over_fully_transparent_foreground(self):
        """Blending fully transparent color over opaque."""
        fg = Color(1.0, 0.0, 0.0, 0.0)  # Transparent red
        bg = Color(0.0, 0.0, 1.0, 1.0)  # Opaque blue
        result = fg.blend_over(bg)
        assert result.r == pytest.approx(0.0)
        assert result.g == pytest.approx(0.0)
        assert result.b == pytest.approx(1.0)
        assert result.a == 1.0

    def test_blend_over_fully_opaque_foreground(self):
        """Blending fully opaque color ignores background."""
        fg = Color(1.0, 0.0, 0.0, 1.0)  # Opaque red
        bg = Color(0.0, 0.0, 1.0, 1.0)  # Opaque blue
        result = fg.blend_over(bg)
        assert result.r == pytest.approx(1.0)
        assert result.g == pytest.approx(0.0)
        assert result.b == pytest.approx(0.0)

    def test_relative_luminance_at_threshold(self):
        """Luminance calculation at 0.03928 threshold."""
        c1 = Color(0.03928, 0, 0)  # Exactly at threshold
        c2 = Color(0.0393, 0, 0)   # Just above threshold
        c3 = Color(0.03927, 0, 0)  # Just below threshold
        lum1 = c1.relative_luminance()
        lum2 = c2.relative_luminance()
        lum3 = c3.relative_luminance()
        # Should be monotonically increasing
        assert lum3 < lum1 < lum2

    def test_contrast_ratio_extremes(self):
        """Contrast between black and white."""
        black = Color(0, 0, 0)
        white = Color(1, 1, 1)
        ratio = contrast_ratio(black, white)
        assert ratio == pytest.approx(21.0, rel=1e-3)

    def test_contrast_ratio_similar_colors(self):
        """Contrast between nearly identical colors."""
        c1 = Color(0.5, 0.5, 0.5)
        c2 = Color(0.5000001, 0.5000001, 0.5000001)
        ratio = contrast_ratio(c1, c2)
        assert ratio == pytest.approx(1.0, abs=1e-5)


class TestImageEdgeCases:
    """Edge cases for image handling."""

    def test_minimum_valid_image(self):
        """1x1 image (minimum)."""
        img = RasterImage(1, 1, (Color(0, 0, 0),))
        assert img.width == 1
        assert img.height == 1
        assert len(img.pixels) == 1

    def test_extreme_aspect_ratios(self):
        """Images with extreme aspect ratios."""
        # 1x10000
        pixels = tuple(Color(0, 0, 0) for _ in range(10000))
        img = RasterImage(1, 10000, pixels)
        assert img.height == 10000

        # 10000x1
        pixels = tuple(Color(0, 0, 0) for _ in range(10000))
        img = RasterImage(10000, 1, pixels)
        assert img.width == 10000

    def test_pixel_count_mismatch_off_by_one(self):
        """Pixel count differs by exactly 1."""
        with pytest.raises(ValueError, match="expected 4 pixels"):
            RasterImage(2, 2, tuple(Color(0, 0, 0) for _ in range(3)))

    def test_empty_image(self):
        """0x0 image (invalid)."""
        with pytest.raises(ValueError, match="dimensions must be positive"):
            RasterImage(0, 0, ())

    def test_negative_dimensions(self):
        """Negative width or height."""
        with pytest.raises(ValueError, match="dimensions must be positive"):
            RasterImage(-1, 10, tuple(Color(0, 0, 0) for _ in range(10)))
        with pytest.raises(ValueError, match="dimensions must be positive"):
            RasterImage(10, -1, tuple(Color(0, 0, 0) for _ in range(10)))

    def test_region_with_whitespace(self):
        """Region string with various whitespace."""
        variants = [
            "0,0,10,10",
            " 0 , 0 , 10 , 10 ",
            "  0  ,  0  ,  10  ,  10  ",
        ]
        for variant in variants:
            region = Region.parse(variant)
            assert region.x == 0 and region.y == 0
            assert region.width == 10 and region.height == 10

    def test_region_parse_float_values(self):
        """Region string with float values (should fail)."""
        with pytest.raises(ValueError, match="must be integers"):
            Region.parse("0.5,0,10,10")

    def test_region_clamp_completely_outside(self):
        """Region completely outside image bounds."""
        image = RasterImage(10, 10, tuple(Color(0, 0, 0) for _ in range(100)))
        region = Region(10, 10, 10, 10)
        with pytest.raises(ValueError):
            region.clamp_to(image)

    def test_region_clamp_partially_outside(self):
        """Region extends beyond image boundary."""
        image = RasterImage(10, 10, tuple(Color(0, 0, 0) for _ in range(100)))
        region = Region(8, 8, 5, 5)  # Extends to (13, 13), but image is 10x10
        clamped = region.clamp_to(image)
        assert clamped.width == 2
        assert clamped.height == 2

    def test_region_zero_dimensions(self):
        """Region with zero width or height."""
        with pytest.raises(ValueError, match="width/height must be positive"):
            Region(0, 0, 0, 10)
        with pytest.raises(ValueError, match="width/height must be positive"):
            Region(0, 0, 10, 0)

    def test_region_negative_coordinates(self):
        """Region with negative x or y."""
        with pytest.raises(ValueError, match="x/y must be non-negative"):
            Region(-1, 0, 10, 10)
        with pytest.raises(ValueError, match="x/y must be non-negative"):
            Region(0, -1, 10, 10)


class TestContrastEstimationEdgeCases:
    """Edge cases for contrast estimation."""

    def test_percentile_zero_invalid(self):
        """Percentile exactly 0 (invalid)."""
        image = RasterImage(2, 1, (Color(0, 0, 0), Color(1, 1, 1)))
        with pytest.raises(ValueError, match="percentile must be > 0"):
            estimate_raster_contrast(image, percentile=0.0)

    def test_percentile_exactly_half(self):
        """Percentile exactly at boundary 0.5."""
        colors = [Color(0, 0, 0) for _ in range(10)] + [Color(1, 1, 1) for _ in range(10)]
        image = RasterImage(2, 10, tuple(colors))
        estimate = estimate_raster_contrast(image, percentile=0.5)
        # Should sample 5 pixels (50%) from each end
        assert estimate.sampled_pixels == 5

    def test_percentile_just_beyond_boundary(self):
        """Percentile just beyond 0.5 (invalid)."""
        image = RasterImage(10, 10, tuple(Color(0, 0, 0) for _ in range(100)))
        with pytest.raises(ValueError, match="percentile must be"):
            estimate_raster_contrast(image, percentile=0.5000001)

    def test_contrast_uniform_color(self):
        """Contrast of uniform color image."""
        image = RasterImage(10, 10, tuple(Color(0.5, 0.5, 0.5) for _ in range(100)))
        estimate = estimate_raster_contrast(image, percentile=0.1)
        # Contrast should be 1.0 (identical colors)
        assert estimate.contrast == pytest.approx(1.0)

    def test_tiny_image_with_percentile(self):
        """Very small image with percentile sampling."""
        image = RasterImage(2, 1, (Color(0, 0, 0), Color(1, 1, 1)))
        estimate = estimate_raster_contrast(image, percentile=0.5)
        # With 2 pixels and percentile=0.5, sample_size should be max(1, round(2*0.5)) = 1
        assert estimate.sampled_pixels == 1

    @pytest.mark.parametrize("threshold", [0, -1, float("inf")])
    def test_contrast_invalid_thresholds(self, threshold):
        """Invalid threshold values."""
        # Threshold values <= 0 or infinity might not be validated
        # This documents current behavior
        image = RasterImage(2, 1, (Color(0, 0, 0), Color(1, 1, 1)))
        estimate = estimate_raster_contrast(image, threshold=threshold)
        # Currently no validation, so these pass through


class TestSampleClassificationEdgeCases:
    """Edge cases for sample classification."""

    def test_luminance_just_below_low_threshold(self):
        """Luminance just below 0.35."""
        sample = Sample(0.3499999, variance=0)
        classification = classify_sample(sample)
        assert classification.risk == "dark-low-risk"

    def test_luminance_exactly_at_low_threshold(self):
        """Luminance exactly 0.35."""
        sample = Sample(0.35, variance=0)
        classification = classify_sample(sample)
        # Currently: balanced (0.35 is not < 0.35)
        assert classification.risk == "balanced-medium-risk"

    def test_luminance_just_above_low_threshold(self):
        """Luminance just above 0.35."""
        sample = Sample(0.3500001, variance=0)
        classification = classify_sample(sample)
        assert classification.risk == "balanced-medium-risk"

    def test_luminance_exactly_at_high_threshold(self):
        """Luminance exactly 0.65."""
        sample = Sample(0.65, variance=0)
        classification = classify_sample(sample)
        # Currently: balanced (0.65 is not > 0.65)
        assert classification.risk == "balanced-medium-risk"

    def test_luminance_just_above_high_threshold(self):
        """Luminance just above 0.65."""
        sample = Sample(0.6500001, variance=0)
        classification = classify_sample(sample)
        assert classification.risk == "bright-high-risk"

    def test_variance_exactly_at_threshold(self):
        """Variance exactly 0.08."""
        sample = Sample(0.5, variance=0.08)
        classification = classify_sample(sample)
        assert classification.risk == "high-variance-high-risk"

    def test_variance_just_below_threshold(self):
        """Variance just below 0.08."""
        sample = Sample(0.5, variance=0.0799999)
        classification = classify_sample(sample)
        assert classification.risk == "balanced-medium-risk"

    def test_variance_priority_over_luminance(self):
        """High variance overrides bright luminance."""
        sample = Sample(0.9, variance=0.1)
        classification = classify_sample(sample)
        # Variance >= 0.08 takes priority
        assert classification.risk == "high-variance-high-risk"

    def test_extreme_variance(self):
        """Variance much higher than 0.08."""
        sample = Sample(0.5, variance=1.0)
        classification = classify_sample(sample)
        assert classification.risk == "high-variance-high-risk"


class TestModeSelectorEdgeCases:
    """Edge cases for mode selection and hysteresis."""

    def test_mode_selector_immediate_switch(self):
        """With stable_samples_required=1, switch immediately."""
        selector = ModeSelector(stable_samples_required=1)
        mode, classification, switched = selector.observe(Sample(0.8, 0))
        assert switched is True
        assert mode == "bright-safe"

    def test_mode_selector_hysteresis_blocks_small_delta(self):
        """Hysteresis prevents switching with small luminance delta."""
        selector = ModeSelector(current_mode="dark-glass", min_luminance_delta=0.1)
        # First sample: observe a bright sample
        selector.observe(Sample(0.8, 0))

        # Artificially set last switch luminance
        selector._last_switch_luminance = 0.8

        # Try to switch back with delta < threshold
        mode, _, switched = selector.observe(Sample(0.75, 0))  # delta = 0.05
        assert switched is False
        assert mode == "dark-glass"  # Stayed in original mode

    def test_mode_selector_hysteresis_exact_boundary(self):
        """Hysteresis at exact threshold boundary."""
        selector = ModeSelector(min_luminance_delta=0.1)
        selector._last_switch_luminance = 0.5

        # delta = 0.1 exactly (should use < check)
        sample = Sample(0.6, 0)
        mode, _, switched = selector.observe(sample)
        # With `<`, delta=0.1 is NOT < 0.1, so switch is blocked
        assert switched is False

    def test_mode_selector_invalid_stable_samples(self):
        """Stable samples < 1 is invalid."""
        with pytest.raises(ValueError, match="stable_samples_required must be >= 1"):
            ModeSelector(stable_samples_required=0)
        with pytest.raises(ValueError):
            ModeSelector(stable_samples_required=-1)


class TestFileIOEdgeCases:
    """Edge cases for atomic write and backup operations."""

    def test_atomic_write_creates_parent_directories(self, tmp_path):
        """Parent directories are created if missing."""
        target = tmp_path / "subdir1" / "subdir2" / "file.txt"
        atomic_write_text(target, "content")
        assert target.exists()
        assert target.read_text() == "content"

    def test_atomic_write_empty_string(self, tmp_path):
        """Writing empty string succeeds."""
        target = tmp_path / "empty.txt"
        atomic_write_text(target, "")
        assert target.exists()
        assert target.read_text() == ""

    def test_atomic_write_large_content(self, tmp_path):
        """Writing large content (10MB)."""
        target = tmp_path / "large.txt"
        content = "x" * (10 * 1024 * 1024)
        atomic_write_text(target, content)
        assert len(target.read_text()) == len(content)

    def test_atomic_write_unicode_path(self, tmp_path):
        """Unicode characters in file path."""
        target = tmp_path / "файл_测试.txt"
        atomic_write_text(target, "content")
        assert target.exists()
        assert target.read_text() == "content"

    def test_atomic_write_overwrites_existing(self, tmp_path):
        """Overwrites existing file atomically."""
        target = tmp_path / "file.txt"
        target.write_text("original")
        atomic_write_text(target, "updated")
        assert target.read_text() == "updated"

    def test_backup_nonexistent_file(self, tmp_path):
        """Backup of nonexistent file is no-op."""
        source = tmp_path / "nonexistent.txt"
        backup = backup_file(source)
        assert not backup.exists()

    def test_backup_existing_file(self, tmp_path):
        """Backup of existing file creates backup."""
        source = tmp_path / "file.txt"
        source.write_text("content")
        backup = backup_file(source)
        assert backup.exists()
        assert backup.read_text() == "content"

    def test_unique_backup_path_special_chars(self, tmp_path):
        """Backup path generation with special characters."""
        source = tmp_path / "file with spaces.txt"
        backup = unique_backup_path(source)
        assert ".backup." in str(backup)


class TestConcurrencyEdgeCases:
    """Edge cases for concurrent operations."""

    def test_concurrent_atomic_writes(self, tmp_path):
        """Multiple threads writing to same file."""
        target = tmp_path / "file.txt"

        def writer(content):
            atomic_write_text(target, content)

        threads = [
            threading.Thread(target=writer, args=("content1",)),
            threading.Thread(target=writer, args=("content2",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # File should exist with one of the contents
        assert target.exists()
        result = target.read_text()
        assert result in ("content1", "content2")

    def test_terminal_detection_with_env_changes(self):
        """Terminal detection with changing environment."""
        with patch.dict(os.environ, {"TERM_PROGRAM": "iTerm.app"}, clear=True):
            info1 = detect_terminal()
            assert info1.is_iterm2

        with patch.dict(os.environ, {"TERM_PROGRAM": "kitty"}, clear=True):
            info2 = detect_terminal()
            assert info2.is_kitty


class TestResourceExhaustion:
    """Edge cases for resource exhaustion."""

    def test_classification_extreme_variance(self):
        """Classification with variance > 1.0 (impossible but edge case)."""
        sample = Sample(0.5, variance=10.0)
        classification = classify_sample(sample)
        assert classification.risk == "high-variance-high-risk"

    def test_contrast_estimation_performance(self):
        """Contrast estimation completes in reasonable time."""
        # 1M colors ranging across spectrum
        colors = tuple(Color(i / 1000000, 0, 0) for i in range(1000000))
        image = RasterImage(1000, 1000, colors)

        start = time.time()
        estimate = estimate_raster_contrast(image, percentile=0.01)
        elapsed = time.time() - start

        # Should complete quickly (< 1 second)
        assert elapsed < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
