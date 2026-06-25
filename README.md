# Term Chameleon

Term Chameleon is an adaptive contrast/readability toolkit for translucent terminals, starting with iTerm2 on macOS.

Glassy terminal themes look good until white text disappears over a bright window, black/dim text vanishes over dark blur, or iTerm2 Light/Dark profile variants silently override the intended palette. Term Chameleon provides static profile diagnostics/fixes plus live background-aware sampling, staging, and adaptation for iTerm2.

## Current status

This repository is prepared as `v0.1.0-alpha.3` / Python package version `0.1.0a3`: an end-to-end alpha for static profile diagnostics, safe profile mutation, deterministic visual artifacts, live iTerm2 adaptation, and controlled macOS GUI/screenshot QA. Implemented:

- iTerm2 Dynamic Profile JSON parsing.
- Color conversion between hex and iTerm2 color dictionaries.
- WCAG contrast calculations.
- Static diagnostics for common glass-terminal readability failures.
- Conservative static fixer with dry-run, backups, deterministic JSON, and explainable changes.
- iTerm2 Dynamic Profile preset install flow, including optional AutoLaunch default-profile script.
- Manual readability mode switching for profile JSON files.
- OSC color sequence generation, including tmux passthrough wrapping.
- Dynamic watcher foundation via `watch-sim` risk classifier and hysteresis mode selector.
- iTerm2 live-adapter script generation/probe foundation for session-local Python API validation.
- Screen/image sampling one-shot adaptation via `sample` and `adapt-once`.
- Live adaptive watcher via `watch-live`, with dry-run, stable-sample, cooldown, duration, and real iTerm2 session-local apply modes.
- Deterministic E2E staging bundle that combines controlled backgrounds, ANSI pattern artifacts, visual simulation, screenshot capture, and screenshot pixel analysis.
- Screenshot contrast estimation for captured PNG/PPM artifacts.
- Text-row/glyph-aware screenshot contrast estimation for rendered terminal pattern captures.
- Live GUI staging that arranges controlled Safari background + iTerm2 ANSI pattern windows and can optionally capture/analyze the result with text-row contrast and pixel-cluster fallback.
- macOS `screencapture` probe and screenshot-test artifact foundation for screenshot-based visual tests.
- Long-running daemon packaging for continuous adaptation.
- Permission-free deterministic self-check command for post-install validation.
- Local readiness status command with human and JSON output.
- Guided setup command that runs deterministic checks and optionally installs the default profile.
- Fixture tests for good and bad iTerm2 profiles.

Optional future refinements:

- Replace heuristic text-row detection with OCR/terminal-cell-aware glyph segmentation.
- Add broader terminal emulator support beyond iTerm2.

## Alpha release verification

Build and install the alpha wheel locally:

```bash
uv build
python3 -m venv /tmp/term-chameleon-alpha-venv
/tmp/term-chameleon-alpha-venv/bin/pip install dist/term_chameleon-0.1.0a3-py3-none-any.whl
/tmp/term-chameleon-alpha-venv/bin/term-chameleon check --output-dir /tmp/term-chameleon-alpha-check
```

See [CHANGELOG.md](CHANGELOG.md) for release notes.

## CLI examples

Run a permission-free deterministic self-check after installation or inspect local readiness:

```bash
term-chameleon check --output-dir artifacts/check
term-chameleon setup
term-chameleon setup --yes
term-chameleon setup --live
term-chameleon status
term-chameleon status --live
term-chameleon status --json
```

`setup` is a guided flow: it runs deterministic checks and reports status. On first run, bare `setup` exits nonzero until a healthy profile exists; use `setup --yes` to install the generated profile, and `setup --live` to include live iTerm2 API/window readiness.

Install a balanced preset into a target directory:

```bash
term-chameleon install --target-dir /tmp/iterm-dynamic-profiles --name "Adaptive Glass"
```

Install an iTerm2 AutoLaunch script that starts the live watcher whenever iTerm2 launches:

```bash
term-chameleon install-watch-daemon --dry-run
term-chameleon install-watch-daemon
```

Apply a manual readability mode to a profile JSON file:

```bash
term-chameleon mode bright-safe ~/Library/Application\ Support/iTerm2/DynamicProfiles/adaptive-glass.json --dry-run
```

Check iTerm2 Python API readiness and generate a conservative session-local adapter script:

```bash
term-chameleon iterm-api-check
term-chameleon iterm-connect-probe
term-chameleon iterm-window-bounds
term-chameleon iterm-live-script --preset balanced --output /tmp/term-chameleon-live.py
```

Probe macOS screenshot availability and generate controlled screenshot-test artifacts:

```bash
term-chameleon screenshot-probe
term-chameleon screenshot-probe --capture --output artifacts/screenshot-probe/screen.png
term-chameleon screenshot-contrast artifacts/screenshot-probe/screen.png --output-dir artifacts/screenshot-contrast
term-chameleon screenshot-text-contrast artifacts/screenshot-probe/screen.png --output-dir artifacts/screenshot-text-contrast
term-chameleon screenshot-test --output-dir artifacts/screenshot-test
term-chameleon screenshot-test --capture --output-dir artifacts/screenshot-test
term-chameleon background-html --output-dir artifacts/background-html
term-chameleon pattern-script --output-dir artifacts/pattern-script
term-chameleon e2e-stage tests/fixtures/iterm/good-dark-glass.json --output-dir artifacts/e2e-stage
term-chameleon live-stage --dry-run --output-dir artifacts/live-stage
term-chameleon live-stage --yes --capture --output-dir artifacts/live-stage
```

`live-stage --yes` is intentionally explicit because it activates Safari, opens the controlled background page, creates/resizes an iTerm2 window, writes the ANSI pattern command into that session, and may require macOS Automation/Accessibility/Screen Recording permissions. It leaves the staged windows open for inspection.

```bash
term-chameleon sample --screen --output artifacts/adapt/screen.png
term-chameleon sample --screen --iterm-window --output artifacts/adapt/iterm-window.png
term-chameleon sample --screen --region 0,0,800,600 --output artifacts/adapt/region.png
term-chameleon adapt-once tests/fixtures/iterm/good-dark-glass.json --screen --dry-run
term-chameleon watch-live --dry-run --duration 10 --interval 1 --stable 2
term-chameleon watch-live --dry-run --iterm-window --duration 10 --interval 1 --stable 2
term-chameleon watch-live --yes --iterm-window --duration 30 --interval 2 --stable 3 --cooldown 10
```

Manual live smoke test, once iTerm2 is running and the Python API is enabled:

```bash
scripts/live-iterm-smoke.sh
```

Run deterministic visual simulation:

```bash
term-chameleon visual-test tests/fixtures/iterm/good-dark-glass.json
```

Doctor a profile:

```bash
term-chameleon doctor tests/fixtures/iterm/bad-light-variant.json
term-chameleon doctor tests/fixtures/iterm/bad-light-variant.json --json
```

`doctor --json` emits machine-readable diagnostics after a profile loads successfully; profile load/parse errors still use the standard nonzero exit code with an error on stderr.

Preview fixes:

```bash
term-chameleon fix tests/fixtures/iterm/bad-light-variant.json --dry-run
```

Apply fixes to a copy:

```bash
cp tests/fixtures/iterm/bad-light-variant.json /tmp/profile.json
term-chameleon fix /tmp/profile.json --yes
term-chameleon doctor /tmp/profile.json
```

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

If you do not use `uv`:

```bash
python3 -m pytest
python3 -m term_chameleon.cli doctor tests/fixtures/iterm/bad-light-variant.json
```

## Safety principles

- Static analysis before mutation.
- `--dry-run` support for fixes.
- Timestamped backups before writing.
- Deterministic JSON output.
- Explainable diagnostics and fixes.
- No direct mutation of `~/Library/Preferences/com.googlecode.iterm2.plist` as the primary mechanism.

## Positioning

Term Chameleon is not just another terminal theme and does not claim to invent automatic contrast. Prior art includes iTerm2 Minimum Contrast, Apple Terminal contrast tweaking, Ghostty minimum contrast, terminal opacity/blur settings, CSS blend-mode/backdrop approaches, and WCAG/APCA contrast engines.

The intended differentiated direction is a live contrast controller for translucent terminal windows: sample or infer the actual visual environment behind the terminal, then adapt palette, opacity, blur, and contrast to keep text readable without giving up the glass effect.
