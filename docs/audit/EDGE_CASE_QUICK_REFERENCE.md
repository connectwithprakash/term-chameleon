# Term Chameleon: Edge Case Quick Reference

## Severity Matrix

| ID | Severity | Component | Issue | Fix Effort |
|---|---|---|---|---|
| 1 | 🔴 CRITICAL | Terminal Detection | Kitty substring false positive in `"kitty" in term` | 15 min |
| 2 | 🔴 CRITICAL | OSC Output | No error handling on `sys.stdout.write()` | 20 min |
| 3 | 🔴 CRITICAL | Color Blending | Floating-point rounding produces out-of-bounds values | 15 min |
| 4 | 🟠 HIGH | Region Parsing | Negative coordinates accepted via parse() | 10 min |
| 5 | 🟠 HIGH | Classification | Boundary at 0.35/0.65 off-by-one | 20 min |
| 6 | 🟠 HIGH | Mode Selection | Hysteresis uses `<` not `<=` at boundary | 15 min |
| 7 | 🟠 HIGH | File I/O | atomic_write_text orphans temp files on failure | 30 min |
| 8 | 🟡 MEDIUM | Percentile Sampling | Small images (2 pixels) give misleading samples | 20 min |
| 9 | 🟡 MEDIUM | Mode Selector | min_luminance_delta not validated | 10 min |
| 10 | 🟡 MEDIUM | OSC | Preset name not validated before use | 10 min |
| 11 | 🟡 MEDIUM | Terminal Detection | GHOSTTY_RESOURCES_DIR path not validated | 5 min |
| 12 | 🟢 LOW | Type Hints | Various minor inconsistencies | Variable |

---

## One-Line Fixes

### #1: Kitty Detection False Positive
```python
# BEFORE:
is_kitty = term_program == "kitty" or "kitty" in term

# AFTER:
is_kitty = (term_program == "kitty") or (term == "xterm-kitty" or term == "kitty")
```

### #2: OSC Output Error Handling
```python
# BEFORE:
sys.stdout.write(payload)
sys.stdout.flush()
return True

# AFTER:
try:
    sys.stdout.write(payload)
    sys.stdout.flush()
    return True
except IOError as e:
    raise RuntimeError(f"Failed to write OSC sequences: {e}") from e
```

### #3: Color Blending Out-of-Bounds
```python
# BEFORE:
return Color(
    self.r * alpha + background.r * (1 - alpha),
    self.g * alpha + background.g * (1 - alpha),
    self.b * alpha + background.b * (1 - alpha),
    1.0,
)

# AFTER:
return Color(
    max(0.0, min(1.0, self.r * alpha + background.r * (1 - alpha))),
    max(0.0, min(1.0, self.g * alpha + background.g * (1 - alpha))),
    max(0.0, min(1.0, self.b * alpha + background.b * (1 - alpha))),
    1.0,
)
```

### #5: Classification Boundary Documentation
```python
# Add to classify_sample() docstring:
"""
Classification uses exclusive boundaries:
  - dark:     luminance < 0.35
  - balanced: 0.35 <= luminance <= 0.65
  - bright:   luminance > 0.65
  - high-variance: variance >= 0.08 (takes priority)
"""
```

### #6: Mode Selector Hysteresis Documentation
```python
# Add to ModeSelector.observe() docstring:
"""
Hysteresis uses STRICT inequality (delta < min_luminance_delta).
Exactly at boundary: delta = min_luminance_delta is REJECTED.
To allow exactly at boundary, change to: delta <= min_luminance_delta
"""
```

### #9: Min Luminance Delta Validation
```python
# BEFORE:
def __post_init__(self) -> None:
    if self.stable_samples_required < 1:
        raise ValueError("stable_samples_required must be >= 1")
    # ... rest of init

# AFTER:
def __post_init__(self) -> None:
    if self.stable_samples_required < 1:
        raise ValueError("stable_samples_required must be >= 1")
    if not 0.0 <= self.min_luminance_delta <= 1.0:
        raise ValueError("min_luminance_delta must be in [0, 1]")
    # ... rest of init
```

---

## Risk Severity Levels

### 🔴 CRITICAL
- **Affects:** Core functionality, user safety, data integrity
- **Timeline:** Fix before next release
- **Impact:** High (crashes, silent failures, data loss)
- **Count:** 3 issues

### 🟠 HIGH
- **Affects:** Robustness, error recovery, common use cases
- **Timeline:** Fix within 1-2 releases
- **Impact:** Medium (occasional failures, confusing behavior)
- **Count:** 4 issues

### 🟡 MEDIUM
- **Affects:** Edge cases, advanced features, rare scenarios
- **Timeline:** Fix within 2-3 releases
- **Impact:** Low (workarounds exist, documented limitations)
- **Count:** 4 issues

### 🟢 LOW
- **Affects:** Code quality, maintainability, documentation
- **Timeline:** Fix as time permits
- **Impact:** Negligible (no user-facing impact)
- **Count:** 1 issue

---

## Component Risk Map

```
terminal.py       : 🔴 🟡
color.py          : 🔴
contrast.py       : 🟢
images.py         : 🟠 🟡
pixel_contrast.py : 🟡
watch.py          : 🟠 🟠 🟡
osc.py            : 🟡
safe_io.py        : 🟠
```

---

## Testing Strategy

### Regression Prevention
```bash
# Run before each commit
pytest tests/test_edge_cases_*.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing
```

### Integration Scenarios
1. **Mixed terminal environments** - User switches between iTerm2, Kitty, Ghostty
2. **Large screenshot processing** - 4K+ image handling
3. **Rapid mode switching** - Background brightness fluctuations
4. **Concurrent operations** - Multiple processes writing backups
5. **Resource constraints** - Low disk, low memory environments

---

## Documentation Updates Needed

1. **Terminal Detection**
   - Document that `TERM` substring matching is used (has false positives)
   - Document `GHOSTTY_RESOURCES_DIR` path is not validated

2. **Classification Thresholds**
   - Clarify boundary conditions (inclusive vs exclusive)
   - Document priority: variance > luminance

3. **Mode Selector**
   - Document hysteresis behavior at exact boundaries
   - Document required min_luminance_delta range

4. **File I/O**
   - Document atomic_write_text temp file cleanup behavior
   - Document concurrent write safety guarantees

5. **Color Handling**
   - Document that blend_over clamps results to [0, 1]
   - Document floating-point precision limitations

---

## Checklist for PR Review

- [ ] All 3 CRITICAL issues addressed
- [ ] All 4 HIGH priority issues addressed
- [ ] Edge case tests added and passing
- [ ] Coverage maintained at 80%+
- [ ] Documentation updated
- [ ] No regression in existing tests
- [ ] Performance benchmarks stable

---

## Resources

1. **Full Analysis:** `ADVERSARIAL_EDGE_CASES.md`
2. **Test Suite:** `EDGE_CASE_TEST_SCENARIOS.py`
3. **Detailed Findings:** `EDGE_CASE_FINDINGS_SUMMARY.md`

---

## Questions to Address Before Merging Fixes

1. **Kitty Detection:** Is the false positive intentional? Should we support nested terminals?
2. **Hysteresis Boundary:** Should exactly at boundary cause a switch or not?
3. **File I/O:** What is the maximum acceptable number of orphaned temp files before alerting?
4. **Color Blending:** Is clamping the right approach or should we raise an error?
5. **Percentile Sampling:** Should we reject images below a minimum size, or document limitations?

