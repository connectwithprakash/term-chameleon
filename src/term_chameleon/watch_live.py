from __future__ import annotations

import atexit
import collections
import contextlib
import logging
import os
import shutil
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .images import Region
from .iterm_window import WindowBoundsResult, get_iterm_window_bounds
from .live_iterm import LiveApplyResult, apply_preset_to_current_session
from .screenshot import capture_screen
from .screenshot_test import analyze_image_file
from .watch import ModeSelector, Sample

WATCH_SAMPLE_MAX_PIXELS = 250_000
WATCH_ANALYSIS_MAX_DIMENSION = 700
WATCH_MAX_ARTIFACTS = 200
# Risk classifications where text is actively washing out; a switch into one of
# these overrides the anti-thrash cooldown so readability is restored at once.
HIGH_RISK = frozenset({"bright-high-risk", "high-variance-high-risk"})
# Maximum events kept in memory for the return value (ring buffer).
# The daemon runs indefinitely; storing all events would exhaust RAM.
WATCH_MAX_EVENTS_BUFFER = 1000

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WatchLiveEvent:
    index: int
    elapsed: float
    luminance: float
    variance: float
    risk: str
    mode: str
    candidate_mode: str
    switched: bool
    applied: bool
    reason: str
    message: str


@dataclass(frozen=True)
class WatchLiveConfig:
    interval: float = 2.0
    duration: float = 60.0
    stable: int = 3
    cooldown: float = 10.0
    output_dir: Path = Path("artifacts/watch-live")
    dry_run: bool = True
    initial_mode: str = "balanced"
    region: Region | None = None
    iterm_window: bool = False

    def __post_init__(self) -> None:
        if self.interval <= 0:
            raise ValueError("interval must be > 0")
        if self.duration <= 0:
            raise ValueError("duration must be > 0")
        if self.stable < 1:
            raise ValueError("stable must be >= 1")
        if self.cooldown < 0:
            raise ValueError("cooldown must be >= 0")
        if self.region is not None and self.iterm_window:
            raise ValueError("use either region or iterm_window, not both")


SampleProvider = Callable[[int, Path, Region | None], tuple[Sample, str]]
ApplyPreset = Callable[[str], LiveApplyResult]
Sleep = Callable[[float], None]
Clock = Callable[[], float]
WindowBoundsProvider = Callable[[], WindowBoundsResult]


def screenshot_sample_provider(
    index: int, output_dir: Path, region: Region | None
) -> tuple[Sample, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"sample-{index:04d}.png"
    screenshot = capture_screen(path)
    if not screenshot.captured or screenshot.output_path is None:
        raise RuntimeError(f"screen capture failed: {screenshot.message}")
    analysis_path = _analysis_image_path(screenshot.output_path)
    stats = analyze_image_file(analysis_path, region=region, max_pixels=WATCH_SAMPLE_MAX_PIXELS)
    suffix = f" region={region}" if region is not None else ""
    analysis_suffix = (
        "" if analysis_path == screenshot.output_path else f" analysis={analysis_path}"
    )
    return Sample(
        stats.average_luminance, stats.luminance_variance
    ), f"{screenshot.output_path}{suffix}{analysis_suffix}"


# A repeating bright/dark cycle used by the self-driving demo provider so the
# watcher visibly switches modes on a timer without sampling the real screen.
DEMO_CYCLE_LUMINANCES: tuple[float, ...] = (0.08, 0.08, 0.92, 0.92)

# Demo-only background tints, applied ONLY in --demo-cycle so the mode switch is
# obvious on an opaque window. The real presets share a near-identical dark
# background and adapt via transparency (invisible without a translucent window),
# so these exaggerated colors exist purely to make the demo legible on screen.
# DEMO_CYCLE_LUMINANCES only drives dark-glass and bright-safe today; the other
# entries are kept so any mode reached by a future cycle still gets a distinct tint
# (an unmapped mode falls back to its real background via .get()).
DEMO_MODE_BACKGROUNDS: dict[str, str] = {
    "dark-glass": "#0A0E1A",
    "balanced": "#1C1330",
    "bright-safe": "#E8ECF2",
    "high-variance-safe": "#3A2A12",
    "accessibility": "#000000",
}


def demo_apply_preset(preset_name: str) -> LiveApplyResult:
    """Apply a preset with an exaggerated demo background so the switch is visible."""
    return apply_preset_to_current_session(
        preset_name, background_override=DEMO_MODE_BACKGROUNDS.get(preset_name)
    )


def demo_cycle_sample_provider(
    index: int, _output_dir: Path, _region: Region | None
) -> tuple[Sample, str]:
    """Return a scripted bright/dark luminance instead of sampling the screen.

    Lets `watch-live --demo-cycle` drive the real sample -> decide -> apply loop
    off a repeating brightness pattern, so the terminal recolors on its own and
    the auto-adaptation can be screen-recorded without rigging a changing
    background. index is 1-based.
    """
    luminance = DEMO_CYCLE_LUMINANCES[(index - 1) % len(DEMO_CYCLE_LUMINANCES)]
    label = "bright" if luminance > 0.5 else "dark"
    return Sample(luminance), f"demo-cycle {label} (lum={luminance:.2f})"


def _analysis_image_path(path: Path) -> Path:
    sips = shutil.which("sips")
    if sips is None:
        return path
    target = path.with_name(f"{path.stem}-analysis{path.suffix}")
    try:
        result = subprocess.run(
            [sips, "-Z", str(WATCH_ANALYSIS_MAX_DIMENSION), str(path), "--out", str(target)],
            check=False,
            capture_output=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return path
    if result.returncode != 0 or not target.exists():
        return path
    return target


def _prune_artifacts(output_dir: Path, *, max_artifacts: int = WATCH_MAX_ARTIFACTS) -> None:
    """Remove the oldest real samples (and their paired analysis files) so that
    at most *max_artifacts* real sample files remain.

    Only files that do NOT have the ``-analysis`` suffix are counted toward the
    cap; their ``-analysis`` companions are deleted alongside them.
    """
    try:
        all_png = sorted(output_dir.glob("sample-*.png"), key=lambda p: p.stat().st_mtime)
    except OSError:
        return
    # Keep only real samples in the count; exclude -analysis companions.
    samples = [p for p in all_png if not p.stem.endswith("-analysis")]
    while len(samples) > max_artifacts:
        oldest = samples.pop(0)
        with contextlib.suppress(OSError):
            oldest.unlink(missing_ok=True)
        # Also remove the paired analysis file if it exists.
        analysis = oldest.with_name(f"{oldest.stem}-analysis.png")
        with contextlib.suppress(OSError):
            analysis.unlink(missing_ok=True)


def _setup_pid_ownership() -> None:
    """Write this process's PID to the path given by the TC_WATCH_PID_PATH env var.

    Called once at the start of :func:`run_watch_live`.  The file is removed
    via :mod:`atexit` when the process exits normally or on SIGINT
    (KeyboardInterrupt).  SIGTERM and SIGHUP handlers are also installed so that
    ``kill(1)``, launchd, and system shutdown — the most common termination paths
    for a background daemon — also clean up the PID file before exiting.

    Without explicit signal handlers, ``atexit`` does NOT run on SIGTERM/SIGHUP,
    which causes a stale PID file to remain.  If the OS later recycles that PID
    to an unrelated live process the duplicate-launch guard treats the daemon as
    still running and refuses to restart it (wedged daemon).
    """
    pid_path_str = os.environ.get("TC_WATCH_PID_PATH")
    if not pid_path_str:
        return
    pid_path = Path(pid_path_str).expanduser()
    try:
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(os.getpid()) + "\n", encoding="utf-8")
    except OSError:
        return

    def _remove_pid() -> None:
        with contextlib.suppress(OSError):
            pid_path.unlink(missing_ok=True)

    atexit.register(_remove_pid)

    # Install SIGTERM and SIGHUP handlers so the PID file is removed on the
    # normal daemon kill path (launchd, ``kill``, OS shutdown) and on reload
    # (SIGHUP).  Each handler removes the PID file then re-raises the default
    # action so the process actually exits with the correct signal status.
    def _signal_cleanup(signum: int, _frame: object) -> None:
        _remove_pid()
        # Restore the default handler and re-raise so the process exits with
        # the correct signal status (e.g. kill -TERM produces exit status 143).
        signal.signal(signum, signal.SIG_DFL)
        os.kill(os.getpid(), signum)

    for _sig in (signal.SIGTERM, signal.SIGHUP):
        # signal.signal can raise OSError (EINVAL) where the signal is
        # unsupported (e.g. Windows); ignore silently.
        with contextlib.suppress(OSError):
            signal.signal(_sig, _signal_cleanup)


def run_watch_live(
    config: WatchLiveConfig,
    *,
    sample_provider: SampleProvider = screenshot_sample_provider,
    apply_preset: ApplyPreset = apply_preset_to_current_session,
    sleep: Sleep = time.sleep,
    clock: Clock = time.monotonic,
    window_bounds_provider: WindowBoundsProvider = get_iterm_window_bounds,
) -> list[WatchLiveEvent]:
    _setup_pid_ownership()
    selector = ModeSelector(current_mode=config.initial_mode, stable_samples_required=config.stable)
    region = config.region
    if config.iterm_window:
        region = _wait_for_iterm_window_bounds(
            interval=config.interval,
            sleep=sleep,
            clock=clock,
            window_bounds_provider=window_bounds_provider,
        )
    start = clock()
    next_allowed_switch = start
    # Bounded ring buffer: keeps at most WATCH_MAX_EVENTS_BUFFER events in
    # memory so the long-running daemon does not exhaust RAM.
    events: collections.deque[WatchLiveEvent] = collections.deque(maxlen=WATCH_MAX_EVENTS_BUFFER)
    index = 0

    while True:
        now = clock()
        if now - start > config.duration and events:
            break
        index += 1
        sample, source = sample_provider(index, config.output_dir, region)
        _prune_artifacts(config.output_dir)
        previous_mode = selector.current_mode
        previous_last_switch_luminance = selector._last_switch_luminance
        previous_candidate_mode = selector._candidate_mode
        previous_candidate_count = selector._candidate_count
        mode, classification, switched = selector.observe(sample)
        candidate_mode = classification.mode
        applied = False
        message = source

        # The cooldown prevents cosmetic flapping between similar modes, but a
        # switch into a high-risk state is a readability emergency (text washing
        # out over a bright or high-variance background) and overrides it.
        cooldown_blocks = switched and now < next_allowed_switch
        if cooldown_blocks and classification.risk in HIGH_RISK:
            cooldown_blocks = False
        if cooldown_blocks:
            selector.current_mode = previous_mode
            selector._last_switch_luminance = previous_last_switch_luminance
            selector._candidate_mode = previous_candidate_mode
            selector._candidate_count = previous_candidate_count
            switched = False
            mode = selector.current_mode
            message = f"cooldown active; next switch allowed in {next_allowed_switch - now:.1f}s"

        if switched:
            if config.dry_run:
                message = f"dry-run would apply {mode}"
                applied = False
            else:
                try:
                    result = apply_preset(mode)
                except RuntimeError as exc:
                    message = f"apply failed; will continue watching: {exc}"
                    applied = False
                else:
                    message = result.message
                    applied = result.applied
            next_allowed_switch = now + config.cooldown

        event = WatchLiveEvent(
            index=index,
            elapsed=now - start,
            luminance=sample.luminance,
            variance=sample.variance,
            risk=classification.risk,
            mode=mode,
            candidate_mode=candidate_mode,
            switched=switched,
            applied=applied,
            reason=classification.reason,
            message=message,
        )
        events.append(event)

        # Emit each event immediately so the log file is populated live even
        # when the loop runs indefinitely (daemon mode with --duration=315360000).
        marker = "switch" if event.switched else "hold"
        apply_marker = " applied" if event.applied else ""
        logger.info(
            "%d: t=%.1fs lum=%.3f var=%.3f risk=%s candidate=%s mode=%s %s%s reason=%s message=%s",
            event.index,
            event.elapsed,
            event.luminance,
            event.variance,
            event.risk,
            event.candidate_mode,
            event.mode,
            marker,
            apply_marker,
            event.reason,
            event.message,
        )

        if clock() - start >= config.duration:
            break
        sleep(config.interval)

    return list(events)


def _wait_for_iterm_window_bounds(
    *,
    interval: float,
    sleep: Sleep,
    clock: Clock,
    window_bounds_provider: WindowBoundsProvider,
) -> Region:
    wait_limit = 60.0
    start = clock()
    last_message = "iTerm2 window bounds unavailable"
    while True:
        result = window_bounds_provider()
        if result.available and result.region is not None:
            return result.region
        last_message = result.message
        if clock() - start >= wait_limit:
            raise RuntimeError(
                f"could not read iTerm2 window bounds after {wait_limit:.1f}s: "
                f"{last_message}; use --region x,y,w,h"
            )
        sleep(min(interval, 1.0))
