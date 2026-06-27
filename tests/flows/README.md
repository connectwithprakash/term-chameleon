# User-Flow Tests

This directory defines **term-chameleon's user journeys as data**, then runs them two ways:

- **Deterministic layer** — runs the real CLI in a subprocess against fixtures and asserts
  on exit codes, stdout, and generated artifacts. Fast, hermetic, CI-safe. Always runs.
- **Visual layer** — drives **real iTerm2** via the [Cua Driver](https://github.com/trycua/cua)
  (background computer-use), captures the rendered window, and asserts the result is actually
  readable on screen. Proves the GUI path end-to-end. Runs only on demand (macOS + iTerm2 + Cua).

The flows double as living documentation of what the tool is supposed to do for a user.

## Layout

```
tests/flows/
├── README.md          # this file
├── schema.md          # the flow-spec format
├── runner.py          # loads specs, executes steps, returns structured results
├── conftest.py        # pytest wiring + --run-visual gate + markers
├── test_flows.py      # parametrizes every spec into a pytest case
└── specs/
    ├── 01-first-time-setup.toml
    ├── 02-diagnose-bad-profile.toml
    ├── ...
    └── 90-visual-live-adapt.toml   # layer: visual
```

## Running

```bash
# Fast deterministic flows only (default; what CI runs)
.venv/bin/python -m pytest tests/flows -m "not visual"

# Everything including the real-iTerm2 visual flows (macOS + iTerm2 + Cua Driver)
.venv/bin/python -m pytest tests/flows --run-visual

# A single flow by name
.venv/bin/python -m pytest tests/flows -k diagnose-bad-profile
```

## Adding a flow

1. Copy an existing spec in `specs/`, give it a unique `name`.
2. Describe the journey from the user's point of view in `description`.
3. List `steps`; each is a CLI invocation plus expectations. See [schema.md](schema.md).
4. Pick `layer: deterministic` (default) or `layer: visual`.
5. Run `pytest tests/flows -k <name>` and iterate.

No Python needed to add a deterministic flow — it is pure data.
