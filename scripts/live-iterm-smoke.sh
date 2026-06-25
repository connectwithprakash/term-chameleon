#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== iTerm2 API readiness =="
uv run --extra iterm term-chameleon iterm-api-check

echo "== live iTerm2 connection =="
uv run --extra iterm term-chameleon iterm-connect-probe

echo "== iTerm2 window bounds =="
uv run term-chameleon iterm-window-bounds

echo "== iTerm2-window sample =="
uv run term-chameleon sample --screen --iterm-window --output /tmp/term-chameleon-watch-live-window.png

echo "== dry-run watcher =="
uv run --extra iterm term-chameleon watch-live --dry-run --iterm-window --duration 3 --interval 1 --stable 1 --cooldown 2 --output-dir /tmp/term-chameleon-watch-live-dry-run

echo "== live watcher apply pass =="
uv run --extra iterm term-chameleon watch-live --yes --iterm-window --duration 3 --interval 1 --stable 1 --cooldown 2 --output-dir /tmp/term-chameleon-watch-live-apply

echo "[ok] live iTerm2 watcher smoke passed"
