# Changelog

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
