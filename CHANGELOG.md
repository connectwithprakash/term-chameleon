# Changelog

## 0.3.0 - 2026-06-28

### Added

- Calibrated glassiness ladder: presets are ordered most-translucent to opaque with a
  test-enforced invariant (transparency non-increasing, minimum-contrast non-decreasing),
  so the watcher steps toward opacity exactly as far as the backdrop demands.
- "Only the default background uses transparency" is now applied by every preset, so a
  bright/colored backdrop cannot bleed through a colored cell and bury its text while empty
  space stays glassy. Wired through the profile dict, live setters, and the generated adapter.
- Optional `[sck]` extra (ScreenCaptureKit): installs the package and reports readiness
  for a planned true-backdrop capture that will exclude the terminal window; the watcher
  currently still uses the `screencapture` composite grab in all cases. New `backdrop-info`
  command reports the detected backend and SCK readiness.
- docs/design-adaptive-readability.md: the design of record, including why true per-glyph
  correction is impossible through terminal controls (a macOS composition limit) and the
  worst-case-background strategy adopted instead.

### Changed

- Validated and locked down (tests) that a high-variance/colliding backdrop routes to the
  high-blur homogenizing rung and overrides the cooldown for immediate readability.

## 0.2.2 - 2026-06-28

### Added

- `watch-live --demo-cycle`: drives the real sample -> decide -> apply loop off a
  repeating bright/dark cycle instead of the screen, so the terminal visibly
  auto-adapts on a timer (for demos and validation). Applies an exaggerated
  demo-only background per mode so the switch is obvious on an opaque window;
  the real presets are unchanged.
- `demo` command: applies a representative range of presets to the live session
  in turn so you can watch the colors shift.
- VHS-rendered CLI demo GIF (`demo/demo.gif`) embedded in the README, with a
  workflow that regenerates it from `demo/demo.tape`.

### Fixed

- `watch-live --demo-cycle` did nothing under the default `stable=3` debounce:
  the cycle alternates every two samples, so no switch ever reached the
  three-consecutive threshold. Demo-cycle now defaults `stable=1` / `cooldown=0`
  (explicit flags still win).

## 0.2.1 - 2026-06-28

### Fixed

- Watch-daemon install/uninstall no longer leaves a `.backup` file in the iTerm2
  AutoLaunch folder. iTerm2 runs every file there on launch, so the stray backup
  produced a "There is no application set to open the document" dialog on every
  launch. Backups now go to the term-chameleon app-state script-backups directory.

## 0.2.0 - 2026-06-27

### Added

- `uninstall` command: removes the installed Dynamic Profile and the make-default
  AutoLaunch script (with a backup), and reports the previously-default profile GUID.
- `watch-live --whole-screen` flag so a config `iterm_window = true` can be overridden.
- User-flow test suite (`tests/flows/`): declarative TOML specs run two ways — fast
  deterministic CLI checks, and an opt-in visual layer that drives real iTerm2.
- `SECURITY.md`, `CODE_OF_CONDUCT.md`, and `docs/README.md`.

### Changed

- Split the CLI into a `commands/` package; no source file exceeds ~610 lines.
- README leads with a two-command quickstart.
- A high-risk (washout) background switch now overrides the `watch-live` cooldown so a
  needed mode switch is not swallowed; low/medium-risk transitions still respect it.
- Diagnostics: ANSI-black, bright-black, and selection contrast deficits below 3.0:1 now
  block `doctor`/`fix` (previously could only warn).
- `contrast_ratio` composites translucent backgrounds; `set_color` preserves a non-sRGB
  Color Space on round-trip.
- Dropped the unused `[visual]` (pillow) optional dependency.

### Fixed

Resolved 87 issues found across five adversarial audit rounds, including: PNG/PPM decode
crashes and a decompression-bomb cap; a live-apply timeout and event-loop fd leak in the
watch daemon; the Otsu threshold returning the wrong class boundary; `e2e-stage` masking
visual-check failures in its exit code; a secondary-monitor negative-origin crash in the
window-bounds probe; PID-file leaks on SIGTERM; and the corrected `[project.urls]` owner.

## 0.1.1 - 2026-06-27

### Added

- Cross-terminal support: `terminal-info` command detects iTerm2, Kitty, Ghostty, and Alacritty.
- `osc apply --write` writes raw OSC escape sequences to any OSC-capable terminal.
- Adaptive Otsu thresholding for text-row glyph/background pixel separation.
- Dedicated test suites for `osc.py` (8 tests) and `safe_io.py` (8 tests).
- GitHub Actions CI (lint + test matrix: Ubuntu/macOS × Python 3.11/3.12/3.13).
- GitHub Actions PyPI publish workflow (OIDC trusted publishing).

### Changed

- Renamed `_setter_mappings` to `setter_mappings` (public API).
- Narrowed `except Exception` to `except (KeyError, ValueError, TypeError)` in `fixes.py` and `modes.py`.
- Replaced runtime `assert` with explicit `ConfigError` in daemon path resolution and config validation.
- Added `help=` text to most CLI arguments (some positionals and optional flags remain undocumented).
- Made `release-check` status step pass on CI environments without iTerm2 installed.

## 0.1.0 - 2026-06-27

### Stable release

- Promoted from beta to stable after sustained daemon dogfood (35+ hours at 0% CPU, bounded disk, no crashes).
- Removed dead code (`query_dynamic_color`, `supported_color_fields`).
- Replaced runtime `assert` with explicit `ConfigError` raises for daemon path resolution and region validation.
- Added `__all__` to package `__init__`.
- Added `help=` text to most CLI arguments (some positionals and optional flags remain undocumented).
- Added README Troubleshooting section.
- Promoted classifier to `Development Status :: 5 - Production/Stable`.

## 0.1.0b4 - 2026-06-27

### Fixed

- `sample` and `adapt-once` now validate `--iterm-window requires --screen` before attempting to contact iTerm2.
- Long-running watcher now prunes old screenshot artifacts to prevent unbounded disk growth (keeps the 200 most recent).

## 0.1.0b3 - 2026-06-25

### Fixed

- Reduced long-running watcher CPU usage by downsampling screenshots before luminance/variance analysis and raising the AutoLaunch daemon's default interval to 10 seconds.

### Verified

- Durable AutoLaunch watcher from the installed wheel stayed running with sample artifacts and live release gate after optimization.

## 0.1.0b2 - 2026-06-25

### Fixed

- `watch-live` now treats live iTerm2 apply failures as recoverable watcher events instead of exiting the long-running daemon. This keeps AutoLaunch watchers alive when iTerm2 temporarily has no current session.

### Verified

- Durable local install under `~/.local/share/term-chameleon/venv`.
- Real iTerm2 AutoLaunch restart with default pid/log paths and sample artifacts.

## 0.1.0b1 - 2026-06-25

### Changed

- AutoLaunch-launched `watch-live --iterm-window` now waits briefly for iTerm2 to create a window instead of exiting immediately during app startup.
- `install-watch-daemon` now defaults to whole-screen sampling for startup robustness and exposes `--iterm-window` as an explicit opt-in.
- Promoted package metadata to beta after real AutoLaunch daemon dogfood.
- Updated README with beta install/use path and daemon restart guidance.

### Verified

- Installed the wheel into a fresh venv, ran `setup --yes`, `release-check --live --live-stage`, and installed the real iTerm2 AutoLaunch watcher.
- Restarted iTerm2 and verified exactly one long-running watcher process from the AutoLaunch script.
- Confirmed daemon status stayed healthy and watcher screenshot sample artifacts were written.

## 0.1.0a7 - 2026-06-25

### Added

- `term-chameleon release-check` top-level release-readiness gate.
- Release-check JSON/Markdown reports that compose deterministic checks, optional config validation, readiness status, daemon status, and live-stage screenshot QA.
- Tests for release-check success/failure behavior.

## 0.1.0a6 - 2026-06-25

### Added

- `term-chameleon config-check` for validating TOML configs before setup/watch/daemon use.
- Config validation for value types, preset names, region shape, and unknown sections/keys.
- JSON output for config validation reports.

## 0.1.0a5 - 2026-06-25

### Added

- `term-chameleon watch-daemon-status` to inspect the AutoLaunch script, log path, pid file, and running pid state.
- `term-chameleon uninstall-watch-daemon` with dry-run and backup support.
- Tests for watch daemon install/status/uninstall lifecycle behavior.

## 0.1.0a4 - 2026-06-25

### Added

- `term-chameleon config-example` for generating a documented TOML config.
- `--config` support for `setup`, `watch-live`, and `install-watch-daemon`.
- Config-driven watcher, daemon, and setup defaults with explicit CLI flags taking precedence.

## 0.1.0a3 - 2026-06-25

### Added

- `term-chameleon setup` guided setup flow.
- Setup flow runs deterministic self-checks, summarizes readiness, and optionally installs the generated profile with `--yes`.
- `setup --live` includes live iTerm2 API/window readiness in the final setup result.

## 0.1.0a2 - 2026-06-25

### Added

- `term-chameleon status` readiness summary for local setup/dogfooding.
- `term-chameleon status --json` machine-readable readiness output.
- Optional `--live` status probes for iTerm2 Python API connectivity and front-window bounds.

## 0.1.0a1 - 2026-06-25

Initial alpha release candidate for Term Chameleon.

### Added

- iTerm2 Dynamic Profile parsing, diagnostics, and conservative safe fixes.
- Machine-readable `doctor --json` diagnostics with preserved exit-code semantics.
- Generated iTerm2 Dynamic Profile preset install flow and optional AutoLaunch default-profile script.
- Manual profile mode switching and OSC/tmux color sequence generation.
- Screen/image sampling with one-shot profile adaptation.
- Live adaptive watcher with dry-run, stability, cooldown, duration, and iTerm2 session-local apply modes.
- iTerm2 Python API readiness checks, connection probe, window bounds probe, and live-adapter script generation.
- AutoLaunch watcher daemon packaging for continuous adaptation.
- Deterministic visual simulation, E2E staging artifacts, screenshot probes, pixel contrast, and text-row contrast reports.
- Controlled Safari+iTerm2 live GUI staging with explicit `--yes` gate and text-row contrast with pixel-cluster fallback.
- Permission-free `term-chameleon check` deterministic self-check for post-install validation.

### Notes

- Live GUI and live watcher flows may require macOS Screen Recording, Automation, Accessibility, and iTerm2 Python API permissions.
- Text-row contrast is heuristic; future releases may add OCR or terminal-cell-aware glyph segmentation.
- iTerm2 on macOS is the supported terminal target for this alpha.
