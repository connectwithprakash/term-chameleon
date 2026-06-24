from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .modes import ModeChange, apply_mode
from .screenshot import ScreenshotResult, capture_screen
from .screenshot_test import analyze_image_file
from .watch import RISK_TO_MODE, Sample, classify_sample


@dataclass(frozen=True)
class AdaptDecision:
    average_luminance: float
    luminance_variance: float
    risk: str
    suggested_mode: str
    reason: str
    source: Path
    screenshot: ScreenshotResult | None = None
    mode_result: tuple[list[ModeChange], list] | None = None


def decide_from_image(path: str | Path) -> AdaptDecision:
    source = Path(path)
    stats = analyze_image_file(source)
    classification = classify_sample(Sample(stats.average_luminance, stats.luminance_variance))
    return AdaptDecision(
        average_luminance=stats.average_luminance,
        luminance_variance=stats.luminance_variance,
        risk=classification.risk,
        suggested_mode=RISK_TO_MODE[classification.risk],
        reason=classification.reason,
        source=source,
    )


def decide_from_screen(output_path: str | Path) -> AdaptDecision:
    screenshot = capture_screen(output_path)
    if not screenshot.captured or screenshot.output_path is None:
        raise RuntimeError(f"screen capture failed: {screenshot.message}")
    decision = decide_from_image(screenshot.output_path)
    return AdaptDecision(
        average_luminance=decision.average_luminance,
        luminance_variance=decision.luminance_variance,
        risk=decision.risk,
        suggested_mode=decision.suggested_mode,
        reason=decision.reason,
        source=decision.source,
        screenshot=screenshot,
    )


def adapt_profile_from_image(
    image_path: str | Path,
    profile_path: str | Path,
    *,
    dry_run: bool = True,
    yes: bool = False,
) -> AdaptDecision:
    decision = decide_from_image(image_path)
    result = apply_mode(profile_path, decision.suggested_mode, dry_run=dry_run, yes=yes)
    return _with_mode_result(decision, result)


def adapt_profile_from_screen(
    profile_path: str | Path,
    screenshot_path: str | Path,
    *,
    dry_run: bool = True,
    yes: bool = False,
) -> AdaptDecision:
    decision = decide_from_screen(screenshot_path)
    result = apply_mode(profile_path, decision.suggested_mode, dry_run=dry_run, yes=yes)
    return _with_mode_result(decision, result)


def _with_mode_result(
    decision: AdaptDecision, result: tuple[list[ModeChange], list]
) -> AdaptDecision:
    return AdaptDecision(
        average_luminance=decision.average_luminance,
        luminance_variance=decision.luminance_variance,
        risk=decision.risk,
        suggested_mode=decision.suggested_mode,
        reason=decision.reason,
        source=decision.source,
        screenshot=decision.screenshot,
        mode_result=result,
    )
