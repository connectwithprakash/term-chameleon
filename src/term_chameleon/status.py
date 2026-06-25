from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .diagnostics import diagnose
from .install import DEFAULT_DYNAMIC_PROFILES_DIR
from .iterm_api import check_environment
from .iterm_connection import probe_iterm_connection
from .iterm_profile import load_profile
from .iterm_window import get_iterm_window_bounds
from .screenshot import probe_screenshot

DEFAULT_PROFILE_PATH = DEFAULT_DYNAMIC_PROFILES_DIR / "term-chameleon-adaptive-glass.json"


@dataclass(frozen=True)
class StatusCheck:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class StatusReport:
    version: str
    profile_path: str
    profile_installed: bool
    profile_name: str | None
    checks: list[StatusCheck]
    recommended_next_command: str

    @property
    def ready_for_live(self) -> bool:
        required = {
            "profile",
            "screencapture",
            "iterm-app",
            "iterm-python-package",
            "iterm-api-connect",
            "iterm-window-bounds",
        }
        passed = {check.name for check in self.checks if check.ok}
        return required.issubset(passed)


def collect_status(*, profile_path: str | Path | None = None, live: bool = False) -> StatusReport:
    """Collect user-facing local readiness checks.

    `live=False` avoids connection probes that require a running iTerm2 Python API. Use
    `live=True` for a dogfood/setup check that actively verifies iTerm2 connectivity.
    """
    target = Path(profile_path if profile_path is not None else DEFAULT_PROFILE_PATH).expanduser()
    checks: list[StatusCheck] = []
    profile_name: str | None = None

    if target.exists():
        try:
            profile = load_profile(target)
            profile_name = profile.name
            failures = [item for item in diagnose(profile) if item.severity == "fail"]
            checks.append(
                StatusCheck(
                    "profile",
                    not failures,
                    f"installed profile {profile.name!r} at {target}"
                    if not failures
                    else f"installed profile has {len(failures)} failure-level diagnostic(s)",
                )
            )
        except Exception as exc:
            checks.append(
                StatusCheck("profile", False, f"profile exists but could not be read: {exc}")
            )
    else:
        checks.append(StatusCheck("profile", False, f"profile not installed at {target}"))

    screenshot = probe_screenshot(capture=False)
    checks.append(StatusCheck("screencapture", screenshot.available, screenshot.message))

    env = check_environment()
    checks.append(
        StatusCheck(
            "iterm-app",
            env.app_installed,
            _yes_no("iTerm2 app installed", env.app_installed),
        )
    )
    checks.append(
        StatusCheck(
            "iterm-python-package",
            env.python_package_available and not env.missing_setters,
            "iterm2 Python package available with required setters"
            if env.python_package_available and not env.missing_setters
            else _iterm_package_detail(env.python_package_available, env.missing_setters),
        )
    )

    if live:
        connection = probe_iterm_connection()
        checks.append(StatusCheck("iterm-api-connect", connection.connected, connection.message))
        try:
            bounds = get_iterm_window_bounds()
            bounds_ok = bounds.available and bounds.region is not None
            checks.append(
                StatusCheck(
                    "iterm-window-bounds",
                    bounds_ok,
                    str(bounds.region) if bounds_ok else bounds.message,
                )
            )
        except Exception as exc:
            checks.append(StatusCheck("iterm-window-bounds", False, str(exc).strip()))
    else:
        checks.append(
            StatusCheck(
                "iterm-api-connect",
                False,
                "not checked; rerun with --live to connect to the iTerm2 Python API",
            )
        )
        checks.append(
            StatusCheck(
                "iterm-window-bounds",
                False,
                "not checked; rerun with --live to read front iTerm2 window bounds",
            )
        )

    report = StatusReport(
        version=_package_version(),
        profile_path=str(target),
        profile_installed=target.exists(),
        profile_name=profile_name,
        checks=checks,
        recommended_next_command="",
    )
    return StatusReport(
        version=report.version,
        profile_path=report.profile_path,
        profile_installed=report.profile_installed,
        profile_name=report.profile_name,
        checks=report.checks,
        recommended_next_command=_recommend_next_command(report, live=live),
    )


def status_to_json(report: StatusReport) -> str:
    payload = asdict(report) | {"ready_for_live": report.ready_for_live}
    return json.dumps(payload, indent=2) + "\n"


def _package_version() -> str:
    try:
        return version("term-chameleon")
    except PackageNotFoundError:
        return "unknown"


def _yes_no(label: str, value: bool) -> str:
    return f"{label}: {'yes' if value else 'no'}"


def _iterm_package_detail(package_available: bool, missing_setters: tuple[str, ...]) -> str:
    if not package_available:
        return (
            "iterm2 Python package unavailable; install with `pip install 'term-chameleon[iterm]'`"
        )
    if missing_setters:
        return "iterm2 package is missing required setters: " + ", ".join(missing_setters)
    return "iterm2 Python package available"


def _recommend_next_command(report: StatusReport, *, live: bool) -> str:
    by_name = {check.name: check for check in report.checks}
    if not by_name["profile"].ok:
        return 'term-chameleon install --name "Adaptive Glass Alpha"'
    if not by_name["iterm-python-package"].ok:
        return "pip install 'term-chameleon[iterm]'"
    if not live:
        return "term-chameleon status --live"
    if report.ready_for_live:
        return "term-chameleon live-stage --yes --capture --output-dir artifacts/live-stage"
    if not by_name["iterm-api-connect"].ok:
        return "Enable iTerm2 Python API, then run: term-chameleon status --live"
    if not by_name["iterm-window-bounds"].ok:
        return "Grant Accessibility permission, then run: term-chameleon status --live"
    return "term-chameleon check --output-dir artifacts/check"
