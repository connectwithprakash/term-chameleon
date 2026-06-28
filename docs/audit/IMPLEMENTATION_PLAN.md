# Term-Chameleon Implementation Plan
## Prioritized Fixes Based on Security, Code Quality, Performance & Testing Audits

**Generated**: 2026-06-27  
**Status**: Ready for implementation  
**Total Estimated Effort**: 35-45 hours (phased over 3-4 weeks)

---

## PHASE 1: CRITICAL SECURITY & DATA LOSS FIXES (Week 1)
**Estimated Effort**: 8-10 hours | **Impact**: BLOCKING

### 1.1 CRITICAL: AppleScript Command Injection via String Escaping
**Issue**: Insufficient AppleScript escaping allows command injection via untrusted file paths  
**Severity**: CRITICAL (attackers can inject commands into iTerm2)  
**File**: `src/term_chameleon/live_stage.py` (lines 84-96)

**Current Problem**:
```python
# INCOMPLETE ESCAPING
escaped = command.replace("\\", "\\\\").replace('"', '\\"')
return f'''tell application "iTerm2"
  ...
  write text "{escaped}"  # Newlines break syntax!
```

**Fix**:
```python
def escape_applescript_string(value: str) -> str:
    """Escape string for AppleScript literal context."""
    # Escape backslash first, then quotes, then control characters
    result = value.replace("\\", "\\\\")
    result = result.replace('"', '\\"')
    result = result.replace('\n', '\\n')
    result = result.replace('\r', '\\r')
    result = result.replace('\t', '\\t')
    return result
```

**Affected Files**:
- `src/term_chameleon/live_stage.py` - `iterm_stage_script()`
- Potentially: `src/term_chameleon/live_iterm.py` - AppleScript string handling

**Verification**:
- Add test with newline in path: `Path("/tmp/test\nmalicious")`
- Add test with quotes: `Path('/tmp/test"injection"')`
- Add test with backslashes: `Path('C:\\\\malicious\\path')`
- Verify generated AppleScript syntax is valid with `osascript -l AppleScript -n` (syntax check)

**Effort**: 1-2 hours

---

### 1.2 CRITICAL: Unsafe Python Executable Parameter in Subprocess
**Issue**: User-supplied `--python` executable path passed directly to subprocess without validation  
**Severity**: CRITICAL (arbitrary executable execution with user privileges)  
**File**: `src/term_chameleon/watch_daemon.py` (lines 68-102)

**Current Problem**:
```python
def watch_live_command(*, executable: str | None = None, ...) -> tuple[str, ...]:
    command = [
        executable or sys.executable,  # No validation!
        "-m", "term_chameleon.cli", ...
    ]
```

**Fix**:
```python
def _validate_python_executable(exe_path: str | None) -> str:
    """Validate that the provided executable is a real Python interpreter."""
    exe = exe_path or sys.executable
    exe_path_obj = Path(exe)
    
    # Reject relative paths (security risk)
    if not exe_path_obj.is_absolute():
        raise ValueError(f"--python must be absolute path, got: {exe}")
    
    # Must exist and be executable
    if not exe_path_obj.exists():
        raise FileNotFoundError(f"Python executable not found: {exe}")
    
    if not os.access(exe, os.X_OK):
        raise PermissionError(f"Not executable: {exe}")
    
    # Validate it's actually Python (basic check)
    try:
        result = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            timeout=2.0,
            check=True,
        )
        if b"Python" not in result.stdout and b"Python" not in result.stderr:
            raise ValueError(f"Not a Python interpreter: {exe}")
    except subprocess.TimeoutExpired:
        raise ValueError(f"Python executable check timed out: {exe}")
    
    return exe

# In watch_live_command():
def watch_live_command(
    *,
    executable: str | None = None,
    ...
) -> tuple[str, ...]:
    exe = _validate_python_executable(executable)
    command = [exe, "-m", "term_chameleon.cli", ...]
```

**Affected Files**:
- `src/term_chameleon/watch_daemon.py` - `watch_live_command()`
- `src/term_chameleon/cli.py` - `--python` option handling

**Verification**:
- Test: Non-existent path → FileNotFoundError
- Test: Relative path → ValueError
- Test: Non-executable file → PermissionError
- Test: Non-Python executable → ValueError
- Test: Valid system Python → accepted
- Test: Valid venv Python → accepted

**Effort**: 2-3 hours (including tests)

---

### 1.3 CRITICAL: Floating-Point Color Blending Out-of-Bounds
**Issue**: `blend_over()` produces out-of-bounds color values from floating-point rounding errors  
**Severity**: CRITICAL (invalid color data can crash renderers)  
**File**: `src/term_chameleon/color.py` (blend_over method)

**Current Problem**:
```python
def blend_over(self, background: Color) -> Color:
    """Blend self over background using Porter-Duff."""
    fg_a = self.alpha
    bg_a = background.alpha
    out_alpha = fg_a + bg_a * (1 - fg_a)
    
    if out_alpha == 0:
        return Color(0.0, 0.0, 0.0, 0.0)
    
    # Rounding errors can push out of [0,1]
    r = (self.red * fg_a + background.red * bg_a * (1 - fg_a)) / out_alpha
    g = (self.green * fg_a + background.green * bg_a * (1 - fg_a)) / out_alpha
    b = (self.blue * fg_a + background.blue * bg_a * (1 - fg_a)) / out_alpha
    
    return Color(r, g, b, out_alpha)  # r,g,b might be 1.0000001
```

**Fix**:
```python
def blend_over(self, background: Color) -> Color:
    """Blend self over background using Porter-Duff with clamping."""
    fg_a = self.alpha
    bg_a = background.alpha
    out_alpha = fg_a + bg_a * (1 - fg_a)
    
    if out_alpha == 0:
        return Color(0.0, 0.0, 0.0, 0.0)
    
    # Compute blended values
    r = (self.red * fg_a + background.red * bg_a * (1 - fg_a)) / out_alpha
    g = (self.green * fg_a + background.green * bg_a * (1 - fg_a)) / out_alpha
    b = (self.blue * fg_a + background.blue * bg_a * (1 - fg_a)) / out_alpha
    
    # Clamp to valid range [0, 1] to handle floating-point rounding errors
    r = max(0.0, min(1.0, r))
    g = max(0.0, min(1.0, g))
    b = max(0.0, min(1.0, b))
    out_alpha = max(0.0, min(1.0, out_alpha))
    
    return Color(r, g, b, out_alpha)
```

**Affected Files**:
- `src/term_chameleon/color.py` - `Color.blend_over()`

**Verification**:
- Stress test with 10,000 random color blends → all results in [0,1]
- Property-based test: all output components <= input components (physical law)
- Test extreme: transparent blended with opaque → result opaque
- Test extreme: opaque blended with transparent → result opaque
- Add assertion in Color.__post_init__: `assert 0 <= self.red <= 1`, etc.

**Effort**: 1-2 hours (tests already exist in stress suite)

---

### 1.4 CRITICAL: Insecure File Permissions on AutoLaunch Scripts
**Issue**: Generated AutoLaunch scripts written with `0o755` (world-readable) when should be `0o700` (owner-only)  
**Severity**: HIGH (information disclosure; scripts contain user configuration/paths)  
**Files**:
- `src/term_chameleon/watch_daemon.py` (line 183)
- `src/term_chameleon/install.py` (line 109)

**Current Problem**:
```python
target.chmod(0o755)  # Owner: rwx, Group: r-x, Other: r-x (WRONG!)
```

**Fix**:
```python
target.chmod(0o700)  # Owner: rwx, Group: ---, Other: --- (CORRECT)
```

**Affected Files**:
- `src/term_chameleon/watch_daemon.py` - `_write_autolaunch_script()`
- `src/term_chameleon/install.py` - `install_autolaunch_script()`
- `src/term_chameleon/iterm_api.py` - `write_live_adapter_script()`

**Verification**:
- After script creation: verify `stat -c '%a' script.py` → `700`
- Verify group and other cannot read: `! su - otheruser -c 'cat script.py'`
- Add test: create script, check permissions, verify only owner reads

**Effort**: 0.5 hours

---

### 1.5 HIGH: Executable Script Generation Without Integrity Verification
**Issue**: Generated Python scripts are syntax-checked but not integrity-verified before execution; TOCTOU race condition possible  
**Severity**: HIGH (privilege escalation if scripts run elevated)  
**File**: `src/term_chameleon/iterm_api.py` (lines 87-93)

**Current Problem**:
```python
def write_live_adapter_script(path: str | Path, *, preset_name: str = "balanced") -> Path:
    target = Path(path)
    content = live_adapter_script(preset_name=preset_name)
    compile(content, str(target), "exec")  # Only syntax check!
    atomic_write_text(target, content)
    target.chmod(0o755)  # Should be 0o700
```

**Fix** (immediate):
```python
import hashlib

def write_live_adapter_script(path: str | Path, *, preset_name: str = "balanced") -> Path:
    target = Path(path)
    content = live_adapter_script(preset_name=preset_name)
    
    # Syntax check
    compile(content, str(target), "exec")
    
    # Write atomically
    atomic_write_text(target, content)
    
    # Secure permissions (owner only)
    target.chmod(0o700)
    
    # Compute and store checksum for integrity verification at load time
    checksum = hashlib.sha256(content.encode()).hexdigest()
    checksum_file = target.with_suffix(target.suffix + ".sha256")
    atomic_write_text(checksum_file, checksum)
    
    return target
```

**Long-term recommendation**: Move scripts to system-wide restricted directory (requires installer privilege or sudo).

**Affected Files**:
- `src/term_chameleon/iterm_api.py` - `write_live_adapter_script()`
- `src/term_chameleon/live_stage.py` - script execution logic

**Verification**:
- Verify checksum file created
- Verify checksum matches content
- Add test: modify script after write, checksum should fail
- Verify script runs despite checksum file existing (backward compat)

**Effort**: 2 hours

---

## PHASE 2: HIGH PRIORITY FIXES (Week 2)
**Estimated Effort**: 10-12 hours | **Impact**: MAJOR BUGS & PERFORMANCE

### 2.1 HIGH: Terminal Detection False Positive (Kitty)
**Issue**: `"kitty" in term` matches unintended values like `"xterm-kitty-256color"`  
**Severity**: HIGH (misidentifies terminal type, breaks features)  
**File**: `src/term_chameleon/terminal.py` (terminal detection logic)

**Fix**:
```python
def detect_terminal_from_env() -> Terminal | None:
    """Detect terminal from TERM/TERM_PROGRAM environment variables."""
    term = os.environ.get("TERM", "").lower()
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    
    # Match exact terminal names, not substrings
    if term_program == "iterm.app":
        return Terminal.ITERM2
    if term_program == "kitty":  # Kitty sets TERM_PROGRAM
        return Terminal.KITTY
    if term_program == "Ghostty":
        return Terminal.GHOSTTY
    
    # TERM-based detection (fallback)
    # Use startswith() or exact match, not substring search
    if term == "xterm-kitty" or term.startswith("xterm-kitty-"):
        return Terminal.KITTY
    if term == "ghostty":
        return Terminal.GHOSTTY
    if term == "alacritty":
        return Terminal.ALACRITTY
    
    return None
```

**Affected Files**:
- `src/term_chameleon/terminal.py` - `detect_terminal_from_env()`

**Verification**:
- Test: `TERM="xterm-kitty-256color"` → KITTY (correct)
- Test: `TERM="xterm-256color"` → None (not Kitty)
- Test: `TERM_PROGRAM="kitty"` → KITTY
- Test: `TERM_PROGRAM="xterm-256color"` → None

**Effort**: 1-2 hours

---

### 2.2 HIGH: OSC Output Error Handling
**Issue**: `sys.stdout.write()` can raise IOError but code always returns True  
**Severity**: HIGH (silent failures in cross-terminal support)  
**File**: `src/term_chameleon/osc.py` (OSC output functions)

**Current Problem**:
```python
def write_osc(sequence: str) -> bool:
    """Write OSC sequence to terminal."""
    try:
        sys.stdout.write(sequence)
        sys.stdout.flush()
    except Exception:
        return False
    return True  # Always returns True even if flush failed!
```

**Fix**:
```python
def write_osc(sequence: str) -> bool:
    """Write OSC sequence to terminal, return True if successful."""
    try:
        written = sys.stdout.write(sequence)
        if written != len(sequence):
            # Short write or error condition
            return False
        sys.stdout.flush()
        return True
    except (IOError, OSError, BrokenPipeError):
        # Terminal closed, pipe broken, or I/O error
        return False
```

**Affected Files**:
- `src/term_chameleon/osc.py` - all OSC write functions

**Verification**:
- Test: write with closed stdout → False
- Test: write with broken pipe → False
- Test: successful write → True
- Test: short write (network socket) → False

**Effort**: 1-2 hours

---

### 2.3 HIGH: Extreme Long Functions (cli.py main = 511 lines)
**Issue**: Main CLI function is 511 lines; violates 50-line best practice  
**Severity**: HIGH (unmaintainable, untestable)  
**File**: `src/term_chameleon/cli.py` (lines 77-587)

**Fix Strategy**: Convert 30+ if-statement command dispatch to dispatch dictionary
```python
async def _doctor_cmd(args: argparse.Namespace) -> int:
    """Handler for 'doctor' command."""
    # ... existing logic from main() ...
    return 0

async def _fix_cmd(args: argparse.Namespace) -> int:
    """Handler for 'fix' command."""
    # ... existing logic from main() ...
    return 0

# ... etc for all commands ...

COMMAND_HANDLERS: dict[str, Callable[[argparse.Namespace], int | Awaitable[int]]] = {
    "doctor": _doctor_cmd,
    "fix": _fix_cmd,
    "install": _install_cmd,
    # ... etc ...
}

async def main(argv: list[str] | None = None) -> int:
    """Parse args and dispatch to appropriate command handler."""
    args = parser.parse_args(argv)
    
    if args.command is None:
        parser.print_help()
        return 0
    
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:
        print(f"error: unknown command {args.command}", file=sys.stderr)
        return 2
    
    try:
        result = handler(args)
        if inspect.iscoroutine(result):
            return await result
        return result
    except (ValueError, OSError, RuntimeError) as exc:
        # Specific error handling
        print(f"error: {exc}", file=sys.stderr)
        return 2
```

**Affected Files**:
- `src/term_chameleon/cli.py` - entire main() function

**Verification**:
- Each command works: `term-chameleon doctor`, `fix --dry-run`, etc.
- Help text unchanged
- Error handling preserved
- Exit codes correct

**Effort**: 4-5 hours (refactor + test)

---

### 2.4 HIGH: O(n²) Pixel Membership Check Fallback
**Issue**: Linear search through entire image pixels with membership checking on list; O(n²) in worst case  
**Severity**: HIGH (performance degradation for large images)  
**File**: `src/term_chameleon/text_contrast.py` (line 217)

**Fix**:
```python
# BEFORE: O(n²)
background_pixels = [pixel for pixel in image.pixels if pixel not in glyph_pixels]

# AFTER: O(n) with set lookup
glyph_set = set(glyph_pixels)
background_pixels = [pixel for pixel in image.pixels if pixel not in glyph_set]
```

**Affected Files**:
- `src/term_chameleon/text_contrast.py` - `estimate_raster_text_contrast()`

**Verification**:
- Benchmark: 4K image (8.3M pixels) before/after
- Expected: <100ms after, >5s before on large images
- Verify correctness: background pixel set matches expected

**Effort**: 0.5 hours

---

### 2.5 HIGH: O(n log n) Sort for Percentile (Use Heap Instead)
**Issue**: Full sort of all pixels even when only extremes are needed  
**Severity**: HIGH (performance, unnecessary O(n log n) → O(n) possible)  
**File**: `src/term_chameleon/pixel_contrast.py` (line 67)

**Fix**:
```python
import heapq

# BEFORE: O(n log n)
pixels = sorted(image.pixels, key=lambda color: color.relative_luminance())
dark_colors = pixels[:sample_size]
bright_colors = pixels[-sample_size:]

# AFTER: O(n) for extremes
luminances = [c.relative_luminance() for c in image.pixels]
darkest_indices = heapq.nsmallest(sample_size, range(len(image.pixels)), key=lambda i: luminances[i])
brightest_indices = heapq.nlargest(sample_size, range(len(image.pixels)), key=lambda i: luminances[i])
dark_colors = [image.pixels[i] for i in darkest_indices]
bright_colors = [image.pixels[i] for i in brightest_indices]
```

**Affected Files**:
- `src/term_chameleon/pixel_contrast.py` - `estimate_from_sample()`

**Verification**:
- Benchmark: 4K image percentile extraction before/after
- Expected: 5-10x speedup for large images
- Verify correctness: same colors extracted

**Effort**: 1 hour

---

### 2.6 HIGH: Missing Return Type Annotation
**Issue**: Nested function lacks return type  
**Severity**: HIGH (type checking incomplete)  
**File**: `src/term_chameleon/live_iterm.py` (line 31)

**Fix**:
```python
def color(hex_value: str) -> iterm2.Color:  # Add return type
    """Convert hex color string to iterm2.Color."""
    hex_value = hex_value.lstrip("#")
    r = int(hex_value[0:2], 16) / 255.0
    g = int(hex_value[2:4], 16) / 255.0
    b = int(hex_value[4:6], 16) / 255.0
    return iterm2.Color(red=r, green=g, blue=b)
```

**Affected Files**:
- `src/term_chameleon/live_iterm.py` - `apply_preset_to_current_session()`

**Verification**:
- `mypy --strict src/term_chameleon/live_iterm.py` → no errors

**Effort**: 0.25 hours

---

## PHASE 3: MEDIUM PRIORITY FIXES (Week 3)
**Estimated Effort**: 10-12 hours | **Impact**: CODE QUALITY, EDGE CASES

### 3.1 MEDIUM: Oversized Functions (8 functions >50 lines)
**Issue**: Multiple functions exceed 50-line best practice  
**Severity**: MEDIUM (maintainability, testability)  
**Affected Functions**:
- `cli.py:_install_watch_daemon()` - 71 lines
- `cli.py:_watch_live()` - 66 lines
- `cli.py:_live_stage()` - 52 lines
- `live_stage.py:run_live_stage()` - 110 lines
- `text_contrast.py:estimate_raster_text_contrast()` - 80 lines
- `watch_live.py:run_watch_live()` - 80 lines
- `release_check.py:run_release_check()` - 60 lines

**Example Fix** (watch_live.py):
```python
def _handle_mode_switch_cooldown(
    selector: ModeSelector,
    now: float,
    next_allowed_switch: float,
    previous_mode: Mode,
    previous_last_switch_luminance: float,
) -> bool:
    """Restore state if too soon after switch; return True if restored."""
    if now >= next_allowed_switch:
        return False
    selector.current_mode = previous_mode
    selector._last_switch_luminance = previous_last_switch_luminance
    return True

def _capture_sample(config: WatchLiveConfig, sips: str | None) -> Image:
    """Capture screenshot and optionally resample."""
    screenshot = screencapture.take_screenshot(config.region, config.bounds)
    if sips and config.analysis_enabled:
        # ... resample logic ...
    return screenshot

def run_watch_live(config: WatchLiveConfig, ...) -> None:
    """Main watch-live loop."""
    selector = ModeSelector(...)
    while True:
        sample = _capture_sample(config, sips)
        observation = selector.observe(sample)
        # ... apply mode, handle cooldown, etc ...
```

**Affected Files**:
- All files listed above

**Verification**:
- Extract each sub-function
- Unit tests for each extracted function
- Integration test verifies behavior unchanged
- All tests pass

**Effort**: 5-6 hours (refactor + tests)

---

### 3.2 MEDIUM: Private Attribute Mutation in Dataclasses
**Issue**: External code directly mutates private ModeSelector fields  
**Severity**: MEDIUM (encapsulation violation, fragile)  
**File**: `src/term_chameleon/watch_live.py` (line 154)

**Current Problem**:
```python
selector._last_switch_luminance = previous_last_switch_luminance  # ❌ Private mutation
```

**Fix**:
```python
# In ModeSelector class:
class ModeSelector:
    # ... existing fields ...
    
    def restore_checkpoint(self, last_switch_luminance: float) -> None:
        """Restore mode selector to previous checkpoint state."""
        self._last_switch_luminance = last_switch_luminance
    
    def save_checkpoint(self) -> dict[str, Any]:
        """Save current state for restoration."""
        return {
            "mode": self.current_mode,
            "last_switch_luminance": self._last_switch_luminance,
        }

# In watch_live.py:
def _handle_mode_switch_cooldown(...) -> bool:
    if now >= next_allowed_switch:
        return False
    selector.current_mode = previous_mode
    selector.restore_checkpoint(previous_last_switch_luminance)  # Use public method
    return True
```

**Affected Files**:
- `src/term_chameleon/watch.py` - `ModeSelector` class
- `src/term_chameleon/watch_live.py` - usage

**Verification**:
- Add property tests: checkpoint save/restore round-trip
- Verify private fields never accessed directly

**Effort**: 1-2 hours

---

### 3.3 MEDIUM: JSON/TOML Parsing Without Size Limits
**Issue**: No file size validation before parsing; potential DoS via huge files  
**Severity**: MEDIUM (DoS vector)  
**Files**:
- `src/term_chameleon/config.py` (line 70)
- `src/term_chameleon/iterm_profile.py` (line 73)

**Fix**:
```python
import os

MAX_CONFIG_FILE_SIZE = 10 * 1024 * 1024  # 10MB limit

def load_config(path: str | Path | None) -> Config:
    """Load TOML config file with size check."""
    if path is None:
        return {}
    
    target = Path(path).expanduser()
    
    # Check file size before parsing
    file_size = target.stat().st_size
    if file_size > MAX_CONFIG_FILE_SIZE:
        raise ValueError(f"Config file too large: {file_size} bytes (max {MAX_CONFIG_FILE_SIZE})")
    
    try:
        with target.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {target}: {exc}") from exc
    
    return _validate_config(data)

def loads_document(text: str, path: Path | None = None) -> ItermProfile:
    """Load iTerm2 profile JSON with nesting depth check."""
    # Limit JSON nesting depth to prevent billion-laughs-like attacks
    MAX_NESTING_DEPTH = 20
    
    try:
        document = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid profile JSON: {exc}") from exc
    
    _validate_json_depth(document, max_depth=MAX_NESTING_DEPTH)
    return ItermProfile(document, path)

def _validate_json_depth(obj: Any, depth: int = 0, max_depth: int = 20) -> None:
    """Check JSON nesting depth."""
    if depth > max_depth:
        raise ValueError(f"JSON nesting too deep (max {max_depth} levels)")
    
    if isinstance(obj, dict):
        for value in obj.values():
            _validate_json_depth(value, depth + 1, max_depth)
    elif isinstance(obj, list):
        for item in obj:
            _validate_json_depth(item, depth + 1, max_depth)
```

**Affected Files**:
- `src/term_chameleon/config.py` - `load_config()`
- `src/term_chameleon/iterm_profile.py` - `loads_document()`

**Verification**:
- Test: file > 10MB → ValueError
- Test: deeply nested JSON (depth 50) → ValueError
- Test: normal file < 1MB → loads successfully

**Effort**: 1-2 hours

---

### 3.4 MEDIUM: Subprocess Output Not Sanitized for Control Sequences
**Issue**: External process output not stripped of ANSI escape sequences  
**Severity**: MEDIUM (terminal hijacking via error messages)  
**File**: `src/term_chameleon/cli.py` (line 1295)

**Fix**:
```python
import re

def strip_ansi_sequences(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    return ansi_escape.sub('', text)

def _show_subprocess_error(completed: subprocess.CompletedProcess) -> None:
    """Display subprocess error without control sequences."""
    message = completed.stderr or completed.stdout or "open failed"
    message = strip_ansi_sequences(message.strip())
    print(f"error: {message}", file=sys.stderr)
```

**Affected Files**:
- `src/term_chameleon/cli.py` - error handling
- All subprocess error output

**Verification**:
- Test: error with ANSI codes `\x1b[31merror\x1b[0m` → "error" (no codes)
- Verify error message still readable

**Effort**: 0.5-1 hour

---

### 3.5 MEDIUM: Redundant Otsu Threshold Histogram Expansion
**Issue**: Histogram expanded unnecessarily; could use formula instead  
**Severity**: MEDIUM (performance, memory)  
**File**: `src/term_chameleon/text_contrast.py` (line 85)

**Fix**:
```python
# BEFORE: Generator expands histogram
sum_all = sum(lo + (i + 0.5) / bins * span for i, c in enumerate(hist) for _ in range(c))

# AFTER: Algebraic formula
sum_all = sum((lo + (i + 0.5) / bins * span) * hist[i] for i in range(bins))
```

**Affected Files**:
- `src/term_chameleon/text_contrast.py` - `_otsu_threshold()`

**Verification**:
- Benchmark: histogram computation on 256-bin histogram
- Expected: 10-100x speedup
- Verify threshold calculation unchanged

**Effort**: 0.5 hours

---

### 3.6 MEDIUM: Redundant Row Score Computation
**Issue**: All row scores computed then filtered; wasted computation  
**Severity**: MEDIUM (performance)  
**File**: `src/term_chameleon/text_contrast.py` (line 113)

**Fix**:
```python
# BEFORE: Compute all scores
active_rows = [(y, _row_score(image, y)) for y in range(image.height)]

# AFTER: Compute + filter in one pass (walrus operator)
min_row_delta = ...  # compute threshold
active_rows = [
    (y, score)
    for y in range(image.height)
    if (score := _row_score(image, y)) >= min_row_delta
]
```

**Affected Files**:
- `src/term_chameleon/text_contrast.py` - row filtering logic

**Verification**:
- Benchmark on typical images: expect 30-40% fewer row_score calls
- Verify same active_rows selected

**Effort**: 0.5 hours

---

## PHASE 4: TESTING GAPS (Week 3-4)
**Estimated Effort**: 12-15 hours | **Impact**: COVERAGE, CONFIDENCE

### 4.1 HIGH: Add Missing Unit Tests (Critical Modules)
**Modules with Zero Test Coverage**: contrast.py, presets.py, iterm_profile.py, fixes.py, modes.py

**Test Targets**:

| Module | Target | Est. Tests |
|--------|--------|-----------|
| **contrast.py** | `contrast_ratio()`, `format_ratio()` | 8-10 |
| **presets.py** | Each preset loads; `get_preset()`, `apply_preset_to_profile_dict()` | 15-20 |
| **iterm_profile.py** | Load/dump, color extraction, mutation methods | 20-25 |
| **fixes.py** | Apply all changes, dry-run, backup, atomic write | 15-20 |
| **modes.py** | Apply each mode, diff detection, dry-run | 12-15 |
| **install.py** | Profile creation, autolaunch generation | 10-12 |
| **visual.py** | Visual checks, report generation | 10-12 |
| **live_iterm.py** | Async iTerm2 application, error handling | 8-10 |

**Total New Tests**: ~130-150

**Example Test Structure**:
```python
# tests/test_contrast.py
import pytest
from term_chameleon.contrast import contrast_ratio, format_ratio
from term_chameleon.color import Color

class TestContrastRatio:
    def test_black_to_white(self):
        black = Color(0.0, 0.0, 0.0)
        white = Color(1.0, 1.0, 1.0)
        assert abs(contrast_ratio(white, black) - 21.0) < 0.1
    
    def test_identical_colors(self):
        gray = Color(0.5, 0.5, 0.5)
        assert contrast_ratio(gray, gray) == pytest.approx(1.0)
    
    def test_format_ratio(self):
        assert format_ratio(21.0) == "21:1"
        assert format_ratio(4.5) == "4.5:1"

class TestBlendingEdgeCases:
    def test_blend_over_clamping(self):
        # Verify no out-of-bounds values from floating-point errors
        for _ in range(10000):
            fg = Color(random(), random(), random(), random())
            bg = Color(random(), random(), random(), random())
            result = fg.blend_over(bg)
            assert 0 <= result.red <= 1
            assert 0 <= result.green <= 1
            assert 0 <= result.blue <= 1
            assert 0 <= result.alpha <= 1
```

**Affected Files**:
- New test files in `tests/` directory

**Effort**: 8-10 hours (writing + debugging tests)

---

### 4.2 HIGH: Add Integration Tests for Critical Paths
**Critical Paths**:
1. Load profile → diagnose → fix → verify clean
2. Load profile → apply mode → verify no conflicts
3. Install profile → make default → verify autolaunch

**Example**:
```python
# tests/test_integration_fix_flow.py
def test_complete_fix_flow_balanced_profile(tmp_path):
    """Test: Load profile → diagnose → fix → verify clean."""
    # Setup
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(BAD_PROFILE_JSON)
    
    # Load
    profile = iterm_profile.load_profile(profile_path)
    
    # Diagnose
    issues = diagnostics.diagnose_profile(profile)
    assert len(issues) > 0, "Should find issues"
    
    # Fix
    changes = fixes.apply_balanced_fix(profile)
    profile_path.write_text(profile.to_json())
    
    # Verify
    profile_reloaded = iterm_profile.load_profile(profile_path)
    issues_after = diagnostics.diagnose_profile(profile_reloaded)
    assert len(issues_after) == 0, "Should have no issues after fix"
```

**Affected Files**:
- New integration test files

**Effort**: 3-4 hours

---

### 4.3 MEDIUM: Add Edge Case Tests
**From Adversarial Analysis**: 50+ edge case tests already documented in stress test suite

**Priority Cases**:
- Negative image dimensions → rejected
- Zero contrast ratio → handled
- NaN/Inf floating-point values → handled
- Very large images (4K, 8K) → process efficiently
- Empty profiles → handled gracefully
- Unicode in file paths → handled
- Concurrent mode selection → thread-safe

**Effort**: 2-3 hours (adapt from existing stress tests)

---

## PHASE 5: LOW PRIORITY IMPROVEMENTS (Ongoing)
**Estimated Effort**: 5-8 hours | **Impact**: POLISH, OPTIMIZATION

### 5.1 LOW: Broad Exception Handling → Specific
**Issue**: Catch broad `Exception` when specific types known  
**Severity**: LOW (debugging, maintainability)

**Example Fix**:
```python
# BEFORE
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)
except Exception:  # TOO BROAD
    raise

# AFTER
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)
except (IOError, OSError, UnicodeEncodeError) as exc:
    raise RuntimeError(f"Failed to write {path}: {exc}") from exc
```

**Affected Files**: All modules with broad exception handlers

**Effort**: 2-3 hours

---

### 5.2 LOW: Cache shutil.which() Results
**Issue**: Subprocess path lookup on every watch-live sample  
**Severity**: LOW (performance optimization)

**Fix**:
```python
@functools.lru_cache(maxsize=4)
def find_sips_tool() -> str | None:
    """Find sips tool, cached for entire session."""
    return shutil.which("sips")
```

**Affected Files**:
- `src/term_chameleon/watch_live.py`

**Effort**: 0.5 hours

---

### 5.3 LOW: Document Magic Numbers
**Issue**: Constants like `WATCH_SAMPLE_MAX_PIXELS = 250_000` lack rationale  
**Severity**: LOW (documentation, maintainability)

**Fix**:
```python
# Limit analysis to keep memory usage under 50MB.
# At typical display density (100 DPI), 250k pixels ≈ 640x390 pixels.
# This balances accuracy with memory efficiency.
WATCH_SAMPLE_MAX_PIXELS = 250_000
```

**Effort**: 0.5 hours

---

### 5.4 LOW: Optimize Atomic Write for Small Files
**Issue**: Atomic write overhead for payloads <1MB unnecessary  
**Severity**: LOW (performance, micro-optimization)

**Effort**: 1-2 hours (if needed for specific bottleneck)

---

## Summary Table

| Phase | Issue | Severity | Effort | Files | Priority |
|-------|-------|----------|--------|-------|----------|
| **1** | AppleScript injection | CRITICAL | 1-2h | live_stage.py | **BLOCKING** |
| **1** | Python executable validation | CRITICAL | 2-3h | watch_daemon.py | **BLOCKING** |
| **1** | Color blending clamping | CRITICAL | 1-2h | color.py | **BLOCKING** |
| **1** | File permissions 0o700 | HIGH | 0.5h | install.py, watch_daemon.py | **BLOCKING** |
| **1** | Script integrity checks | HIGH | 2h | iterm_api.py | **BLOCKING** |
| **2** | Terminal detection Kitty false positive | HIGH | 1-2h | terminal.py | **Week 2** |
| **2** | OSC output error handling | HIGH | 1-2h | osc.py | **Week 2** |
| **2** | Main CLI refactor (511 lines) | HIGH | 4-5h | cli.py | **Week 2** |
| **2** | O(n²) pixel membership check | HIGH | 0.5h | text_contrast.py | **Week 2** |
| **2** | O(n log n) sort → heap | HIGH | 1h | pixel_contrast.py | **Week 2** |
| **2** | Missing return type | HIGH | 0.25h | live_iterm.py | **Week 2** |
| **3** | Function refactoring (8 >50 lines) | MEDIUM | 5-6h | multiple | **Week 3** |
| **3** | Private attribute mutations | MEDIUM | 1-2h | watch.py, watch_live.py | **Week 3** |
| **3** | JSON/TOML size limits | MEDIUM | 1-2h | config.py, iterm_profile.py | **Week 3** |
| **3** | Sanitize subprocess output | MEDIUM | 0.5-1h | cli.py | **Week 3** |
| **3** | Histogram expansion | MEDIUM | 0.5h | text_contrast.py | **Week 3** |
| **3** | Row score filtering | MEDIUM | 0.5h | text_contrast.py | **Week 3** |
| **4** | Unit tests (8 modules) | HIGH | 8-10h | tests/ | **Week 3-4** |
| **4** | Integration tests | HIGH | 3-4h | tests/ | **Week 4** |
| **4** | Edge case tests | MEDIUM | 2-3h | tests/ | **Week 4** |
| **5** | Exception handling specificity | LOW | 2-3h | multiple | **Ongoing** |
| **5** | Cache shutil.which() | LOW | 0.5h | watch_live.py | **Ongoing** |
| **5** | Document magic numbers | LOW | 0.5h | multiple | **Ongoing** |
| **5** | Atomic write optimization | LOW | 1-2h | safe_io.py | **Optional** |

---

## Implementation Sequence

**Week 1 (8-10 hrs)**: Phase 1 CRITICAL fixes
- AppleScript escaping → merge & deploy immediately
- Python executable validation → merge & deploy immediately
- Color clamping → merge & deploy immediately
- File permissions → merge & deploy immediately
- Script integrity checks → merge & deploy

**Week 2 (10-12 hrs)**: Phase 2 HIGH fixes
- Terminal detection fix → merge
- OSC error handling → merge
- CLI refactor → full review cycle
- Performance optimizations (pixel, heap, row score)
- Missing type annotation

**Week 3-4 (12-15 hrs)**: Phase 3-4 MEDIUM + Testing
- Function refactoring
- Encapsulation fixes
- Input validation (size limits, sanitization)
- Unit tests for untested modules
- Integration tests
- Edge case tests

**Ongoing**: Phase 5 LOW improvements
- Exception handling cleanup
- Minor optimizations
- Documentation

---

## Verification Strategy

### Pre-Merge Checklist (All Phases)
- [ ] All existing tests pass
- [ ] New tests added for fixes (>80% coverage)
- [ ] No performance regression
- [ ] Code review: security audit
- [ ] Manual testing on macOS + Linux

### Deploy Sequence
1. **Security fixes first** (Phase 1)
2. **High-priority bugs** (Phase 2)
3. **Code quality** (Phase 3)
4. **Testing improvements** (Phase 4)

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| AppleScript breaking iTerm integration | HIGH | Test on real iTerm2 before merge |
| Python validation breaks `--python` flag | MEDIUM | Add backward-compat tests |
| CLI refactor introduces regressions | HIGH | Comprehensive test coverage required |
| Performance changes cause slowdown | MEDIUM | Benchmark before/after each optimization |
| Tests take long to implement | MEDIUM | Use existing stress test suite as reference |

---

## Success Criteria

- [ ] All CRITICAL security issues fixed and tested
- [ ] No more functions >50 lines (except well-documented exceptions)
- [ ] Test coverage ≥90% (target 95%)
- [ ] All stress tests pass (44 tests)
- [ ] Performance improvements documented (benchmarks)
- [ ] Zero security audit findings in follow-up review
- [ ] Terminal detection 100% accurate
- [ ] Platform compatibility verified (macOS, Linux)

