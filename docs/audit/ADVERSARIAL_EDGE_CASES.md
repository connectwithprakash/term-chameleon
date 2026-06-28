# Term Chameleon: Adversarial Edge Case Discovery

## Executive Summary

This document outlines critical edge cases and boundary conditions that could cause term-chameleon to fail, behave unexpectedly, or produce incorrect results. Areas covered include terminal detection, color handling, image processing, contrast calculation, and file I/O operations.

**Severity Levels:**
- 🔴 CRITICAL: Could crash, corrupt data, or silently produce incorrect results
- 🟠 HIGH: Degrades functionality or produces misleading output
- 🟡 MEDIUM: Works but suboptimally or with unexpected behavior
- 🟢 LOW: Minor edge case, likely rare in practice

---

## 1. Terminal Detection & OSC Sequences

### 1.1 Missing or Corrupted Environment Variables

**Edge Cases:**
- `TERM_PROGRAM` is empty string (vs. not set)
- `TERM_PROGRAM` contains mixed case variations: `iTerm.APP`, `iterm.APP`, `ITERM2`, `ITERM.app` (case sensitivity)
- `TERM` contains multiple values: `"screen.xterm-256color"`, `"tmux-256color"`, `"xterm-kitty"`
- `GHOSTTY_RESOURCES_DIR` is set but path doesn't exist or is empty string
- Environment variables are extremely long (>10KB)

**Current Implementation:**
```python
# terminal.py, lines 36-42
term_program = os.environ.get("TERM_PROGRAM", "").lower()
term = os.environ.get("TERM", "").lower()
is_iterm2 = term_program == "iterm.app" or term_program == "iterm2"
is_kitty = term_program == "kitty" or "kitty" in term
is_ghostty = ghostty_environ or term_program == "ghostty"
```

**Issues:**
- `"iterm2"` is explicitly checked, but the actual iTerm2 value is `"iTerm.app"` → `.lower()` handles this
- `"kitty" in term` will match unintended values like `"xterm-kitty"` or `"my-kitty-terminal"`
- No validation that `GHOSTTY_RESOURCES_DIR` path is accessible or valid
- No handling for `TERM` values like `"screen.xterm"` which may indicate nested tmux

**Test Scenarios:**
```python
# Test 1: Mixed case variants
@pytest.mark.parametrize("variant", [
    "iTerm.APP", "iterm.APP", "ITERM.app", "iterm.APP",
    "KITTY", "Kitty", "xterm-kitty", "kitty-terminal",
    "GHOSTTY", "Ghostty", "ALACRITTY"
])
def test_terminal_detection_case_insensitivity(variant):
    with patch.dict(os.environ, {"TERM_PROGRAM": variant}, clear=True):
        info = detect_terminal()
        # Assert correct detection despite casing

# Test 2: Kitty substring false positives
def test_kitty_false_positive_in_term():
    with patch.dict(os.environ, {"TERM": "xterm-kitty-256color"}, clear=True):
        # Should not be detected as Kitty, only recognize explicit "kitty" TERM_PROGRAM
        pass

# Test 3: Invalid/missing GHOSTTY_RESOURCES_DIR
def test_ghostty_nonexistent_path():
    with patch.dict(os.environ, {"GHOSTTY_RESOURCES_DIR": "/nonexistent/path"}, clear=True):
        info = detect_terminal()
        assert info.is_ghostty is True
        # But path doesn't exist - might cause issues later

# Test 4: Environment variable pollution
def test_terminal_detection_with_empty_strings():
    with patch.dict(os.environ, {
        "TERM_PROGRAM": "",
        "TERM": "",
        "GHOSTTY_RESOURCES_DIR": ""
    }, clear=True):
        info = detect_terminal()
        assert info.is_supported is False

# Test 5: Very long environment values (potential DoS)
def test_terminal_detection_very_long_env_values():
    with patch.dict(os.environ, {
        "TERM_PROGRAM": "x" * 100000
    }, clear=True):
        info = detect_terminal()
        # Should complete quickly without excessive memory use
```

---

### 1.2 OSC Sequence Edge Cases

**Edge Cases:**
- Stdout is not writable or is redirected to pipe/file
- Stdout encoding is not UTF-8 (e.g., ASCII, Latin-1)
- Escape sequences contain invalid characters or control codes
- Very large preset with many colors (>256 ANSI indices)
- tmux wrapping with nested escape sequences

**Current Implementation:**
```python
# terminal.py, lines 67-83
def apply_osc_to_terminal(preset_name: str, *, reset: bool = False) -> bool:
    seqs = reset_sequences() if reset else sequences_for_preset(preset_name)
    payload = "".join(s.sequence for s in seqs)
    import sys
    sys.stdout.write(payload)
    sys.stdout.flush()
    return True
```

**Issues:**
- No error handling for `sys.stdout.write()` failures (e.g., broken pipe)
- `sys.stdout.flush()` can raise `IOError` if pipe is closed
- No validation that `preset_name` exists before generating sequences
- Return value is always `True` even if flush fails

**Test Scenarios:**
```python
def test_apply_osc_with_closed_stdout():
    import io
    with patch('sys.stdout', io.StringIO()):
        # Manually close the stream
        sys.stdout.close()
        # Should handle gracefully or raise with clear error
        result = apply_osc_to_terminal("balanced")

def test_apply_osc_with_invalid_preset():
    with pytest.raises(KeyError):
        apply_osc_to_terminal("nonexistent-preset-xyz")

def test_apply_osc_reset_still_works_after_error():
    # If initial sequence fails, reset should still be callable
    pass
```

---

## 2. Color Handling

### 2.1 Color Component Boundary Conditions

**Edge Cases:**
- Color components at exact boundaries: 0.0, 1.0, 0.03928 (threshold for luminance)
- Color from extremely large/small hex values
- From hex with lowercase letters: `#aabbcc` vs `#AABBCC`
- From hex with leading/trailing whitespace: `" #FFFFFF "`
- Alpha channel edge cases: 0.0 (fully transparent), 1.0 (fully opaque)
- Very close to boundaries: 0.0000001, 0.9999999

**Current Implementation:**
```python
# color.py, lines 13-16, 19-29
def __post_init__(self) -> None:
    for name, value in (("r", self.r), ("g", self.g), ("b", self.b), ("a", self.a)):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} component must be between 0 and 1, got {value!r}")

@classmethod
def from_hex(cls, value: str) -> Color:
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6:
        raise ValueError(f"expected #RRGGBB color, got {value!r}")
    return cls(
        int(text[0:2], 16) / 255.0,
        int(text[2:4], 16) / 255.0,
        int(text[4:6], 16) / 255.0,
    )
```

**Issues:**
- `from_hex()` doesn't handle lowercase letters (but Python's `int(..., 16)` does, so actually OK)
- No validation for 8-character hex strings (#RRGGBBAA format)
- Floating-point division may produce values slightly outside [0, 1] due to rounding
- `blend_over()` could produce colors slightly outside bounds due to floating-point math

**Test Scenarios:**
```python
# Test 1: Hex parsing edge cases
@pytest.mark.parametrize("hex_str,expected", [
    ("#000000", Color(0, 0, 0)),
    ("#FFFFFF", Color(1, 1, 1)),
    ("#ffffff", Color(1, 1, 1)),  # lowercase
    (" #FFFFFF ", Color(1, 1, 1)),  # whitespace
    ("#aabbcc", Color(170/255, 187/255, 204/255)),
])
def test_color_from_hex_edge_cases(hex_str, expected):
    result = Color.from_hex(hex_str)
    assert result.r == approx(expected.r, abs=1e-9)

# Test 2: 8-character hex (should fail)
def test_color_from_hex_with_alpha():
    with pytest.raises(ValueError):
        Color.from_hex("#FFFFFF80")  # RGBA format

# Test 3: Floating-point precision at boundaries
def test_color_components_at_boundaries():
    c1 = Color(0.0, 0.0, 0.0, 0.0)  # Valid: fully transparent black
    c2 = Color(1.0, 1.0, 1.0, 1.0)  # Valid: fully opaque white
    
# Test 4: Invalid colors just outside bounds
def test_color_invalid_components():
    with pytest.raises(ValueError):
        Color(1.0000001, 0.5, 0.5)
    with pytest.raises(ValueError):
        Color(-0.0000001, 0.5, 0.5)

# Test 5: Blend-over at boundaries
def test_blend_over_with_transparent_foreground():
    fg = Color(1.0, 0.0, 0.0, 0.0)  # Fully transparent red
    bg = Color(0.0, 0.0, 1.0, 1.0)  # Opaque blue
    result = fg.blend_over(bg)
    assert result.r == approx(0.0)  # Should be entirely background
    assert result.g == approx(0.0)
    assert result.b == approx(1.0)
    assert result.a == 1.0
```

---

### 2.2 Luminance & Contrast Calculation Edge Cases

**Edge Cases:**
- Colors with luminance threshold exactly at 0.03928
- Pure white vs pure black
- Very low contrast pairs (almost identical colors)
- Division by zero in contrast_ratio (both luminances 0)
- Extreme colors: (0.0000001, 0, 0) vs (0.9999999, 1, 1)

**Current Implementation:**
```python
# color.py, lines 52-58
def relative_luminance(self) -> float:
    def channel(c: float) -> float:
        if c <= 0.03928:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(self.r) + 0.7152 * channel(self.g) + 0.0722 * channel(self.b)

# contrast.py, lines 6-14
def contrast_ratio(foreground: Color, background: Color) -> float:
    fg = foreground.blend_over(background) if foreground.a < 1 else foreground
    bg = background
    l1 = fg.relative_luminance()
    l2 = bg.relative_luminance()
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)
```

**Issues:**
- No explicit handling for the 0.03928 threshold boundary
- `(lighter + 0.05) / (darker + 0.05)` is safe from division by zero (minimum ratio is 1.0)
- Floating-point precision issues near threshold could cause inconsistent results

**Test Scenarios:**
```python
# Test 1: Luminance threshold boundary
def test_relative_luminance_at_threshold():
    c1 = Color(0.03928, 0, 0)  # Exactly at threshold
    c2 = Color(0.0393, 0, 0)   # Just above threshold
    c3 = Color(0.03927, 0, 0)  # Just below threshold
    lum1 = c1.relative_luminance()
    lum2 = c2.relative_luminance()
    lum3 = c3.relative_luminance()
    # Verify monotonic increase

# Test 2: Extreme contrast pairs
def test_contrast_ratio_extremes():
    black = Color(0, 0, 0)
    white = Color(1, 1, 1)
    ratio = contrast_ratio(black, white)
    assert ratio == approx(21.0, rel=1e-3)

# Test 3: Very similar colors (low contrast)
def test_contrast_ratio_similar_colors():
    c1 = Color(0.5, 0.5, 0.5)
    c2 = Color(0.5000001, 0.5000001, 0.5000001)
    ratio = contrast_ratio(c1, c2)
    assert ratio == approx(1.0, abs=1e-6)

# Test 4: Transparent color blending edge case
def test_contrast_with_fully_transparent_fg():
    fg = Color(1, 0, 0, 0.0)  # Fully transparent red
    bg = Color(0, 0, 1, 1.0)  # Opaque blue
    ratio = contrast_ratio(fg, bg)
    # Should be contrast of blue with itself (1.0)
    assert ratio == approx(1.0)
```

---

## 3. Image & Pixel Processing

### 3.1 RasterImage Construction Edge Cases

**Edge Cases:**
- 1x1 image (minimum valid)
- 1x1000000 or 1000000x1 images (extreme aspect ratios)
- Image dimensions > available memory (10000x10000 = 100M pixels)
- Pixel tuple length mismatch by 1
- Empty pixel tuple (0 pixels)
- Pixel tuple too large

**Current Implementation:**
```python
# images.py, lines 10-21
@dataclass(frozen=True)
class RasterImage:
    width: int
    height: int
    pixels: tuple[Color, ...]

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("image dimensions must be positive")
        if len(self.pixels) != self.width * self.height:
            raise ValueError(f"expected {self.width * self.height} pixels, got {len(self.pixels)}")
```

**Issues:**
- Multiplication `width * height` could overflow (though unlikely in practice for int in Python)
- No validation that dimensions are reasonable (e.g., < 100000)
- Large images could consume excessive memory when created

**Test Scenarios:**
```python
# Test 1: Minimum valid image
def test_minimum_valid_image():
    img = RasterImage(1, 1, (Color(0, 0, 0),))
    assert img.width == 1
    assert img.height == 1

# Test 2: Extreme aspect ratios
def test_extreme_aspect_ratio():
    # 1x10000 image
    pixels = tuple(Color(0, 0, 0) for _ in range(10000))
    img = RasterImage(1, 10000, pixels)
    assert img.height == 10000

# Test 3: Pixel count mismatch by 1
def test_pixel_count_off_by_one():
    with pytest.raises(ValueError, match="expected 4 pixels"):
        RasterImage(2, 2, tuple(Color(0, 0, 0) for _ in range(3)))

# Test 4: Empty image
def test_empty_image():
    with pytest.raises(ValueError):
        RasterImage(0, 0, ())

# Test 5: Large image doesn't crash (memory check)
def test_large_image_creation():
    # 1000x1000 = 1M pixels
    pixels = tuple(Color(0.5, 0.5, 0.5) for _ in range(1000000))
    img = RasterImage(1000, 1000, pixels)
    assert len(img.pixels) == 1000000
```

---

### 3.2 Region Parsing & Clamping Edge Cases

**Edge Cases:**
- Region string with extra whitespace: `" 0 , 0 , 10 , 10 "`, `"0 , 0, 10 , 10"`
- Region string with non-integer values: `"0.5,0,10,10"`, `"0,0,10,abc"`
- Region at image origin: `(0,0)` with width/height
- Region completely outside image: `x >= width` or `y >= height`
- Region partially outside (needs clamping)
- Region with zero or negative dimensions: `-1,0,10,10`, `0,0,0,10`

**Current Implementation:**
```python
# images.py, lines 32-62
@classmethod
def parse(cls, raw: str) -> Region:
    parts = raw.split(",")
    if len(parts) != 4:
        raise ValueError("region must be x,y,width,height")
    try:
        x, y, width, height = (int(part.strip()) for part in parts)
    except ValueError as exc:
        raise ValueError("region values must be integers") from exc
    return cls(x, y, width, height)

def clamp_to(self, image: RasterImage) -> Region:
    if self.x >= image.width or self.y >= image.height:
        raise ValueError(...)
    width = min(self.width, image.width - self.x)
    height = min(self.height, image.height - self.y)
    return Region(self.x, self.y, width, height)
```

**Issues:**
- `clamp_to()` raises error if region origin is outside, but should perhaps clamp instead
- Clamping produces 0-width/height regions (e.g., x=9, image.width=10, original.width=1 → clamped width=1)

**Test Scenarios:**
```python
# Test 1: Whitespace in region string
@pytest.mark.parametrize("region_str", [
    " 0 , 0 , 10 , 10 ",
    "0,0,10,10",
    "  0  ,  0  ,  10  ,  10  ",
])
def test_region_parse_whitespace(region_str):
    region = Region.parse(region_str)
    assert region.x == 0 and region.y == 0
    assert region.width == 10 and region.height == 10

# Test 2: Non-integer region values
def test_region_parse_float():
    with pytest.raises(ValueError, match="must be integers"):
        Region.parse("0.5,0,10,10")

# Test 3: Region completely outside image
def test_region_clamp_completely_outside():
    image = RasterImage(10, 10, tuple(Color(0, 0, 0) for _ in range(100)))
    region = Region(10, 10, 10, 10)
    with pytest.raises(ValueError):
        region.clamp_to(image)

# Test 4: Region partially outside (edge case at boundary)
def test_region_clamp_at_boundary():
    image = RasterImage(10, 10, tuple(Color(0, 0, 0) for _ in range(100)))
    region = Region(8, 8, 5, 5)  # Extends beyond 10x10
    clamped = region.clamp_to(image)
    assert clamped.width == 2
    assert clamped.height == 2

# Test 5: Region with zero dimensions
def test_region_zero_dimensions():
    with pytest.raises(ValueError):
        Region(0, 0, 0, 10)
    with pytest.raises(ValueError):
        Region(0, 0, 10, 0)
```

---

### 3.3 Image Statistics Sampling Edge Cases

**Edge Cases:**
- Image with 1 pixel (cannot calculate variance)
- Image with 2 pixels (edge case for sampling)
- `max_pixels=1` with large image
- `max_pixels=0` or negative
- Uniform color image (variance = 0)
- Image with extreme luminance values
- Very large sample size requested

**Issues:**
- Sampling algorithm divides image into regions and samples uniformly
- Edge cases around sample size boundaries not well tested

---

## 4. Contrast Estimation & Thresholding

### 4.1 Percentile Boundary Conditions

**Edge Cases:**
- `percentile=0.0` (should fail: "must be > 0")
- `percentile=0.5` (exactly at boundary)
- `percentile=0.5000001` (just beyond boundary)
- `percentile=0.0001` (very small)
- Very small image (< 100 pixels)

**Current Implementation:**
```python
# pixel_contrast.py, lines 37-46, 59-85
def estimate_image_contrast(
    image_path: str | Path,
    *,
    region: Region | None = None,
    threshold: float = 4.5,
    percentile: float = 0.10,
) -> ContrastEstimate:
    if not 0 < percentile <= 0.5:
        raise ValueError("percentile must be > 0 and <= 0.5")
    ...
    sample_size = max(1, round(len(pixels) * percentile))
```

**Issues:**
- `sample_size = max(1, round(...))` means even with 2 pixels and percentile=0.1, sample_size=1
- Rounding could cause sample_size > len(pixels)//2 (violates percentile assumption)
- Edge case: image with 2 pixels, percentile=0.5 → sample_size=1 (could give misleading results)

**Test Scenarios:**
```python
# Test 1: Very small image
def test_contrast_estimation_tiny_image():
    image = RasterImage(2, 1, (Color(0, 0, 0), Color(1, 1, 1)))
    estimate = estimate_raster_contrast(image, percentile=0.5)
    assert estimate.sampled_pixels == 1

# Test 2: Percentile boundary exactly at 0.5
def test_percentile_exactly_half():
    colors = [Color(0, 0, 0) for _ in range(10)] + [Color(1, 1, 1) for _ in range(10)]
    image = RasterImage(2, 10, tuple(colors))
    estimate = estimate_raster_contrast(image, percentile=0.5)
    # Should sample 5 pixels (50%)
    assert estimate.sampled_pixels == 5

# Test 3: Percentile just beyond boundary
def test_percentile_invalid_boundary():
    with pytest.raises(ValueError):
        image = RasterImage(10, 10, tuple(Color(0, 0, 0) for _ in range(100)))
        estimate_raster_contrast(image, percentile=0.5000001)

# Test 4: Uniform color image (no contrast)
def test_contrast_uniform_color():
    image = RasterImage(10, 10, tuple(Color(0.5, 0.5, 0.5) for _ in range(100)))
    estimate = estimate_raster_contrast(image, percentile=0.1)
    assert estimate.contrast == approx(1.0)
```

---

### 4.2 Threshold & Percentile Validation

**Edge Cases:**
- `threshold=0` or negative (WCAG contrast ratios are always >= 1.0)
- `threshold=1.0` (edge case: all images "pass")
- `threshold=21.0` (maximum contrast, very few images pass)
- `threshold=float('inf')` or `float('nan')`

**Test Scenarios:**
```python
# Test 1: Edge case thresholds
@pytest.mark.parametrize("threshold", [0, -1, 1.0, 21.0, float('inf')])
def test_contrast_estimate_with_edge_thresholds(threshold):
    image = RasterImage(2, 1, (Color(0, 0, 0), Color(1, 1, 1)))
    if threshold <= 0 or threshold == float('inf'):
        # Might need validation
        pass
    estimate = estimate_raster_contrast(image, threshold=threshold)
    assert estimate.threshold == threshold
```

---

## 5. Sample Classification & Mode Selection

### 5.1 Classification Boundary Conditions

**Edge Cases:**
- `luminance=0.35` (exactly at boundary)
- `luminance=0.65` (exactly at boundary)
- `variance=0.08` (exactly at boundary)
- `luminance=0.0` (black)
- `luminance=1.0` (white)
- `variance=0.0` (uniform)
- Extremely high variance (e.g., 1.0)

**Current Implementation:**
```python
# watch.py, lines 43-56
def classify_sample(sample: Sample) -> Classification:
    if sample.variance >= 0.08:
        risk = "high-variance-high-risk"
        reason = f"variance {sample.variance:.2f} >= 0.08"
    elif sample.luminance > 0.65:
        risk = "bright-high-risk"
        reason = f"luminance {sample.luminance:.2f} > 0.65"
    elif sample.luminance < 0.35:
        risk = "dark-low-risk"
        reason = f"luminance {sample.luminance:.2f} < 0.35"
    else:
        risk = "balanced-medium-risk"
        reason = f"luminance {sample.luminance:.2f} in balanced range"
```

**Issues:**
- Boundary conditions use `>`, `<`, `>=` inconsistently:
  - `luminance > 0.65` means 0.65 is balanced, not bright
  - `luminance < 0.35` means 0.35 is balanced, not dark
  - `variance >= 0.08` means exactly 0.08 is high-variance
- Dead zone at 0.35-0.65 for luminance
- No explicit handling for variance exactly at 0.08

**Test Scenarios:**
```python
# Test 1: Luminance boundary conditions
@pytest.mark.parametrize("luminance,expected_risk", [
    (0.34, "dark-low-risk"),
    (0.35, "balanced-medium-risk"),  # Boundary
    (0.36, "balanced-medium-risk"),
    (0.64, "balanced-medium-risk"),
    (0.65, "balanced-medium-risk"),  # Boundary
    (0.66, "bright-high-risk"),
])
def test_classify_luminance_boundaries(luminance, expected_risk):
    sample = Sample(luminance, variance=0)
    classification = classify_sample(sample)
    assert classification.risk == expected_risk

# Test 2: Variance boundary exactly at 0.08
def test_classify_variance_boundary():
    sample = Sample(0.5, variance=0.08)
    classification = classify_sample(sample)
    assert classification.risk == "high-variance-high-risk"
    
    sample2 = Sample(0.5, variance=0.0799999)
    classification2 = classify_sample(sample2)
    assert classification2.risk == "balanced-medium-risk"

# Test 3: Extreme variance
def test_classify_extreme_variance():
    sample = Sample(0.5, variance=1.0)
    classification = classify_sample(sample)
    assert classification.risk == "high-variance-high-risk"

# Test 4: Verify priority: variance > luminance
def test_classify_variance_takes_priority():
    # High variance should override bright luminance
    sample = Sample(luminance=0.9, variance=0.1)
    classification = classify_sample(sample)
    assert classification.risk == "high-variance-high-risk"
```

---

### 5.2 ModeSelector Stability & Edge Cases

**Edge Cases:**
- `stable_samples_required=1` (should switch immediately)
- `stable_samples_required=0` or negative (invalid)
- `min_luminance_delta=0` (no hysteresis)
- Exactly meeting delta threshold: `delta == min_luminance_delta`
- Alternating between two modes (thrashing)
- Single sample that crosses boundary
- Mode selector with invalid initial mode

**Current Implementation:**
```python
# watch.py, lines 59-97
class ModeSelector:
    def __post_init__(self) -> None:
        if self.stable_samples_required < 1:
            raise ValueError("stable_samples_required must be >= 1")
        ...
    
    def observe(self, sample: Sample) -> tuple[str, Classification, bool]:
        classification = classify_sample(sample)
        candidate = classification.mode
        if candidate == self.current_mode:
            return self.current_mode, classification, False

        if self._last_switch_luminance is not None:
            delta = abs(sample.luminance - self._last_switch_luminance)
            if delta < self.min_luminance_delta:
                return self.current_mode, classification, False
        ...
```

**Issues:**
- Hysteresis uses `<`, not `<=` → exactly at boundary still rejects
- `_last_switch_luminance` initialized to None, preventing hysteresis check on first switch
- No validation of `min_luminance_delta` (could be negative or NaN)

**Test Scenarios:**
```python
# Test 1: Immediate mode switch with stable_samples_required=1
def test_mode_selector_immediate_switch():
    selector = ModeSelector(stable_samples_required=1)
    mode, classification, switched = selector.observe(Sample(0.8, 0))
    assert switched is True
    assert mode == "bright-safe"

# Test 2: Hysteresis prevents rapid switching
def test_mode_selector_hysteresis():
    selector = ModeSelector(
        current_mode="dark-glass",
        stable_samples_required=1,
        min_luminance_delta=0.1
    )
    # Simulate a bright sample
    mode1, _, switched1 = selector.observe(Sample(0.8, 0))
    assert switched1 is True
    assert mode1 == "bright-safe"
    
    # Try to switch back with small delta
    selector._last_switch_luminance = 0.8
    mode2, _, switched2 = selector.observe(Sample(0.75, 0))  # delta = 0.05
    assert switched2 is False  # Should reject due to hysteresis

# Test 3: Hysteresis at exact boundary
def test_mode_selector_hysteresis_exact_boundary():
    selector = ModeSelector(min_luminance_delta=0.1)
    selector._last_switch_luminance = 0.5
    sample = Sample(0.6, 0)  # delta = 0.1 exactly
    mode, _, switched = selector.observe(sample)
    # With `<`, delta=0.1 should NOT switch (needs > 0.1)
    assert switched is False

# Test 4: Negative or invalid delta
def test_mode_selector_invalid_delta():
    selector = ModeSelector(min_luminance_delta=-0.1)
    # Might not validate, could lead to unexpected behavior
    mode, _, switched = selector.observe(Sample(0.5, 0))
```

---

## 6. File I/O & Atomic Operations

### 6.1 atomic_write_text Edge Cases

**Edge Cases:**
- Target directory doesn't exist (requires parent creation)
- Target is a symlink (replace behavior)
- Parent directory is read-only
- Disk full during write
- Concurrent writes to same file
- Extremely long filename or path
- Content is empty string
- Content contains null bytes or invalid UTF-8

**Current Implementation:**
```python
# safe_io.py, lines 30-45
def atomic_write_text(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        tmp.replace(target)
    except Exception:
        with suppress(FileNotFoundError):
            tmp.unlink()
        raise
```

**Issues:**
- If `target.parent.mkdir()` fails, exception is raised before temp file cleanup
- `os.fsync()` can fail on some filesystems (e.g., FAT32)
- Race condition: if process crashes between fsync and replace, orphaned temp file remains
- No handling for when `tmp.replace(target)` fails

**Test Scenarios:**
```python
# Test 1: Target directory doesn't exist
def test_atomic_write_creates_parent():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "subdir1" / "subdir2" / "file.txt"
        atomic_write_text(target, "content")
        assert target.exists()
        assert target.read_text() == "content"

# Test 2: Empty content
def test_atomic_write_empty_string():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "empty.txt"
        atomic_write_text(target, "")
        assert target.exists()
        assert target.read_text() == ""

# Test 3: Symlink replacement
def test_atomic_write_symlink():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "target.txt"
        symlink = Path(tmpdir) / "link.txt"
        target.write_text("original")
        symlink.symlink_to(target)
        atomic_write_text(symlink, "updated")
        # symlink should now point to updated content (or be replaced)

# Test 4: Parent directory read-only
def test_atomic_write_readonly_parent():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "readonly" / "file.txt"
        target.parent.mkdir()
        target.parent.chmod(0o555)  # Read-only
        try:
            with pytest.raises(PermissionError):
                atomic_write_text(target, "content")
        finally:
            target.parent.chmod(0o755)  # Restore permissions

# Test 5: Disk full simulation
@pytest.mark.skip(reason="Hard to simulate disk full in test")
def test_atomic_write_disk_full():
    # Would need mocking of write() to raise OSError
    pass
```

---

### 6.2 backup_file & unique_backup_path Edge Cases

**Edge Cases:**
- Original file doesn't exist (backup created from nothing?)
- Original file has unusual characters in name: spaces, Unicode, etc.
- Backup directory has thousands of backups (counter increments hugely)
- Timestamp precision issues (multiple backups in same millisecond)
- Filesystem doesn't support backup files (e.g., read-only mount)

**Current Implementation:**
```python
# safe_io.py, lines 11-28
def unique_backup_path(path: str | Path) -> Path:
    source = Path(path)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S.%f")
    candidate = source.with_name(f"{source.name}.backup.{stamp}")
    counter = 1
    while candidate.exists():
        candidate = source.with_name(f"{source.name}.backup.{stamp}.{counter}")
        counter += 1
    return candidate

def backup_file(path: str | Path) -> Path:
    source = Path(path)
    backup = unique_backup_path(source)
    if source.exists():
        shutil.copy2(source, backup)
    return backup
```

**Issues:**
- `backup_file()` returns backup path even if source doesn't exist (silent no-op)
- No limit on counter (if millions of backups exist, could loop forever)
- Timestamp granularity (microseconds) could still have collisions under rapid fire

**Test Scenarios:**
```python
# Test 1: Original doesn't exist
def test_backup_nonexistent_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "nonexistent.txt"
        backup = backup_file(source)
        assert backup.exists() is False  # Backup wasn't created
        assert not backup.exists()

# Test 2: Backup path with special characters
def test_unique_backup_path_special_chars():
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "file with spaces.txt"
        backup = unique_backup_path(source)
        # Should construct valid path
        assert ".backup." in str(backup)

# Test 3: Many backups (counter performance)
def test_unique_backup_path_many_collisions():
    with tempfile.TemporaryDirectory() as tmpdir:
        source = Path(tmpdir) / "file.txt"
        # Create many backup files with same timestamp
        base_name = "file.txt.backup.20240101T000000.000000"
        for i in range(10):
            Path(tmpdir, f"{base_name}.{i}").write_text(f"backup {i}")
        
        backup = unique_backup_path(source)
        # Should find the next available counter
        assert str(backup).endswith(".10")
```

---

## 7. Terminal Size & Display Boundaries

### 7.1 Extreme Terminal Sizes

**Edge Cases:**
- 1x1 terminal (minimum)
- 1x10000 terminal (tall, narrow)
- 10000x1 terminal (wide, short)
- Terminal size changes during operation
- Terminal size reported as 0x0 (error case)
- Terminal size is negative (should never happen, but defensive coding)

**Test Scenarios:**
```python
# Test 1: Minimum terminal size
def test_terminal_size_1x1():
    # If code renders ANSI patterns, ensure it handles 1x1
    pass

# Test 2: Terminal size edge cases
@pytest.mark.parametrize("rows,cols", [
    (1, 1),
    (1, 10000),
    (10000, 1),
    (0, 10),
    (10, 0),
    (-1, 10),
])
def test_extreme_terminal_sizes(rows, cols):
    # Validate that code gracefully handles or rejects invalid sizes
    pass
```

---

## 8. Resource Exhaustion

### 8.1 Memory & CPU Extremes

**Edge Cases:**
- Very large screenshots (50000x50000 pixels)
- Recursive symlink loops
- Infinite loops in classification algorithm
- Stack overflow from deep recursion
- High-frequency OSC sequence generation

**Test Scenarios:**
```python
# Test 1: Large image handling
def test_very_large_image_sampling():
    # Don't create the actual image, but test sampling logic
    # with hypothetical 100M pixel image
    pass

# Test 2: Classification with extreme variance
def test_classification_extreme_values():
    # Variance > 1.0 (technically impossible with normalized colors)
    sample = Sample(0.5, variance=10.0)
    classification = classify_sample(sample)
    assert classification.risk == "high-variance-high-risk"

# Test 3: Contrast estimation timeout (does it complete?)
def test_contrast_estimation_performance():
    # Large image should complete quickly
    colors = [Color(i/1000, 0, 0) for i in range(1000000)]
    image = RasterImage(1000, 1000, tuple(colors))
    # Should complete in < 1 second
    start = time.time()
    estimate = estimate_raster_contrast(image, percentile=0.01)
    elapsed = time.time() - start
    assert elapsed < 1.0
```

---

## 9. Concurrency & Race Conditions

### 9.1 Concurrent File Operations

**Edge Cases:**
- Two processes writing to same backup file
- Terminal detection while environment changes
- Screenshot capture while display changes
- Reading image while another process modifies it

**Test Scenarios:**
```python
# Test 1: Concurrent atomic writes
def test_atomic_write_concurrent():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "file.txt"
        
        def writer(content):
            atomic_write_text(target, content)
        
        # Run two threads simultaneously
        t1 = threading.Thread(target=writer, args=("content1",))
        t2 = threading.Thread(target=writer, args=("content2",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # File should exist and contain one of the contents
        assert target.exists()
        result = target.read_text()
        assert result in ("content1", "content2")
```

---

## 10. Encoding & Text Handling

### 10.1 UTF-8 & Special Characters

**Edge Cases:**
- Preset names with Unicode characters
- File paths with Unicode characters
- Color hex values with invalid characters: `#GGGGGG`, `#12345G`
- ANSI pattern with invalid escape sequences
- Extremely long escape sequences

**Current Implementation Issues:**
- `from_hex()` calls `int(text[0:2], 16)` without catching all exceptions
- OSC sequence generation doesn't validate color format

**Test Scenarios:**
```python
# Test 1: Invalid hex characters
def test_color_hex_invalid_characters():
    with pytest.raises(ValueError):
        Color.from_hex("#GGGGGG")
    with pytest.raises(ValueError):
        Color.from_hex("#12345G")

# Test 2: Unicode in paths
def test_atomic_write_unicode_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "файл_测试.txt"
        atomic_write_text(target, "content")
        assert target.exists()
        assert target.read_text() == "content"

# Test 3: Very long content
def test_atomic_write_large_content():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "large.txt"
        content = "x" * (10 * 1024 * 1024)  # 10MB
        atomic_write_text(target, content)
        assert target.read_text() == content
```

---

## 11. Summary of High-Priority Issues

### CRITICAL (🔴)

1. **Terminal Detection: Kitty Substring False Positive**
   - `"kitty" in term` matches `"xterm-kitty"` unintentionally
   - Recommendation: Check for exact TERM_PROGRAM match first, then TERM exact value

2. **OSC Sequence Output Error Handling**
   - `sys.stdout.write()` and `sys.stdout.flush()` can raise IOError
   - Return value always True even on failure
   - Recommendation: Add try-except and proper error propagation

3. **Floating-Point Precision in Color Components**
   - `blend_over()` could produce colors slightly outside [0, 1] bounds
   - Recommendation: Clamp results or add epsilon tolerance

4. **Region Parsing Accepts Negative Coordinates**
   - No validation in `__post_init__` for x < 0
   - Recommendation: Add validation

### HIGH (🟠)

5. **Mode Selector Hysteresis Boundary Condition**
   - Uses `<` instead of `<=` for min_luminance_delta check
   - Samples exactly at boundary are rejected
   - Recommendation: Document behavior or use `<=`

6. **atomic_write_text Error Recovery**
   - If mkdir fails, temp file not cleaned up
   - If replace fails, orphaned temp file remains
   - Recommendation: Ensure all paths clean up temp files

7. **Classification Boundary Condition Inconsistency**
   - Luminance boundaries use `<` and `>` (off-by-one in classification)
   - 0.35 and 0.65 are in "balanced" rather than at boundaries
   - Recommendation: Document intended boundaries and add tests

### MEDIUM (🟡)

8. **Sample Size Calculation with Small Images**
   - `max(1, round(...))` can produce misleading results with 2-3 pixel images
   - Recommendation: Add minimum image size validation

9. **Mode Selector No Min_Luminance_Delta Validation**
   - Negative or NaN delta not caught
   - Recommendation: Validate in `__post_init__`

10. **Preset Name Not Validated Before Use**
    - `sequences_for_preset()` calls `get_preset()` which may raise KeyError
    - Recommendation: Add error handling or validation

---

## 12. Recommended Test Coverage Additions

**Suggested test files to create or expand:**

1. `tests/test_terminal_edge_cases.py` - Terminal detection edge cases
2. `tests/test_color_edge_cases.py` - Color boundary conditions
3. `tests/test_image_edge_cases.py` - Image and region edge cases
4. `tests/test_contrast_edge_cases.py` - Contrast calculation boundaries
5. `tests/test_classification_edge_cases.py` - Sample classification boundaries
6. `tests/test_io_edge_cases.py` - File I/O and atomic operations
7. `tests/test_concurrency.py` - Thread-safety and race conditions
8. `tests/test_resource_limits.py` - Large data and memory handling

**Target: 95%+ edge case coverage for critical paths**

