"""Visual flow execution via the Cua Driver against real iTerm2.

This layer is intentionally thin and best-effort: it shells out to the
``cua-driver`` CLI (the same binary the MCP server wraps) to launch/capture a
real window, writes the capture to disk, and reuses term-chameleon's own
``screenshot-text-contrast`` analysis to assert readability. It is only imported
and exercised under ``pytest --run-visual`` on macOS with the driver installed.

Keeping the driver interaction in one place means a future switch to a different
host-control backend touches only this file.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from runner import REPO_ROOT, Step, StepResult

DRIVER = "cua-driver"


def _driver_available() -> bool:
    return shutil.which(DRIVER) is not None


def _driver_call(tool: str, payload: dict, *, timeout: int = 30) -> dict:
    """Invoke a Cua Driver tool via the CLI and parse its JSON result."""
    proc = subprocess.run(
        [DRIVER, "call", tool, "--json", json.dumps(payload)],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"cua-driver {tool} failed: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"raw": proc.stdout}


def _measure_capture_contrast(capture_path: Path, workdir: Path) -> float:
    """Run term-chameleon's own text-contrast analysis on a captured image.

    Reuses the shipped `screenshot-text-contrast` command, which writes a JSON
    report to its output dir, then reads back the measured WCAG `contrast`.
    """
    out_dir = workdir / "visual-contrast"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "term_chameleon.cli",
            "screenshot-text-contrast",
            str(capture_path),
            "--output-dir",
            str(out_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"text-contrast analysis failed: {proc.stderr.strip()}")
    report = out_dir / "text-contrast-report.json"
    if not report.exists():
        raise RuntimeError(f"text-contrast report not written: {report}")
    data = json.loads(report.read_text())
    return float(data.get("contrast", 0.0))


def _window_area(window) -> float:
    bounds = window.get("bounds") or {}
    return float(bounds.get("width", 0)) * float(bounds.get("height", 0))


def _select_window(windows_result, app):
    """Pick the largest content window owned by the launched app.

    iTerm reports many sliver windows (tab bars, title fragments); selecting by
    area avoids capturing a 35px-tall title strip instead of the terminal body.
    A titled window is preferred as a tie-breaker since it is the real session.
    """
    windows = windows_result.get("windows", [])
    candidates = windows
    if app:
        needle = app.lower().replace("2", "")
        owned = [w for w in windows if needle in (w.get("app_name", "").lower())]
        if owned:
            candidates = owned
    if not candidates:
        return None
    return max(candidates, key=lambda w: (_window_area(w), bool(w.get("title"))))


def _write_capture(state, workdir):
    """Decode the driver's inline base64 PNG capture to a file for analysis."""
    b64 = state.get("screenshot_png_b64")
    if not b64:
        return None
    out = workdir / "capture.png"
    out.write_bytes(base64.b64decode(b64))
    return out


def run_visual_step(step: Step, variables: dict) -> StepResult:
    """Execute a visual step. Returns a StepResult mirroring the deterministic shape."""
    if not _driver_available():
        return StepResult(step, ok=False, failures=("cua-driver not on PATH",))

    spec = step.visual
    failures: list[str] = []
    workdir = Path(variables["workdir"])

    try:
        # Confirm the driver is healthy before driving anything.
        health = _driver_call("health_report", {})
        if health.get("overall") not in {"ok", "pass", None}:
            return StepResult(step, ok=False, failures=(f"driver unhealthy: {health}",))

        app = spec.get("launch_app")
        if app:
            # iTerm has a stable bundle id; fall back to name for anything else.
            if app.lower() in {"iterm", "iterm2"}:
                payload = {"bundle_id": "com.googlecode.iterm2"}
            else:
                payload = {"name": app}
            _driver_call("launch_app", payload)

        # Render visible text in the terminal so there is something to measure.
        typed = spec.get("type_text")
        if typed and app:
            target = _select_window(_driver_call("list_windows", {}), app)
            if target is not None:
                _driver_call("type_text", {"pid": target["pid"], "text": typed + "\n"})

        # Stage a controlled background (delegates to term-chameleon background-html)
        background = spec.get("background")
        if background:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "term_chameleon.cli",
                    "background-html",
                    "--output-dir",
                    str(workdir / "bg"),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )

        # Apply the requested mode via OSC to the live session (universal path).
        preset = spec.get("apply")
        if preset:
            subprocess.run(
                [sys.executable, "-m", "term_chameleon.cli", "osc", "apply", preset],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=15,
            )

        # Let the terminal render before capturing.
        if spec.get("type_text"):
            time.sleep(1.5)

        # Capture the target window and assert readability.
        threshold = spec.get("assert_contrast_at_least")
        if threshold is not None:
            target = _select_window(_driver_call("list_windows", {}), app)
            if target is None:
                failures.append(f"no on-screen window found for app {app!r}")
            else:
                state = _driver_call(
                    "get_window_state",
                    {
                        "pid": target["pid"],
                        "window_id": target["window_id"],
                        "capture_mode": "vision",
                    },
                )
                capture = _write_capture(state, workdir)
                if capture is None:
                    failures.append("driver returned no screenshot to analyze")
                else:
                    ratio = _measure_capture_contrast(capture, workdir)
                    if ratio < float(threshold):
                        failures.append(f"captured contrast {ratio:.2f} < required {threshold}")
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        failures.append(f"visual step error: {exc}")

    return StepResult(step, ok=not failures, failures=tuple(failures))
