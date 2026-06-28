from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .commands import checks, demo, imaging, live, profile, watch
from .commands.watch import watch_live as _watch_live
from .config import DEFAULT_CONFIG_PATH
from .install import (
    DEFAULT_APP_STATE_DIR,
    DEFAULT_AUTOLAUNCH_DIR,
    DEFAULT_DYNAMIC_PROFILES_DIR,
)
from .iterm_api import check_environment
from .iterm_connection import probe_iterm_connection
from .iterm_window import get_iterm_window_bounds
from .presets import PRESETS
from .release_check import run_deterministic_check
from .setup import run_setup
from .watch_live import run_watch_live

__all__ = ["main"]

# Names re-exported here are looked up through this module by their command handlers
# and patched in tests, so they must remain attributes of term_chameleon.cli.
_REEXPORTED = (
    _watch_live,
    check_environment,
    get_iterm_window_bounds,
    probe_iterm_connection,
    run_deterministic_check,
    run_setup,
    run_watch_live,
)


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

    uninstall = sub.add_parser(
        "uninstall",
        help="Remove the installed Dynamic Profile JSON and make-default AutoLaunch script",
    )
    uninstall.add_argument(
        "--target-dir",
        type=Path,
        default=DEFAULT_DYNAMIC_PROFILES_DIR,
        help="Directory containing the installed Dynamic Profile JSON",
    )
    uninstall.add_argument(
        "--autolaunch-dir",
        type=Path,
        default=DEFAULT_AUTOLAUNCH_DIR,
        help="iTerm2 AutoLaunch scripts directory",
    )
    uninstall.add_argument(
        "--app-state-dir",
        type=Path,
        default=DEFAULT_APP_STATE_DIR,
        help="Term Chameleon app-state directory (stores previous-default GUID)",
    )
    uninstall.add_argument("--dry-run", action="store_true", help="Preview without removing")
    uninstall.add_argument(
        "--no-backup", action="store_true", help="Do not back up files before removing"
    )

    install_watch = sub.add_parser(
        "install-watch-daemon",
        help="Install an iTerm2 AutoLaunch script that starts watch-live",
    )
    install_watch.add_argument("--config", type=Path, help="TOML config file")
    install_watch.add_argument(
        "--autolaunch-dir", type=Path, default=None, help="iTerm2 AutoLaunch scripts directory"
    )
    install_watch.add_argument(
        "--python", dest="python_executable", default=None, help="Python executable for the daemon"
    )
    install_watch.add_argument(
        "--interval", type=float, default=None, help="Seconds between samples"
    )
    install_watch.add_argument(
        "--stable", type=int, default=None, help="Consecutive samples required before switching"
    )
    install_watch.add_argument(
        "--cooldown", type=float, default=None, help="Minimum seconds between mode switches"
    )
    install_watch.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for watcher screenshot artifacts",
    )
    install_watch.add_argument(
        "--initial-mode", choices=sorted(PRESETS), default=None, help="Starting readability mode"
    )
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
    install_watch.add_argument("--log-path", type=Path, default=None, help="Daemon log file path")
    install_watch.add_argument("--pid-path", type=Path, default=None, help="Daemon PID file path")
    install_watch.add_argument("--dry-run", action="store_true", help="Preview without installing")

    watch_daemon_status = sub.add_parser(
        "watch-daemon-status",
        help="Inspect the iTerm2 AutoLaunch watch daemon script, log, and pid",
    )
    watch_daemon_status.add_argument("--config", type=Path, help="TOML config file")
    watch_daemon_status.add_argument(
        "--autolaunch-dir", type=Path, default=None, help="iTerm2 AutoLaunch scripts directory"
    )
    watch_daemon_status.add_argument(
        "--log-path", type=Path, default=None, help="Daemon log file path"
    )
    watch_daemon_status.add_argument(
        "--pid-path", type=Path, default=None, help="Daemon PID file path"
    )
    watch_daemon_status.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )

    uninstall_watch = sub.add_parser(
        "uninstall-watch-daemon",
        help="Remove the Term Chameleon iTerm2 AutoLaunch watch daemon script",
    )
    uninstall_watch.add_argument("--config", type=Path, help="TOML config file")
    uninstall_watch.add_argument(
        "--autolaunch-dir", type=Path, default=None, help="iTerm2 AutoLaunch scripts directory"
    )
    uninstall_watch.add_argument("--dry-run", action="store_true", help="Preview without removing")
    uninstall_watch.add_argument(
        "--no-backup", action="store_true", help="Do not back up the script before removing"
    )

    mode = sub.add_parser("mode", help="Apply a readability mode/preset to a profile JSON file")
    mode.add_argument("preset", choices=sorted(PRESETS))
    mode.add_argument("profile", type=Path, help="Dynamic Profile JSON file")
    mode.add_argument("--dry-run", action="store_true", help="Preview without writing")
    mode.add_argument("--yes", action="store_true", help="Confirm writing to the profile file")

    osc = sub.add_parser("osc", help="Print or apply OSC color sequences for a preset")
    osc.add_argument("action", choices=["apply", "reset"])
    osc.add_argument("preset", nargs="?", choices=sorted(PRESETS), default="balanced")
    osc.add_argument("--tmux", action="store_true", help="Wrap sequences for tmux DCS passthrough")
    osc.add_argument("--shell", action="store_true", help="Print shell-safe printf command")
    osc.add_argument("--write", action="store_true", help="Write raw escape sequences to stdout")

    terminal_info = sub.add_parser(
        "terminal-info",
        help="Detect the current terminal emulator and its capabilities",
    )
    terminal_info.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

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
    release_check.add_argument(
        "--yes",
        action="store_true",
        help="Confirm driving GUI apps when --live-stage is set",
    )

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
    setup.add_argument(
        "--live",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Probe live iTerm2 API/window bounds (--no-live disables config live=true)",
    )

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
    region_group.add_argument(
        "--whole-screen",
        action="store_true",
        help="Sample the whole screen instead of the iTerm window",
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

    sub.add_parser(
        "demo",
        help="Apply each readability preset to the live iTerm2 session in turn (watch it adapt)",
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
            return profile.doctor(args.profile, json_output=args.json)
        if args.command == "fix":
            return profile.fix(args.profile, dry_run=args.dry_run, yes=args.yes)
        if args.command == "install":
            return profile.install(
                args.target_dir,
                args.autolaunch_dir,
                name=args.name,
                preset=args.preset,
                make_default=args.make_default,
                dry_run=args.dry_run,
            )
        if args.command == "uninstall":
            return profile.uninstall(
                target_dir=args.target_dir,
                autolaunch_dir=args.autolaunch_dir,
                app_state_dir=args.app_state_dir,
                dry_run=args.dry_run,
                backup=not args.no_backup,
            )
        if args.command == "install-watch-daemon":
            return watch.install_watch_daemon(
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
            return watch.watch_daemon_status(
                autolaunch_dir=args.autolaunch_dir,
                log_path=args.log_path,
                pid_path=args.pid_path,
                json_output=args.json,
                config=args.config,
            )
        if args.command == "uninstall-watch-daemon":
            return watch.uninstall_watch_daemon(
                autolaunch_dir=args.autolaunch_dir,
                dry_run=args.dry_run,
                backup=not args.no_backup,
                config=args.config,
            )
        if args.command == "mode":
            return profile.mode(args.profile, args.preset, dry_run=args.dry_run, yes=args.yes)
        if args.command == "osc":
            return live.osc(
                args.action,
                args.preset,
                tmux=args.tmux,
                shell=args.shell,
                write=args.write,
            )
        if args.command == "terminal-info":
            return live.terminal_info(json_output=args.json)
        if args.command == "visual-test":
            return imaging.visual_test(args.profile, args.output_dir)
        if args.command == "check":
            return checks.check(output_dir=args.output_dir, width=args.width, height=args.height)
        if args.command == "release-check":
            return checks.release_check(
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
                yes=args.yes,
            )
        if args.command == "status":
            return checks.status(profile=args.profile, live=args.live, json_output=args.json)
        if args.command == "setup":
            return checks.setup(
                output_dir=args.output_dir,
                profile=args.profile,
                preset=args.preset,
                name=args.name,
                yes=args.yes,
                live=args.live,
                config=args.config,
            )
        if args.command == "config-example":
            return checks.config_example(output=args.output)
        if args.command == "config-check":
            return checks.config_check(config=args.config, json_output=args.json)
        if args.command == "watch-sim":
            return watch.watch_sim(args.samples, stable=args.stable)
        if args.command == "watch-live":
            return watch.watch_live(
                interval=args.interval,
                duration=args.duration,
                stable=args.stable,
                cooldown=args.cooldown,
                output_dir=args.output_dir,
                initial_mode=args.initial_mode,
                region=args.region,
                iterm_window=args.iterm_window,
                whole_screen=args.whole_screen,
                dry_run=args.dry_run,
                yes=args.yes,
                config=args.config,
            )
        if args.command == "iterm-api-check":
            return live.iterm_api_check()
        if args.command == "iterm-connect-probe":
            return live.iterm_connect_probe()
        if args.command == "iterm-window-bounds":
            return live.iterm_window_bounds()
        if args.command == "iterm-live-script":
            return live.iterm_live_script(args.preset, output=args.output)
        if args.command == "screenshot-probe":
            return imaging.screenshot_probe(capture=args.capture, output=args.output)
        if args.command == "demo":
            return demo.demo()
        if args.command == "screenshot-test":
            return imaging.screenshot_test(
                output_dir=args.output_dir,
                capture=args.capture,
                width=args.width,
                height=args.height,
            )
        if args.command == "screenshot-contrast":
            return imaging.screenshot_contrast(
                image=args.image,
                output_dir=args.output_dir,
                region=args.region,
                threshold=args.threshold,
                percentile=args.percentile,
            )
        if args.command == "screenshot-text-contrast":
            return imaging.screenshot_text_contrast(
                image=args.image,
                output_dir=args.output_dir,
                region=args.region,
                threshold=args.threshold,
                min_row_delta=args.min_row_delta,
                glyph_delta=args.glyph_delta,
            )
        if args.command == "background-html":
            return imaging.background_html(
                output_dir=args.output_dir, open_browser=args.open_browser
            )
        if args.command == "pattern-script":
            return imaging.pattern_script(output_dir=args.output_dir)
        if args.command == "e2e-stage":
            return checks.e2e_stage(
                profile=args.profile,
                output_dir=args.output_dir,
                capture=args.capture,
                width=args.width,
                height=args.height,
            )
        if args.command == "live-stage":
            return checks.live_stage(
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
            return checks.sample(
                image=args.image,
                screen=args.screen,
                output=args.output,
                region=args.region,
                iterm_window=args.iterm_window,
            )
        if args.command == "adapt-once":
            return checks.adapt_once(
                profile=args.profile,
                image=args.image,
                screen=args.screen,
                output=args.output,
                region=args.region,
                iterm_window=args.iterm_window,
                dry_run=args.dry_run,
                yes=args.yes,
            )
        raise RuntimeError(f"unhandled command: {args.command!r}")
    except (ValueError, OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
