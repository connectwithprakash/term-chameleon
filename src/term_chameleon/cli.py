from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .adapt import (
    adapt_profile_from_image,
    adapt_profile_from_screen,
    decide_from_image,
    decide_from_screen,
)
from .background_html import open_file, write_background_html
from .diagnostics import diagnose
from .e2e_stage import run_e2e_stage
from .fixes import fix_file
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
from .iterm_profile import load_profile, loads_document
from .modes import apply_mode
from .osc import reset_sequences, sequences_for_preset, shell_printf
from .presets import PRESETS
from .screenshot import probe_screenshot
from .screenshot_test import run_screenshot_test
from .terminal_pattern import write_pattern_bundle
from .visual import write_visual_report
from .watch import ModeSelector, Sample


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="term-chameleon")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Diagnose an iTerm2 Dynamic Profile JSON file")
    doctor.add_argument("profile", type=Path)

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

    watch_sim = sub.add_parser("watch-sim", help="Simulate dynamic mode selection from samples")
    watch_sim.add_argument(
        "samples",
        nargs="+",
        help="Samples as luminance or luminance:variance, e.g. 0.2 0.8 0.5:0.12",
    )
    watch_sim.add_argument("--stable", type=int, default=3)

    sub.add_parser("iterm-api-check", help="Check local iTerm2 Python API readiness")

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

    sample = sub.add_parser("sample", help="Sample an image or live screen and suggest a mode")
    sample_source = sample.add_mutually_exclusive_group(required=True)
    sample_source.add_argument("--image", type=Path)
    sample_source.add_argument("--screen", action="store_true")
    sample.add_argument("--output", type=Path, default=Path("artifacts/adapt/screen.png"))

    adapt = sub.add_parser(
        "adapt-once", help="Sample image/screen and apply suggested mode to a profile"
    )
    adapt.add_argument("profile", type=Path)
    adapt_source = adapt.add_mutually_exclusive_group(required=True)
    adapt_source.add_argument("--image", type=Path)
    adapt_source.add_argument("--screen", action="store_true")
    adapt.add_argument("--output", type=Path, default=Path("artifacts/adapt/screen.png"))
    adapt.add_argument("--dry-run", action="store_true")
    adapt.add_argument("--yes", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            return _doctor(args.profile)
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
        if args.command == "mode":
            return _mode(args.profile, args.preset, dry_run=args.dry_run, yes=args.yes)
        if args.command == "osc":
            return _osc(args.action, args.preset, tmux=args.tmux, shell=args.shell)
        if args.command == "visual-test":
            return _visual_test(args.profile, args.output_dir)
        if args.command == "watch-sim":
            return _watch_sim(args.samples, stable=args.stable)
        if args.command == "iterm-api-check":
            return _iterm_api_check()
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
        if args.command == "sample":
            return _sample(image=args.image, screen=args.screen, output=args.output)
        if args.command == "adapt-once":
            return _adapt_once(
                profile=args.profile,
                image=args.image,
                screen=args.screen,
                output=args.output,
                dry_run=args.dry_run,
                yes=args.yes,
            )
    except (ValueError, OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    parser.error("unknown command")
    return 2


def _doctor(path: Path) -> int:
    profile = load_profile(path)
    diagnostics = diagnose(profile)
    print(f"Profile: {profile.name}")
    bg = profile.background
    fg = profile.foreground
    if bg:
        print(f"Background: {bg.to_hex()}")
    if fg:
        print(f"Foreground: {fg.to_hex()}")
    if bg and fg:
        from .contrast import contrast_ratio, format_ratio

        print(f"Foreground contrast: {format_ratio(contrast_ratio(fg, bg))}")
    print()
    if not diagnostics:
        print("[ok] no contrast/profile issues detected")
        return 0
    for d in diagnostics:
        print(f"[{d.severity}] {d.code}: {d.message}")
        print(f"  {d.detail}")
        if d.suggestion:
            print(f"  Suggestion: {d.suggestion}")
    return 1 if any(d.severity == "fail" for d in diagnostics) else 0


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


def _sample(*, image: Path | None, screen: bool, output: Path) -> int:
    decision = decide_from_screen(output) if screen else decide_from_image(_require_path(image))
    _print_decision(decision)
    return 0


def _adapt_once(
    *,
    profile: Path,
    image: Path | None,
    screen: bool,
    output: Path,
    dry_run: bool,
    yes: bool,
) -> int:
    if not dry_run and not yes:
        print("Refusing to write without --yes. Use --dry-run to preview.", file=sys.stderr)
        return 2
    decision = (
        adapt_profile_from_screen(profile, output, dry_run=dry_run, yes=yes)
        if screen
        else adapt_profile_from_image(_require_path(image), profile, dry_run=dry_run, yes=yes)
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
    print(f"Average luminance: {decision.average_luminance:.3f}")
    print(f"Luminance variance: {decision.luminance_variance:.3f}")
    print(f"Risk: {decision.risk}")
    print(f"Suggested mode: {decision.suggested_mode}")
    print(f"Reason: {decision.reason}")


def _require_path(path: Path | None) -> Path:
    if path is None:
        raise ValueError("image path is required")
    return path


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
