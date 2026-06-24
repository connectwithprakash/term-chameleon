# Product Spec: Term Chameleon

## Summary

Term Chameleon is a contrast-management tool for translucent/glassy terminal environments. It helps users keep transparent or blurred terminals readable by diagnosing, fixing, and eventually dynamically adapting profile colors, contrast settings, transparency, and blur.

Initial platform: iTerm2 on macOS.

## Product goals

1. Keep glass terminals readable.
2. Preserve aesthetics when possible.
3. Explain contrast problems clearly.
4. Make profile changes safe and reversible.
5. Evolve from static doctor/fixer to dynamic adaptation.

## Non-goals for MVP

- Renderer-level per-glyph inversion.
- Forking terminal emulators.
- Universal terminal support on day one.
- Perfect aesthetic judgment automation.
- Direct mutation of iTerm2 plist preferences as primary integration.

## User-facing modes

### Static doctor

```bash
term-chameleon doctor <profile.json>
```

Reports risks such as Light/Dark variant drift, low foreground/background contrast, ANSI black invisibility, selection contrast failures, risky transparency, and missing Minimum Contrast.

### Static fixer

```bash
term-chameleon fix <profile.json> --dry-run
term-chameleon fix <profile.json> --yes
```

Shows an explainable diff, creates timestamped backups before writing, and applies conservative readable defaults.

### Install / preset flow

Planned:

```bash
term-chameleon install --preset balanced --name "Adaptive Glass"
```

Installs iTerm2 Dynamic Profile JSON under:

```text
~/Library/Application Support/iTerm2/DynamicProfiles/
```

### Visual test harness

Planned:

```bash
term-chameleon visual-test
```

Creates controlled backgrounds, renders ANSI test patterns, captures screenshots, and computes contrast metrics.

### Dynamic watcher

Planned:

```bash
term-chameleon watch
```

Starts with mode switching and eventually screen-sampling background-aware adaptation.

## Adaptation modes

| Mode | Use case | Transparency | Blur | Minimum Contrast |
|---|---:|---:|---:|---:|
| dark-glass | dark background | 0.10 | 18 | 0.30 |
| balanced | default | 0.08 | 18 | 0.35 |
| bright-safe | bright background | 0.04 | 22 | 0.45 |
| high-variance-safe | noisy background | 0.05 | 24 | 0.45 |
| presentation | screen share | 0.00 | 0 | 0.45 |
| accessibility | maximum readability | 0.00 | 0 | 0.55 |

## Default balanced palette

```text
Background:        #090C16
Foreground:        #E5EBF5
Bold:              #E5EBF5
Cursor:            #939FFB
Selection:         #31394F
Selected Text:     #E5EBF5
ANSI black:        #6B7280
ANSI bright black: #9CA3AF
ANSI white:        #C7CDD8
ANSI bright white: #F8FAFC
Transparency:      0.08
Blur:              true
Blur Radius:       18
Minimum Contrast:  0.35
Separate Light/Dark Colors: false
```

## Dynamic behavior principles

- Prefer mode switching before continuous tuning.
- Use hysteresis to prevent flicker.
- Preserve hue and theme semantics where possible.
- Adjust transparency/blur only within user-configured policy bounds.
- Treat screen-sampling as experimental until proven reliable.
