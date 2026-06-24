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
- Controlled HTML backgrounds for browser/window staging.
- Terminal ANSI pattern script artifacts.

Remaining live visual work:

- Automatically arrange controlled browser background + iTerm2 pattern window.
- Locate rendered text pixels and compute foreground/background contrast from screenshots.

## Milestone 5: dynamic watcher and one-shot adaptation

Implemented:

- `watch.py` risk classifier.
- hysteresis `ModeSelector`.
- deterministic CLI simulation: `term-chameleon watch-sim`.
- image/screen sampling: `term-chameleon sample --image/--screen`.
- safe one-shot adaptation: `term-chameleon adapt-once <profile.json> --image/--screen --dry-run|--yes`.

`watch-sim` is not a live daemon; it is the deterministic testable core. `adapt-once` is the first working screen-sampling adaptation path.

## Milestone 6: live iTerm2/screenshot spike

Implemented:

- `term-chameleon iterm-api-check` reports iTerm2.app, `iterm2` Python package availability, Python executable, and required `LocalWriteOnlyProfile` setter readiness.
- `term-chameleon iterm-live-script` generates a conservative session-local adapter script using `LocalWriteOnlyProfile` and `session.async_set_profile_properties`.
- Optional package extra: `uv sync --extra iterm`.
- `term-chameleon screenshot-probe` checks macOS `screencapture` availability and can attempt a real capture.

Observed local state:

- iTerm2.app is installed.
- `uv sync --extra iterm` installs `iterm2==2.20` successfully.
- Required `LocalWriteOnlyProfile` setters are present in that package.
- `screencapture` works in the current session.

Remaining live iTerm2 work:

1. Run the generated script from inside iTerm2 after any required iTerm2 Python API permissions are enabled.
2. Package a long-running AutoLaunch daemon around the validated session-local adapter.
3. Add optional window orchestration for fully automatic screenshot/text-pixel validation.

## Milestone 7: deterministic E2E staging

Implemented:

- `term-chameleon e2e-stage <profile.json>` combines background HTML, ANSI pattern script, deterministic visual simulation, screenshot-test, and a top-level report.
- `--capture` performs real screen capture and screenshot pixel analysis when permissions allow.

This is the current automated integration layer before full GUI/window orchestration.
