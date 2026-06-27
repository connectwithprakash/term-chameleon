"""Load and execute term-chameleon user-flow specs.

A flow is a TOML file describing a user journey as a sequence of CLI invocations
with expectations. The runner executes the real CLI in a subprocess and checks
exit codes, stdout/stderr, and generated artifacts. Visual steps are described
here but executed by the Cua Driver layer in ``conftest.py``.

This module has no third-party dependencies (tomllib is stdlib on 3.11+).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SPECS_DIR = Path(__file__).resolve().parent / "specs"


def detect_capabilities() -> set[str]:
    """Return the set of capability tags available in this environment."""
    caps: set[str] = set()
    if sys.platform == "darwin":
        caps.add("macos")
        if shutil.which("cua-driver"):
            caps.add("cua")
        if shutil.which("osascript"):
            caps.add("iterm2-capable")
    return caps

# An uncaught Python exception is never an acceptable user-facing outcome.
TRACEBACK_MARKER = "Traceback (most recent call last)"

DEFAULT_STEP_TIMEOUT = 60


@dataclass(frozen=True)
class Step:
    run: str | None
    name: str = ""
    expect_exit: tuple[int, ...] = (0,)
    expect_stdout_contains: tuple[str, ...] = ()
    expect_stdout_not_contains: tuple[str, ...] = ()
    expect_stderr_contains: tuple[str, ...] = ()
    expect_artifact: tuple[str, ...] = ()
    timeout: int = DEFAULT_STEP_TIMEOUT
    visual: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Flow:
    name: str
    description: str
    layer: str
    requires: tuple[str, ...]
    vars: dict
    steps: tuple[Step, ...]
    path: Path


@dataclass(frozen=True)
class StepResult:
    step: Step
    ok: bool
    failures: tuple[str, ...]
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""


def _as_tuple(value) -> tuple:
    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return (value,)


def _parse_step(raw: dict) -> Step:
    expect_exit = raw.get("expect_exit", 0)
    exits = tuple(expect_exit) if isinstance(expect_exit, (list, tuple)) else (expect_exit,)
    return Step(
        run=raw.get("run"),
        name=raw.get("name", ""),
        expect_exit=exits,
        expect_stdout_contains=_as_tuple(raw.get("expect_stdout_contains")),
        expect_stdout_not_contains=_as_tuple(raw.get("expect_stdout_not_contains")),
        expect_stderr_contains=_as_tuple(raw.get("expect_stderr_contains")),
        expect_artifact=_as_tuple(raw.get("expect_artifact")),
        timeout=int(raw.get("timeout", DEFAULT_STEP_TIMEOUT)),
        visual=raw.get("visual", {}) or {},
    )


def load_flow(path: Path) -> Flow:
    with path.open("rb") as handle:
        data = tomllib.load(handle)

    name = data.get("name")
    if not name:
        raise ValueError(f"flow spec {path} is missing required 'name'")

    steps = tuple(_parse_step(s) for s in data.get("steps", []))
    if not steps:
        raise ValueError(f"flow spec {path} has no steps")

    return Flow(
        name=name,
        description=(data.get("description") or "").strip(),
        layer=data.get("layer", "deterministic"),
        requires=_as_tuple(data.get("requires")),
        vars=data.get("vars", {}) or {},
        steps=steps,
        path=path,
    )


def discover_flows() -> list[Flow]:
    return [load_flow(p) for p in sorted(SPECS_DIR.glob("*.toml"))]


def _interpolate(text: str, variables: dict) -> str:
    out = text
    for key, value in variables.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def run_deterministic_step(step: Step, variables: dict) -> StepResult:
    """Execute one CLI step in a subprocess and check all expectations."""
    if step.run is None:
        return StepResult(step, ok=True, failures=())  # visual-only step, handled elsewhere

    command = _interpolate(step.run, variables)
    argv = [sys.executable, "-m", "term_chameleon.cli", *command.split()]

    try:
        proc = subprocess.run(
            argv,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=step.timeout,
        )
    except subprocess.TimeoutExpired:
        return StepResult(
            step,
            ok=False,
            failures=(f"step timed out after {step.timeout}s: {command}",),
        )

    failures: list[str] = []

    if proc.returncode not in step.expect_exit:
        failures.append(
            f"exit code {proc.returncode} not in expected {step.expect_exit} (cmd: {command})"
        )

    combined = proc.stdout + proc.stderr
    if TRACEBACK_MARKER in combined:
        failures.append(f"uncaught traceback in output (cmd: {command})")

    for needle in step.expect_stdout_contains:
        if needle not in proc.stdout:
            failures.append(f"stdout missing {needle!r}")

    for needle in step.expect_stdout_not_contains:
        if needle in proc.stdout:
            failures.append(f"stdout unexpectedly contains {needle!r}")

    for needle in step.expect_stderr_contains:
        if needle not in proc.stderr:
            failures.append(f"stderr missing {needle!r}")

    for artifact in step.expect_artifact:
        resolved = Path(_interpolate(artifact, variables))
        if not resolved.is_absolute():
            resolved = REPO_ROOT / resolved
        if not resolved.exists():
            failures.append(f"expected artifact missing: {resolved}")

    return StepResult(
        step,
        ok=not failures,
        failures=tuple(failures),
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )
