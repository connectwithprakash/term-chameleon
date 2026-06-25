from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .deterministic_check import DeterministicCheckReport, run_deterministic_check
from .install import install_profile
from .presets import PRESETS
from .status import DEFAULT_PROFILE_PATH, StatusReport, collect_status


@dataclass(frozen=True)
class SetupReport:
    check_report: DeterministicCheckReport
    status_before: StatusReport
    status_after: StatusReport
    installed_profile: bool
    installed_profile_path: str | None
    next_command: str

    @property
    def passed(self) -> bool:
        profile_ready = _check_by_name(self.status_after, "profile")
        if not self.check_report.passed or not profile_ready:
            return False
        if _live_checks_requested(self.status_after):
            return self.status_after.ready_for_live
        return True


def run_setup(
    *,
    output_dir: str | Path,
    yes: bool = False,
    live: bool = False,
    profile_path: str | Path | None = None,
    preset: str = "balanced",
    name: str = "Adaptive Glass Alpha",
) -> SetupReport:
    """Run the guided local setup flow.

    The flow is intentionally conservative: it always runs the deterministic self-check,
    but only writes the iTerm2 Dynamic Profile when `yes=True` and the default/selected
    profile is missing or failing diagnostics.
    """
    if preset not in PRESETS:
        raise ValueError(f"unknown preset: {preset}")

    target = Path(profile_path).expanduser() if profile_path is not None else DEFAULT_PROFILE_PATH
    check_report = run_deterministic_check(output_dir)
    status_before = collect_status(profile_path=target, live=False)
    before_profile_ok = _check_by_name(status_before, "profile")

    installed_profile = False
    installed_profile_path: str | None = None
    if yes and not before_profile_ok:
        installed_path, _content = install_profile(
            target_dir=target.parent,
            name=name,
            preset_name=preset,
            filename=target.name,
            dry_run=False,
        )
        installed_profile = True
        installed_profile_path = str(installed_path)
        target = installed_path

    status_after = collect_status(profile_path=target, live=live)
    return SetupReport(
        check_report=check_report,
        status_before=status_before,
        status_after=status_after,
        installed_profile=installed_profile,
        installed_profile_path=installed_profile_path,
        next_command=_setup_next_command(status_after, yes=yes, live=live),
    )


def _check_by_name(report: StatusReport, name: str) -> bool:
    return any(check.name == name and check.ok for check in report.checks)


def _live_checks_requested(report: StatusReport) -> bool:
    live_checks = {"iterm-api-connect", "iterm-window-bounds"}
    return all(
        any(
            check.name == name and not check.detail.startswith("not checked;")
            for check in report.checks
        )
        for name in live_checks
    )


def _setup_next_command(report: StatusReport, *, yes: bool, live: bool) -> str:
    if not _check_by_name(report, "profile") and not yes:
        return "term-chameleon setup --yes"
    if not live:
        return "term-chameleon setup --live"
    return report.recommended_next_command
