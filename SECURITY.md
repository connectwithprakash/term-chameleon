# Security Policy

## Supported versions

Term Chameleon is pre-1.0. Security fixes land on the latest released version only.

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |
| < 0.1   | No        |

## Reporting a vulnerability

Report suspected vulnerabilities privately via GitHub's "Report a vulnerability"
flow on the repository's Security tab (Security advisories), not as a public issue.

Include the version, platform, a reproduction, and the impact you observed. You can
expect an acknowledgement within a few days and a fix or mitigation plan once the
report is confirmed.

## Threat model

Term Chameleon runs locally on a developer's macOS machine. It reads and writes
iTerm2 Dynamic Profile JSON, generates OSC color sequences, samples the screen via
`screencapture`, and drives the local iTerm2 Python API. It has no network surface
and no runtime dependencies, which keeps the attack surface small.

The inputs that matter for safety:

- **Profile JSON** — parsed from user-supplied or hand-edited files. Malformed input
  is rejected with a clear `ValueError`, never an uncaught crash. Profile writes are
  atomic and create a timestamped backup before mutating.
- **PNG/PPM images** — decoded by a built-in codec with a pixel-count cap and bounded
  decompression to prevent decompression-bomb resource exhaustion.
- **Daemon executable path** — the `--python` value baked into the AutoLaunch script is
  validated (rejects shell metacharacters and non-existent paths) before use.
- **AppleScript / subprocess** — window-bounds and screenshot calls use fixed scripts
  with arguments passed as separate `subprocess` argv entries, not shell strings.

If you find an input that produces an uncaught crash, a path traversal, command
injection, or unbounded resource use, that is a security issue worth reporting.
