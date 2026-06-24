# Testing Strategy

## Goal

Term Chameleon should be verifiable without manual supervision for objective correctness. Subjective aesthetics can still require human taste, but profile correctness, contrast metrics, and dynamic mode switching should be testable.

## Automated layers

1. Unit tests for colors, contrast, profile parsing, diagnostics, fixes, and mode selection.
2. CLI tests with fixture profiles.
3. Integration tests for iTerm2 Dynamic Profile file installation and AutoLaunch script compilation.
4. Visual tests in two layers: deterministic profile simulation first, screenshot/pixel tests later.
5. Dynamic watcher E2E tests with controlled background changes and hysteresis assertions.

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

Planned screenshot harness:

1. Create controlled backgrounds: dark, light, gray, checkerboard, gradient.
2. Open iTerm2 with target profile.
3. Render the ANSI test pattern.
4. Capture screenshots.
5. Locate known text rows or markers.
6. Measure foreground/background contrast with WCAG and later APCA.
7. Emit PNG artifacts and a pass/fail report.

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
artifacts/visual-test/*.png  # planned screenshot harness
```

## Dynamic E2E design

Planned command:

```bash
term-chameleon e2e-test --watch
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
