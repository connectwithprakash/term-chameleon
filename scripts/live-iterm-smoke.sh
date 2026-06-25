#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== iTerm2 API readiness =="
uv run --extra iterm term-chameleon iterm-api-check

echo "== live iTerm2 connection =="
uv run --extra iterm term-chameleon iterm-connect-probe

echo "== dry-run watcher =="
uv run --extra iterm term-chameleon watch-live --dry-run --duration 3 --interval 1 --stable 1 --cooldown 2 --output-dir /tmp/term-chameleon-watch-live-dry-run

echo "== live watcher apply pass =="
uv run --extra iterm term-chameleon watch-live --yes --duration 3 --interval 1 --stable 1 --cooldown 2 --output-dir /tmp/term-chameleon-watch-live-apply

echo "[ok] live iTerm2 watcher smoke passed"
