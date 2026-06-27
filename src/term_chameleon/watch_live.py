from __future__ import annotations

import contextlib
import shutil
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
    try:
        files = sorted(output_dir.glob("sample-*.png"), key=lambda p: p.stat().st_mtime)
    except OSError:
        return
    while len(files) > max_artifacts:
        oldest = files.pop(0)
        with contextlib.suppress(OSError):
            oldest.unlink(missing_ok=True)
        analysis = oldest.with_name(f"{oldest.stem}-analysis.png")
        if analysis.exists():
            with contextlib.suppress(OSError):
                analysis.unlink()


def run_watch_live(
    config: WatchLiveConfig,
    *,
    sample_provider: SampleProvider = screenshot_sample_provider,
    apply_preset: ApplyPreset = apply_preset_to_current_session,
    sleep: Sleep = time.sleep,
    clock: Clock = time.monotonic,
    window_bounds_provider: WindowBoundsProvider = get_iterm_window_bounds,
) -> list[WatchLiveEvent]:
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
    events: list[WatchLiveEvent] = []
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
        mode, classification, switched = selector.observe(sample)
        candidate_mode = classification.mode
        applied = False
        message = source

        if switched and now < next_allowed_switch:
            selector.current_mode = previous_mode
            selector._last_switch_luminance = previous_last_switch_luminance
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

        events.append(
            WatchLiveEvent(
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
        )

        if clock() - start >= config.duration:
            break
        sleep(config.interval)

    return events


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
