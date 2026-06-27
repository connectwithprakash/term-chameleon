from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .adapt import (
    adapt_profile_from_image,
    adapt_profile_from_screen,
    decide_from_image,
    decide_from_screen,
    resolve_region,
)
from .background_html import open_file, write_background_html
from .config import (
    DEFAULT_CONFIG_PATH,
    EXAMPLE_CONFIG,
    ConfigError,
    bool_value,
    float_value,
    int_value,
    load_config,
    merged_section,
    path_value,
    str_value,
    validate_config,
    value,
)
from .deterministic_check import run_deterministic_check
from .diagnostics import diagnose
from .e2e_stage import run_e2e_stage
from .fixes import fix_file
from .images import Region
from .install import (
    DEFAULT_AUTOLAUNCH_DIR,
    DEFAULT_DYNAMIC_PROFILES_DIR,
    install_autolaunch_script,
    install_profile,
)
from .iterm_api import (
    check_environment,
    live_adapter_script,
    live_adapter_setters,
    write_live_adapter_script,
)
from .iterm_connection import probe_iterm_connection
from .iterm_profile import load_profile, loads_document
from .iterm_window import get_iterm_window_bounds
from .live_stage import run_live_stage
from .modes import apply_mode
from .osc import reset_sequences, sequences_for_preset, shell_printf
from .pixel_contrast import write_contrast_report
from .presets import PRESETS
from .release_check import run_release_check
from .screenshot import probe_screenshot
from .screenshot_test import run_screenshot_test
from .setup import run_setup
from .status import collect_status, status_to_json
from .terminal_pattern import write_pattern_bundle
from .text_contrast import write_text_contrast_report
from .visual import write_visual_report
from .watch import ModeSelector, Sample
from .watch_daemon import (
    DEFAULT_LOG_PATH,
    DEFAULT_PID_PATH,
    get_watch_daemon_status,
    install_watch_autolaunch_script,
    shell_command,
    uninstall_watch_autolaunch_script,
    watch_live_command,
)
from .watch_live import WatchLiveConfig, run_watch_live


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="term-chameleon")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Diagnose an iTerm2 Dynamic Profile JSON file")
    doctor.add_argument("profile", type=Path)
    doctor.add_argument("--json", action="store_true", help="Emit machine-readable diagnostics")

    fix = sub.add_parser("fix", help="Apply conservative readability fixes to an iTerm2 profile")
    fix.add_argument("profile", type=Path)
    fix.add_argument("--dry-run", action="store_true", help="Show planned changes without writing")
    fix.add_argument("--yes", action="store_true", help="Write changes after creating a backup")

    install = sub.add_parser("install", help="Install a generated iTerm2 Dynamic Profile preset")
    install.add_argument("--preset", choices=sorted(PRESETS), default="balanced")
    install.add_argument("--name", default="Adaptive Glass")
    install.add_argument("--target-dir", type=Path, default=DEFAULT_DYNAMIC_PROFILES_DIR)
    install.add_argument("--autolaunch-dir", type=Path, default=DEFAULT_AUTOLAUNCH_DIR)
    install.add_argument("--make-default", action="store_true")
    install.add_argument("--dry-run", action="store_true")

    install_watch = sub.add_parser(
        "install-watch-daemon",
        help="Install an iTerm2 AutoLaunch script that starts watch-live",
    )
    install_watch.add_argument("--config", type=Path, help="TOML config file")
    install_watch.add_argument("--autolaunch-dir", type=Path, default=None)
    install_watch.add_argument("--python", dest="python_executable", default=None)
    install_watch.add_argument("--interval", type=float, default=None)
    install_watch.add_argument("--stable", type=int, default=None)
    install_watch.add_argument("--cooldown", type=float, default=None)
    install_watch.add_argument(
        "--output-dir",
        type=Path,
        default=None,
    )
    install_watch.add_argument("--initial-mode", choices=sorted(PRESETS), default=None)
    daemon_region = install_watch.add_mutually_exclusive_group()
    daemon_region.add_argument("--region", help="Screen region as x,y,width,height")
    daemon_region.add_argument(
        "--iterm-window",
        action="store_true",
        help="Sample the front iTerm2 window instead of the whole screen",
    )
    daemon_region.add_argument(
        "--whole-screen",
        action="store_true",
        help="Sample the whole screen instead of the iTerm window",
    )
    install_watch.add_argument("--log-path", type=Path, default=None)
    install_watch.add_argument("--pid-path", type=Path, default=None)
    install_watch.add_argument("--dry-run", action="store_true")

    watch_daemon_status = sub.add_parser(
        "watch-daemon-status",
        help="Inspect the iTerm2 AutoLaunch watch daemon script, log, and pid",
    )
    watch_daemon_status.add_argument("--config", type=Path, help="TOML config file")
    watch_daemon_status.add_argument("--autolaunch-dir", type=Path, default=None)
    watch_daemon_status.add_argument("--log-path", type=Path, default=None)
    watch_daemon_status.add_argument("--pid-path", type=Path, default=None)
    watch_daemon_status.add_argument("--json", action="store_true")

    uninstall_watch = sub.add_parser(
        "uninstall-watch-daemon",
        help="Remove the Term Chameleon iTerm2 AutoLaunch watch daemon script",
    )
    uninstall_watch.add_argument("--config", type=Path, help="TOML config file")
    uninstall_watch.add_argument("--autolaunch-dir", type=Path, default=None)
    uninstall_watch.add_argument("--dry-run", action="store_true")
    uninstall_watch.add_argument("--no-backup", action="store_true")

    mode = sub.add_parser("mode", help="Apply a readability mode/preset to a profile JSON file")
    mode.add_argument("preset", choices=sorted(PRESETS))
    mode.add_argument("profile", type=Path)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--yes", action="store_true")

    osc = sub.add_parser("osc", help="Print OSC color sequences for a preset")
    osc.add_argument("action", choices=["apply", "reset"])
    osc.add_argument("preset", nargs="?", choices=sorted(PRESETS), default="balanced")
    osc.add_argument("--tmux", action="store_true")
    osc.add_argument("--shell", action="store_true", help="Print shell-safe printf command")

    visual = sub.add_parser("visual-test", help="Run deterministic visual contrast simulation")
    visual.add_argument("profile", type=Path)
    visual.add_argument("--output-dir", type=Path, default=Path("artifacts/visual-test"))

    check = sub.add_parser(
        "check",
        help="Run permission-free deterministic self-checks and write a report",
    )
    check.add_argument("--output-dir", type=Path, default=Path("artifacts/check"))
    check.add_argument("--width", type=int, default=96)
    check.add_argument("--height", type=int, default=48)

    release_check = sub.add_parser(
        "release-check",
        help="Run the top-level release-readiness gate and write a report",
    )
    release_check.add_argument("--output-dir", type=Path, default=Path("artifacts/release-check"))
    release_check.add_argument("--config", type=Path, help="Optional TOML config file to validate")
    release_check.add_argument("--profile", type=Path, help="Dynamic Profile JSON path to inspect")
    release_check.add_argument("--width", type=int, default=64)
    release_check.add_argument("--height", type=int, default=32)
    release_check.add_argument(
        "--live", action="store_true", help="Include live iTerm2 readiness probes"
    )
    release_check.add_argument(
        "--daemon", action="store_true", help="Require watch daemon AutoLaunch health"
    )
    release_check.add_argument(
        "--live-stage",
        action="store_true",
        help="Drive Safari+iTerm2 and capture/analyze a live staged screenshot",
    )
    release_check.add_argument("--threshold", type=float, default=4.5)
    release_check.add_argument("--settle-delay", type=float, default=0.2)

    status = sub.add_parser(
        "status",
        help="Summarize local Term Chameleon/iTerm2 readiness and recommend next step",
    )
    status.add_argument("--profile", type=Path, help="Dynamic Profile JSON path to inspect")
    status.add_argument("--live", action="store_true", help="Probe live iTerm2 API/window bounds")
    status.add_argument("--json", action="store_true", help="Emit machine-readable status JSON")

    setup = sub.add_parser(
        "setup",
        help="Run guided local setup checks and optionally install the default profile",
    )
    setup.add_argument("--config", type=Path, help="TOML config file")
    setup.add_argument("--output-dir", type=Path, default=None)
    setup.add_argument("--profile", type=Path, help="Dynamic Profile JSON path to inspect/install")
    setup.add_argument("--preset", choices=sorted(PRESETS), default=None)
    setup.add_argument("--name", default=None)
    setup.add_argument("--yes", action="store_true", help="Install the generated profile if needed")
    setup.add_argument("--live", action="store_true", help="Probe live iTerm2 API/window bounds")

    config_example = sub.add_parser("config-example", help="Print an example TOML config")
    config_example.add_argument("--output", type=Path, help="Write config example to a file")

    config_check = sub.add_parser("config-check", help="Validate a Term Chameleon TOML config")
    config_check.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="TOML config file to validate",
    )
    config_check.add_argument("--json", action="store_true", help="Emit validation as JSON")

    watch_sim = sub.add_parser("watch-sim", help="Simulate dynamic mode selection from samples")
    watch_sim.add_argument(
        "samples",
        nargs="+",
        help="Samples as luminance or luminance:variance, e.g. 0.2 0.8 0.5:0.12",
    )
    watch_sim.add_argument("--stable", type=int, default=3)

    watch_live = sub.add_parser(
        "watch-live", help="Continuously sample the screen and adapt current iTerm2 session"
    )
    watch_live.add_argument("--config", type=Path, help="TOML config file")
    watch_live.add_argument("--interval", type=float, default=None)
    watch_live.add_argument("--duration", type=float, default=None)
    watch_live.add_argument("--stable", type=int, default=None)
    watch_live.add_argument("--cooldown", type=float, default=None)
    watch_live.add_argument("--output-dir", type=Path, default=None)
    watch_live.add_argument("--initial-mode", choices=sorted(PRESETS), default=None)
    region_group = watch_live.add_mutually_exclusive_group()
    region_group.add_argument("--region", help="Screen region as x,y,width,height")
    region_group.add_argument(
        "--iterm-window", action="store_true", help="Sample the front iTerm2 window bounds"
    )
    watch_live.add_argument("--dry-run", action="store_true")
    watch_live.add_argument(
        "--yes", action="store_true", help="Actually mutate the current iTerm2 session"
    )

    sub.add_parser("iterm-api-check", help="Check local iTerm2 Python API readiness")
    sub.add_parser("iterm-connect-probe", help="Attempt to connect to the live iTerm2 Python API")
    sub.add_parser(
        "iterm-window-bounds", help="Read the front iTerm2 window bounds via Accessibility"
    )

    iterm_script = sub.add_parser(
        "iterm-live-script", help="Generate a conservative iTerm2 session-local adapter script"
    )
    iterm_script.add_argument("--preset", choices=sorted(PRESETS), default="balanced")
    iterm_script.add_argument("--output", type=Path)

    screenshot = sub.add_parser("screenshot-probe", help="Check or exercise macOS screencapture")
    screenshot.add_argument("--capture", action="store_true")
    screenshot.add_argument(
        "--output", type=Path, default=Path("artifacts/screenshot-probe/screen.png")
    )

    screenshot_test = sub.add_parser(
        "screenshot-test",
        help="Generate controlled background artifacts and optionally capture a screenshot",
    )
    screenshot_test.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/screenshot-test")
    )
    screenshot_test.add_argument("--capture", action="store_true")
    screenshot_test.add_argument("--width", type=int, default=640)
    screenshot_test.add_argument("--height", type=int, default=360)

    contrast = sub.add_parser(
        "screenshot-contrast", help="Estimate foreground/background contrast from image pixels"
    )
    contrast.add_argument("image", type=Path)
    contrast.add_argument("--output-dir", type=Path, default=Path("artifacts/screenshot-contrast"))
    contrast.add_argument("--region", help="Analyze only x,y,width,height")
    contrast.add_argument("--threshold", type=float, default=4.5)
    contrast.add_argument("--percentile", type=float, default=0.10)

    text_contrast = sub.add_parser(
        "screenshot-text-contrast",
        help="Estimate text/background contrast by detecting text-like screenshot rows",
    )
    text_contrast.add_argument("image", type=Path)
    text_contrast.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/screenshot-text-contrast")
    )
    text_contrast.add_argument("--region", help="Analyze only x,y,width,height")
    text_contrast.add_argument("--threshold", type=float, default=4.5)
    text_contrast.add_argument("--min-row-delta", type=float, default=0.12)
    text_contrast.add_argument("--glyph-delta", type=float, default=0.08)

    backgrounds = sub.add_parser("background-html", help="Generate controlled HTML backgrounds")
    backgrounds.add_argument("--output-dir", type=Path, default=Path("artifacts/background-html"))
    backgrounds.add_argument("--open", action="store_true", dest="open_browser")

    pattern = sub.add_parser("pattern-script", help="Write ANSI terminal pattern artifacts")
    pattern.add_argument("--output-dir", type=Path, default=Path("artifacts/pattern-script"))

    e2e = sub.add_parser("e2e-stage", help="Run the deterministic end-to-end staging bundle")
    e2e.add_argument("profile", type=Path)
    e2e.add_argument("--output-dir", type=Path, default=Path("artifacts/e2e-stage"))
    e2e.add_argument("--capture", action="store_true")
    e2e.add_argument("--width", type=int, default=640)
    e2e.add_argument("--height", type=int, default=360)

    live_stage = sub.add_parser(
        "live-stage",
        help="Arrange controlled browser+iTerm2 windows and optionally capture/analyze",
    )
    live_stage.add_argument("--output-dir", type=Path, default=Path("artifacts/live-stage"))
    live_stage.add_argument(
        "--background",
        choices=["solid-dark", "solid-light", "mid-gray", "checkerboard", "gradient"],
        default="solid-light",
    )
    live_stage.add_argument("--browser-bounds", default="0,0,1470,956")
    live_stage.add_argument("--iterm-bounds", default="80,90,980,760")
    live_stage.add_argument("--capture", action="store_true")
    live_stage.add_argument("--threshold", type=float, default=4.5)
    live_stage.add_argument("--settle-delay", type=float, default=1.0)
    live_stage.add_argument("--dry-run", action="store_true")
    live_stage.add_argument("--yes", action="store_true", help="Actually drive Safari and iTerm2")

    sample = sub.add_parser("sample", help="Sample an image or live screen and suggest a mode")
    sample_source = sample.add_mutually_exclusive_group(required=True)
    sample_source.add_argument("--image", type=Path)
    sample_source.add_argument("--screen", action="store_true")
    sample.add_argument("--output", type=Path, default=Path("artifacts/adapt/screen.png"))
    sample_region = sample.add_mutually_exclusive_group()
    sample_region.add_argument("--region", help="Analyze only x,y,width,height")
    sample_region.add_argument(
        "--iterm-window", action="store_true", help="Analyze the front iTerm2 window bounds"
    )

    adapt = sub.add_parser(
        "adapt-once", help="Sample image/screen and apply suggested mode to a profile"
    )
    adapt.add_argument("profile", type=Path)
    adapt_source = adapt.add_mutually_exclusive_group(required=True)
    adapt_source.add_argument("--image", type=Path)
    adapt_source.add_argument("--screen", action="store_true")
    adapt.add_argument("--output", type=Path, default=Path("artifacts/adapt/screen.png"))
    adapt_region = adapt.add_mutually_exclusive_group()
    adapt_region.add_argument("--region", help="Analyze only x,y,width,height")
    adapt_region.add_argument(
        "--iterm-window", action="store_true", help="Analyze the front iTerm2 window bounds"
    )
    adapt.add_argument("--dry-run", action="store_true")
    adapt.add_argument("--yes", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            return _doctor(args.profile, json_output=args.json)
        if args.command == "fix":
            return _fix(args.profile, dry_run=args.dry_run, yes=args.yes)
        if args.command == "install":
            return _install(
                args.target_dir,
                args.autolaunch_dir,
                name=args.name,
                preset=args.preset,
                make_default=args.make_default,
                dry_run=args.dry_run,
            )
        if args.command == "install-watch-daemon":
            return _install_watch_daemon(
                autolaunch_dir=args.autolaunch_dir,
                python_executable=args.python_executable,
                interval=args.interval,
                stable=args.stable,
                cooldown=args.cooldown,
                output_dir=args.output_dir,
                initial_mode=args.initial_mode,
                region=args.region,
                iterm_window=args.iterm_window,
                whole_screen=args.whole_screen,
                log_path=args.log_path,
                pid_path=args.pid_path,
                dry_run=args.dry_run,
                config=args.config,
            )
        if args.command == "watch-daemon-status":
            return _watch_daemon_status(
                autolaunch_dir=args.autolaunch_dir,
                log_path=args.log_path,
                pid_path=args.pid_path,
                json_output=args.json,
                config=args.config,
            )
        if args.command == "uninstall-watch-daemon":
            return _uninstall_watch_daemon(
                autolaunch_dir=args.autolaunch_dir,
                dry_run=args.dry_run,
                backup=not args.no_backup,
                config=args.config,
            )
        if args.command == "mode":
            return _mode(args.profile, args.preset, dry_run=args.dry_run, yes=args.yes)
        if args.command == "osc":
            return _osc(args.action, args.preset, tmux=args.tmux, shell=args.shell)
        if args.command == "visual-test":
            return _visual_test(args.profile, args.output_dir)
        if args.command == "check":
            return _check(output_dir=args.output_dir, width=args.width, height=args.height)
        if args.command == "release-check":
            return _release_check(
                output_dir=args.output_dir,
                config=args.config,
                profile=args.profile,
                width=args.width,
                height=args.height,
                live=args.live,
                daemon=args.daemon,
                live_stage=args.live_stage,
                threshold=args.threshold,
                settle_delay=args.settle_delay,
            )
        if args.command == "status":
            return _status(profile=args.profile, live=args.live, json_output=args.json)
        if args.command == "setup":
            return _setup(
                output_dir=args.output_dir,
                profile=args.profile,
                preset=args.preset,
                name=args.name,
                yes=args.yes,
                live=args.live,
                config=args.config,
            )
        if args.command == "config-example":
            return _config_example(output=args.output)
        if args.command == "config-check":
            return _config_check(config=args.config, json_output=args.json)
        if args.command == "watch-sim":
            return _watch_sim(args.samples, stable=args.stable)
        if args.command == "watch-live":
            return _watch_live(
                interval=args.interval,
                duration=args.duration,
                stable=args.stable,
                cooldown=args.cooldown,
                output_dir=args.output_dir,
                initial_mode=args.initial_mode,
                region=args.region,
                iterm_window=args.iterm_window,
                dry_run=args.dry_run,
                yes=args.yes,
                config=args.config,
            )
        if args.command == "iterm-api-check":
            return _iterm_api_check()
        if args.command == "iterm-connect-probe":
            return _iterm_connect_probe()
        if args.command == "iterm-window-bounds":
            return _iterm_window_bounds()
        if args.command == "iterm-live-script":
            return _iterm_live_script(args.preset, output=args.output)
        if args.command == "screenshot-probe":
            return _screenshot_probe(capture=args.capture, output=args.output)
        if args.command == "screenshot-test":
            return _screenshot_test(
                output_dir=args.output_dir,
                capture=args.capture,
                width=args.width,
                height=args.height,
            )
        if args.command == "screenshot-contrast":
            return _screenshot_contrast(
                image=args.image,
                output_dir=args.output_dir,
                region=args.region,
                threshold=args.threshold,
                percentile=args.percentile,
            )
        if args.command == "screenshot-text-contrast":
            return _screenshot_text_contrast(
                image=args.image,
                output_dir=args.output_dir,
                region=args.region,
                threshold=args.threshold,
                min_row_delta=args.min_row_delta,
                glyph_delta=args.glyph_delta,
            )
        if args.command == "background-html":
            return _background_html(output_dir=args.output_dir, open_browser=args.open_browser)
        if args.command == "pattern-script":
            return _pattern_script(output_dir=args.output_dir)
        if args.command == "e2e-stage":
            return _e2e_stage(
                profile=args.profile,
                output_dir=args.output_dir,
                capture=args.capture,
                width=args.width,
                height=args.height,
            )
        if args.command == "live-stage":
            return _live_stage(
                output_dir=args.output_dir,
                background=args.background,
                browser_bounds=args.browser_bounds,
                iterm_bounds=args.iterm_bounds,
                capture=args.capture,
                threshold=args.threshold,
                settle_delay=args.settle_delay,
                dry_run=args.dry_run,
                yes=args.yes,
            )
        if args.command == "sample":
            return _sample(
                image=args.image,
                screen=args.screen,
                output=args.output,
                region=args.region,
                iterm_window=args.iterm_window,
            )
        if args.command == "adapt-once":
            return _adapt_once(
                profile=args.profile,
                image=args.image,
                screen=args.screen,
                output=args.output,
                region=args.region,
                iterm_window=args.iterm_window,
                dry_run=args.dry_run,
                yes=args.yes,
            )
    except (ValueError, OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    parser.error("unknown command")
    return 2


def _doctor(path: Path, *, json_output: bool = False) -> int:
    profile = load_profile(path)
    diagnostics = diagnose(profile)
    bg = profile.background
    fg = profile.foreground
    foreground_contrast = None
    if bg and fg:
        from .contrast import contrast_ratio

        foreground_contrast = contrast_ratio(fg, bg)
    exit_code = 1 if any(d.severity == "fail" for d in diagnostics) else 0
    if json_output:
        payload = {
            "profile": profile.name,
            "path": str(path),
            "background": bg.to_hex() if bg else None,
            "foreground": fg.to_hex() if fg else None,
            "foreground_contrast": foreground_contrast,
            "diagnostics": [asdict(d) for d in diagnostics],
            "summary": {
                "ok": len([d for d in diagnostics if d.severity == "ok"]),
                "info": len([d for d in diagnostics if d.severity == "info"]),
                "warn": len([d for d in diagnostics if d.severity == "warn"]),
                "fail": len([d for d in diagnostics if d.severity == "fail"]),
            },
            "passed": exit_code == 0,
        }
        print(json.dumps(payload, indent=2) + "\n", end="")
        return exit_code

    print(f"Profile: {profile.name}")
    if bg:
        print(f"Background: {bg.to_hex()}")
    if fg:
        print(f"Foreground: {fg.to_hex()}")
    if foreground_contrast is not None:
        from .contrast import format_ratio

        print(f"Foreground contrast: {format_ratio(foreground_contrast)}")
    print()
    if not diagnostics:
        print("[ok] no contrast/profile issues detected")
        return 0
    for d in diagnostics:
        print(f"[{d.severity}] {d.code}: {d.message}")
        print(f"  {d.detail}")
        if d.suggestion:
            print(f"  Suggestion: {d.suggestion}")
    return exit_code


def _fix(path: Path, *, dry_run: bool, yes: bool) -> int:
    if not dry_run and not yes:
        print("Refusing to write without --yes. Use --dry-run to preview.", file=sys.stderr)
        return 2
    changes, remaining = fix_file(path, dry_run=dry_run, yes=yes)
    print("Planned changes:" if dry_run else "Applied changes:")
    _print_changes(changes)
    return _print_remaining_failures(remaining, "fixed profile passes failure-level doctor checks")


def _install(
    target_dir: Path,
    autolaunch_dir: Path,
    *,
    name: str,
    preset: str,
    make_default: bool,
    dry_run: bool,
) -> int:
    target, content = install_profile(
        target_dir=target_dir,
        name=name,
        preset_name=preset,
        dry_run=dry_run,
    )
    loads_document(content, target)
    action = "Would write" if dry_run else "Wrote"
    print(f"{action}: {target}")
    print(f"Profile name: {name}")
    print(f"Preset: {preset}")
    print("[ok] generated Dynamic Profile JSON is valid")
    if make_default:
        script_target, script_content = install_autolaunch_script(
            target_dir=autolaunch_dir,
            profile_name=name,
            dry_run=dry_run,
        )
        compile(script_content, str(script_target), "exec")
        print(f"{action} AutoLaunch script: {script_target}")
        print("[ok] AutoLaunch script compiles")
    return 0


def _install_watch_daemon(
    *,
    autolaunch_dir: Path | None,
    python_executable: str | None,
    interval: float | None,
    stable: int | None,
    cooldown: float | None,
    output_dir: Path | None,
    initial_mode: str | None,
    region: str | None,
    iterm_window: bool,
    whole_screen: bool,
    log_path: Path | None,
    pid_path: Path | None,
    dry_run: bool,
    config: Path | None,
) -> int:
    cfg = load_config(config)
    daemon_cfg = merged_section(cfg, "daemon", fallback="watch")
    resolved_region = region if region is not None else str_value(value(daemon_cfg, "region"))
    if iterm_window:
        resolved_iterm_window = True
        resolved_region = None
    elif whole_screen:
        resolved_iterm_window = False
        resolved_region = None
    elif resolved_region is not None:
        resolved_iterm_window = False
    else:
        resolved_iterm_window = bool_value(value(daemon_cfg, "iterm_window"), False)
    daemon_interval = (
        interval if interval is not None else float_value(value(daemon_cfg, "interval"), 10.0)
    )
    daemon_stable = stable if stable is not None else int_value(value(daemon_cfg, "stable"), 3)
    daemon_cooldown = (
        cooldown if cooldown is not None else float_value(value(daemon_cfg, "cooldown"), 10.0)
    )
    daemon_output_dir = output_dir or path_value(
        value(daemon_cfg, "output_dir"),
        Path("~/Library/Logs/term-chameleon/watch-live-artifacts"),
    )
    daemon_initial_mode = _preset_or_error(
        initial_mode or str_value(value(daemon_cfg, "initial_mode")), "balanced"
    )
    daemon_python = python_executable or str_value(value(daemon_cfg, "python")) or sys.executable
    command = watch_live_command(
        executable=daemon_python,
        interval=daemon_interval,
        stable=daemon_stable,
        cooldown=daemon_cooldown,
        output_dir=daemon_output_dir,
        initial_mode=daemon_initial_mode,
        iterm_window=resolved_iterm_window and resolved_region is None,
        region=resolved_region,
    )
    result = install_watch_autolaunch_script(
        target_dir=autolaunch_dir
        or path_value(value(daemon_cfg, "autolaunch_dir"), DEFAULT_AUTOLAUNCH_DIR),
        command=command,
        log_path=log_path or path_value(value(daemon_cfg, "log_path"), DEFAULT_LOG_PATH),
        pid_path=pid_path or path_value(value(daemon_cfg, "pid_path"), DEFAULT_PID_PATH),
        dry_run=dry_run,
    )
    compile(result.content, str(result.target), "exec")
    action = "Would write" if dry_run else "Wrote"
    print(f"{action} watch AutoLaunch script: {result.target}")
    print(f"Command: {shell_command(result.command)}")
    print(f"Log path: {result.log_path.expanduser()}")
    print(f"PID path: {result.pid_path.expanduser()}")
    print("[ok] watch AutoLaunch script compiles")
    return 0


def _daemon_paths_from_config(
    *,
    config: Path | None,
    autolaunch_dir: Path | None,
    log_path: Path | None = None,
    pid_path: Path | None = None,
) -> tuple[Path, Path, Path]:
    cfg = load_config(config)
    daemon_cfg = merged_section(cfg, "daemon", fallback="watch")
    resolved_autolaunch = autolaunch_dir or path_value(
        value(daemon_cfg, "autolaunch_dir"), DEFAULT_AUTOLAUNCH_DIR
    )
    resolved_log = log_path or path_value(value(daemon_cfg, "log_path"), DEFAULT_LOG_PATH)
    resolved_pid = pid_path or path_value(value(daemon_cfg, "pid_path"), DEFAULT_PID_PATH)
    assert resolved_autolaunch is not None
    assert resolved_log is not None
    assert resolved_pid is not None
    return (resolved_autolaunch, resolved_log, resolved_pid)


def _watch_daemon_status(
    *,
    autolaunch_dir: Path | None,
    log_path: Path | None,
    pid_path: Path | None,
    json_output: bool,
    config: Path | None,
) -> int:
    resolved_autolaunch, resolved_log, resolved_pid = _daemon_paths_from_config(
        config=config,
        autolaunch_dir=autolaunch_dir,
        log_path=log_path,
        pid_path=pid_path,
    )
    status = get_watch_daemon_status(
        target_dir=resolved_autolaunch,
        log_path=resolved_log,
        pid_path=resolved_pid,
    )
    if json_output:
        print(json.dumps(asdict(status), indent=2, default=str))
    else:
        print(f"AutoLaunch script: {status.target}")
        print(f"Installed: {'yes' if status.installed else 'no'}")
        print(f"Executable: {'yes' if status.executable else 'no'}")
        print(f"Log path: {status.log_path} ({'exists' if status.log_exists else 'missing'})")
        print(f"PID path: {status.pid_path}")
        if status.pid is None:
            print("PID: none")
        else:
            print(f"PID: {status.pid} ({'running' if status.running else 'not running'})")
        if status.healthy:
            print("[ok] watch daemon AutoLaunch script is installed")
        else:
            print("[warn] watch daemon AutoLaunch script is not installed and executable")
    return 0 if status.healthy else 1


def _uninstall_watch_daemon(
    *,
    autolaunch_dir: Path | None,
    dry_run: bool,
    backup: bool,
    config: Path | None,
) -> int:
    resolved_autolaunch, _resolved_log, _resolved_pid = _daemon_paths_from_config(
        config=config,
        autolaunch_dir=autolaunch_dir,
    )
    result = uninstall_watch_autolaunch_script(
        target_dir=resolved_autolaunch,
        dry_run=dry_run,
        backup=backup,
    )
    if result.removed:
        action = "Would remove" if dry_run else "Removed"
        print(f"{action}: {result.target}")
        if result.backup_path is not None:
            print(f"Backup: {result.backup_path}")
        print("[ok] watch daemon AutoLaunch script removed")
        return 0
    print(f"Not installed: {result.target}")
    return 1


def _mode(path: Path, preset: str, *, dry_run: bool, yes: bool) -> int:
    if not dry_run and not yes:
        print("Refusing to write without --yes. Use --dry-run to preview.", file=sys.stderr)
        return 2
    changes, remaining = apply_mode(path, preset, dry_run=dry_run, yes=yes)
    print(("Planned" if dry_run else "Applied") + f" mode: {preset}")
    _print_changes(changes)
    return _print_remaining_failures(remaining, "mode profile passes failure-level doctor checks")


def _osc(action: str, preset: str, *, tmux: bool, shell: bool) -> int:
    sequences = reset_sequences() if action == "reset" else sequences_for_preset(preset)
    if shell:
        print(shell_printf(sequences, tmux=tmux))
    else:
        for seq in sequences:
            rendered = seq.sequence
            if tmux:
                from .osc import tmux_wrap

                rendered = tmux_wrap(rendered)
            print(f"# {seq.description}")
            print(rendered.encode("unicode_escape").decode("ascii"))
    return 0


def _visual_test(profile: Path, output_dir: Path) -> int:
    json_path, md_path, checks = write_visual_report(profile, output_dir)
    failed = [c for c in checks if not c.passed]
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    print(f"Checks: {len(checks)} total, {len(failed)} failed")
    if failed:
        for c in failed[:10]:
            print(f"[fail] {c.background}/{c.style}: {c.contrast:.2f}:1 < {c.threshold:.1f}:1")
        return 1
    print("[ok] visual contrast simulation passed")
    return 0


def _check(*, output_dir: Path, width: int, height: int) -> int:
    report = run_deterministic_check(output_dir, width=width, height=height)
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


def _release_check(
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
) -> int:
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


def _status(*, profile: Path | None, live: bool, json_output: bool) -> int:
    report = collect_status(profile_path=profile, live=live)
    if json_output:
        print(status_to_json(report), end="")
        return 0 if report.ready_for_live or not live else 1
    print(f"Term Chameleon version: {report.version}")
    print(f"Profile path: {report.profile_path}")
    if report.profile_name:
        print(f"Profile name: {report.profile_name}")
    print("")
    for check in report.checks:
        marker = "ok" if check.ok else "warn"
        print(f"[{marker}] {check.name}: {check.detail}")
    print("")
    print(f"Ready for live: {'yes' if report.ready_for_live else 'no'}")
    print(f"Recommended next command: {report.recommended_next_command}")
    return 0 if report.ready_for_live or not live else 1


def _setup(
    *,
    output_dir: Path | None,
    profile: Path | None,
    preset: str | None,
    name: str | None,
    yes: bool,
    live: bool,
    config: Path | None,
) -> int:
    cfg = load_config(config)
    setup_cfg = merged_section(cfg, "setup")
    output = output_dir or path_value(value(setup_cfg, "output_dir"), Path("artifacts/setup"))
    config_live = bool_value(value(setup_cfg, "live"), False)
    report = run_setup(
        output_dir=output,
        yes=yes,
        live=live or config_live,
        profile_path=profile or path_value(value(setup_cfg, "profile")),
        preset=preset or str_value(value(setup_cfg, "preset"), "balanced"),
        name=name or str_value(value(setup_cfg, "name"), "Adaptive Glass Alpha"),
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


def _config_example(*, output: Path | None) -> int:
    if output is None:
        print(EXAMPLE_CONFIG, end="")
    else:
        output.expanduser().parent.mkdir(parents=True, exist_ok=True)
        output.expanduser().write_text(EXAMPLE_CONFIG, encoding="utf-8")
        print(f"Wrote: {output.expanduser()}")
    return 0


def _config_check(*, config: Path, json_output: bool) -> int:
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


def _watch_sim(samples: list[str], *, stable: int) -> int:
    selector = ModeSelector(stable_samples_required=stable)
    for index, raw in enumerate(samples, start=1):
        sample = _parse_sample(raw)
        mode, classification, switched = selector.observe(sample)
        marker = "switch" if switched else "hold"
        print(
            f"{index}: luminance={sample.luminance:.2f} variance={sample.variance:.2f} "
            f"risk={classification.risk} mode={mode} {marker} reason={classification.reason}"
        )
    return 0


def _watch_live(
    *,
    interval: float | None,
    duration: float | None,
    stable: int | None,
    cooldown: float | None,
    output_dir: Path | None,
    initial_mode: str | None,
    region: str | None,
    iterm_window: bool,
    dry_run: bool,
    yes: bool,
    config: Path | None,
) -> int:
    if not dry_run and not yes:
        print("Refusing to mutate iTerm2 without --yes. Use --dry-run to preview.", file=sys.stderr)
        return 2
    cfg = load_config(config)
    watch_cfg = merged_section(cfg, "watch")
    resolved_region = region if region is not None else str_value(value(watch_cfg, "region"))
    if iterm_window:
        resolved_region = None
        resolved_iterm_window = True
    else:
        resolved_iterm_window = bool_value(value(watch_cfg, "iterm_window"), False)
        if resolved_region is not None:
            resolved_iterm_window = False
    watch_interval = (
        interval if interval is not None else float_value(value(watch_cfg, "interval"), 2.0)
    )
    watch_duration = (
        duration if duration is not None else float_value(value(watch_cfg, "duration"), 60.0)
    )
    watch_stable = stable if stable is not None else int_value(value(watch_cfg, "stable"), 3)
    watch_cooldown = (
        cooldown if cooldown is not None else float_value(value(watch_cfg, "cooldown"), 10.0)
    )
    watch_output_dir = output_dir or path_value(
        value(watch_cfg, "output_dir"), Path("artifacts/watch-live")
    )
    watch_initial_mode = _preset_or_error(
        initial_mode or str_value(value(watch_cfg, "initial_mode")), "balanced"
    )
    config_obj = WatchLiveConfig(
        interval=watch_interval,
        duration=watch_duration,
        stable=watch_stable,
        cooldown=watch_cooldown,
        output_dir=watch_output_dir,
        dry_run=dry_run,
        initial_mode=watch_initial_mode,
        region=Region.parse(resolved_region) if resolved_region else None,
        iterm_window=resolved_iterm_window,
    )
    events = run_watch_live(config_obj)
    for event in events:
        marker = "switch" if event.switched else "hold"
        apply_marker = " applied" if event.applied else ""
        print(
            f"{event.index}: t={event.elapsed:.1f}s lum={event.luminance:.3f} "
            f"var={event.variance:.3f} risk={event.risk} "
            f"candidate={event.candidate_mode} mode={event.mode} {marker}{apply_marker} "
            f"reason={event.reason} message={event.message}"
        )
    print(f"[ok] watch-live completed {len(events)} sample(s)")
    return 0


def _iterm_api_check() -> int:
    env = check_environment()
    print(f"iTerm2 app installed: {'yes' if env.app_installed else 'no'}")
    print(f"iTerm2 Python package available: {'yes' if env.python_package_available else 'no'}")
    print(f"Python executable: {env.python_executable}")
    print("app paths checked:")
    for path in env.app_paths_checked:
        print(f"- {path}")
    print("required LocalWriteOnlyProfile setters:")
    for setter in live_adapter_setters():
        if not env.python_package_available:
            status = "skipped"
        else:
            status = "missing" if setter in env.missing_setters else "ok"
        print(f"- {setter}: {status}")
    if env.ready_for_live_probe:
        print("[ok] ready for live iTerm2 API probe")
        return 0
    if not env.python_package_available:
        print("[hint] install iTerm support with: uv sync --extra iterm")
    if env.missing_setters:
        print("[warn] installed iterm2 package is missing required setter(s)")
    print("[warn] live iTerm2 API probe is not ready on this Python environment")
    return 1


def _iterm_live_script(preset: str, *, output: Path | None) -> int:
    content = live_adapter_script(preset_name=preset)
    compile(content, str(output or "<term-chameleon-iterm-live-script>"), "exec")
    if output is None:
        print(content)
    else:
        target = write_live_adapter_script(output, preset_name=preset)
        print(f"Wrote: {target}")
    print("[ok] generated iTerm2 live adapter script compiles")
    return 0


def _iterm_connect_probe() -> int:
    result = probe_iterm_connection()
    print(result.message)
    if result.connected:
        print("[ok] connected to live iTerm2 Python API")
        return 0
    print("[warn] could not connect to live iTerm2 Python API")
    print("[hint] start iTerm2 and enable Preferences > General > Magic > Python API")
    return 1


def _iterm_window_bounds() -> int:
    result = get_iterm_window_bounds()
    if result.available and result.region is not None:
        print(str(result.region))
        print("[ok] read iTerm2 window bounds")
        return 0
    print(result.message)
    print("[warn] could not read iTerm2 window bounds")
    print("[hint] grant Accessibility permission or pass --region x,y,width,height")
    return 1


def _screenshot_probe(*, capture: bool, output: Path) -> int:
    result = probe_screenshot(output, capture=capture)
    print(result.message)
    if result.output_path is not None:
        print(f"output: {result.output_path}")
    if not result.available:
        return 1
    if capture and not result.captured:
        return 1
    return 0


def _screenshot_test(*, output_dir: Path, capture: bool, width: int, height: int) -> int:
    report = run_screenshot_test(output_dir, capture=capture, width=width, height=height)
    print(f"Wrote: {report.output_dir / 'report.json'}")
    print(f"Wrote: {report.output_dir / 'report.md'}")
    print(f"Backgrounds: {len(report.backgrounds)}")
    for artifact in report.backgrounds:
        print(
            f"- {artifact.name}: lum={artifact.stats.average_luminance:.3f} "
            f"var={artifact.stats.luminance_variance:.3f} "
            f"risk={artifact.risk} mode={artifact.suggested_mode}"
        )
    if report.screenshot is not None:
        print(report.screenshot.message)
        if report.screenshot_stats is not None:
            print(
                f"Screenshot stats: lum={report.screenshot_stats.average_luminance:.3f} "
                f"var={report.screenshot_stats.luminance_variance:.3f}"
            )
        if not report.screenshot.captured:
            return 1
    print("[ok] screenshot-test foundation passed")
    return 0


def _screenshot_contrast(
    *, image: Path, output_dir: Path, region: str | None, threshold: float, percentile: float
) -> int:
    json_path, md_path, estimate = write_contrast_report(
        image,
        output_dir,
        region=Region.parse(region) if region else None,
        threshold=threshold,
        percentile=percentile,
    )
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    print(f"Dark cluster: {estimate.dark_color}")
    print(f"Light cluster: {estimate.light_color}")
    print(f"Estimated contrast: {estimate.contrast:.2f}:1")
    print("[ok] screenshot contrast estimate passed" if estimate.passed else "[fail] low contrast")
    return 0 if estimate.passed else 1


def _screenshot_text_contrast(
    *,
    image: Path,
    output_dir: Path,
    region: str | None,
    threshold: float,
    min_row_delta: float,
    glyph_delta: float,
) -> int:
    json_path, md_path, estimate = write_text_contrast_report(
        image,
        output_dir,
        region=Region.parse(region) if region else None,
        threshold=threshold,
        min_row_delta=min_row_delta,
        glyph_delta=glyph_delta,
    )
    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    print(f"Detected row bands: {len(estimate.bands)}")
    print(f"Foreground estimate: {estimate.foreground_color}")
    print(f"Background estimate: {estimate.background_color}")
    print(f"Estimated contrast: {estimate.contrast:.2f}:1")
    print("[ok] text contrast estimate passed" if estimate.passed else "[fail] low text contrast")
    return 0 if estimate.passed else 1


def _background_html(*, output_dir: Path, open_browser: bool) -> int:
    artifacts = write_background_html(output_dir)
    for artifact in artifacts:
        print(f"Wrote: {artifact.path}")
    if open_browser:
        index = next(artifact.path for artifact in artifacts if artifact.name == "index")
        completed = open_file(index)
        if completed.returncode != 0:
            message = completed.stderr or completed.stdout or "open failed"
            print(f"error: {message.strip()}", file=sys.stderr)
            return 1
        print(f"Opened: {index}")
    print("[ok] generated controlled HTML backgrounds")
    return 0


def _pattern_script(*, output_dir: Path) -> int:
    pattern, script = write_pattern_bundle(output_dir)
    print(f"Wrote: {pattern}")
    print(f"Wrote: {script}")
    print("[ok] generated ANSI terminal pattern artifacts")
    return 0


def _e2e_stage(*, profile: Path, output_dir: Path, capture: bool, width: int, height: int) -> int:
    report = run_e2e_stage(profile, output_dir, capture=capture, width=width, height=height)
    print(f"Wrote: {report.output_dir / 'e2e-stage-report.json'}")
    print(f"Wrote: {report.output_dir / 'e2e-stage-report.md'}")
    print(f"Background files: {len(report.background_files)}")
    print(f"Pattern files: {len(report.pattern_files)}")
    print(f"Visual report: {report.visual_report_json}")
    print(f"Screenshot report: {report.screenshot_report_json}")
    print(f"Screenshot captured: {report.screenshot_captured}")
    print("[ok] e2e staging bundle passed")
    return 0


def _live_stage(
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


def _sample(
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
        else decide_from_image(_require_path(image), region=resolved_region)
    )
    _print_decision(decision)
    return 0


def _adapt_once(
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
            _require_path(image), profile, region=resolved_region, dry_run=dry_run, yes=yes
        )
    )
    _print_decision(decision)
    if decision.mode_result is not None:
        changes, remaining = decision.mode_result
        print("Planned changes:" if dry_run else "Applied changes:")
        _print_changes(changes)
        return _print_remaining_failures(remaining, "adapted profile passes failure-level checks")
    return 0


def _print_decision(decision) -> None:
    print(f"Source: {decision.source}")
    if getattr(decision, "region", None) is not None:
        print(f"Region: {decision.region}")
    print(f"Average luminance: {decision.average_luminance:.3f}")
    print(f"Luminance variance: {decision.luminance_variance:.3f}")
    print(f"Risk: {decision.risk}")
    print(f"Suggested mode: {decision.suggested_mode}")
    print(f"Reason: {decision.reason}")


def _require_path(path: Path | None) -> Path:
    if path is None:
        raise ValueError("image path is required")
    return path


def _preset_or_error(value: str | None, default: str) -> str:
    resolved = value or default
    if resolved not in PRESETS:
        raise ConfigError(f"unknown preset/mode in config: {resolved!r}")
    return resolved


def _parse_sample(raw: str) -> Sample:
    if ":" in raw:
        luminance, variance = raw.split(":", 1)
        return Sample(float(luminance), float(variance))
    return Sample(float(raw), 0.0)


def _print_changes(changes) -> None:
    if not changes:
        print("  none")
    for c in changes:
        print(f"- {c.key}: {c.before} -> {c.after}")
        reason = getattr(c, "reason", None)
        if reason:
            print(f"  reason: {reason}")


def _print_remaining_failures(remaining, ok_message: str) -> int:
    blocking = [d for d in remaining if d.severity == "fail"]
    if blocking:
        print("\nRemaining failures after proposal:")
        for d in blocking:
            print(f"- {d.code}: {d.message}")
        return 1
    print(f"\n[ok] {ok_message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
