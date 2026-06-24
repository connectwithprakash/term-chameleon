# Implementation Plan

## Milestone 0: repository and docs

- Scaffold Python project.
- Write durable source-backed docs.
- Add tests directory and fixture profiles.

Acceptance:

```bash
python -m pytest
```

runs and at least fixture/parser/contrast tests pass.

## Milestone 1: static iTerm2 profile doctor

Implement:

- `Color` model and conversions.
- WCAG contrast calculations.
- iTerm2 Dynamic Profile parser.
- Diagnostic rule engine.
- CLI: `term-chameleon doctor <profile.json>`.

Diagnostic codes:

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

Implement:

- `term-chameleon fix <profile.json>`.
- `--dry-run`.
- `--yes`.
- timestamped backups.
- deterministic JSON.
- explainable diff.

Acceptance:

- Bad fixtures become passing or only informational after fix.
- Backups are created before writes.

## Milestone 3: iTerm2 install flow

Implement:

- Preset generation.
- Dynamic Profile install path.
- Optional AutoLaunch script generation.
- Verification command.

## Milestone 4: visual test harness

Current implementation is a deterministic pre-screenshot simulation: controlled solid-background blending, ANSI pattern artifact, JSON/Markdown reports, and WCAG contrast checks. The full screenshot harness remains planned.

Next full harness work:

- controlled background windows.
- terminal test pattern rendering in iTerm2.
- screenshot capture.
- pixel contrast report.

## Milestone 5: dynamic watcher foundation

Implemented foundation:

- `watch.py` risk classifier.
- hysteresis `ModeSelector`.
- deterministic CLI simulation: `term-chameleon watch-sim`.

Do not treat `watch-sim` as a live daemon; it is the deterministic testable core.

## Milestone 6: live iTerm2/screenshot spike

Implemented safe foundation:

- `term-chameleon iterm-api-check` reports whether iTerm2.app and the `iterm2` Python package are available.
- `term-chameleon iterm-live-script` generates a conservative session-local adapter script using `LocalWriteOnlyProfile` and `session.async_set_profile_properties`.
- `term-chameleon screenshot-probe` checks macOS `screencapture` availability and can attempt a real capture.

Observed local state during development:

- iTerm2.app is installed.
- The active project Python environment does not currently have the `iterm2` package importable.
- `screencapture` exists and `term-chameleon screenshot-probe --capture` succeeded in the current session. Future full harness work can build on this, while still handling permission failures gracefully.

Next validation steps:

1. Install/enable iTerm2 Python runtime support in the environment used by iTerm2 scripts.
2. Run the generated script from iTerm2 after permissions are granted.
3. Build controlled background windows now that basic screenshot capture has been verified.
4. Add pixel-level screenshot analysis and compare it with deterministic visual simulation.
