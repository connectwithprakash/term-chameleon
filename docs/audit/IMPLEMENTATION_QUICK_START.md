# Implementation Quick Start Guide
## Term-Chameleon Audit Fixes — Developer Checklist

**Use this document to quickly understand what needs to be fixed and why.**

---

## CRITICAL (Do First — This Week)

### 1. AppleScript Command Injection Fix
**File**: `src/term_chameleon/live_stage.py`  
**Problem**: Commands with newlines/quotes can break AppleScript syntax  
**Fix**: Add `escape_applescript_string()` function to properly escape newlines, quotes, backslashes  
**Why**: Security — attackers could inject arbitrary iTerm2 commands  
**Tests**: 3 new unit tests with malicious paths  
**Effort**: 1-2 hours

### 2. Python Executable Validation
**File**: `src/term_chameleon/watch_daemon.py`  
**Problem**: `--python` flag accepts any path without validation  
**Fix**: Add `_validate_python_executable()` that checks:
- Path exists and is executable
- Path is absolute (reject relative paths)
- Actually runs Python (`--version` check)  
**Why**: Security — prevents arbitrary code execution  
**Tests**: 5 new unit tests  
**Effort**: 2-3 hours

### 3. Color Blending Clamping
**File**: `src/term_chameleon/color.py`  
**Problem**: `blend_over()` produces values > 1.0 from floating-point rounding  
**Fix**: Clamp result to [0, 1] range with `max(0, min(1, value))`  
**Why**: Prevents invalid color data  
**Tests**: Run existing stress tests (should now pass)  
**Effort**: 1-2 hours

### 4. File Permissions Fix
**Files**: `src/term_chameleon/install.py`, `src/term_chameleon/watch_daemon.py`, `src/term_chameleon/iterm_api.py`  
**Problem**: Scripts written with `0o755` (world-readable) instead of `0o700`  
**Fix**: Change all `.chmod(0o755)` → `.chmod(0o700)`  
**Why**: Security — sensitive paths/config should be owner-only readable  
**Tests**: Simple permission check in test  
**Effort**: 0.5 hours

### 5. Script Integrity Checks
**File**: `src/term_chameleon/iterm_api.py`  
**Problem**: No integrity verification for generated scripts (TOCTOU race)  
**Fix**: 
- After writing script, compute SHA256 checksum
- Save checksum to `.sha256` file
- Load time can verify (optional for now)  
**Why**: Prevents TOCTOU attacks  
**Tests**: 3 new tests  
**Effort**: 2 hours

---

## HIGH PRIORITY (Week 2)

### 6. Terminal Detection False Positive
**File**: `src/term_chameleon/terminal.py`  
**Problem**: `"kitty" in term` matches `"xterm-kitty-256color"` incorrectly  
**Fix**: Use `startswith()` or exact match instead of substring search  
**Code**:
```python
if term == "xterm-kitty" or term.startswith("xterm-kitty-"):
    return Terminal.KITTY
```
**Tests**: 4 new tests with different TERM values  
**Effort**: 1-2 hours

### 7. OSC Output Error Handling
**File**: `src/term_chameleon/osc.py`  
**Problem**: `sys.stdout.write()` can fail but code always returns True  
**Fix**: Check for short writes and exceptions:
```python
try:
    written = sys.stdout.write(sequence)
    if written != len(sequence):
        return False
    sys.stdout.flush()
    return True
except (IOError, OSError, BrokenPipeError):
    return False
```
**Tests**: 3-4 new tests with closed/broken pipes  
**Effort**: 1-2 hours

### 8. Refactor CLI Main Function
**File**: `src/term_chameleon/cli.py`  
**Problem**: `main()` is 511 lines with 30+ if-statements  
**Fix**: Convert to dispatch dictionary:
```python
HANDLERS = {
    "doctor": _doctor_cmd,
    "fix": _fix_cmd,
    # ... etc
}

async def main(argv):
    handler = HANDLERS.get(args.command)
    return await handler(args)
```
**Tests**: All existing CLI tests must still pass  
**Effort**: 4-5 hours (refactor + verification)

### 9. Performance: O(n²) → O(n) Pixel Check
**File**: `src/term_chameleon/text_contrast.py:217`  
**Problem**: `pixel not in glyph_pixels` is O(n) per pixel  
**Fix**:
```python
glyph_set = set(glyph_pixels)  # O(n) conversion
background = [p for p in image.pixels if p not in glyph_set]  # O(n)
```
**Tests**: Existing tests should pass; benchmark on 4K images  
**Effort**: 0.5 hours

### 10. Performance: O(n log n) → O(n) Percentile
**File**: `src/term_chameleon/pixel_contrast.py:67`  
**Problem**: Full sort when only extremes needed  
**Fix**: Use `heapq.nsmallest()` and `heapq.nlargest()`  
**Tests**: Existing tests pass; benchmark  
**Effort**: 1 hour

### 11. Add Missing Type Annotation
**File**: `src/term_chameleon/live_iterm.py:31`  
**Problem**: Nested function `color()` has no return type  
**Fix**: Add `-> iterm2.Color:`  
**Tests**: `mypy --strict` should pass  
**Effort**: 0.25 hours

---

## MEDIUM PRIORITY (Week 3)

### 12. Refactor 8 Oversized Functions
**Functions >50 lines**:
- `cli.py:_install_watch_daemon()` (71 lines)
- `cli.py:_watch_live()` (66 lines)
- `live_stage.py:run_live_stage()` (110 lines)
- `watch_live.py:run_watch_live()` (80 lines)
- `text_contrast.py:estimate_raster_text_contrast()` (80 lines)
- Others...

**Fix Strategy**: Extract helper functions for logical sections  
**Tests**: New unit tests for each extracted function  
**Effort**: 5-6 hours

### 13. Fix Private Attribute Mutations
**File**: `src/term_chameleon/watch_live.py:154`  
**Problem**: Direct mutation of private `selector._last_switch_luminance`  
**Fix**: Add public `restore_checkpoint()` method to ModeSelector  
**Tests**: Property-based tests for checkpoint round-trip  
**Effort**: 1-2 hours

### 14. Add Size Limits to JSON/TOML Parsing
**Files**: `src/term_chameleon/config.py`, `src/term_chameleon/iterm_profile.py`  
**Problem**: No validation before parsing; potential DoS  
**Fix**: 
```python
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
if path.stat().st_size > MAX_FILE_SIZE:
    raise ValueError("File too large")
```
**Tests**: 3 new tests with oversized files  
**Effort**: 1-2 hours

### 15. Sanitize Subprocess Output
**File**: `src/term_chameleon/cli.py`  
**Problem**: Error messages may contain ANSI escape sequences  
**Fix**: Strip sequences before printing:
```python
import re
ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
message = ansi_escape.sub('', message)
```
**Tests**: 2 new tests with ANSI codes  
**Effort**: 0.5-1 hour

### 16. Additional Performance Optimizations
- Histogram expansion fix (0.5h)
- Row score filtering (0.5h)
- Cache `shutil.which()` (0.5h)
- Total: 1.5 hours

---

## TESTING GAPS (Week 3-4)

### 17. Unit Tests for Untested Modules
**Missing tests for**:
- `contrast.py` - contrast ratio calculations (8-10 tests)
- `presets.py` - preset loading and application (15-20 tests)
- `iterm_profile.py` - JSON loading/dumping (20-25 tests)
- `fixes.py` - profile fixing logic (15-20 tests)
- `modes.py` - mode application (12-15 tests)
- `install.py` - profile installation (10-12 tests)
- `visual.py` - visual checks and reporting (10-12 tests)

**Total**: 130-150 new tests  
**Effort**: 8-10 hours

### 18. Integration Tests
- Load → diagnose → fix → verify flow (3 tests)
- Load → apply preset → verify flow (3 tests)
- Install → make default → verify flow (3 tests)

**Total**: 9 integration tests  
**Effort**: 3-4 hours

### 19. Edge Case Tests
Adapt 50+ edge cases from stress test suite:
- Boundary conditions (negative dims, zero contrast)
- Large images (4K, 8K)
- Unicode paths
- Concurrent access
- Empty/malformed input

**Effort**: 2-3 hours

---

## IMPLEMENTATION ORDER

**Recommended workflow for each fix**:

1. Create feature branch: `git checkout -b fix/description`
2. Write test first (TDD):
   - Create `tests/test_xxxxx.py`
   - Add failing test(s)
3. Implement fix:
   - Modify source file
   - Tests should now pass
4. Verify:
   - Run full test suite: `pytest`
   - Run type check: `mypy --strict`
   - Run linter: `ruff check`
5. Create PR with clear description
6. Get review + merge

---

## Effort Estimates

| Phase | Total Hours | Weeks | Priority |
|-------|-------------|-------|----------|
| **Phase 1** (Critical Security) | 8-10h | 1 week | **DO FIRST** |
| **Phase 2** (High Priority Bugs) | 10-12h | 1 week | **DO SECOND** |
| **Phase 3** (Medium - Code Quality) | 10-12h | 1 week | **DO THIRD** |
| **Phase 4** (Testing Gaps) | 12-15h | 1-2 weeks | **DO FOURTH** |
| **Phase 5** (Low - Polish) | 5-8h | Ongoing | **Do as time allows** |
| **TOTAL** | **45-57 hours** | **4 weeks** | |

---

## Quick Command Reference

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_contrast.py -v

# Run with coverage
pytest tests/ --cov=src/term_chameleon --cov-report=html

# Type checking
mypy src/term_chameleon --strict

# Linting
ruff check src/term_chameleon

# Format code
ruff format src/term_chameleon

# Run stress tests (edge cases)
pytest tests/test_extreme_stress.py -v
```

---

## Questions?

Refer to **`IMPLEMENTATION_PLAN.md`** for detailed analysis of each fix, including:
- Exact code locations
- Before/after code examples
- Verification procedures
- Files affected
- Detailed effort breakdown

All issues are documented with security/performance/quality justifications.
