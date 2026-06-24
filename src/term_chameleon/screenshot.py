from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ScreenshotResult:
    available: bool
    captured: bool
    output_path: Path | None
    message: str
    returncode: int | None = None


def screencapture_path() -> str | None:
    return shutil.which("screencapture")


def capture_screen(output_path: str | Path, *, timeout: float = 10.0) -> ScreenshotResult:
    command = screencapture_path()
    target = Path(output_path)
    if command is None:
        return ScreenshotResult(False, False, target, "macOS screencapture command not found")
    target.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [command, "-x", str(target)],
        check=False,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if completed.returncode == 0 and target.exists() and target.stat().st_size > 0:
        return ScreenshotResult(
            True, True, target, f"captured screenshot: {target}", completed.returncode
        )
    message = (completed.stderr or completed.stdout or "screencapture failed").strip()
    return ScreenshotResult(True, False, target, message, completed.returncode)


def probe_screenshot(
    output_path: str | Path | None = None, *, capture: bool = False
) -> ScreenshotResult:
    command = screencapture_path()
    target = Path(output_path) if output_path is not None else None
    if command is None:
        return ScreenshotResult(False, False, target, "macOS screencapture command not found")
    if not capture:
        return ScreenshotResult(True, False, target, f"screencapture available: {command}")
    if target is None:
        target = Path("artifacts/screenshot-probe/screen.png")
    return capture_screen(target)
