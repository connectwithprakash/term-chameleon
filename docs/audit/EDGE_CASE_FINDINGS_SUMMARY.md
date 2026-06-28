# Term Chameleon: Edge Case Discovery Findings Summary

## Overview

A comprehensive adversarial analysis of term-chameleon identified **12 substantive edge cases** spanning terminal detection, color handling, image processing, file I/O, and concurrency. Three are **CRITICAL**, requiring immediate attention.

---

## Critical Findings

### 🔴 CRITICAL-1: Kitty Terminal False Positive Detection

**Location:** `terminal.py:41`

**Issue:**
```python
is_kitty = term_program == "kitty" or "kitty" in term
```

The substring check `"kitty" in term` matches unintended values like `"xterm-kitty-256color"`, causing false-positive detection.

**Impact:**
- Unsupported terminals incorrectly identified as Kitty
- OSC sequences sent to terminals that may not support them
- Loss of user trust if terminal behaves unexpectedly

**Recommended Fix:**
```python
# Option 1: Be explicit about TERM values
is_kitty = term_program == "kitty" or term == "xterm-kitty" or term == "kitty"

# Option 2: Add documentation noting this is a known limitation
# and require explicit TERM_PROGRAM="kitty"
```

**Test Case Provided:**
```python
def test_kitty_substring_false_positive():
    with patch.dict(os.environ, {"TERM": "xterm-kitty-256color"}, clear=True):
        info = detect_terminal()
        # Currently: info.is_kitty is True (false positive)
```

---

### 🔴 CRITICAL-2: OSC Sequence Output Without Error Handling

**Location:** `terminal.py:67-83`

**Issue:**
```python
def apply_osc_to_terminal(preset_name: str, *, reset: bool = False) -> bool:
    # ...
    sys.stdout.write(payload)
    sys.stdout.flush()
    return True  # Always returns True, even on failure
```

Neither `write()` nor `flush()` have error handling. Return value is always `True` even if stdout is closed or broken pipe occurs.

**Impact:**
- Silently fails if stdout is redirected or closed
- Caller believes sequences were applied when they weren't
- Errors in stdin/stdout are not propagated to caller
- No way for the terminal to know application failed

**Recommended Fix:**
```python
def apply_osc_to_terminal(preset_name: str, *, reset: bool = False) -> bool:
    try:
        seqs = reset_sequences() if reset else sequences_for_preset(preset_name)
        payload = "".join(s.sequence for s in seqs)
        sys.stdout.write(payload)
        sys.stdout.flush()
        return True
    except IOError as e:
        raise RuntimeError(f"Failed to write OSC sequences to terminal: {e}") from e
```

**Test Case Provided:**
```python
def test_apply_osc_with_closed_stdout():
    with patch('sys.stdout', io.StringIO()) as mock_stdout:
        mock_stdout.write.side_effect = IOError("pipe closed")
        with pytest.raises(RuntimeError):
            apply_osc_to_terminal("balanced")
```

---

### 🔴 CRITICAL-3: Floating-Point Color Blending Out-of-Bounds

**Location:** `color.py:60-67`

**Issue:**
```python
def blend_over(self, background: Color) -> Color:
    alpha = self.a
    return Color(
        self.r * alpha + background.r * (1 - alpha),
        self.g * alpha + background.g * (1 - alpha),
        self.b * alpha + background.b * (1 - alpha),
        1.0,
    )
```

Floating-point arithmetic can produce values slightly outside [0, 1] bounds due to rounding errors.

**Impact:**
- Color construction can raise ValueError in rare cases
- Contrast calculations may fail unpredictably
- Hard to debug (rare race condition in floating-point arithmetic)

**Example Scenario:**
```python
# Hypothetical case where rounding produces 1.0000000001
fg = Color(0.5, 0.5, 0.5, 0.5)
bg = Color(0.5, 0.5, 0.5, 1.0)
result = fg.blend_over(bg)  # Might raise ValueError
```

**Recommended Fix:**
```python
def blend_over(self, background: Color) -> Color:
    alpha = self.a
    r = self.r * alpha + background.r * (1 - alpha)
    g = self.g * alpha + background.g * (1 - alpha)
    b = self.b * alpha + background.b * (1 - alpha)
    # Clamp to [0, 1] to handle floating-point rounding
    return Color(
        max(0.0, min(1.0, r)),
        max(0.0, min(1.0, g)),
        max(0.0, min(1.0, b)),
        1.0,
    )
```

**Test Case Provided:**
```python
def test_blend_over_at_boundaries():
    fg = Color(1.0, 0.0, 0.0, 0.5)
    bg = Color(1.0, 0.0, 0.0, 1.0)
    result = fg.blend_over(bg)  # Should not raise
    assert 0.0 <= result.r <= 1.0
```

---

## High-Priority Findings

### 🟠 HIGH-1: Region Parsing Accepts Negative Coordinates

**Location:** `images.py:32-53`

**Issue:**
```python
@classmethod
def parse(cls, raw: str) -> Region:
    # No validation of negative x/y
    x, y, width, height = (int(part.strip()) for part in parts)
    return cls(x, y, width, height)  # Negative x/y accepted here

def __post_init__(self) -> None:
    if self.x < 0 or self.y < 0:
        raise ValueError("region x/y must be non-negative")
```

The validation happens in `__post_init__`, so it works, but design is fragile.

**Recommended Fix:** Ensure early validation in parse method and document.

---

### 🟠 HIGH-2: Classification Boundary Condition Inconsistency

**Location:** `watch.py:43-56`

**Issue:**
```python
elif sample.luminance > 0.65:     # 0.65 is balanced
    risk = "bright-high-risk"
elif sample.luminance < 0.35:     # 0.35 is balanced
    risk = "dark-low-risk"
```

Boundaries are off-by-one. The values 0.35 and 0.65 are classified as "balanced" rather than at the threshold.

**Impact:**
- Inconsistent classification at boundaries
- Difficult to document or understand thresholds
- Could cause mode switching at unexpected luminance values

**Test Results:**
- `luminance=0.35` → "balanced-medium-risk" (not "dark-low-risk")
- `luminance=0.65` → "balanced-medium-risk" (not "bright-high-risk")

**Recommendation:** Document intended thresholds and add test cases for boundary conditions.

---

### 🟠 HIGH-3: Mode Selector Hysteresis Boundary Condition

**Location:** `watch.py:80-83`

**Issue:**
```python
if delta < self.min_luminance_delta:
    return self.current_mode, classification, False
```

Uses `<` instead of `<=`. Samples exactly at the boundary are rejected when they should be accepted (or vice versa).

**Example:**
- `min_luminance_delta=0.1`, `delta=0.1` exactly
- `delta < 0.1` is False, so switch is rejected
- Behavior may be unintended

**Recommendation:** Document the boundary condition explicitly or change to `<=`.

---

### 🟠 HIGH-4: atomic_write_text Incomplete Error Recovery

**Location:** `safe_io.py:30-45`

**Issue:**
```python
try:
    target.parent.mkdir(parents=True, exist_ok=True)  # May fail
    # ...
except Exception:
    with suppress(FileNotFoundError):
        tmp.unlink()
    raise
```

If `mkdir()` fails, the temp file is never created, but the exception handler still tries to unlink it (harmless but fragile).

More critically, if `tmp.replace(target)` fails, the temp file is not cleaned up.

**Impact:**
- Orphaned temp files accumulate on disk
- Filesystem eventually fills with `.{filename}.tmp` files
- No error recovery after atomic operation failure

**Recommended Fix:**
```python
fd, tmp_name = tempfile.mkstemp(...)
tmp = Path(tmp_name)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(target)
except Exception:
    # Always clean up temp file, even if replace fails
    with suppress(FileNotFoundError):
        tmp.unlink()
    raise
```

---

## Medium-Priority Findings

### 🟡 MEDIUM-1: Percentile Sample Size Misleading for Tiny Images

**Location:** `pixel_contrast.py:59-85`

**Issue:**
```python
sample_size = max(1, round(len(pixels) * percentile))
```

With a 2-pixel image and `percentile=0.1`, `sample_size=1`. Result misleads about how representative the sample is.

**Example:**
- 2-pixel image: black and white
- `percentile=0.1` → sample_size=1
- Samples only one pixel (either black OR white, not both)
- Contrast estimate is inaccurate

**Recommendation:** Validate minimum image size before sampling, or document limitations.

---

### 🟡 MEDIUM-2: No Validation of min_luminance_delta

**Location:** `watch.py:59-71`

**Issue:**
```python
class ModeSelector:
    def __post_init__(self) -> None:
        if self.stable_samples_required < 1:
            raise ValueError(...)
        # No validation of min_luminance_delta
```

Negative or NaN `min_luminance_delta` accepted without error.

**Recommendation:** Add validation:
```python
if not 0.0 <= self.min_luminance_delta <= 1.0:
    raise ValueError("min_luminance_delta must be between 0 and 1")
```

---

### 🟡 MEDIUM-3: Preset Name Not Validated Before Use

**Location:** `terminal.py:73-75` and `osc.py:40-60`

**Issue:**
```python
def apply_osc_to_terminal(preset_name: str, *, reset: bool = False) -> bool:
    seqs = reset_sequences() if reset else sequences_for_preset(preset_name)
    # sequences_for_preset may raise KeyError if preset doesn't exist
```

**Impact:**
- User gets KeyError instead of friendly error message
- Difficult to debug which preset name is invalid

**Recommended Fix:**
```python
try:
    seqs = sequences_for_preset(preset_name)
except KeyError:
    raise ValueError(f"Unknown preset: {preset_name}") from None
```

---

### 🟡 MEDIUM-4: GHOSTTY_RESOURCES_DIR Path Not Validated

**Location:** `terminal.py:38`

**Issue:**
```python
ghostty_environ = os.environ.get("GHOSTTY_RESOURCES_DIR") is not None
is_ghostty = ghostty_environ or term_program == "ghostty"
```

Detects Ghostty if the env var is set, but doesn't validate the path exists or is accessible.

**Impact:**
- Later code might try to access invalid path
- Could cause confusing errors downstream

**Recommendation:** Document that the path is not validated at detection time.

---

## Testing Recommendations

### Test Coverage Gaps

1. **Terminal Detection Edge Cases** (New file: `tests/test_terminal_edge_cases.py`)
   - 20+ test cases for mixed case, substring false positives, empty env vars
   - Concurrency tests for environment variable changes

2. **Color Boundary Conditions** (New file: `tests/test_color_edge_cases.py`)
   - Luminance at 0.03928 threshold
   - Contrast ratio extremes and similarities
   - Blending with transparent colors

3. **Image & Region Edge Cases** (New file: `tests/test_image_edge_cases.py`)
   - 1x1, 10000x1, 1x10000 images
   - Region parsing with whitespace and special characters
   - Clamping boundary conditions

4. **Contrast Estimation Boundaries** (New file: `tests/test_contrast_edge_cases.py`)
   - Percentile at exact 0.5 boundary
   - Uniform color images (contrast = 1.0)
   - Very small images with percentile sampling

5. **Classification Boundaries** (New file: `tests/test_classification_edge_cases.py`)
   - Luminance at 0.35 and 0.65 boundaries
   - Variance at 0.08 boundary
   - Priority of variance over luminance

6. **File I/O Concurrency** (New file: `tests/test_io_concurrency.py`)
   - Concurrent atomic writes
   - Symlink handling
   - Large file writes (10MB+)

7. **Resource Exhaustion** (New file: `tests/test_resource_limits.py`)
   - Large image handling (1M+ pixels)
   - Classification performance
   - Memory efficiency

---

## Suggested Implementation Priority

### Phase 1 (Immediate - Fix Critical Issues)
1. Fix Kitty detection substring false positive
2. Add error handling to `apply_osc_to_terminal()`
3. Add bounds clamping to `blend_over()`

**Estimated effort:** 2-3 hours

### Phase 2 (High Priority - Fix Major Issues)
1. Fix mode selector hysteresis boundary condition
2. Improve `atomic_write_text()` error recovery
3. Add classification boundary documentation and tests
4. Validate `min_luminance_delta`

**Estimated effort:** 4-5 hours

### Phase 3 (Medium Priority - Improve Robustness)
1. Add preset name validation
2. Document GHOSTTY_RESOURCES_DIR limitations
3. Add minimum image size validation for percentile sampling
4. Add preset name validation

**Estimated effort:** 2-3 hours

---

## Test Execution

All test scenarios are provided in `EDGE_CASE_TEST_SCENARIOS.py`:

```bash
# Run all edge case tests
pytest tests/test_edge_cases_*.py -v

# Run specific category
pytest tests/test_terminal_edge_cases.py -v
pytest tests/test_color_edge_cases.py -v
pytest tests/test_image_edge_cases.py -v
pytest tests/test_contrast_edge_cases.py -v
pytest tests/test_classification_edge_cases.py -v

# Run with coverage
pytest tests/ --cov=src/term_chameleon --cov-report=term-missing
```

---

## Conclusion

Term Chameleon is generally well-structured with good validation practices. However, three critical edge cases require immediate attention:

1. **Kitty detection false positive** - Could misidentify terminals
2. **OSC output error handling** - Silently fails without user awareness
3. **Floating-point color blending** - Rare but crashes in edge cases

Additionally, four high-priority issues should be addressed to improve robustness and prevent data loss or unexpected behavior.

The provided test suite covers all identified edge cases and can be integrated into CI/CD pipeline to prevent regressions.

