# Flow-spec schema

A flow is a TOML file in `specs/`. One file = one user journey. TOML is used
because `tomllib` is in the Python 3.11+ standard library — the project ships
with zero runtime dependencies and the flow suite keeps that property.

```toml
name = "diagnose-bad-profile"        # unique, kebab-case; used in pytest -k
description = """
A user has a glass theme where ANSI black text vanishes. They run the
diagnostician and expect to be told what is wrong.
"""
layer = "deterministic"              # "deterministic" (default) | "visual"
requires = []                        # optional capability tags, e.g. ["iterm2", "cua", "macos"]

# Optional values interpolated into step `run` strings as {key}.
# `workdir` is always available and points at a per-flow temp dir.
[vars]
profile = "tests/fixtures/iterm/bad-ansi-black.json"

[[steps]]
name = "diagnose"                    # optional human label
run = "doctor {profile}"             # args passed to the term-chameleon CLI (no leading binary)
expect_exit = 1                      # int, or list of acceptable ints; default 0
expect_stdout_contains = ["[fail]", "ITERM_LIGHT_DARK_DRIFT"]
expect_stdout_not_contains = ["Traceback"]
expect_stderr_contains = []          # optional
expect_artifact = []                 # optional: file paths that must exist after the step
timeout = 30                         # seconds; default 60
```

## Step execution

- Each `run` is executed as `python -m term_chameleon.cli <run...>` in a subprocess,
  with `cwd` = repo root and a fresh per-flow `workdir` temp dir.
- `{key}` placeholders are filled from `[vars]` plus the built-in `{workdir}`.
- A step fails the flow if: exit code is not allowed, a required stdout/stderr substring is
  missing, a forbidden substring appears, an expected artifact is absent, or it times out.
- `Traceback (most recent call last)` in stdout/stderr always fails the step (an uncaught
  exception is never a user-friendly outcome), even if not explicitly forbidden — robustness guardrail.

## Visual steps (`layer = "visual"`)

Visual flows add a `[[steps]]` entry with a `[steps.visual]` table, executed through the
Cua Driver against real iTerm2:

```toml
[[steps]]
name = "live-adapt-stays-readable"
[steps.visual]
launch_app = "iTerm"                 # launch/focus a real app in the background
background = "gradient"              # controlled browser background staged behind it
apply = "balanced"                   # mode/preset applied to the live session
capture = "front-window"             # capture the rendered window
assert_contrast_at_least = 4.5       # WCAG ratio the captured text/bg must meet
```

The runner captures the window via the driver, runs the existing `screenshot-text-contrast`
analysis on the capture, and asserts the measured ratio. Visual steps are **skipped** (not
failed) when their `requires` capabilities are absent, so the suite stays green off-macOS.
