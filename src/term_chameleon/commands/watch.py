from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from ..config import (
    ConfigError,
    bool_value,
    float_value,
    int_value,
    load_config,
    merged_section,
    path_value,
    str_value,
    value,
)
from ..images import Region
from ..install import DEFAULT_AUTOLAUNCH_DIR
from ..watch import ModeSelector
from ..watch_daemon import (
    DEFAULT_LOG_PATH,
    DEFAULT_PID_PATH,
    get_watch_daemon_status,
    install_watch_autolaunch_script,
    shell_command,
    uninstall_watch_autolaunch_script,
    watch_live_command,
)
from ..watch_live import WatchLiveConfig
from .shared import parse_sample, preset_or_error


def watch_sim(samples: list[str], *, stable: int) -> int:
    selector = ModeSelector(stable_samples_required=stable)
    for index, raw in enumerate(samples, start=1):
        sample = parse_sample(raw)
        mode, classification, switched = selector.observe(sample)
        marker = "switch" if switched else "hold"
        print(
            f"{index}: luminance={sample.luminance:.2f} variance={sample.variance:.2f} "
            f"risk={classification.risk} mode={mode} {marker} reason={classification.reason}"
        )
    return 0


def watch_live(
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
    whole_screen: bool = False,
) -> int:
    from .. import cli

    if not dry_run and not yes:
        print("Refusing to mutate iTerm2 without --yes. Use --dry-run to preview.", file=sys.stderr)
        return 2
    cfg = load_config(config)
    watch_cfg = merged_section(cfg, "watch")
    resolved_region = region if region is not None else str_value(value(watch_cfg, "region"))
    if iterm_window:
        resolved_region = None
        resolved_iterm_window = True
    elif whole_screen:
        # Explicit CLI flag overrides config iterm_window=true -> force whole-screen sampling.
        resolved_iterm_window = False
        resolved_region = None
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
    watch_initial_mode = preset_or_error(
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
    events = cli.run_watch_live(config_obj)
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


def install_watch_daemon(
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
    daemon_initial_mode = preset_or_error(
        initial_mode or str_value(value(daemon_cfg, "initial_mode")), "balanced"
    )
    # Validate resolved numeric/region values using the same rules as WatchLiveConfig and
    # Region.parse so the daemon installer never bakes a permanently-broken command.
    # ValueError (and ConfigError, a subclass) propagates to the CLI error handler.
    WatchLiveConfig(
        interval=daemon_interval,
        stable=daemon_stable,
        cooldown=daemon_cooldown,
        output_dir=daemon_output_dir,
        initial_mode=daemon_initial_mode,
        iterm_window=resolved_iterm_window and resolved_region is None,
        region=Region.parse(resolved_region) if resolved_region is not None else None,
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
    if resolved_autolaunch is None:
        raise ConfigError("autolaunch_dir must be a path string")
    if resolved_log is None:
        raise ConfigError("log_path must be a path string")
    if resolved_pid is None:
        raise ConfigError("pid_path must be a path string")
    return (resolved_autolaunch, resolved_log, resolved_pid)


def watch_daemon_status(
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
        payload = {**asdict(status), "healthy": status.healthy}
        print(json.dumps(payload, indent=2, default=str))
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


def uninstall_watch_daemon(
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
