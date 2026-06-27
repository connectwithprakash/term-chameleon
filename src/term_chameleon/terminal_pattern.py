from __future__ import annotations

from pathlib import Path

from .safe_io import atomic_write_text
from .visual import ANSI_TEST_PATTERN


def shell_script_content() -> str:
    escaped = ANSI_TEST_PATTERN.encode("unicode_escape").decode("ascii")
    return f"""#!/usr/bin/env bash
set -euo pipefail
printf '%b' '{escaped}'
echo
echo 'Term Chameleon pattern rendered. Press Ctrl-C or close the terminal when done.'
if [[ "${{TERM_CHAMELEON_PATTERN_WAIT:-1}}" == "1" ]]; then
  while true; do sleep 3600; done
fi
"""


def write_pattern_script(path: str | Path) -> Path:
    target = Path(path)
    atomic_write_text(target, shell_script_content())
    try:
        target.chmod(0o755)
    except OSError as exc:
        raise OSError(
            f"script written to {target} but could not set executable bit: {exc}"
        ) from exc
    return target


def write_pattern_bundle(output_dir: str | Path) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    pattern = out / "ansi-pattern.txt"
    script = out / "render-pattern.sh"
    pattern.write_text(ANSI_TEST_PATTERN, encoding="utf-8")
    write_pattern_script(script)
    return pattern, script
