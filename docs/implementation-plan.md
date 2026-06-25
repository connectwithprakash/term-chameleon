# Implementation Plan

## Milestone 0: repository and docs

Implemented:

- Python package scaffold.
- Durable source-backed docs.
- Tests directory and fixture profiles.

Acceptance:

```bash
uv run --extra dev pytest -q
```

## Milestone 1: static iTerm2 profile doctor

Implemented:

- `Color` model and conversions.
- WCAG contrast calculations.
- iTerm2 Dynamic Profile parser.
- Diagnostic rule engine.
- CLI: `term-chameleon doctor <profile.json>`.

Diagnostic codes include:

```text
ITERM_LIGHT_DARK_DRIFT
LOW_FOREGROUND_CONTRAST
LOW_BOLD_CONTRAST
LOW_ANSI_BLACK_CONTRAST
LOW_ANSI_BRIGHT_BLACK_CONTRAST
LOW_ANSI_WHITE_CONTRAST
LOW_ANSI_BRIGHT_WHITE_CONTRAST
LOW_SELECTION_CONTRAST
HIGH_TRANSPARENCY_RISK
MISSING_MINIMUM_CONTRAST
```

## Milestone 2: static fixer

Implemented:

- `term-chameleon fix <profile.json>`.
- `--dry-run`.
- `--yes`.
- unique timestamped backups.
- atomic writes.
- deterministic JSON.
- explainable diff.

## Milestone 3: iTerm2 install and manual modes

Implemented:

- Preset generation.
- Dynamic Profile install path.
- Optional AutoLaunch default-profile script generation.
- Manual mode application: `term-chameleon mode <preset> <profile.json>`.
- OSC apply/reset generation with tmux wrapping.

## Milestone 4: visual test harness foundation

Implemented:

- Deterministic visual simulation: controlled solid-background blending, ANSI pattern artifact, JSON/Markdown reports, and WCAG contrast checks.
- Screenshot-test foundation: controlled PPM background artifacts, luminance/variance/risk classification, optional real macOS screenshot capture, PNG screenshot luminance/variance analysis.
- Screenshot pixel contrast estimator: darkest/lightest cluster contrast reports for captured PNG/PPM artifacts.
- Text-row/glyph-aware contrast estimator: detects high-delta text-like rows and estimates glyph/background contrast.
- Permission-free deterministic self-check: `term-chameleon check` generates a built-in balanced profile, runs doctor, E2E staging, pixel contrast, text-row contrast, and watcher hysteresis checks, then writes JSON/Markdown reports.
- Controlled HTML backgrounds for browser/window staging.
- Terminal ANSI pattern script artifacts.
- Live GUI staging: `term-chameleon live-stage` arranges Safari controlled-background and iTerm2 ANSI-pattern windows, then optionally captures/analyzes screenshot region contrast using text-row contrast when detectable and pixel-cluster fallback otherwise.

Remaining live visual work:

- Optional future refinement: replace heuristic text-row detection with OCR/terminal-cell-aware glyph segmentation.

## Milestone 5: dynamic watcher and one-shot adaptation

Implemented:

- `watch.py` risk classifier.
- hysteresis `ModeSelector`.
- deterministic CLI simulation: `term-chameleon watch-sim`.
- image/screen sampling: `term-chameleon sample --image/--screen`.
- safe one-shot adaptation: `term-chameleon adapt-once <profile.json> --image/--screen --dry-run|--yes`.
- live adaptive iTerm2 watcher: `term-chameleon watch-live --dry-run|--yes`, with interval, duration, stable-sample, cooldown, initial-mode, manual region, and iTerm-window sampling controls.

`watch-sim` is the deterministic testable core. `adapt-once` is a single adaptation pass. `watch-live` is the working continuous live loop for the current iTerm2 session.

## Milestone 6: live iTerm2/screenshot spike

Implemented:

- `term-chameleon iterm-api-check` reports iTerm2.app, `iterm2` Python package availability, Python executable, and required `LocalWriteOnlyProfile` setter readiness.
- `term-chameleon iterm-connect-probe` attempts an actual live Python API connection and reports the permission/runtime blocker clearly.
- `term-chameleon iterm-live-script` generates a conservative session-local adapter script using `LocalWriteOnlyProfile` and `session.async_set_profile_properties`.
- Optional package extra: `uv sync --extra iterm`.
- `term-chameleon screenshot-probe` checks macOS `screencapture` availability and can attempt a real capture.
- `term-chameleon install-watch-daemon` packages the validated live watcher as an iTerm2 AutoLaunch script with pid/log paths and duplicate-process guard.

Observed local state:

- iTerm2.app is installed.
- `uv sync --extra iterm` installs `iterm2==2.20` successfully.
- Required `LocalWriteOnlyProfile` setters are present in that package.
- The live connection probe currently reports that iTerm2's Python API is not reachable until iTerm2 is running and Python API support is enabled.
- `screencapture` works in the current session.

Remaining live iTerm2 work:

1. Optional future refinement: replace heuristic text-row detection with OCR/terminal-cell-aware glyph segmentation.

## Milestone 7: deterministic E2E staging

Implemented:

- `term-chameleon e2e-stage <profile.json>` combines background HTML, ANSI pattern script, deterministic visual simulation, screenshot-test, and a top-level report.
- `--capture` performs real screen capture and screenshot pixel analysis when permissions allow.

This is the current automated integration layer before full GUI/window orchestration.

## Milestone 8: setup, configuration, daemon lifecycle, and release gate

Implemented:

- `term-chameleon status` and `status --live` summarize local readiness and recommend the next command.
- `term-chameleon setup` runs deterministic checks, inspects/installs the generated Dynamic Profile, and optionally verifies live iTerm2 readiness.
- `term-chameleon config-example` and `config-check` provide repeatable TOML defaults with strict validation before setup/watch/daemon use.
- `term-chameleon watch-daemon-status` and `uninstall-watch-daemon` complete the AutoLaunch lifecycle.
- `term-chameleon release-check` is the top-level local release-readiness gate, composing deterministic self-checks, optional config validation, status/live readiness, optional daemon health, and optional controlled live-stage screenshot QA into JSON/Markdown reports.

## Milestone 9: beta dogfood hardening

Implemented/verified:

- Installed the beta wheel into a durable local venv (`~/.local/share/term-chameleon/venv`), reinstalled AutoLaunch with default pid/log paths, restarted iTerm2, and verified sample artifacts plus live release gate.
- Hardened long-running watcher behavior so transient iTerm2 apply failures (for example no current session) are logged as recoverable events instead of terminating the daemon.

- Observed watcher screenshot sample artifacts over a sustained run.
- Promoted release metadata to `0.1.0b2` / `v0.1.0-beta.2`.
