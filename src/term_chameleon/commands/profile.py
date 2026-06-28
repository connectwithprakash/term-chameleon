from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from ..diagnostics import diagnose
from ..fixes import fix_file
from ..install import (
    install_autolaunch_script,
    install_profile,
    uninstall_profile,
)
from ..iterm_profile import load_profile, loads_document
from ..modes import apply_mode
from .shared import print_changes, print_remaining_failures


def doctor(path: Path, *, json_output: bool = False) -> int:
    profile = load_profile(path)
    diagnostics = diagnose(profile)
    bg = profile.background
    fg = profile.foreground
    foreground_contrast = None
    if bg and fg:
        from ..contrast import contrast_ratio

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
        from ..contrast import format_ratio

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


def fix(path: Path, *, dry_run: bool, yes: bool) -> int:
    if not dry_run and not yes:
        print("Refusing to write without --yes. Use --dry-run to preview.", file=sys.stderr)
        return 2
    changes, remaining = fix_file(path, dry_run=dry_run, yes=yes)
    print("Planned changes:" if dry_run else "Applied changes:")
    print_changes(changes)
    return print_remaining_failures(remaining, "fixed profile passes failure-level doctor checks")


def install(
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


def uninstall(
    *,
    target_dir: Path,
    autolaunch_dir: Path,
    app_state_dir: Path,
    dry_run: bool,
    backup: bool,
) -> int:
    result = uninstall_profile(
        target_dir=target_dir,
        autolaunch_dir=autolaunch_dir,
        app_state_dir=app_state_dir,
        dry_run=dry_run,
        backup=backup,
    )
    action = "Would remove" if dry_run else "Removed"
    anything_removed = result.profile_removed or result.autolaunch_removed
    if result.profile_removed:
        print(f"{action} profile: {result.profile_target}")
        if result.profile_backup_path is not None:
            print(f"Backup: {result.profile_backup_path}")
    else:
        print(f"Profile not installed: {result.profile_target}")
    if result.autolaunch_removed:
        print(f"{action} AutoLaunch script: {result.autolaunch_target}")
        if result.autolaunch_backup_path is not None:
            print(f"Backup: {result.autolaunch_backup_path}")
    else:
        print(f"AutoLaunch script not installed: {result.autolaunch_target}")
    if result.previous_default_guid is not None:
        print(
            f"Previous default profile GUID: {result.previous_default_guid}\n"
            "  To restore: open iTerm2 > Preferences > Profiles and select the profile\n"
            "  with that GUID (or the profile name you prefer) as the default."
        )
    else:
        print(
            "Note: make-default is not automatically reversed.\n"
            "  To restore your prior default: open iTerm2 > Preferences > Profiles\n"
            "  and select your preferred profile as the default."
        )
    if anything_removed:
        print("[ok] Term Chameleon profile uninstalled")
        return 0
    print("[warn] nothing was installed; nothing to remove")
    return 1


def mode(path: Path, preset: str, *, dry_run: bool, yes: bool) -> int:
    if not dry_run and not yes:
        print("Refusing to write without --yes. Use --dry-run to preview.", file=sys.stderr)
        return 2
    changes, remaining = apply_mode(path, preset, dry_run=dry_run, yes=yes)
    print(("Planned" if dry_run else "Applied") + f" mode: {preset}")
    print_changes(changes)
    return print_remaining_failures(remaining, "mode profile passes failure-level doctor checks")
