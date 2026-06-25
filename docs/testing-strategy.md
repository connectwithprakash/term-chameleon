# Testing Strategy

## Goal

Term Chameleon should be verifiable without manual supervision for objective correctness. Subjective aesthetics can still require human taste, but profile correctness, contrast metrics, and dynamic mode switching should be testable.

## Automated layers

1. Unit tests for colors, contrast, profile parsing, diagnostics, fixes, and mode selection.
2. CLI tests with fixture profiles.
3. Integration tests for iTerm2 Dynamic Profile file installation and AutoLaunch script compilation.
4. Permission-free deterministic self-check via `term-chameleon check` for post-install smoke validation.
5. Visual tests in deterministic simulation, screenshot/pixel analysis, text-row contrast analysis, and live GUI staging layers.
6. Dynamic watcher E2E tests with controlled samples, iTerm-window sampling, and hysteresis assertions.

## Visual test design

Current command:

```bash
term-chameleon visual-test <profile.json>
```

The current harness is a deterministic pre-screenshot simulation. It:

1. Models the terminal background blended over controlled solid backgrounds.
2. Generates an ANSI terminal test pattern artifact.
3. Computes WCAG contrast for normal, bold, ANSI black, bright black, white, and bright white.
4. Emits JSON and Markdown reports.

Screenshot/live harness commands:

```bash
term-chameleon screenshot-test --capture --output-dir artifacts/screenshot-test
term-chameleon screenshot-contrast artifacts/screenshot-probe/screen.png
term-chameleon screenshot-text-contrast artifacts/screenshot-probe/screen.png
term-chameleon live-stage --yes --capture --output-dir artifacts/live-stage
```

The first three commands are deterministic or permission-light. `live-stage --yes --capture` is a live smoke gate: it can run unattended after macOS Screen Recording/Automation permissions are granted, but it intentionally activates/moves Safari and iTerm2 windows.

The screenshot/live harness:

1. Creates controlled backgrounds: dark, light, gray, checkerboard, gradient.
2. Renders an ANSI test pattern.
3. Captures screenshots when macOS permissions allow.
4. Locates the iTerm2 window region.
5. Measures text-row contrast with pixel-cluster fallback.
6. Emits PNG artifacts plus JSON/Markdown pass/fail reports.

Text styles to test:

```text
normal
bold
dim
ANSI 0 black
ANSI 8 bright black
ANSI 7 white
ANSI 15 bright white
selection-like sample
statusline-muted sample
```

Artifacts:

```text
artifacts/visual-test/report.json
artifacts/visual-test/report.md
artifacts/visual-test/ansi-pattern.txt
artifacts/screenshot-test/*
artifacts/screenshot-contrast/contrast-report.json
artifacts/screenshot-text-contrast/text-contrast-report.json
artifacts/live-stage/live-stage-report.json
artifacts/live-stage/live-stage-screen.png
```

## Dynamic E2E design

Implemented commands:

```bash
term-chameleon watch-sim --stable 2 0.2 0.2 0.8 0.8 0.5:0.12 0.5:0.12
term-chameleon watch-live --dry-run --iterm-window --duration 10 --interval 1 --stable 2
scripts/live-iterm-smoke.sh
```

Flow:

1. Start watcher.
2. Show dark background, assert dark-glass mode.
3. Show bright background, assert bright-safe mode.
4. Show checkerboard, assert high-variance-safe mode.
5. Capture screenshots and assert contrast thresholds.
6. Verify hysteresis prevents rapid flicker.

## Permissions

macOS visual tests may require:

- Screen Recording permission.
- Accessibility permission for moving windows.
- Automation permission for iTerm2 control.

After initial permission grants, objective visual tests should run unattended.
