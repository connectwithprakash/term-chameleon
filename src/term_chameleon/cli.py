from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .diagnostics import diagnose
from .fixes import fix_file
from .install import (
    DEFAULT_AUTOLAUNCH_DIR,
    DEFAULT_DYNAMIC_PROFILES_DIR,
    install_autolaunch_script,
    install_profile,
)
from .iterm_profile import load_profile, loads_document
from .modes import apply_mode
from .osc import reset_sequences, sequences_for_preset, shell_printf
from .presets import PRESETS
from .visual import write_visual_report


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
    except (ValueError, OSError, json.JSONDecodeError) as exc:
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
