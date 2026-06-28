# Documentation

Reference and design docs for Term Chameleon. Start with the
[project README](../README.md) for install and usage.

## Design and planning

- [product-spec.md](product-spec.md) — what the tool is and the problems it solves
- [implementation-plan.md](implementation-plan.md) — milestone roadmap
- [testing-strategy.md](testing-strategy.md) — how the tool is tested, including the
  deterministic and live (real-iTerm2) layers

## Research

- [research/prior-art.md](research/prior-art.md)
- [research/iterm2-integration.md](research/iterm2-integration.md)
- [research/terminal-osc-compatibility.md](research/terminal-osc-compatibility.md)

## Audit history

The codebase went through several adversarial audit rounds before release. Each round's
confirmed findings are recorded as machine-readable JSON; each maps to the commit that
resolved it.

- `audit-findings-round2-2026-06-27.json` — concurrency, lifecycle, CLI dispatch
- `audit-findings-round3-2026-06-27.json` — domain logic, format round-trips, fuzzing
- `audit-findings-round4-2026-06-27.json` — GUI/multi-monitor, install lifecycle, docs
- `audit-findings-round5.md` — final ship-blocker pass (converged: no new source issues)
- `audit/` — earlier human-readable audit and edge-case prose, kept for reference

The dated JSON files are the canonical record; the prose under `audit/` is superseded
background.
