# Product Spec: Term Chameleon

## Summary

Term Chameleon is a contrast-management tool for translucent/glassy terminal environments. It helps users keep transparent or blurred terminals readable by diagnosing, fixing, staging, measuring, and dynamically adapting profile colors, contrast settings, transparency, and blur.

Initial platform: iTerm2 on macOS.

## Product goals

1. Keep glass terminals readable.
2. Preserve aesthetics when possible.
3. Explain contrast problems clearly.
4. Make profile changes safe and reversible.
5. Provide objective deterministic and live screenshot QA evidence for readability changes.

## Non-goals

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

```bash
term-chameleon install --preset balanced --name "Adaptive Glass"
term-chameleon install-watch-daemon --dry-run
```

Installs iTerm2 Dynamic Profile JSON under:

```text
~/Library/Application Support/iTerm2/DynamicProfiles/
```

`install-watch-daemon` installs an iTerm2 AutoLaunch script under the user's AutoLaunch scripts directory so `watch-live --yes --iterm-window` can start when iTerm2 launches.

### Visual test harness

Runs the current deterministic pre-screenshot visual simulation:

```bash
term-chameleon visual-test <profile.json>
```

It models controlled solid backgrounds, writes ANSI pattern artifacts, computes WCAG contrast metrics, and is complemented by screenshot/pixel QA commands:

```bash
term-chameleon screenshot-contrast <image>
term-chameleon screenshot-text-contrast <image>
term-chameleon live-stage --yes --capture
```

The live stage arranges a controlled Safari background and iTerm2 pattern window, captures the screen, scopes analysis to the iTerm2 window, and reports text-row contrast with pixel-cluster fallback.

### Dynamic watcher

Dynamic mode-selection simulation and live iTerm2 session adaptation:

```bash
term-chameleon watch-sim 0.2 0.8 0.8 0.8 0.5:0.12
term-chameleon sample --screen --iterm-window
term-chameleon watch-live --yes --iterm-window
```

This exercises the risk classifier and hysteresis mode selector in simulation, then uses live iTerm2 session-local profile mutation for screen/window-aware adaptation.

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
