from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .diagnostics import diagnose
from .fixes import fix_file
from .install import DEFAULT_DYNAMIC_PROFILES_DIR, install_balanced_profile
from .iterm_profile import load_profile, loads_document
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
    install.add_argument("--preset", choices=["balanced"], default="balanced")
    install.add_argument("--name", default="Adaptive Glass")
    install.add_argument("--target-dir", type=Path, default=DEFAULT_DYNAMIC_PROFILES_DIR)
    install.add_argument("--dry-run", action="store_true")

    visual = sub.add_parser("visual-test", help="Run deterministic visual contrast simulation")
    visual.add_argument("profile", type=Path)
    visual.add_argument("--output-dir", type=Path, default=Path("artifacts/visual-test"))

    args = parser.parse_args(argv)
    if args.command == "doctor":
        return _doctor(args.profile)
    if args.command == "fix":
        return _fix(args.profile, dry_run=args.dry_run, yes=args.yes)
    if args.command == "install":
        return _install(args.target_dir, name=args.name, dry_run=args.dry_run)
    if args.command == "visual-test":
        return _visual_test(args.profile, args.output_dir)
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
    if not changes:
        print("  none")
    for c in changes:
        print(f"- {c.key}: {c.before} -> {c.after}")
        print(f"  reason: {c.reason}")
    blocking = [d for d in remaining if d.severity == "fail"]
    if blocking:
        print("\nRemaining failures after fix proposal:")
        for d in blocking:
            print(f"- {d.code}: {d.message}")
        return 1
    print("\n[ok] fixed profile passes failure-level doctor checks")
    return 0


def _install(target_dir: Path, *, name: str, dry_run: bool) -> int:
    target, content = install_balanced_profile(target_dir=target_dir, name=name, dry_run=dry_run)
    # Validate generated JSON through the same parser used by doctor.
    loads_document(content, target)
    action = "Would write" if dry_run else "Wrote"
    print(f"{action}: {target}")
    print(f"Profile name: {name}")
    print("[ok] generated Dynamic Profile JSON is valid")
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


if __name__ == "__main__":
    raise SystemExit(main())
