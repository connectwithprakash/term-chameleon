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

Implement controlled background windows, terminal test pattern, screenshot capture, and contrast report.

## Milestone 5: dynamic prototypes

Order:

1. Manual mode switching.
2. iTerm2 Python API session-local mutation.
3. Heuristic watcher.
4. Screen-sampling watcher.
5. OSC backend.
6. tmux support.

Do not start this until static doctor/fixer is solid.
