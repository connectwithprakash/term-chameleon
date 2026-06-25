from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .live_iterm import LiveApplyResult, apply_preset_to_current_session
from .screenshot import capture_screen
from .screenshot_test import analyze_image_file
from .watch import ModeSelector, Sample


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

    def __post_init__(self) -> None:
        if self.interval <= 0:
            raise ValueError("interval must be > 0")
        if self.duration <= 0:
            raise ValueError("duration must be > 0")
        if self.stable < 1:
            raise ValueError("stable must be >= 1")
        if self.cooldown < 0:
            raise ValueError("cooldown must be >= 0")


SampleProvider = Callable[[int, Path], tuple[Sample, str]]
ApplyPreset = Callable[[str], LiveApplyResult]
Sleep = Callable[[float], None]
Clock = Callable[[], float]


def screenshot_sample_provider(index: int, output_dir: Path) -> tuple[Sample, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"sample-{index:04d}.png"
    screenshot = capture_screen(path)
    if not screenshot.captured or screenshot.output_path is None:
        raise RuntimeError(f"screen capture failed: {screenshot.message}")
    stats = analyze_image_file(screenshot.output_path)
    return Sample(stats.average_luminance, stats.luminance_variance), str(screenshot.output_path)


def run_watch_live(
    config: WatchLiveConfig,
    *,
    sample_provider: SampleProvider = screenshot_sample_provider,
    apply_preset: ApplyPreset = apply_preset_to_current_session,
    sleep: Sleep = time.sleep,
    clock: Clock = time.monotonic,
) -> list[WatchLiveEvent]:
    selector = ModeSelector(current_mode=config.initial_mode, stable_samples_required=config.stable)
    start = clock()
    next_allowed_switch = start
    events: list[WatchLiveEvent] = []
    index = 0

    while True:
        now = clock()
        if now - start > config.duration and events:
            break
        index += 1
        sample, source = sample_provider(index, config.output_dir)
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
                result = apply_preset(mode)
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
