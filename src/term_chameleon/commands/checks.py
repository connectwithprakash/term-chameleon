from __future__ import annotations

import json
import sys
from pathlib import Path

from ..adapt import (
    adapt_profile_from_image,
    adapt_profile_from_screen,
    decide_from_image,
    decide_from_screen,
    resolve_region,
)
from ..config import (
    EXAMPLE_CONFIG,
    bool_value,
    load_config,
    merged_section,
    path_value,
    str_value,
    validate_config,
    value,
)
from ..e2e_stage import run_e2e_stage
from ..images import Region
from ..live_stage import run_live_stage
from ..release_check import run_release_check
from ..status import collect_status, status_to_json
from .shared import (
    print_changes,
    print_decision,
    print_remaining_failures,
    require_path,
)


def check(*, output_dir: Path, width: int, height: int) -> int:
    from .. import cli

    report = cli.run_deterministic_check(output_dir, width=width, height=height)
    json_path = output_dir / "deterministic-check-report.json"
    md_path = output_dir / "deterministic-check-report.md"
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    for step in report.steps:
        marker = "ok" if step.passed else "fail"
        print(f"[{marker}] {step.name}: {step.detail}")
    if not report.passed:
        return 1
    print("[ok] deterministic self-check passed")
    return 0


def release_check(
    *,
    output_dir: Path,
    config: Path | None,
    profile: Path | None,
    width: int,
    height: int,
    live: bool,
    daemon: bool,
    live_stage: bool,
    threshold: float,
    settle_delay: float,
    yes: bool = False,
) -> int:
    if live_stage and not yes:
        print(
            "Refusing to drive GUI apps without --yes. Use --dry-run to preview.", file=sys.stderr
        )
        return 2
    report = run_release_check(
        output_dir=output_dir,
        config_path=config,
        profile_path=profile,
        live=live,
        live_stage=live_stage,
        daemon=daemon,
        width=width,
        height=height,
        live_stage_threshold=threshold,
        live_stage_settle_delay=settle_delay,
    )
    json_path = output_dir / "release-check-report.json"
    md_path = output_dir / "release-check-report.md"
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    for step in report.steps:
        marker = "ok" if step.passed else "fail"
        print(f"[{marker}] {step.name}: {step.detail}")
    if report.passed:
        print("[ok] release check passed")
        return 0
    print("[fail] release check failed")
    return 1


def status(*, profile: Path | None, live: bool, json_output: bool) -> int:
    report = collect_status(profile_path=profile, live=live)
    if json_output:
        print(status_to_json(report), end="")
        return 0 if report.ready_for_live or not live else 1
    print(f"Term Chameleon version: {report.version}")
    print(f"Profile path: {report.profile_path}")
    if report.profile_name:
        print(f"Profile name: {report.profile_name}")
    print("")
    for check_item in report.checks:
        marker = "ok" if check_item.ok else "warn"
        print(f"[{marker}] {check_item.name}: {check_item.detail}")
    print("")
    print(f"Ready for live: {'yes' if report.ready_for_live else 'no'}")
    print(f"Recommended next command: {report.recommended_next_command}")
    return 0 if report.ready_for_live or not live else 1


def setup(
    *,
    output_dir: Path | None,
    profile: Path | None,
    preset: str | None,
    name: str | None,
    yes: bool,
    live: bool | None,
    config: Path | None,
) -> int:
    from .. import cli

    cfg = load_config(config)
    setup_cfg = merged_section(cfg, "setup")
    output = output_dir or path_value(value(setup_cfg, "output_dir"), Path("artifacts/setup"))
    config_live = bool_value(value(setup_cfg, "live"), False)
    # Explicit CLI flag (True or False) overrides config; None means unspecified -> use config.
    resolved_live = config_live if live is None else live
    report = cli.run_setup(
        output_dir=output,
        yes=yes,
        live=resolved_live,
        profile_path=profile or path_value(value(setup_cfg, "profile")),
        preset=preset or str_value(value(setup_cfg, "preset"), "balanced"),
        # Explicit None check: an empty string --name '' must not fall back to config/default.
        name=(
            name
            if name is not None
            else str_value(value(setup_cfg, "name"), "Adaptive Glass Alpha")
        ),
    )
    print(f"Wrote: {output / 'deterministic-check-report.json'}")
    print(f"Wrote: {output / 'deterministic-check-report.md'}")
    for step in report.check_report.steps:
        marker = "ok" if step.passed else "fail"
        print(f"[{marker}] check/{step.name}: {step.detail}")
    if report.installed_profile:
        print(f"[ok] installed profile: {report.installed_profile_path}")
    elif not any(check.name == "profile" and check.ok for check in report.status_after.checks):
        print("[warn] profile not installed or not healthy; rerun with --yes to install")
    print("")
    for check in report.status_after.checks:
        marker = "ok" if check.ok else "warn"
        print(f"[{marker}] status/{check.name}: {check.detail}")
    print("")
    print(f"Ready for live: {'yes' if report.status_after.ready_for_live else 'no'}")
    print(f"Recommended next command: {report.next_command}")
    return 0 if report.passed else 1


def config_example(*, output: Path | None) -> int:
    if output is None:
        print(EXAMPLE_CONFIG, end="")
    else:
        output.expanduser().parent.mkdir(parents=True, exist_ok=True)
        output.expanduser().write_text(EXAMPLE_CONFIG, encoding="utf-8")
        print(f"Wrote: {output.expanduser()}")
    return 0


def config_check(*, config: Path, json_output: bool) -> int:
    loaded = load_config(config)
    validation = validate_config(loaded, path=config)
    if json_output:
        print(json.dumps(validation.as_dict(), indent=2))
    else:
        print(f"Config: {Path(config).expanduser()}")
        print(f"Sections: {', '.join(validation.sections) if validation.sections else '(none)'}")
        for warning in validation.warnings:
            print(f"[warn] {warning}")
        for error in validation.errors:
            print(f"[fail] {error}")
        if validation.passed:
            print("[ok] config is valid")
        else:
            print("[fail] config has validation errors")
    return 0 if validation.passed else 1


def e2e_stage(*, profile: Path, output_dir: Path, capture: bool, width: int, height: int) -> int:
    report = run_e2e_stage(profile, output_dir, capture=capture, width=width, height=height)
    print(f"Wrote: {report.output_dir / 'e2e-stage-report.json'}")
    print(f"Wrote: {report.output_dir / 'e2e-stage-report.md'}")
    print(f"Background files: {len(report.background_files)}")
    print(f"Pattern files: {len(report.pattern_files)}")
    print(f"Visual report: {report.visual_report_json}")
    print(f"Screenshot report: {report.screenshot_report_json}")
    print(f"Screenshot captured: {report.screenshot_captured}")
    visual_status = (
        "passed"
        if report.visual_checks_passed
        else f"FAILED ({report.visual_checks_failed} failed)"
    )
    print(f"Visual checks: {visual_status}")
    if not report.visual_checks_passed:
        print("[fail] e2e stage visual checks failed", file=sys.stderr)
        return 1
    if capture and report.screenshot_captured is False:
        print("[fail] e2e stage screenshot capture failed", file=sys.stderr)
        return 1
    print("[ok] e2e staging bundle passed")
    return 0


def live_stage(
    *,
    output_dir: Path,
    background: str,
    browser_bounds: str,
    iterm_bounds: str,
    capture: bool,
    threshold: float,
    settle_delay: float,
    dry_run: bool,
    yes: bool,
) -> int:
    if not dry_run and not yes:
        print(
            "Refusing to drive GUI apps without --yes. Use --dry-run to preview.", file=sys.stderr
        )
        return 2
    report = run_live_stage(
        output_dir,
        background=background,
        browser_bounds=browser_bounds,
        iterm_bounds=iterm_bounds,
        dry_run=dry_run,
        capture=capture,
        threshold=threshold,
        settle_delay=settle_delay,
    )
    print(f"Wrote: {report.output_dir / 'live-stage-report.json'}")
    print(f"Wrote: {report.output_dir / 'live-stage-report.md'}")
    print(f"Background: {report.background_file}")
    print(f"Pattern script: {report.pattern_script}")
    print(f"Browser return code: {report.browser_returncode}")
    print(f"iTerm2 return code: {report.iterm_returncode}")
    if report.screenshot_path:
        print(f"Screenshot: {report.screenshot_path}")
        print(f"Screenshot captured: {report.screenshot_captured}")
    if report.iterm_region:
        print(f"iTerm2 region: {report.iterm_region}")
    if report.suggested_mode:
        print(f"Suggested mode: {report.suggested_mode}")
    if report.estimated_contrast is not None:
        method = f" ({report.contrast_method})" if report.contrast_method else ""
        print(f"Estimated contrast: {report.estimated_contrast:.2f}:1{method}")
    if not dry_run:
        if report.browser_returncode != 0 or report.iterm_returncode != 0:
            return 1
        if capture and not report.screenshot_captured:
            return 1
        if capture and report.contrast_passed is False:
            return 1
    print("[ok] live stage completed")
    return 0


def sample(
    *,
    image: Path | None,
    screen: bool,
    output: Path,
    region: str | None,
    iterm_window: bool,
) -> int:
    if iterm_window and not screen:
        raise ValueError("--iterm-window requires --screen; use --region for image files")
    resolved_region = resolve_region(
        Region.parse(region) if region else None, iterm_window=iterm_window
    )
    decision = (
        decide_from_screen(output, region=resolved_region)
        if screen
        else decide_from_image(require_path(image), region=resolved_region)
    )
    print_decision(decision)
    return 0


def adapt_once(
    *,
    profile: Path,
    image: Path | None,
    screen: bool,
    output: Path,
    region: str | None,
    iterm_window: bool,
    dry_run: bool,
    yes: bool,
) -> int:
    if not dry_run and not yes:
        print("Refusing to write without --yes. Use --dry-run to preview.", file=sys.stderr)
        return 2
    if iterm_window and not screen:
        raise ValueError("--iterm-window requires --screen; use --region for image files")
    resolved_region = resolve_region(
        Region.parse(region) if region else None, iterm_window=iterm_window
    )
    decision = (
        adapt_profile_from_screen(profile, output, region=resolved_region, dry_run=dry_run, yes=yes)
        if screen
        else adapt_profile_from_image(
            require_path(image), profile, region=resolved_region, dry_run=dry_run, yes=yes
        )
    )
    print_decision(decision)
    if decision.mode_result is not None:
        changes, remaining = decision.mode_result
        print("Planned changes:" if dry_run else "Applied changes:")
        print_changes(changes)
        return print_remaining_failures(remaining, "adapted profile passes failure-level checks")
    return 0
